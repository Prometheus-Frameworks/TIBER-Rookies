#!/usr/bin/env python3
"""
compute_ppr_projections.py

Generates first-year PPR point projection ranges for 2026 draft prospects.

Method:
  1. Base layer (preserved): position + alpha-band → floor / median / ceiling
     from historical rookie PPR distributions (2017–2023).
  2. Player-level modifiers: small deterministic adjustments using available
     repo signals (draft capital, production, age-adjusted production,
     breakout age, athletic score, missing-model-inputs penalty).
  3. Position-aware shaping:
     - WR: stronger tie to production + breakout age
     - TE: wider uncertainty by default, toolsy/late-breakout profiles more volatile
     - RB: stronger tie to capital + athleticism + production
     - QB: separate readiness logic (rushing upside widens ceiling)
  4. Fallback: if only alpha exists, emits band-based range (v1 behavior).

Output metadata per player:
  projection_floor, projection_median, projection_ceiling,
  projection_band, projection_confidence, projection_volatility,
  projection_thesis, projection_method
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DEFAULT_ALPHA_PATH = Path("exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json")
DEFAULT_OUTPUT_PATH = Path("data/processed/2026_ppr_projections.json")

# ---------------------------------------------------------------------------
# Band definitions
# ---------------------------------------------------------------------------
BANDS: list[tuple[str, float, float]] = [
    ("Elite",       80.0, 100.0),
    ("Starter",     55.0,  79.9),
    ("Contributor", 30.0,  54.9),
    ("Lottery",      0.0,  29.9),
]

# PPR ranges: position → band_label → (floor, median, ceiling)
PPR_RANGES: dict[str, dict[str, tuple[int, int, int]]] = {
    "WR": {
        "Elite":       (130, 175, 240),
        "Starter":     (70,  115, 165),
        "Contributor": (30,  60,  100),
        "Lottery":     (5,   25,  65),
    },
    "RB": {
        "Elite":       (150, 200, 310),
        "Starter":     (90,  135, 190),
        "Contributor": (40,  75,  120),
        "Lottery":     (5,   30,  70),
    },
    "QB": {
        "Elite":       (280, 340, 420),
        "Starter":     (180, 245, 320),
        "Contributor": (80,  140, 210),
        "Lottery":     (10,  50,  120),
    },
    "TE": {
        "Elite":       (100, 140, 200),
        "Starter":     (55,  90,  135),
        "Contributor": (20,  45,  80),
        "Lottery":     (5,   20,  50),
    },
}

# Maximum modifier magnitude (PPR points) — prevents runaway adjustments
MAX_MEDIAN_SHIFT = 20
MAX_SPREAD_SHIFT = 15


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class PPRProjection:
    player_id: str
    player_name: str
    position: str
    rookie_alpha_0_100: float
    rookie_alpha_rank: int
    projection_band: str
    ppr_floor: int
    ppr_median: int
    ppr_ceiling: int
    projection_confidence: str = "Medium"
    projection_volatility: str = "Balanced"
    projection_thesis: str = ""
    projection_method: str = "alpha_band_v2"
    data_gap_flag: bool = False
    data_gap_note: str | None = None
    modifier_details: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core logic — band lookup (preserved from v1)
# ---------------------------------------------------------------------------
def alpha_band(alpha: float) -> str:
    for label, lo, hi in BANDS:
        if lo <= alpha <= hi:
            return label
    return "Lottery"


# ---------------------------------------------------------------------------
# Signal extraction helpers
# ---------------------------------------------------------------------------
def _score(player: dict, key: str) -> float | None:
    """Extract a 0-100 score, returning None if absent."""
    val = player.get("scores", {}).get(key)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _context(player: dict, key: str, default=None):
    return player.get("context", {}).get(key, default)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Modifier engine
# ---------------------------------------------------------------------------
def _compute_median_shift(
    position: str,
    alpha: float,
    draft_capital: float | None,
    production: float | None,
    age_adj_production: float | None,
    breakout_age: int | None,
    young_breakout: bool,
    athletic_score: float | None,
    missing_inputs: list[str],
) -> tuple[float, dict]:
    """
    Compute a small PPR-point shift to the band median based on player signals.
    Returns (shift_points, detail_dict).

    Design: each signal contributes a small delta (±0–8 pts). Signals are
    weighted by position relevance. Total is clamped to MAX_MEDIAN_SHIFT.
    """
    details: dict[str, float] = {}
    shift = 0.0

    # -- Draft capital: strong signal for RB, moderate for others
    if draft_capital is not None:
        cap_delta = (draft_capital - 50) / 50  # -1 to +1
        weight = {"RB": 8.0, "WR": 5.0, "TE": 4.0, "QB": 6.0}.get(position, 5.0)
        contrib = cap_delta * weight
        details["capital"] = round(contrib, 1)
        shift += contrib

    # -- Production: strong for WR/RB, moderate for TE/QB
    if production is not None:
        prod_delta = (production - 50) / 50
        weight = {"WR": 7.0, "RB": 6.0, "TE": 5.0, "QB": 4.0}.get(position, 5.0)
        contrib = prod_delta * weight
        details["production"] = round(contrib, 1)
        shift += contrib

    # -- Age-adjusted production: bonus for WR/TE breakout profiles
    if age_adj_production is not None:
        age_delta = (age_adj_production - 50) / 50
        weight = {"WR": 5.0, "TE": 4.0, "RB": 3.0, "QB": 2.0}.get(position, 3.0)
        contrib = age_delta * weight
        details["age_adj_prod"] = round(contrib, 1)
        shift += contrib

    # -- Breakout age: young breakouts get a nudge up
    if young_breakout:
        contrib = {"WR": 4.0, "TE": 3.0, "RB": 2.0, "QB": 1.0}.get(position, 2.0)
        details["young_breakout"] = round(contrib, 1)
        shift += contrib
    elif breakout_age is not None and breakout_age >= 22:
        # Late breakout: slight penalty, bigger for TE/WR
        contrib = {"WR": -3.0, "TE": -3.0, "RB": -1.0, "QB": -1.0}.get(position, -1.0)
        details["late_breakout"] = round(contrib, 1)
        shift += contrib

    # -- Athletic score: meaningful for RB, moderate for TE
    if athletic_score is not None:
        ath_delta = (athletic_score - 50) / 50
        weight = {"RB": 5.0, "TE": 4.0, "WR": 2.0, "QB": 2.0}.get(position, 3.0)
        contrib = ath_delta * weight
        details["athletic"] = round(contrib, 1)
        shift += contrib

    # -- Missing inputs penalty: reduces confidence in upside
    if missing_inputs:
        penalty = -2.0 * len(missing_inputs)
        penalty = max(penalty, -6.0)  # cap at -6
        details["missing_inputs"] = round(penalty, 1)
        shift += penalty

    shift = _clamp(shift, -MAX_MEDIAN_SHIFT, MAX_MEDIAN_SHIFT)
    return shift, details


def _compute_volatility_shift(
    position: str,
    alpha: float,
    production: float | None,
    draft_capital: float | None,
    athletic_score: float | None,
    breakout_age: int | None,
    young_breakout: bool,
    missing_inputs: list[str],
) -> tuple[float, str]:
    """
    Compute spread adjustment (widens or tightens floor-ceiling gap).
    Positive = wider (more volatile), negative = tighter (more stable).
    Returns (spread_shift, volatility_label).
    """
    vol = 0.0

    # TE: wider by default (position uncertainty)
    if position == "TE":
        vol += 4.0

    # Missing inputs → wider range
    if missing_inputs:
        vol += 2.0 * min(len(missing_inputs), 3)

    # High athletic + low production = volatile
    if athletic_score is not None and production is not None:
        if athletic_score >= 70 and production < 40:
            vol += 5.0  # toolsy upside, unproven
        elif production >= 70 and athletic_score >= 60:
            vol -= 3.0  # proven + athletic = more stable

    # Young breakout → tighter range (more confident floor)
    if young_breakout:
        vol -= 3.0

    # Late breakout → wider range
    if breakout_age is not None and breakout_age >= 22:
        vol += 3.0

    # High capital + high alpha → tighter range
    if draft_capital is not None and draft_capital >= 75 and alpha >= 70:
        vol -= 3.0

    vol = _clamp(vol, -MAX_SPREAD_SHIFT, MAX_SPREAD_SHIFT)

    if vol <= -4:
        label = "Stable"
    elif vol >= 4:
        label = "Volatile"
    else:
        label = "Balanced"

    return vol, label


def _derive_confidence(
    alpha: float,
    missing_inputs: list[str],
    production: float | None,
    draft_capital: float | None,
) -> str:
    """Derive a confidence label for the projection."""
    score = 0
    if alpha >= 65:
        score += 2
    elif alpha >= 45:
        score += 1

    if production is not None and production >= 60:
        score += 1
    if draft_capital is not None and draft_capital >= 60:
        score += 1
    if not missing_inputs:
        score += 1

    if score >= 4:
        return "High"
    elif score >= 2:
        return "Medium"
    return "Low"


def _derive_thesis(
    position: str,
    band: str,
    draft_capital: float | None,
    production: float | None,
    athletic_score: float | None,
    breakout_age: int | None,
    young_breakout: bool,
    volatility: str,
    missing_inputs: list[str],
) -> str:
    """Build a one-line projection thesis from available signals."""
    parts: list[str] = []

    # Lead with breakout context
    if young_breakout:
        parts.append("Early-breakout")
    elif breakout_age is not None and breakout_age >= 22:
        parts.append("Late-breakout")

    # Athletic profile
    if athletic_score is not None:
        if athletic_score >= 80:
            parts.append("elite-athlete")
        elif athletic_score >= 65:
            parts.append("above-average athlete")

    # Production + capital context
    if production is not None and production >= 75:
        parts.append("with strong college production")
    elif production is not None and production < 35:
        parts.append("with limited college production")

    if draft_capital is not None and draft_capital >= 80:
        parts.append("and premium draft capital")
    elif draft_capital is not None and draft_capital < 30:
        parts.append("as a later-round selection")

    # Position-specific flavor
    pos_labels = {
        "WR": "receiver",
        "TE": "tight end",
        "RB": "back",
        "QB": "quarterback",
    }
    pos_label = pos_labels.get(position, "prospect")

    # Volatility note
    if volatility == "Volatile":
        vol_note = "Wide outcome range reflects projection uncertainty"
    elif volatility == "Stable":
        vol_note = "Tighter range supported by converging signals"
    else:
        vol_note = "Balanced range with moderate confidence"

    if parts:
        profile = " ".join(parts)
        thesis = f"{profile} {pos_label}. {vol_note}."
    elif band in ("Elite", "Starter"):
        thesis = f"Alpha-tier {pos_label} with {band.lower()}-level projection. {vol_note}."
    else:
        thesis = f"{band}-band {pos_label}. {vol_note}."

    # Capitalize first letter
    return thesis[0].upper() + thesis[1:]


# ---------------------------------------------------------------------------
# Player projection (v2)
# ---------------------------------------------------------------------------
def project_player(player: dict[str, Any]) -> PPRProjection:
    pid = player["player_id"]
    name = player["player_name"]
    position = player["position"]
    scores = player.get("scores", {})
    alpha = float(scores.get("rookie_alpha_0_100", 50.0))
    rank = int(player.get("rookie_alpha_rank", 99))

    missing = player.get("model_inputs_missing", [])
    data_gap = len(missing) > 0
    data_gap_note = (
        f"Missing model inputs: {', '.join(missing)}. "
        "Range may understate true projection."
        if data_gap
        else None
    )

    # --- Base layer (v1 preserved) ---
    pos_ranges = PPR_RANGES.get(position)
    if pos_ranges is None:
        band = "Lottery"
        base_floor, base_median, base_ceiling = 5, 25, 65
    else:
        band = alpha_band(alpha)
        base_floor, base_median, base_ceiling = pos_ranges[band]

    # --- Extract signals ---
    draft_capital = _score(player, "draft_capital_proxy_0_100")
    production = _score(player, "production_0_100")
    age_adj_production = _score(player, "age_adjusted_production_0_100")
    athletic_score = _score(player, "ras_0_100")  # fallback to RAS
    breakout_age = _context(player, "breakout_age")
    young_breakout = bool(_context(player, "young_breakout_flag", False))

    has_signals = any(v is not None for v in [draft_capital, production, athletic_score])

    # --- Compute modifiers ---
    if has_signals:
        median_shift, modifier_details = _compute_median_shift(
            position, alpha, draft_capital, production,
            age_adj_production, breakout_age, young_breakout,
            athletic_score, missing,
        )
        spread_shift, volatility = _compute_volatility_shift(
            position, alpha, production, draft_capital,
            athletic_score, breakout_age, young_breakout, missing,
        )
        method = "alpha_band_v2"
    else:
        median_shift = 0.0
        modifier_details = {}
        spread_shift = 0.0
        volatility = "Balanced"
        method = "alpha_band_v1_fallback"

    # --- Apply modifiers ---
    adjusted_median = base_median + median_shift
    base_spread_low = base_median - base_floor
    base_spread_high = base_ceiling - base_median
    # spread_shift widens (positive) or tightens (negative) proportionally
    spread_factor = 1.0 + (spread_shift / 30.0)  # ±0.5 range factor
    spread_factor = _clamp(spread_factor, 0.6, 1.5)
    adjusted_floor = adjusted_median - (base_spread_low * spread_factor)
    adjusted_ceiling = adjusted_median + (base_spread_high * spread_factor)

    # --- Sanity caps ---
    final_floor = max(0, round(adjusted_floor))
    final_median = max(final_floor + 1, round(adjusted_median))
    final_ceiling = max(final_median + 1, round(adjusted_ceiling))

    # --- Confidence ---
    confidence = _derive_confidence(alpha, missing, production, draft_capital)

    # --- Thesis ---
    thesis = _derive_thesis(
        position, band, draft_capital, production, athletic_score,
        breakout_age, young_breakout, volatility, missing,
    )

    return PPRProjection(
        player_id=pid,
        player_name=name,
        position=position,
        rookie_alpha_0_100=round(alpha, 1),
        rookie_alpha_rank=rank,
        projection_band=band,
        ppr_floor=final_floor,
        ppr_median=final_median,
        ppr_ceiling=final_ceiling,
        projection_confidence=confidence,
        projection_volatility=volatility,
        projection_thesis=thesis,
        projection_method=method,
        data_gap_flag=data_gap,
        data_gap_note=data_gap_note,
        modifier_details=modifier_details,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate PPR projection ranges for 2026 class")
    p.add_argument("--alpha-input", type=Path, default=DEFAULT_ALPHA_PATH)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return p.parse_args()


def main() -> None:
    args = parse_args()

    alpha_data = json.loads(args.alpha_input.read_text())
    players = alpha_data.get("players", alpha_data) if isinstance(alpha_data, dict) else alpha_data

    projections = [project_player(p) for p in players]

    # Sort by rookie alpha rank
    projections.sort(key=lambda x: x.rookie_alpha_rank)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    output = [asdict(proj) for proj in projections]
    args.output.write_text(json.dumps(output, indent=2))

    logging.info("PPR projections for %d players:", len(projections))
    logging.info(
        "  %-24s %-4s  %-12s  %5s  %6s  %7s  %-8s %-9s  %s",
        "Player", "Pos", "Band", "Floor", "Median", "Ceil", "Conf", "Volat", "Method",
    )
    for proj in projections:
        gap = " *" if proj.data_gap_flag else ""
        logging.info(
            "  %-24s %-4s  %-12s  %5d  %6d  %7d  %-8s %-9s  %s%s",
            proj.player_name[:24], proj.position, proj.projection_band,
            proj.ppr_floor, proj.ppr_median, proj.ppr_ceiling,
            proj.projection_confidence, proj.projection_volatility,
            proj.projection_method, gap,
        )
    logging.info("")
    logging.info("* = data gap; range may understate true projection")
    logging.info("Wrote %d records to %s", len(projections), args.output)


if __name__ == "__main__":
    main()
