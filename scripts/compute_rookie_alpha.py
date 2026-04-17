#!/usr/bin/env python3
"""Standalone pre-draft Rookie Alpha pipeline (v0).

Reads artifact-only JSON inputs and writes promoted JSON + CSV outputs.
No DB writes. No runtime dependencies on TIBER-Fantasy services.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


@dataclass(frozen=True)
class PlayerInputs:
    player_id: str
    player_name: str
    position: str
    ras_score_0_100: float | None
    production_score_0_100: float | None
    draft_capital_proxy_0_100: float | None
    age_adjusted_production_0_100: float | None = None
    # Generalized athletic input layer — abstracts over RAS / SPORQ / partial combine.
    athletic_score_0_100: float | None = None
    athletic_source: str | None = None        # "RAS", "SPORQ", "COMBINE_FALLBACK"
    athletic_confidence: float = 0.0          # 0.0–1.0
    athletic_explainer: str | None = None


@dataclass(frozen=True)
class MergeDiagnostics:
    duplicate_rows_skipped: int
    identity_conflicts_skipped: int
    excluded_for_missing_sources: dict[str, int]


CONTEXT_EVIDENCE_TAG_VOCAB = {
    "elite_early_producer",
    "young_breakout",
    "early_declare",
    "multi_season_efficiency",
    "one_year_context_suppression",
    "injury_adjusted",
    "inside_out_versatility",
    "yac_signal",
    "rushing_signal",
    "late_round_dart",
    # efficiency / athleticism tier tags
    "elite_efficiency_tier",
    "r1_p4_wr_comps",
    "non_r1_p4_wr_comps",
    "elite_athleticism",
    "elite_speed",
    "exceptional_strength",
    # volume / consistency tags
    "elite_volume_producer",
    "elite_yac_producer",
    "multi_season_consistency",
    # context tags
    "broken_offense_context",
    "late_breakout",
    "size_concern",
    # injury / pre-draft flags
    "acl_injury_predraft",
    # transfer / backfield context
    "shared_backfield_context",
    # craft / technician tags (used by market-conviction RAS override)
    "route_runner",           # technique-driven separation; not athleticism-dependent
    "contested_catch_signal", # hands + body control; catch % in traffic above average
    "yprr_elite",             # career or peak YPRR >= 2.3; most predictive WR efficiency metric
}

CONTEXT_FLAG_VOCAB = {
    "limited_multi_season_data",
    "limited_production_data",
    "single_season_efficiency_dip",
    "injury_context",
    "suppressed_offense_context",
    "path_disruption",
    # research-sourced red flag flags
    "bottom_10_mtf_day2_rb_since_2014",
    "yac_consistency_concern",
    "one_hit_wonder_risk",
    "senior_breakout_flag",
    "poor_ol_context",
    "size_risk",
    # combine context flags
    "combine_drills_skipped_hamstring",
    "combine_drills_skipped_injury",
    "injury_adjusted_2024_playoffs",
    # injury flags
    "pre_draft_acl_march_2026",
    # backfield / teammate context
    "shared_backfield_love_2024",
    # data quality flags
    "synthetic_profile_pending_cfbd",
}

TRANSLATION_FLAG_VOCAB = {
    "young_breakout",
    "multi_season_efficiency",
    "one_year_context_suppression",
    "injury_adjusted",
    "inside_out_versatility",
    "yac_signal",
    "rushing_signal",
    "late_round_dart",
    "elite_efficiency_tier",
    "broken_offense_context",
    "acl_injury_predraft",
}

# ---------------------------------------------------------------------------
# Exceptional metric detection and ceiling bonus
# ---------------------------------------------------------------------------
# Any combine metric with |z| >= EXCEPTIONAL_Z_THRESHOLD within the position
# peer group is flagged as exceptional (informational; already captured by RAS).
EXCEPTIONAL_Z_THRESHOLD = 1.65  # ~top/bottom 5% within group

# Context-sourced exceptional_metrics entries (from 2026_prospect_context.json)
# may carry a ceiling bonus to alpha when alpha_bonus_eligible=True.
# Use this for metrics not captured by the model formula (e.g. contested catch
# rate, historically elite 3-cone when peer group is too small to normalize).
CEILING_BONUS_TIERS: dict[str, float] = {
    "notable": 0.0,   # surface only; no alpha adjustment
    "elite": 1.5,     # verified top ~5-10% historically
    "historic": 3.0,  # verified top 1-2% historically; generational metric
}
CEILING_BONUS_CAP = 5.0  # max total ceiling bonus applied to alpha

# ---------------------------------------------------------------------------
# Market-conviction RAS override
# ---------------------------------------------------------------------------
# Fires ONLY when all of the following are true:
#   1. Position is WR or TE (not RB — different failure mode)
#   2. RAS was actually computed from combine data (not None / missing fallback)
#   3. Confirmed RAS < MARKET_CONVICTION_RAS_CAP
#   4. Draft capital proxy >= MARKET_CONVICTION_CAPITAL_FLOOR (Day 2+ investment)
#   5. At least one craft/efficiency signal is present — either a qualifying
#      evidence_tag OR a numeric context field above its threshold.
#      Capital alone does not trigger; the market must be corroborated by
#      something we independently observe in the context file.
#
# Rationale: RAS penalises technician WRs/TEs whose craft (route running,
# contested catch, separation via timing) does not show up on a timing sheet.
# When confirmed-low RAS conflicts with high draft investment AND an observed
# craft signal, the model's athletic penalty is likely overstated.
#
# This is an additive post-score field. It never mutates the base formula.
# It is logged clearly and surfaced in the output payload.
MARKET_CONVICTION_POSITIONS: frozenset[str] = frozenset({"WR", "TE"})
MARKET_CONVICTION_RAS_CAP = 45.0        # confirmed RAS must be strictly below this
MARKET_CONVICTION_CAPITAL_FLOOR = 65.0  # proxy must be >= this (~pick 50 / Day 2)

# Evidence tags that qualify as a craft signal
MARKET_CONVICTION_CRAFT_TAGS: frozenset[str] = frozenset({
    "elite_efficiency_tier",
    "inside_out_versatility",
    "yac_signal",
    "elite_yac_producer",
    "multi_season_efficiency",
    "route_runner",
    "contested_catch_signal",
    "yprr_elite",
    "r1_p4_wr_comps",
})

# Numeric context field thresholds that also qualify as a craft signal
# (field_name, minimum_value)
MARKET_CONVICTION_NUMERIC_SIGNALS: list[tuple[str, float]] = [
    ("career_yards_per_route_run", 2.3),   # elite YPRR floor
    ("best_season_yprr", 2.6),             # exceptional peak season
    ("contested_catch_rate", 0.45),        # above-average in-traffic catch rate
]

MARKET_CONVICTION_BONUS_BASE = 2.5    # 1 craft signal
MARKET_CONVICTION_BONUS_STRONG = 4.0  # 2+ craft signals

# ---------------------------------------------------------------------------
# Positional consensus score curves
# ---------------------------------------------------------------------------
# Maps positional rank (1 = best) to an expected score on the 0-100 alpha scale.
# These values represent the consensus expectation for a player at each positional
# rank — NOT derived from overall board pick bands.  Calibrated so that a player
# whose model score matches positional consensus shows a near-zero delta, while
# genuine model disagreements produce proportionate signals.
#
# Design properties:
#   - Monotonically decreasing within each position
#   - Fit to the alpha scale (typical top-10 picks score 60-85)
#   - Modular: each position can be tuned independently
#   - Ranks beyond the table decay by _POSITIONAL_CURVE_TAIL_STEP per rank,
#     floored at _POSITIONAL_CURVE_FLOOR
#
# To tune: adjust values here without touching compute logic.
POSITIONAL_SCORE_CURVES: dict[str, list[float]] = {
    #         1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
    "QB": [82.0, 77.0, 72.0, 67.0, 62.0, 58.0, 54.0, 51.0, 48.0, 46.0, 44.0, 42.0, 40.0, 38.0, 37.0],
    "WR": [80.0, 75.0, 71.0, 67.0, 63.0, 60.0, 57.0, 54.0, 51.0, 49.0, 47.0, 45.0, 43.0, 42.0, 41.0],
    "RB": [79.0, 74.0, 69.0, 65.0, 61.0, 58.0, 55.0, 52.0, 50.0, 48.0, 46.0, 44.0, 43.0, 42.0, 41.0],
    "TE": [79.0, 73.0, 67.0, 63.0, 59.0, 56.0, 53.0, 50.0, 47.0, 45.0, 43.0, 41.0, 40.0, 39.0, 38.0],
}
_POSITIONAL_CURVE_TAIL_STEP = 0.5   # score drop per rank beyond the table
_POSITIONAL_CURVE_FLOOR = 28.0      # minimum consensus score for any rank


def positional_rank_to_score(position: str, rank: int) -> float:
    """Convert a blended positional consensus rank to a 0-100 score.

    Uses per-position curves calibrated to the alpha scale.  Falls back to
    the WR curve for unrecognised positions.  Extends past the table with a
    linear tail.
    """
    curve = POSITIONAL_SCORE_CURVES.get(position, POSITIONAL_SCORE_CURVES["WR"])
    if rank <= len(curve):
        return curve[rank - 1]
    extra = rank - len(curve)
    return max(_POSITIONAL_CURVE_FLOOR, curve[-1] - extra * _POSITIONAL_CURVE_TAIL_STEP)


def load_positional_consensus(path: Path) -> dict[str, dict]:
    """Load a positional consensus artifact and return a per-player lookup.

    Returns ``{player_id: {"ranks": [int, ...], "sources": [str, ...]}}``
    keyed on player_id.  Returns an empty dict when the file does not exist
    (positional consensus is optional).

    The artifact supports multiple sources per class year; all source entries
    are merged into the per-player ranks list so blending happens at compute
    time.
    """
    if not path.exists():
        logging.warning("Positional consensus file not found at %s — positional delta fields will be null.", path)
        return {}
    data = load_json(path)
    result: dict[str, dict] = {}
    for source_entry in data.get("sources", []):
        source_name = source_entry.get("source", "unknown")
        for entry in source_entry.get("entries", []):
            pid = entry.get("player_id")
            rank = entry.get("positional_rank")
            if not pid or rank is None:
                continue
            if pid not in result:
                result[pid] = {"ranks": [], "sources": []}
            result[pid]["ranks"].append(int(rank))
            result[pid]["sources"].append(source_name)
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc.msg} (line {exc.lineno}, column {exc.colno})") from exc
    except OSError as exc:
        raise SystemExit(f"Unable to read input file {path}: {exc}") from exc


def clamp_0_100(value: float) -> float:
    return max(0.0, min(100.0, value))


def z_to_score(z: float) -> float:
    # 50 at average, ~16.7 points per standard deviation.
    return clamp_0_100(50.0 + (z * 16.6667))


def safe_stats(values: list[float]) -> tuple[float, float]:
    if not values:
        return (0.0, 1.0)
    if len(values) == 1:
        return (values[0], 1.0)
    sd = pstdev(values)
    return (mean(values), sd if sd > 1e-9 else 1.0)


def coerce_float(
    value: Any,
    field_name: str,
    player_id: str,
    source_name: str,
    warned_invalid_values: set[tuple[str, str, str, str]] | None = None,
) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        warning_key = (field_name, repr(value), player_id, source_name)
        if warned_invalid_values is None or warning_key not in warned_invalid_values:
            logging.warning(
                "Skipping invalid %s value %r for player_id=%s in %s; field will be treated as missing.",
                field_name,
                value,
                player_id,
                source_name,
            )
            if warned_invalid_values is not None:
                warned_invalid_values.add(warning_key)
        return None


def normalize_row(
    row: dict[str, Any],
    source_name: str,
    row_number: int,
) -> tuple[str, str, str] | None:
    player_id_raw = row.get("player_id")
    if player_id_raw is None or str(player_id_raw).strip() == "":
        logging.warning(
            "Skipping row %s in %s because required field player_id is missing.",
            row_number,
            source_name,
        )
        return None
    player_id = str(player_id_raw)
    player_name = str(row.get("player_name", player_id))
    position = str(row.get("position", "UNK"))
    return (player_id, player_name, position)


def _flag_exceptional(
    metric: str,
    value: float,
    z: float,
    position: str,
    direction_positive: str,
    direction_negative: str,
    unit: str = "",
) -> dict[str, Any]:
    """Build an exceptional-metric entry for a combine measurement."""
    tier = "historic" if abs(z) >= 2.5 else "elite"
    direction = direction_positive if z > 0 else direction_negative
    val_str = f"{value:.2f}{unit}" if unit != '"' else f'{value:.1f}"'
    return {
        "metric": metric,
        "value": value,
        "z_score": round(z, 2),
        "context": f"{val_str} {metric.replace('_', ' ')} ({direction}; z={z:.2f} vs {position} peer group)",
        "percentile_tier": tier,
        "alpha_bonus_eligible": False,
        "source": "combine",
    }


def compute_ras_scores(
    combine_rows: list[dict[str, Any]],
) -> tuple[
    dict[str, float],
    dict[str, list[dict[str, Any]]],
    dict[str, int],
    dict[str, tuple[float, int]],
]:
    """Return ``(ras_scores_by_id, exceptional_combine, component_counts, combine_fallback)``.

    RAS component weights:
      forty 0.30 / vertical 0.20 / broad 0.20 / three_cone 0.15 / size 0.15.
    Weights are renormalized over whichever components are present.

    A score is computed only when at least one explosive/agility metric is
    available (vertical, broad, or three_cone).  Players with only 40 + size
    (typically top picks who skipped drills) default to 50.0.

    ``component_counts``: maps player_id → number of component categories that
    contributed to the RAS score (max 5: forty, vertical, broad, three_cone, size).

    ``combine_fallback``: maps player_id → (score, metric_count) for players
    who had some combine data but did not qualify for a full RAS score (missing
    explosive metrics). These partial scores carry low confidence.

    Exceptional combine metrics are flagged when any individual metric z-score
    reaches ±EXCEPTIONAL_Z_THRESHOLD within the position peer group.  These
    are informational only — they are already captured in the RAS score.
    """
    by_position: dict[str, list[dict[str, Any]]] = {}
    warned_invalid_values: set[tuple[str, str, str, str]] = set()
    for idx, row in enumerate(combine_rows, start=1):
        normalized = normalize_row(row, "combine input", idx)
        if normalized is None:
            continue
        pid, _, position = normalized
        by_position.setdefault(position, []).append({"player_id": pid, **row})

    scores: dict[str, float] = {}
    exceptional_combine: dict[str, list[dict[str, Any]]] = {}
    component_counts: dict[str, int] = {}
    combine_fallback: dict[str, tuple[float, int]] = {}

    for position, rows in by_position.items():
        def _vals(field: str) -> list[float]:
            return [
                v
                for r in rows
                for v in [coerce_float(r.get(field), field, str(r["player_id"]), "combine input", warned_invalid_values)]
                if v is not None
            ]

        forties = _vals("forty")
        verticals = _vals("vertical")
        broads = _vals("broad")
        three_cones = _vals("three_cone")
        heights = _vals("height_in")
        weights = _vals("weight_lb")

        forty_mu, forty_sd = safe_stats(forties)
        vert_mu, vert_sd = safe_stats(verticals)
        broad_mu, broad_sd = safe_stats(broads)
        cone_mu, cone_sd = safe_stats(three_cones)
        h_mu, h_sd = safe_stats(heights)
        w_mu, w_sd = safe_stats(weights)

        for r in rows:
            pid = str(r["player_id"])
            components: list[tuple[float, float]] = []
            exceptional_for_player: list[dict[str, Any]] = []

            forty = coerce_float(r.get("forty"), "forty", pid, "combine input", warned_invalid_values)
            vertical = coerce_float(r.get("vertical"), "vertical", pid, "combine input", warned_invalid_values)
            broad = coerce_float(r.get("broad"), "broad", pid, "combine input", warned_invalid_values)
            three_cone = coerce_float(r.get("three_cone"), "three_cone", pid, "combine input", warned_invalid_values)
            height = coerce_float(r.get("height_in"), "height_in", pid, "combine input", warned_invalid_values)
            weight = coerce_float(r.get("weight_lb"), "weight_lb", pid, "combine input", warned_invalid_values)

            if forty is not None:
                z = (forty_mu - forty) / forty_sd  # lower is better
                components.append((0.30, z_to_score(z)))
                if abs(z) >= EXCEPTIONAL_Z_THRESHOLD:
                    exceptional_for_player.append(
                        _flag_exceptional("forty", forty, z, position, "fast", "slow", "s")
                    )
            if vertical is not None:
                z = (vertical - vert_mu) / vert_sd
                components.append((0.20, z_to_score(z)))
                if abs(z) >= EXCEPTIONAL_Z_THRESHOLD:
                    exceptional_for_player.append(
                        _flag_exceptional("vertical", vertical, z, position, "high", "low", '"')
                    )
            if broad is not None:
                z = (broad - broad_mu) / broad_sd
                components.append((0.20, z_to_score(z)))
                if abs(z) >= EXCEPTIONAL_Z_THRESHOLD:
                    exceptional_for_player.append(
                        _flag_exceptional("broad", broad, z, position, "long", "short", '"')
                    )
            if three_cone is not None:
                z = (cone_mu - three_cone) / cone_sd  # lower is better
                components.append((0.15, z_to_score(z)))
                if abs(z) >= EXCEPTIONAL_Z_THRESHOLD:
                    exceptional_for_player.append(
                        _flag_exceptional("three_cone", three_cone, z, position, "fast", "slow", "s")
                    )

            size_parts: list[float] = []
            if height is not None:
                size_parts.append(z_to_score((height - h_mu) / h_sd))
            if weight is not None:
                size_parts.append(z_to_score((weight - w_mu) / w_sd))
            if size_parts:
                components.append((0.15, mean(size_parts)))

            # Require at least one explosive/agility metric (vertical, broad, or
            # three_cone). Without these, the score is built almost entirely from
            # 40 + size and is not a reliable RAS proxy — most often this means
            # the player skipped testing (a non-signal for top picks), not that
            # they lack athleticism. Omit rather than mislead.
            has_explosive = vertical is not None or broad is not None or three_cone is not None
            if components and has_explosive:
                weight_sum = sum(w for w, _ in components)
                weighted = sum(w * s for w, s in components) / weight_sum
                scores[pid] = clamp_0_100(weighted)
                component_counts[pid] = len(components)
                if exceptional_for_player:
                    exceptional_combine[pid] = exceptional_for_player
            elif components:
                # Has some combine data but no explosive metrics → fallback
                weight_sum = sum(w for w, _ in components)
                weighted = sum(w * s for w, s in components) / weight_sum
                combine_fallback[pid] = (clamp_0_100(weighted), len(components))

    return scores, exceptional_combine, component_counts, combine_fallback


# ---------------------------------------------------------------------------
# Generalized athletic input layer
# ---------------------------------------------------------------------------
# Position-aware SPORQ trust: controls whether SPORQ from exceptional_metrics
# can be used as the primary athletic score when RAS is missing.
#   "preferred"   — use SPORQ as primary when RAS unavailable (TE)
#   "supplemental" — log it but don't substitute for RAS (WR)
#   "ignore"      — do not use SPORQ at all (RB, QB)
SPORQ_TRUST: dict[str, str] = {
    "TE": "preferred",
    "WR": "supplemental",
    "RB": "ignore",
    "QB": "ignore",
}


def _extract_sporq(context: dict[str, Any] | None) -> tuple[float | None, str | None]:
    """Extract SPORQ percentile from exceptional_metrics in context.

    Returns (sporq_value, sporq_context_str) or (None, None).
    """
    if not context:
        return None, None
    for em in context.get("exceptional_metrics") or []:
        if em.get("metric") == "sporq_percentile" and em.get("value") is not None:
            try:
                return float(em["value"]), em.get("context")
            except (TypeError, ValueError):
                pass
    return None, None


def _ras_confidence(component_count: int) -> float:
    """Confidence for a full RAS score based on how many combine components were used.

    Max 5 components (forty, vertical, broad, three_cone, size).
    """
    if component_count >= 5:
        return 1.0
    if component_count >= 4:
        return 0.95
    if component_count >= 3:
        return 0.85
    return 0.80  # minimum (2 components — rare but possible)


def resolve_athletic_input(
    player_id: str,
    position: str,
    ras_score: float | None,
    ras_metric_count: int,
    combine_fallback_entry: tuple[float, int] | None,
    context: dict[str, Any] | None,
) -> tuple[float | None, str | None, float, str | None, bool]:
    """Resolve the best available athletic score for a player.

    Returns ``(score, source, confidence, explainer, sporq_used_as_athletic)``.

    Priority:
      1. RAS (full combine composite) — default for all positions
      2. SPORQ (for TE only when trust=preferred and RAS missing)
      3. COMBINE_FALLBACK (partial combine data, low confidence)
      4. None (no athletic data)
    """
    # 1. RAS is the primary source
    if ras_score is not None:
        confidence = _ras_confidence(ras_metric_count)
        return (
            ras_score,
            "RAS",
            confidence,
            f"RAS {ras_score:.1f} from {ras_metric_count} combine metrics",
            False,
        )

    # 2. SPORQ — position-gated
    sporq_val, sporq_ctx = _extract_sporq(context)
    trust = SPORQ_TRUST.get(position, "ignore")
    if sporq_val is not None and trust == "preferred":
        return (
            sporq_val,
            "SPORQ",
            0.75,
            f"SPORQ {sporq_val:.0f}th percentile (no combine RAS available)",
            True,
        )

    # 3. COMBINE_FALLBACK — partial combine data
    if combine_fallback_entry is not None:
        fallback_score, metric_count = combine_fallback_entry
        confidence = 0.30 + 0.10 * min(metric_count, 2)  # 0.40–0.50
        return (
            fallback_score,
            "COMBINE_FALLBACK",
            confidence,
            f"Partial combine ({metric_count} metrics, no explosive drills)",
            False,
        )

    # 4. No athletic data
    return (None, None, 0.0, None, False)


AGE_ADJUSTED_BLEND_WEIGHT = 0.60  # weight on age-adjusted score
EXISTING_PRODUCTION_BLEND_WEIGHT = 0.40  # weight on existing efficiency-based score


def blend_production_rows(
    production_rows: list[dict[str, Any]],
    age_adjusted_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Blend existing production scores with age-adjusted scores.

    blended = 0.60 × age_adjusted_production + 0.40 × existing_production

    Players with no age-adjusted entry retain their existing score unchanged.
    The original score is preserved as ``raw_production_score_0_100``; the
    blended value replaces ``production_score_0_100`` so downstream logic
    requires no changes.
    """
    age_adj_by_id: dict[str, float] = {
        row["player_id"]: float(row["age_adjusted_production_score"])
        for row in age_adjusted_rows
        if row.get("player_id") and row.get("age_adjusted_production_score") is not None
    }

    blended: list[dict[str, Any]] = []
    for row in production_rows:
        row = dict(row)  # shallow copy — don't mutate input
        pid = row.get("player_id", "")
        existing = row.get("production_score_0_100")
        age_adj = age_adj_by_id.get(pid)

        if existing is not None and age_adj is not None:
            row["raw_production_score_0_100"] = existing
            row["age_adjusted_production_0_100"] = age_adj
            row["production_score_0_100"] = round(
                AGE_ADJUSTED_BLEND_WEIGHT * age_adj
                + EXISTING_PRODUCTION_BLEND_WEIGHT * float(existing),
                4,
            )
        elif age_adj is not None:
            # No existing score — use age-adjusted only
            row["age_adjusted_production_0_100"] = age_adj
            row["production_score_0_100"] = round(age_adj, 4)
        # else: no age-adjusted entry — leave row unchanged

        blended.append(row)
    return blended


# ---------------------------------------------------------------------------
# Context-driven production adjustments
# ---------------------------------------------------------------------------

# WR efficiency tier: for WRs verified in 75th+ pctile YPRR / passer rating
# with low-volume college profiles, the 60/40 age-adj blend underweights their
# per-route efficiency. Flip to 40/60 (age-adj/raw) — but only when age-adj is
# already pulling the score DOWN relative to the CFBD raw score (i.e., never harm
# an early-breakout WR who is already getting the age multiplier boost).
WR_EFFICIENCY_TIER_AGE_ADJ_WEIGHT = 0.40
WR_EFFICIENCY_TIER_RAW_WEIGHT = 0.60

# RB MTF penalty: career MTF/touch below threshold indicates poor contact quality
# relative to day-2 peers. Applied as a tiered deduction to production score.
RB_MTF_POOR_THRESHOLD = 0.18   # below → poor tier (−5 pts)
RB_MTF_BELOW_AVG_THRESHOLD = 0.20  # below → below-average tier (−2.5 pts)

# RB YAC consistency penalty: yac_plus_catch_2nd_best_season < threshold flags
# one-hit-wonder risk. Uses the 2nd-best season as a floor signal (a player's
# worst relevant season tells you more about their floor than their peak).
# Comps for the severe tier: D.Harris, Sony Michel, Rashaad Penny, CEH.
RB_YAC_SEVERE_THRESHOLD = 40.0   # < 40 yd/game → −4 pts
RB_YAC_CONCERN_THRESHOLD = 48.0  # < 48 yd/game → −2 pts

# WR production translation penalties: penalize manufactured/low-translation
# production profiles. Three independent signals — screen-heavy yards, lack of
# vertical route evidence, and slot separation concern — each apply a tiered
# deduction to production_score_0_100. Applied after the efficiency-tier reblend
# so both quality signals hit the final production score independently.
# All signals are null-safe: they fire only when the field is present in context.
# Combined total is capped at WR_TRANSLATION_PENALTY_CAP to prevent triple-taxing
# correlated archetypes (screen-heavy slot WRs tend to score poorly on all three).
WR_SCREEN_CONCERN_THRESHOLD = 0.40   # screen_yard_share > → -3.0 pts
WR_SCREEN_SEVERE_THRESHOLD  = 0.50   # screen_yard_share > → -5.0 pts
WR_DEEP_CONCERN_THRESHOLD   = 0.245  # deep_yard_share < → -2.0 pts
WR_DEEP_SEVERE_THRESHOLD    = 0.18   # deep_yard_share < → -4.0 pts
WR_SLOT_CONTESTED_CONCERN   = 0.30   # slot_contested_target_rate > → -1.5 pts
WR_SLOT_CONTESTED_SEVERE    = 0.40   # slot_contested_target_rate > → -3.0 pts
WR_TRANSLATION_PENALTY_CAP  = 8.0    # max combined penalty across all three signals


def apply_context_production_adjustments(
    production_rows: list[dict[str, Any]],
    context_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply context-driven adjustments to blended production scores.

    Three adjustments (applied in order):

    1. **WR elite_efficiency_tier re-blend** — for WRs with verified 75th+
       pctile YPRR/passer-rating/TPRR whose age-adjusted score is pulling their
       blended production *below* the CFBD raw efficiency score, flip the blend
       weights to 40% age-adjusted / 60% raw.  This corrects the volume-bias for
       low-target-share / high-efficiency WRs (Sarratt archetype; Nacua precedent).
       Only applied when age_adj < raw — never harms early-breakout WRs.

    2. **WR production translation penalties** — three independent signals that
       penalize manufactured/low-translation production profiles:
         - screen_yard_share > 0.40 → −3.0 pts / > 0.50 → −5.0 pts
         - deep_yard_share < 0.245 → −2.0 pts / < 0.18 → −4.0 pts
         - slot_contested_target_rate > 0.30 → −1.5 pts / > 0.40 → −3.0 pts
       Combined total capped at −8.0 to prevent triple-taxing correlated
       archetypes (screen-heavy slot WRs tend to score poorly on all three).
       Each signal is null-safe — fires only when the field exists in context.
       Penalty amount stored as ``wr_translation_penalty`` on the row.

    3. **RB MTF penalty** — for RBs with ``career_mtf_per_touch`` below threshold,
       apply a tiered production deduction:
         < 0.18 → −5 pts   (poor tier: bottom ~10% of Day-2 RBs since 2014)
         < 0.20 → −2.5 pts (below-average tier)
       Corrects for the gap between RAS/combine athleticism and actual
       after-contact production (Washington Jr. archetype).
    """
    adjusted: list[dict[str, Any]] = []
    for row in production_rows:
        row = dict(row)
        pid = row.get("player_id", "")
        ctx = context_by_id.get(pid, {})
        position = ctx.get("position") or row.get("position", "")
        evidence_tags: list[str] = ctx.get("evidence_tags", [])

        # --- WR efficiency tier re-blend ---
        if (
            position == "WR"
            and "elite_efficiency_tier" in evidence_tags
            and row.get("raw_production_score_0_100") is not None
            and row.get("age_adjusted_production_0_100") is not None
            and float(row["age_adjusted_production_0_100"]) < float(row["raw_production_score_0_100"])
        ):
            raw = float(row["raw_production_score_0_100"])
            age_adj = float(row["age_adjusted_production_0_100"])
            old_blended = float(row["production_score_0_100"])
            new_blended = round(
                WR_EFFICIENCY_TIER_AGE_ADJ_WEIGHT * age_adj
                + WR_EFFICIENCY_TIER_RAW_WEIGHT * raw,
                4,
            )
            logging.info(
                "WR efficiency-tier re-blend for %s: %.1f → %.1f "
                "(raw=%.1f age_adj=%.1f weights=%.0f%%/%.0f%%)",
                pid, old_blended, new_blended, raw, age_adj,
                WR_EFFICIENCY_TIER_RAW_WEIGHT * 100,
                WR_EFFICIENCY_TIER_AGE_ADJ_WEIGHT * 100,
            )
            row["production_score_0_100"] = new_blended
            row["efficiency_tier_reblend"] = True

        # --- WR production translation penalties ---
        # Three independent signals; each null-safe. Applied after efficiency-
        # tier reblend so both production-quality adjustments land separately.
        # Combined total is capped at WR_TRANSLATION_PENALTY_CAP.
        if position == "WR":
            translation_signals: list[tuple[str, float]] = []  # (audit_label, penalty_pts)

            screen = ctx.get("screen_yard_share")
            if screen is not None:
                sv = float(screen)
                if sv > WR_SCREEN_SEVERE_THRESHOLD:
                    translation_signals.append(
                        (f"screen_yard_share={sv:.2f} > {WR_SCREEN_SEVERE_THRESHOLD}", 5.0)
                    )
                elif sv > WR_SCREEN_CONCERN_THRESHOLD:
                    translation_signals.append(
                        (f"screen_yard_share={sv:.2f} > {WR_SCREEN_CONCERN_THRESHOLD}", 3.0)
                    )

            deep = ctx.get("deep_yard_share")
            if deep is not None:
                dv = float(deep)
                if dv < WR_DEEP_SEVERE_THRESHOLD:
                    translation_signals.append(
                        (f"deep_yard_share={dv:.2f} < {WR_DEEP_SEVERE_THRESHOLD}", 4.0)
                    )
                elif dv < WR_DEEP_CONCERN_THRESHOLD:
                    translation_signals.append(
                        (f"deep_yard_share={dv:.2f} < {WR_DEEP_CONCERN_THRESHOLD}", 2.0)
                    )

            slot_ct = ctx.get("slot_contested_target_rate")
            if slot_ct is not None:
                scv = float(slot_ct)
                if scv > WR_SLOT_CONTESTED_SEVERE:
                    translation_signals.append(
                        (f"slot_contested_target_rate={scv:.2f} > {WR_SLOT_CONTESTED_SEVERE}", 3.0)
                    )
                elif scv > WR_SLOT_CONTESTED_CONCERN:
                    translation_signals.append(
                        (f"slot_contested_target_rate={scv:.2f} > {WR_SLOT_CONTESTED_CONCERN}", 1.5)
                    )

            if translation_signals:
                raw_total = sum(pen for _, pen in translation_signals)
                capped = min(raw_total, WR_TRANSLATION_PENALTY_CAP)
                old_score = float(row.get("production_score_0_100") or 50.0)
                new_score = clamp_0_100(old_score - capped)
                detail_parts = [f"{label} → -{pen:.1f}" for label, pen in translation_signals]
                if capped < raw_total:
                    detail_parts.append(f"cap applied ({raw_total:.1f} → {capped:.1f})")
                signal_detail = " | ".join(detail_parts)
                logging.info(
                    "WR translation penalty for %s: %.1f → %.1f (−%.1f) [%s]",
                    pid, old_score, new_score, capped, signal_detail,
                )
                row["production_score_0_100"] = round(new_score, 4)
                row["wr_translation_penalty"] = round(capped, 2)
                row["wr_translation_signals"] = signal_detail

        # --- RB MTF penalty ---
        if position == "RB":
            mtf = ctx.get("career_mtf_per_touch")
            if mtf is not None:
                mtf_val = float(mtf)
                if mtf_val < RB_MTF_POOR_THRESHOLD:
                    penalty = 5.0 if mtf_val < RB_MTF_POOR_THRESHOLD else 2.5
                    old_score = float(row.get("production_score_0_100") or 50.0)
                    new_score = clamp_0_100(old_score - penalty)
                    logging.info(
                        "RB MTF penalty for %s: mtf_per_touch=%.3f → −%.1f pts (%.1f → %.1f)",
                        pid, mtf_val, penalty, old_score, new_score,
                    )
                    row["production_score_0_100"] = round(new_score, 4)
                    row["mtf_production_penalty"] = penalty
                elif mtf_val < RB_MTF_BELOW_AVG_THRESHOLD:
                    penalty = 2.5
                    old_score = float(row.get("production_score_0_100") or 50.0)
                    new_score = clamp_0_100(old_score - penalty)
                    logging.info(
                        "RB MTF below-avg penalty for %s: mtf_per_touch=%.3f → −%.1f pts (%.1f → %.1f)",
                        pid, mtf_val, penalty, old_score, new_score,
                    )
                    row["production_score_0_100"] = round(new_score, 4)
                    row["mtf_production_penalty"] = penalty

        # --- RB YAC consistency penalty ---
        if position == "RB":
            yac_floor = ctx.get("yac_plus_catch_2nd_best_season")
            if yac_floor is not None:
                yac_val = float(yac_floor)
                if yac_val < RB_YAC_SEVERE_THRESHOLD:
                    penalty = 4.0
                    old_score = float(row.get("production_score_0_100") or 50.0)
                    new_score = clamp_0_100(old_score - penalty)
                    logging.info(
                        "RB YAC floor penalty for %s: 2nd-best-season=%.1f yd/g → −%.1f pts (%.1f → %.1f) "
                        "[severe: < %.0f]",
                        pid, yac_val, penalty, old_score, new_score, RB_YAC_SEVERE_THRESHOLD,
                    )
                    row["production_score_0_100"] = round(new_score, 4)
                    row["yac_floor_penalty"] = penalty
                elif yac_val < RB_YAC_CONCERN_THRESHOLD:
                    penalty = 2.0
                    old_score = float(row.get("production_score_0_100") or 50.0)
                    new_score = clamp_0_100(old_score - penalty)
                    logging.info(
                        "RB YAC floor penalty for %s: 2nd-best-season=%.1f yd/g → −%.1f pts (%.1f → %.1f) "
                        "[concern: < %.0f]",
                        pid, yac_val, penalty, old_score, new_score, RB_YAC_CONCERN_THRESHOLD,
                    )
                    row["production_score_0_100"] = round(new_score, 4)
                    row["yac_floor_penalty"] = penalty

        adjusted.append(row)
    return adjusted


def merge_inputs(
    combine_rows: list[dict[str, Any]],
    production_rows: list[dict[str, Any]],
    draft_proxy_rows: list[dict[str, Any]],
    context_by_id: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[PlayerInputs], MergeDiagnostics]:
    def build_identity_map(
        rows: list[dict[str, Any]],
        source_name: str,
    ) -> tuple[dict[str, tuple[str, str]], int, int]:
        identities: dict[str, tuple[str, str]] = {}
        duplicate_rows_skipped = 0
        identity_conflicts_skipped = 0
        for idx, row in enumerate(rows, start=1):
            normalized = normalize_row(row, source_name, idx)
            if normalized is None:
                continue
            player_id, player_name, position = normalized
            incoming = (player_name, position)
            if player_id in identities:
                if identities[player_id] == incoming:
                    duplicate_rows_skipped += 1
                    logging.warning(
                        "Skipping duplicate row for player_id=%s in %s (row %s).",
                        player_id,
                        source_name,
                        idx,
                    )
                else:
                    identity_conflicts_skipped += 1
                    logging.warning(
                        "Skipping conflicting identity for player_id=%s in %s (row %s): existing=%s incoming=%s.",
                        player_id,
                        source_name,
                        idx,
                        identities[player_id],
                        incoming,
                    )
                continue
            identities[player_id] = incoming
        return identities, duplicate_rows_skipped, identity_conflicts_skipped

    combine_identities, combine_duplicates, combine_conflicts = build_identity_map(combine_rows, "combine input")
    production_identities, production_duplicates, production_conflicts = build_identity_map(
        production_rows,
        "production input",
    )
    draft_identities, draft_duplicates, draft_conflicts = build_identity_map(draft_proxy_rows, "draft proxy input")

    conflicting_across_sources: set[str] = set()
    for player_id in sorted(set(combine_identities) | set(production_identities) | set(draft_identities)):
        seen = [m[player_id] for m in (combine_identities, production_identities, draft_identities) if player_id in m]
        if len(set(seen)) > 1:
            conflicting_across_sources.add(player_id)
            logging.warning(
                "Excluding player_id=%s due to cross-source identity mismatch: %s",
                player_id,
                seen,
            )

    ras_by_id, exceptional_combine_by_id, ras_component_counts, combine_fallback_by_id = compute_ras_scores(combine_rows)
    warned_invalid_values: set[tuple[str, str, str, str]] = set()
    prod_by_id: dict[str, float] = {}
    age_adj_by_id: dict[str, float] = {}
    for idx, row in enumerate(production_rows, start=1):
        normalized = normalize_row(row, "production input", idx)
        if normalized is None:
            continue
        player_id, _, _ = normalized
        value = coerce_float(
            row.get("production_score_0_100"),
            "production_score_0_100",
            player_id,
            "production input",
            warned_invalid_values,
        )
        if value is not None:
            prod_by_id[player_id] = value
        age_adj = coerce_float(
            row.get("age_adjusted_production_0_100"),
            "age_adjusted_production_0_100",
            player_id,
            "production input",
            warned_invalid_values,
        )
        if age_adj is not None:
            age_adj_by_id[player_id] = age_adj

    draft_by_id: dict[str, float] = {}
    for idx, row in enumerate(draft_proxy_rows, start=1):
        normalized = normalize_row(row, "draft proxy input", idx)
        if normalized is None:
            continue
        player_id, _, _ = normalized
        value = coerce_float(
            row.get("draft_capital_proxy_0_100"),
            "draft_capital_proxy_0_100",
            player_id,
            "draft proxy input",
            warned_invalid_values,
        )
        if value is not None:
            draft_by_id[player_id] = value

    # Production + draft capital are required; RAS is optional.
    # Players who didn't test (or only have partial measurements) are included
    # with ras_score_0_100=None, which defaults to 50.0 in the alpha formula.
    common_ids = sorted(set(prod_by_id) & set(draft_by_id))
    missing_combine = (set(prod_by_id) | set(draft_by_id)) - set(ras_by_id)
    missing_production = (set(ras_by_id) | set(draft_by_id)) - set(prod_by_id)
    missing_draft = (set(ras_by_id) | set(prod_by_id)) - set(draft_by_id)
    excluded_ids = (set(ras_by_id) | set(prod_by_id) | set(draft_by_id)) - set(common_ids)

    ctx = context_by_id or {}
    players: list[PlayerInputs] = []
    for pid in common_ids:
        if pid in conflicting_across_sources:
            continue
        name, position = combine_identities.get(pid) or production_identities.get(pid) or draft_identities.get(pid) or (
            pid,
            "UNK",
        )
        ras_val = ras_by_id.get(pid)
        ath_score, ath_source, ath_conf, ath_explainer, _ = resolve_athletic_input(
            pid, position, ras_val,
            ras_component_counts.get(pid, 0),
            combine_fallback_by_id.get(pid),
            ctx.get(pid),
        )
        players.append(
            PlayerInputs(
                player_id=pid,
                player_name=name,
                position=position,
                ras_score_0_100=ras_val,
                production_score_0_100=prod_by_id.get(pid),
                draft_capital_proxy_0_100=draft_by_id.get(pid),
                age_adjusted_production_0_100=age_adj_by_id.get(pid),
                athletic_score_0_100=ath_score,
                athletic_source=ath_source,
                athletic_confidence=ath_conf,
                athletic_explainer=ath_explainer,
            )
        )
    diagnostics = MergeDiagnostics(
        duplicate_rows_skipped=combine_duplicates + production_duplicates + draft_duplicates,
        identity_conflicts_skipped=combine_conflicts + production_conflicts + draft_conflicts + len(conflicting_across_sources),
        excluded_for_missing_sources={
            "missing_combine": len(missing_combine),
            "missing_production": len(missing_production),
            "missing_draft_proxy": len(missing_draft),
            "total_excluded": len(excluded_ids | conflicting_across_sources),
        },
    )
    return players, diagnostics, exceptional_combine_by_id


def load_context_by_player_id(context_path: Path | None) -> dict[str, dict[str, Any]]:
    if context_path is None or not context_path.exists():
        return {}
    context_rows = load_json(context_path)
    if not isinstance(context_rows, list):
        raise SystemExit(f"Expected list JSON in {context_path}, got {type(context_rows).__name__}")
    context_by_id: dict[str, dict[str, Any]] = {}
    for idx, row in enumerate(context_rows, start=1):
        if not isinstance(row, dict):
            logging.warning("Skipping context row %s in %s because row is not an object.", idx, context_path)
            continue
        normalized = normalize_row(row, str(context_path), idx)
        if normalized is None:
            continue
        player_id, _, _ = normalized
        context_by_id[player_id] = row
    return context_by_id


def normalize_context_entry(context_row: dict[str, Any]) -> dict[str, Any]:
    evidence_tags = [
        str(tag)
        for tag in context_row.get("evidence_tags", [])
        if isinstance(tag, str) and tag in CONTEXT_EVIDENCE_TAG_VOCAB
    ]
    context_flags = [
        str(flag)
        for flag in context_row.get("context_flags", [])
        if isinstance(flag, str) and flag in CONTEXT_FLAG_VOCAB
    ]
    translation_flags = [tag for tag in evidence_tags if tag in TRANSLATION_FLAG_VOCAB]
    normalized = {
        "player_id": context_row.get("player_id"),
        "player_name": context_row.get("player_name"),
        "position": context_row.get("position"),
        "school": context_row.get("school"),
        "class_year": context_row.get("class_year"),
        "early_declare_flag": context_row.get("early_declare_flag"),
        "breakout_age": context_row.get("breakout_age"),
        "age_at_first_impact_season": context_row.get("age_at_first_impact_season"),
        "freshman_total_yards": context_row.get("freshman_total_yards"),
        "sophomore_total_yards": context_row.get("sophomore_total_yards"),
        "freshman_impact_flag": context_row.get("freshman_impact_flag"),
        "young_breakout_flag": context_row.get("young_breakout_flag"),
        "breakout_strength": context_row.get("breakout_strength"),
        "breakout_confidence": context_row.get("breakout_confidence"),
        "breakout_age_rating_0_100": context_row.get("breakout_age_rating_0_100"),
        "breakout_label": context_row.get("breakout_label"),
        "career_yards_per_route_run": context_row.get("career_yards_per_route_run"),
        "best_season_yprr": context_row.get("best_season_yprr"),
        "worst_season_yprr": context_row.get("worst_season_yprr"),
        "seasons_over_2_3_yprr": context_row.get("seasons_over_2_3_yprr"),
        "single_season_efficiency_dip_flag": context_row.get("single_season_efficiency_dip_flag"),
        "multi_season_efficiency_flag": context_row.get("multi_season_efficiency_flag"),
        "injury_affected_season_count": context_row.get("injury_affected_season_count"),
        "injury_adjusted_profile_flag": context_row.get("injury_adjusted_profile_flag"),
        "broken_offense_context_flag": context_row.get("broken_offense_context_flag"),
        "suppressed_context_season_count": context_row.get("suppressed_context_season_count"),
        "rush_attempts_or_rush_usage_signal": context_row.get("rush_attempts_or_rush_usage_signal"),
        "rushing_production_signal": context_row.get("rushing_production_signal"),
        "missed_tackles_forced_per_reception": context_row.get("missed_tackles_forced_per_reception"),
        "yac_proxy_per_reception": context_row.get("yac_proxy_per_reception"),
        "contested_catch_rate": context_row.get("contested_catch_rate"),
        "inside_out_versatility_flag": context_row.get("inside_out_versatility_flag"),
        "man_zone_versatility_flag": context_row.get("man_zone_versatility_flag"),
        "power4_early_contributor_flag": context_row.get("power4_early_contributor_flag"),
        "career_receiving_market_share": context_row.get("career_receiving_market_share"),
        "career_mtf_per_attempt": context_row.get("career_mtf_per_attempt"),
        "freshman_ypc": context_row.get("freshman_ypc"),
        "athletic_upside_flag": context_row.get("athletic_upside_flag"),
        "path_disruption_flag": context_row.get("path_disruption_flag"),
    }
    return {
        "context": normalized,
        "evidence": {
            "evidence_tags": evidence_tags,
            "context_flags": context_flags,
            "translation_flags": translation_flags,
            "evidence_summary": context_row.get("evidence_summary"),
            "context_source": context_row.get("context_source"),
        },
    }


def rookie_alpha_score(player: PlayerInputs) -> float:
    # Use resolved athletic score (RAS / SPORQ / COMBINE_FALLBACK), falling
    # back to raw RAS, then to 50.0 (neutral) when nothing is available.
    ath = player.athletic_score_0_100 if player.athletic_score_0_100 is not None else (
        player.ras_score_0_100 if player.ras_score_0_100 is not None else 50.0
    )
    if player.production_score_0_100 is None:
        production = 50.0
    elif player.age_adjusted_production_0_100 is None:
        # Evidence-discipline fallback: if age-adjusted production is missing,
        # do not preserve full raw production credit.
        production = player.production_score_0_100 * 0.85
    else:
        production = player.production_score_0_100
    draft = player.draft_capital_proxy_0_100 if player.draft_capital_proxy_0_100 is not None else 50.0
    return clamp_0_100((0.35 * ath) + (0.45 * production) + (0.20 * draft))


def talent_score(player: PlayerInputs) -> float:
    """Athletic + production only, renormalized to sum to 1.0.

    Weights derived from rookie_alpha formula: 0.35 / 0.80 = 0.4375 (ATH),
    0.45 / 0.80 = 0.5625 (production). Null inputs default to 50.0.
    """
    ath = player.athletic_score_0_100 if player.athletic_score_0_100 is not None else (
        player.ras_score_0_100 if player.ras_score_0_100 is not None else 50.0
    )
    production = player.production_score_0_100 if player.production_score_0_100 is not None else 50.0
    return clamp_0_100((0.4375 * ath) + (0.5625 * production))


def compute_market_conviction_override(
    position: str,
    ras_score: float | None,
    capital: float | None,
    raw_context: dict[str, Any] | None,
) -> tuple[float, str | None]:
    """Return (bonus, reason) for the market-conviction RAS override.

    Never fires if RAS is None (missing/defaulted) — only confirmed combine
    scores below the threshold qualify. Capital alone is not sufficient; at
    least one independently-observed craft signal is required.
    """
    if position not in MARKET_CONVICTION_POSITIONS:
        return 0.0, None
    if ras_score is None:
        return 0.0, None  # missing/defaulted RAS must never trigger
    if ras_score >= MARKET_CONVICTION_RAS_CAP:
        return 0.0, None
    cap_val = capital if capital is not None else 50.0
    if cap_val < MARKET_CONVICTION_CAPITAL_FLOOR:
        return 0.0, None
    if not raw_context:
        return 0.0, None

    craft_signals: list[str] = []

    # Tag-based signals
    raw_tags = set(raw_context.get("evidence_tags", []))
    for tag in sorted(MARKET_CONVICTION_CRAFT_TAGS):
        if tag in raw_tags:
            craft_signals.append(f"tag:{tag}")

    # inside_out_versatility_flag (boolean field, separate from evidence tag)
    if raw_context.get("inside_out_versatility_flag"):
        signal = "field:inside_out_versatility_flag"
        if signal not in craft_signals:
            craft_signals.append(signal)

    # Numeric field thresholds
    for field, threshold in MARKET_CONVICTION_NUMERIC_SIGNALS:
        val = raw_context.get(field)
        if val is not None:
            try:
                if float(val) >= threshold:
                    craft_signals.append(f"field:{field}>={threshold}")
            except (TypeError, ValueError):
                pass

    if not craft_signals:
        return 0.0, None

    bonus = MARKET_CONVICTION_BONUS_STRONG if len(craft_signals) >= 2 else MARKET_CONVICTION_BONUS_BASE
    reason = (
        f"{position} craft override: confirmed RAS {ras_score:.1f} < {MARKET_CONVICTION_RAS_CAP} "
        f"| capital {cap_val:.0f} >= {MARKET_CONVICTION_CAPITAL_FLOOR} "
        f"| craft signals [{', '.join(craft_signals)}] "
        f"| +{bonus:.1f} pts"
    )
    return bonus, reason


def write_outputs(
    players: list[PlayerInputs],
    merge_diagnostics: MergeDiagnostics,
    season: int,
    combine_path: Path,
    production_path: Path,
    draft_proxy_path: Path,
    output_json: Path,
    output_csv: Path,
    output_manifest: Path,
    context_path: Path | None = None,
    context_by_id: dict[str, dict[str, Any]] | None = None,
    exceptional_combine_by_id: dict[str, list[dict[str, Any]]] | None = None,
    wr_translation_penalty_by_id: dict[str, tuple[float, str]] | None = None,
    positional_consensus_path: Path | None = None,
    positional_consensus_by_id: dict[str, dict] | None = None,
) -> None:
    generated_at = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
    run_id = f"rookie-alpha-{season}-{generated_at}"

    ranked: list[dict[str, Any]] = []
    context_by_id = context_by_id or {}
    exceptional_combine_by_id = exceptional_combine_by_id or {}
    players_with_context = 0
    missing_any = 0
    for p in players:
        alpha = rookie_alpha_score(p)
        ts = talent_score(p)

        # ------------------------------------------------------------------
        # Exceptional metrics: combine-derived (informational, already in RAS)
        # + context-sourced (may carry ceiling bonus when alpha_bonus_eligible).
        # Computed before the scores dict so ceiling_bonus can adjust alpha.
        # ------------------------------------------------------------------
        player_exceptional: list[dict[str, Any]] = []

        combine_exc = exceptional_combine_by_id.get(p.player_id, [])
        player_exceptional.extend(combine_exc)

        ctx_exc: list[dict[str, Any]] = context_by_id.get(p.player_id, {}).get("exceptional_metrics") or []
        player_exceptional.extend(ctx_exc)

        # When SPORQ is used as the athletic score, suppress its ceiling bonus
        # to avoid double-counting athleticism in the alpha formula.
        sporq_used = p.athletic_source == "SPORQ"

        ceiling_bonus = 0.0
        for em in ctx_exc:
            if em.get("alpha_bonus_eligible", False):
                if sporq_used and em.get("metric") == "sporq_percentile":
                    logging.info(
                        "Suppressing SPORQ ceiling bonus for %s — already used as athletic_score",
                        p.player_id,
                    )
                    continue
                ceiling_bonus += CEILING_BONUS_TIERS.get(em.get("percentile_tier", "notable"), 0.0)
        ceiling_bonus = min(ceiling_bonus, CEILING_BONUS_CAP)
        if ceiling_bonus > 0.0:
            logging.info(
                "Ceiling bonus for %s: +%.1f pts (alpha %.4f → %.4f)",
                p.player_id, ceiling_bonus, alpha, min(100.0, alpha + ceiling_bonus),
            )
            alpha = clamp_0_100(alpha + ceiling_bonus)

        # Market-conviction RAS override — additive post-score, logged separately.
        # Uses raw context row so numeric fields and unfiltered tags are accessible.
        raw_ctx = context_by_id.get(p.player_id)
        mc_bonus, mc_reason = compute_market_conviction_override(
            p.position,
            p.ras_score_0_100,           # None → confirmed missing → no trigger
            p.draft_capital_proxy_0_100,
            raw_ctx,
        )
        if mc_bonus > 0.0:
            logging.info(
                "Market conviction override for %s: %s",
                p.player_id, mc_reason,
            )
            alpha = clamp_0_100(alpha + mc_bonus)

        missing_components = [
            key
            for key, value in {
                "athletic": p.athletic_score_0_100,
                "production": p.production_score_0_100,
                "draft_capital_proxy": p.draft_capital_proxy_0_100,
            }.items()
            if value is None
        ]
        if missing_components:
            missing_any += 1
            logging.warning(
                "Missing model inputs for player_id=%s (%s): %s. Defaulting missing inputs to 50.0.",
                p.player_id,
                p.player_name,
                ",".join(missing_components),
            )
        draft_val = p.draft_capital_proxy_0_100 if p.draft_capital_proxy_0_100 is not None else 50.0
        # DEPRECATED: alpha minus overall draft-capital proxy.  Kept for backward
        # compatibility only — this comparison is structurally misleading because
        # draft_capital_proxy_0_100 reflects overall board investment (incl. defenders,
        # OL) while alpha is a skill-position talent composite.  Use
        # consensus_delta_positional for model-vs-consensus signal.
        market_investment_delta_legacy = round(alpha - draft_val, 1)

        # --- Positional consensus delta (position-aware) ---------------------
        # Compares model alpha against a position-specific consensus expectation
        # score derived from positional rank curves, not overall draft capital.
        pos_entry = (positional_consensus_by_id or {}).get(p.player_id, {})
        pos_ranks = pos_entry.get("ranks", [])
        if pos_ranks:
            blended_rank = round(mean(pos_ranks))
            sources_count: int | None = len(pos_ranks)
            consensus_score_pos: float | None = round(positional_rank_to_score(p.position, blended_rank), 1)
            consensus_delta_pos: float | None = round(alpha - consensus_score_pos, 1)
        else:
            blended_rank = None
            sources_count = None
            consensus_score_pos = None
            consensus_delta_pos = None

        row_payload = {
            "player_id": p.player_id,
            "player_name": p.player_name,
            "position": p.position,
            "scores": {
                "ras_0_100": round(p.ras_score_0_100, 4) if p.ras_score_0_100 is not None else None,
                "athletic_score_0_100": round(p.athletic_score_0_100, 4) if p.athletic_score_0_100 is not None else None,
                "athletic_source": p.athletic_source,
                "athletic_confidence": round(p.athletic_confidence, 2),
                "athletic_explainer": p.athletic_explainer,
                "production_0_100": round(
                    p.production_score_0_100 if p.production_score_0_100 is not None else 50.0,
                    4,
                ),
                "age_adjusted_production_0_100": round(p.age_adjusted_production_0_100, 1)
                if p.age_adjusted_production_0_100 is not None
                else None,
                "draft_capital_proxy_0_100": round(draft_val, 4),
                "talent_score_0_100": round(ts, 4),
                "rookie_alpha_0_100": round(alpha, 4),
                "ceiling_bonus": round(ceiling_bonus, 2) if ceiling_bonus > 0.0 else None,
                "market_conviction_ras_override": round(mc_bonus, 2) if mc_bonus > 0.0 else None,
                "market_conviction_reason": mc_reason,
                "wr_translation_penalty": round(
                    (wr_translation_penalty_by_id or {}).get(p.player_id, (0.0, ""))[0], 2
                ) if (wr_translation_penalty_by_id or {}).get(p.player_id) else None,
                "wr_translation_signals": (wr_translation_penalty_by_id or {}).get(p.player_id, (None, None))[1]
                or None,
                # Positional consensus fields (position-aware, not overall-board-based)
                "consensus_position_rank_blended": blended_rank,
                "consensus_position_rank_sources_count": sources_count,
                "consensus_score_positional_0_100": consensus_score_pos,
                "consensus_delta_positional": consensus_delta_pos,
                # Legacy field — kept for backward compat; semantics are misleading
                # (compares alpha against overall draft capital, not positional consensus)
                "market_investment_delta_legacy": market_investment_delta_legacy,
            },
            "model_inputs_missing": missing_components,
        }
        if player_exceptional:
            row_payload["exceptional_metrics"] = player_exceptional

        if p.player_id in context_by_id:
            row_payload.update(normalize_context_entry(context_by_id[p.player_id]))
            players_with_context += 1

        # Score caveats: surface cases where alpha score diverges from dynasty
        # value for reasons the model doesn't capture (e.g. pre-draft injury).
        caveats: list[str] = []
        ctx_flags = row_payload.get("evidence", {}).get("context_flags", [])
        ev_tags = row_payload.get("evidence", {}).get("evidence_tags", [])
        if "pre_draft_acl_march_2026" in ctx_flags or "acl_injury_predraft" in ev_tags:
            caveats.append(
                "ACL tear (pre-draft 2026): alpha reflects pre-injury talent profile. "
                "Dynasty value is materially lower than alpha implies; year-1 contribution "
                "is unlikely. Consensus delta overstates model edge vs current dynasty market."
            )
        if "synthetic_profile_pending_cfbd" in ctx_flags:
            caveats.append(
                "Route profile estimated (pending CFBD fetch): age-adjusted production score "
                "is based on synthetic target data derived from career totals. Ranking may shift "
                "materially once real CFBD play-by-play data is available."
            )
        if caveats:
            row_payload["scores"]["score_caveats"] = caveats

        ranked.append(row_payload)

    ranked.sort(key=lambda r: (-r["scores"]["rookie_alpha_0_100"], r["player_id"]))
    for i, row in enumerate(ranked, start=1):
        row["rookie_alpha_rank"] = i

    talent_sorted = sorted(ranked, key=lambda r: (-r["scores"]["talent_score_0_100"], r["player_id"]))
    talent_rank_map = {row["player_id"]: i for i, row in enumerate(talent_sorted, start=1)}
    for row in ranked:
        row["talent_rank"] = talent_rank_map[row["player_id"]]

    for row in ranked:
        row["draft_proxy_delta"] = row["talent_rank"] - row["rookie_alpha_rank"]

    payload = {
        "model": {
            "name": "tiber-rookie-alpha",
            "stage": "pre-draft",
            "label": "pre-draft v0",
            "model_version": "rookie-alpha-predraft-v0.4.0",
            "formula": {
                "ras_weight": 0.35,
                "production_weight": 0.45,
                "draft_capital_proxy_weight": 0.20,
                "age_at_entry_supported": False,
            },
        },
        "generated_at": generated_at,
        "run_id": run_id,
        "season": season,
        "coverage_summary": {
            "players_total": len(ranked),
            "players_with_any_missing_input": missing_any,
            "players_with_full_inputs": len(ranked) - missing_any,
            "players_with_context_fields": players_with_context,
            "input_alignment": {
                "duplicate_rows_skipped": merge_diagnostics.duplicate_rows_skipped,
                "identity_conflicts_skipped": merge_diagnostics.identity_conflicts_skipped,
                **merge_diagnostics.excluded_for_missing_sources,
            },
        },
        "source_files_used": [str(combine_path), str(production_path), str(draft_proxy_path)],
        "players": ranked,
    }
    if context_path is not None and context_path.exists():
        payload["source_files_used"].append(str(context_path))
    if positional_consensus_path is not None and positional_consensus_path.exists():
        payload["source_files_used"].append(str(positional_consensus_path))
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rookie_alpha_rank",
                "player_id",
                "player_name",
                "position",
                "ras_0_100",
                "athletic_score_0_100",
                "athletic_source",
                "production_0_100",
                "draft_capital_proxy_0_100",
                "talent_score_0_100",
                "rookie_alpha_0_100",
                "consensus_position_rank_blended",
                "consensus_score_positional_0_100",
                "consensus_delta_positional",
                "market_investment_delta_legacy",
                "talent_rank",
                "draft_proxy_delta",
                "model_inputs_missing",
                "market_conviction_ras_override",
                "wr_translation_penalty",
            ],
        )
        writer.writeheader()
        for row in ranked:
            writer.writerow(
                {
                    "rookie_alpha_rank": row["rookie_alpha_rank"],
                    "player_id": row["player_id"],
                    "player_name": row["player_name"],
                    "position": row["position"],
                    "ras_0_100": row["scores"]["ras_0_100"] or "",
                    "athletic_score_0_100": row["scores"]["athletic_score_0_100"] or "",
                    "athletic_source": row["scores"]["athletic_source"] or "",
                    "production_0_100": row["scores"]["production_0_100"],
                    "draft_capital_proxy_0_100": row["scores"]["draft_capital_proxy_0_100"],
                    "talent_score_0_100": row["scores"]["talent_score_0_100"],
                    "rookie_alpha_0_100": row["scores"]["rookie_alpha_0_100"],
                    "consensus_position_rank_blended": row["scores"].get("consensus_position_rank_blended") or "",
                    "consensus_score_positional_0_100": row["scores"].get("consensus_score_positional_0_100") or "",
                    "consensus_delta_positional": row["scores"].get("consensus_delta_positional") if row["scores"].get("consensus_delta_positional") is not None else "",
                    "market_investment_delta_legacy": row["scores"].get("market_investment_delta_legacy") or "",
                    "talent_rank": row["talent_rank"],
                    "draft_proxy_delta": row["draft_proxy_delta"],
                    "model_inputs_missing": ",".join(row["model_inputs_missing"]),
                    "market_conviction_ras_override": row["scores"].get("market_conviction_ras_override") or "",
                    "wr_translation_penalty": row["scores"].get("wr_translation_penalty") or "",
                }
            )

    input_files = [
        {
            "path": str(combine_path),
            "sha256": sha256_file(combine_path),
            "row_count": len(load_json(combine_path)),
        },
        {
            "path": str(production_path),
            "sha256": sha256_file(production_path),
            "row_count": len(load_json(production_path)),
        },
        {
            "path": str(draft_proxy_path),
            "sha256": sha256_file(draft_proxy_path),
            "row_count": len(load_json(draft_proxy_path)),
        },
    ]
    if context_path is not None and context_path.exists():
        input_files.append(
            {
                "path": str(context_path),
                "sha256": sha256_file(context_path),
                "row_count": len(load_json(context_path)),
            }
        )
    if positional_consensus_path is not None and positional_consensus_path.exists():
        pc_data = load_json(positional_consensus_path)
        entry_count = sum(
            len(s.get("entries", [])) for s in pc_data.get("sources", [])
        )
        input_files.append(
            {
                "path": str(positional_consensus_path),
                "sha256": sha256_file(positional_consensus_path),
                "row_count": entry_count,
            }
        )
    output_files = [
        {"path": str(output_json), "sha256": sha256_file(output_json)},
        {"path": str(output_csv), "sha256": sha256_file(output_csv)},
    ]
    manifest = {
        "season": season,
        "model_version": payload["model"]["model_version"],
        "generated_at": generated_at,
        "run_id": run_id,
        "input_files": input_files,
        "coverage_summary": payload["coverage_summary"],
        "output_files": output_files,
        "export_metadata": {},
    }
    exported_payload = load_json(output_json)
    manifest["export_metadata"] = {
        "season": exported_payload["season"],
        "model_version": exported_payload["model"]["model_version"],
        "generated_at": exported_payload["generated_at"],
        "run_id": exported_payload["run_id"],
        "coverage_summary": exported_payload["coverage_summary"],
        "source_files_used": exported_payload["source_files_used"],
    }
    expected_export_metadata = {
        "season": manifest["season"],
        "model_version": manifest["model_version"],
        "generated_at": manifest["generated_at"],
        "run_id": manifest["run_id"],
        "coverage_summary": manifest["coverage_summary"],
        "source_files_used": [entry["path"] for entry in manifest["input_files"]],
    }
    if manifest["export_metadata"] != expected_export_metadata:
        raise RuntimeError("Manifest export_metadata does not match top-level manifest metadata.")

    with output_manifest.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute standalone Rookie Alpha promoted export")
    parser.add_argument("--season", type=int, default=datetime.now(tz=timezone.utc).year)
    parser.add_argument(
        "--combine-input",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--production-input",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--draft-proxy-input",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output-manifest",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--context-input",
        type=Path,
        default=None,
        help="Optional deterministic prospect context artifact; additive export enrichment only.",
    )
    parser.add_argument(
        "--age-adjusted-input",
        type=Path,
        default=None,
        help=(
            "Optional age-adjusted production artifact (2026_age_adjusted_production.json). "
            "When provided, production scores are blended: "
            f"{AGE_ADJUSTED_BLEND_WEIGHT:.0%} age-adjusted + "
            f"{EXISTING_PRODUCTION_BLEND_WEIGHT:.0%} existing."
        ),
    )
    parser.add_argument(
        "--positional-consensus-input",
        type=Path,
        default=None,
        help=(
            "Optional positional consensus rankings artifact "
            "(e.g. data/processed/2026_positional_consensus.json). "
            "When provided, enables consensus_delta_positional and related fields. "
            "When absent, those fields are null. "
            "Defaults to data/processed/{season}_positional_consensus.json."
        ),
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    combine_input = args.combine_input or Path(f"data/raw/{args.season}_combine_results.json")
    production_input = args.production_input or Path(f"data/processed/{args.season}_college_production.json")
    draft_proxy_input = args.draft_proxy_input or Path(f"data/processed/{args.season}_draft_capital_proxy.json")
    output_json = args.output_json or Path(f"exports/promoted/rookie-alpha/{args.season}_rookie_alpha_predraft_v0.json")
    output_csv = args.output_csv or Path(f"exports/promoted/rookie-alpha/{args.season}_rookie_alpha_predraft_v0.csv")
    output_manifest = args.output_manifest or Path(f"exports/promoted/rookie-alpha/{args.season}_manifest.json")
    context_input = args.context_input or Path(f"data/processed/{args.season}_prospect_context.json")

    age_adjusted_input = args.age_adjusted_input or Path(
        f"data/processed/{args.season}_age_adjusted_production.json"
    )
    positional_consensus_input = args.positional_consensus_input or Path(
        f"data/processed/{args.season}_positional_consensus.json"
    )

    combine_rows = load_json(combine_input)
    production_rows = load_json(production_input)
    draft_rows = load_json(draft_proxy_input)
    if not isinstance(combine_rows, list):
        raise SystemExit(f"Expected list JSON in {combine_input}, got {type(combine_rows).__name__}")
    if not isinstance(production_rows, list):
        raise SystemExit(f"Expected list JSON in {production_input}, got {type(production_rows).__name__}")
    if not isinstance(draft_rows, list):
        raise SystemExit(f"Expected list JSON in {draft_proxy_input}, got {type(draft_rows).__name__}")

    # Load context early — needed for context-driven production adjustments
    context_by_id = load_context_by_player_id(context_input)

    if age_adjusted_input.exists():
        age_adjusted_rows = load_json(age_adjusted_input)
        if isinstance(age_adjusted_rows, list):
            production_rows = blend_production_rows(production_rows, age_adjusted_rows)
            logging.info(
                "Blended production scores from %s (%.0f%% age-adjusted, %.0f%% existing)",
                age_adjusted_input,
                AGE_ADJUSTED_BLEND_WEIGHT * 100,
                EXISTING_PRODUCTION_BLEND_WEIGHT * 100,
            )
            # Merge BOAR fields from age-adjusted output into context entries
            # so they flow through normalize_context_entry into the export.
            boar_fields = ("breakout_strength", "breakout_confidence",
                           "breakout_age_rating_0_100", "breakout_label")
            for row in age_adjusted_rows:
                pid = row.get("player_id", "")
                if pid and pid in context_by_id:
                    for field in boar_fields:
                        if row.get(field) is not None:
                            context_by_id[pid][field] = row[field]
        else:
            logging.warning("Age-adjusted input %s is not a list — skipping blend", age_adjusted_input)
    else:
        logging.warning("Age-adjusted input not found at %s — using unblended production scores", age_adjusted_input)

    production_rows = apply_context_production_adjustments(production_rows, context_by_id)

    # Extract WR translation penalties from the adjusted rows before merge strips them.
    wr_translation_penalty_by_id: dict[str, tuple[float, str]] = {
        row["player_id"]: (
            float(row["wr_translation_penalty"]),
            row.get("wr_translation_signals", ""),
        )
        for row in production_rows
        if row.get("wr_translation_penalty") is not None and row.get("player_id")
    }

    positional_consensus_by_id = load_positional_consensus(positional_consensus_input)

    players, merge_diagnostics, exceptional_combine_by_id = merge_inputs(
        combine_rows, production_rows, draft_rows, context_by_id=context_by_id,
    )
    write_outputs(
        players=players,
        merge_diagnostics=merge_diagnostics,
        season=args.season,
        combine_path=combine_input,
        production_path=production_input,
        draft_proxy_path=draft_proxy_input,
        output_json=output_json,
        output_csv=output_csv,
        output_manifest=output_manifest,
        context_path=context_input,
        context_by_id=context_by_id,
        exceptional_combine_by_id=exceptional_combine_by_id,
        wr_translation_penalty_by_id=wr_translation_penalty_by_id,
        positional_consensus_path=positional_consensus_input,
        positional_consensus_by_id=positional_consensus_by_id,
    )


if __name__ == "__main__":
    main()
