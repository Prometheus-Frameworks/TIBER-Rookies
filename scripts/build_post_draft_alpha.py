#!/usr/bin/env python3
"""Build the 2026 post-draft Rookie Alpha adjustment artifact.

v0 doctrine:
- pre-draft alpha remains frozen
- post-draft alpha is deterministic translator logic from Round 1 / Day 2 profiles
- every non-zero delta is reason-code explainable
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROW_FIELDS = [
    "player_id",
    "player_name",
    "position",
    "pre_draft_alpha",
    "post_draft_alpha",
    "post_draft_delta",
    "delta_reason_codes",
    "draft_round",
    "draft_pick",
    "team",
    "talent_confirmation_signal",
    "opportunity_insulation_signal",
    "short_term_fantasy_runway",
    "translator_tags",
    "remaining_risks",
    "source_profile",
    "source_status",
]

TALENT_STRENGTH = {"uncertain": 0.0, "mixed": 0.3, "moderate": 0.5, "strong": 0.75, "elite": 1.0}
OPPORTUNITY_STRENGTH = {"uncertain": 0.0, "limited": 0.35, "moderate": 0.6, "strong": 0.8, "elite": 1.0}


def normalize_player_id(value: str) -> str:
    base = value.lower().strip()
    return base[:-5] if base.endswith("_2026") else base


def clamp(n: float, low: float, high: float) -> float:
    return max(low, min(high, n))


def band_score(low: float, high: float, factor: float) -> float:
    return low + (high - low) * factor


@dataclass
class DeltaPart:
    points: float
    reason: str


def compute_adjustment_parts(profile: dict[str, Any], source_profile: str) -> list[DeltaPart]:
    tags = set(profile.get("translator_tags", []))
    talent_signal = profile.get("talent_confirmation_signal", "uncertain")
    opportunity_signal = profile.get("opportunity_insulation_signal", "uncertain")

    talent_factor = TALENT_STRENGTH.get(talent_signal, 0.0)
    opp_factor = OPPORTUNITY_STRENGTH.get(opportunity_signal, 0.0)

    parts: list[DeltaPart] = []

    def add_band(tag: str, low: float, high: float, factor: float, prefix: str) -> None:
        if tag in tags:
            points = round(band_score(low, high, factor), 1)
            parts.append(DeltaPart(points=points, reason=f"{prefix}:{tag}"))

    if source_profile == "round1":
        add_band("top5_skill_capital", 6.0, 8.0, talent_factor, "talent_confirmation")
        add_band("top10_skill_capital", 4.0, 6.0, talent_factor, "talent_confirmation")
        add_band("round1_wr_capital", 3.0, 5.0, talent_factor, "talent_confirmation")
        add_band("late_round1_wr_capital", 2.0, 3.0, talent_factor, "talent_confirmation")
        add_band("round1_market_confirmation", 2.0, 3.0, talent_factor, "talent_confirmation")
        add_band("model_wr1_validation", 2.0, 3.0, talent_factor, "talent_confirmation")
        add_band("fifth_year_option_signal", 0.8, 1.5, talent_factor, "talent_confirmation")
        add_band("round1_rb_capital", 5.0, 7.0, talent_factor, "talent_confirmation")
        add_band("round1_te_capital", 3.0, 5.0, talent_factor, "talent_confirmation")
        add_band("round1_qb_capital", 3.0, 5.0, talent_factor, "talent_confirmation")
        add_band("trade_up_conviction", 1.0, 2.0, talent_factor, "talent_confirmation")
        add_band("elite_developmental_environment", 1.0, 3.0, opp_factor, "opportunity_insulation")
        add_band("delayed_start_insulation", 0.8, 1.5, opp_factor, "opportunity_insulation")

        if "class_inflation_adjustment_candidate" in tags:
            parts.append(DeltaPart(points=-1.0, reason="talent_confirmation:class_inflation_adjustment"))

    if source_profile == "day2":
        has_predraft_edge = profile.get("pre_draft_tiber_stance") not in (None, "")
        if "near_round1_skill_capital" in tags and has_predraft_edge:
            add_band("near_round1_skill_capital", 7.0, 10.0, talent_factor, "talent_confirmation")

        add_band("early_day2_capital", 4.0, 6.0, talent_factor, "talent_confirmation")
        add_band("round2_skill_capital", 3.0, 5.0, talent_factor, "talent_confirmation")
        add_band("round3_skill_capital", 1.0, 3.0, talent_factor, "talent_confirmation")
        add_band("round3_qb_capital", 1.0, 2.0, talent_factor, "talent_confirmation")
        add_band("day2_te_cluster", 1.0, 2.0, talent_factor, "talent_confirmation")
        add_band("scarce_day2_rb_capital", 2.0, 4.0, talent_factor, "talent_confirmation")

    # Opportunity insulation adjustment is intentionally separated from talent confirmation.
    if source_profile in {"round1", "day2"}:
        opportunity_points = round(1.5 * opp_factor, 1)
        if opportunity_points > 0:
            parts.append(DeltaPart(points=opportunity_points, reason="opportunity_insulation:signal_bonus"))

    # Risk modifiers
    if "target_room_competition_watch" in tags:
        parts.append(DeltaPart(points=round(-1.0 - 2.0 * (1 - opp_factor), 1), reason="risk:target_room_competition_watch"))
    if "year1_volume_uncertainty" in tags:
        parts.append(DeltaPart(points=-1.5, reason="risk:year1_volume_uncertainty"))
    if "delayed_te_translation_watch" in tags:
        parts.append(DeltaPart(points=-1.0, reason="risk:delayed_te_translation_watch"))
    if "developmental_qb_capital" in tags:
        parts.append(DeltaPart(points=-0.8, reason="risk:developmental_qb_capital"))
    if "landing_spot_volatility" in tags:
        parts.append(DeltaPart(points=-1.0, reason="risk:landing_spot_volatility"))
    if "delayed_start_insulation" in tags:
        parts.append(DeltaPart(points=-0.6, reason="risk:delayed_start_timeline"))

    return parts


def apply_opportunity_caps(delta: float, tags: set[str]) -> float:
    if "delayed_start_insulation" in tags:
        delta = min(delta, 6.0)
    if "landing_spot_volatility" in tags:
        delta = min(delta, 6.0)
    if "developmental_qb_capital" in tags:
        delta = min(delta, 2.0)
    if "delayed_te_translation_watch" in tags:
        delta = min(delta, 3.0)
    if "opportunity_insulation_limited" in tags:
        return clamp(delta, -3.0, 4.0)
    if "opportunity_insulation_moderate" in tags:
        return clamp(delta, -3.0, 7.0)
    if "opportunity_insulation_strong" in tags:
        return clamp(delta, -3.0, 9.0)
    if "opportunity_insulation_elite" in tags or "elite_opportunity_insulation" in tags:
        return clamp(delta, -3.0, 11.0)
    return clamp(delta, -3.0, 8.0)


def load_predraft_alpha(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for player in payload.get("players", []):
        key = normalize_player_id(player["player_id"])
        by_id[key] = player
        by_name[player["player_name"].strip().lower()] = player
    return by_id, by_name


def build_row(
    profile: dict[str, Any],
    source_profile: str,
    predraft: dict[str, Any],
    has_predraft_baseline: bool,
) -> dict[str, Any]:
    pre = round(float(predraft["scores"]["rookie_alpha_0_100"]), 1)
    tags = list(profile.get("translator_tags", []))
    tag_set = set(tags)
    parts = compute_adjustment_parts(profile, source_profile) if has_predraft_baseline else []
    raw_delta = round(sum(part.points for part in parts), 1)

    capped_delta = round(apply_opportunity_caps(raw_delta, tag_set), 1)
    reason_codes = [part.reason for part in parts if part.points != 0]
    if capped_delta != raw_delta:
        reason_codes.append("risk:opportunity_insulation_cap")

    post = round(clamp(pre + capped_delta, 0.0, 100.0), 1)
    actual_delta = round(post - pre, 1)

    if actual_delta != 0 and not reason_codes:
        raise ValueError(f"Non-zero delta for {profile.get('player_name')} missing reason codes")

    return {
        "player_id": predraft["player_id"],
        "player_name": profile["player_name"],
        "position": profile["position"],
        "pre_draft_alpha": pre,
        "post_draft_alpha": post,
        "post_draft_delta": actual_delta,
        "delta_reason_codes": reason_codes,
        "draft_round": 1 if source_profile == "round1" else profile.get("round"),
        "draft_pick": profile.get("pick"),
        "team": profile.get("team", ""),
        "talent_confirmation_signal": profile.get("talent_confirmation_signal", ""),
        "opportunity_insulation_signal": profile.get("opportunity_insulation_signal", ""),
        "short_term_fantasy_runway": profile.get("short_term_fantasy_runway", ""),
        "translator_tags": tags,
        "remaining_risks": profile.get("primary_risks", []),
        "source_profile": source_profile,
        "source_status": profile.get("source_status", "operator_seeded"),
    }


def build_post_draft_rows(predraft_path: Path, round1_path: Path, day2_path: Path) -> list[dict[str, Any]]:
    predraft_by_id, predraft_by_name = load_predraft_alpha(predraft_path)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def resolve_predraft_player(profile: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        normalized = normalize_player_id(profile["player_id"])
        candidate = predraft_by_id.get(normalized)
        if candidate is not None:
            return candidate, True

        by_name = predraft_by_name.get(profile["player_name"].strip().lower())
        if by_name is not None:
            return by_name, True

        fallback_player = {
            "player_id": profile["player_id"],
            "player_name": profile["player_name"],
            "position": profile["position"],
            "scores": {"rookie_alpha_0_100": 0.0},
        }
        return fallback_player, False

    for source_profile, path in (("round1", round1_path), ("day2", day2_path)):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for profile in payload:
            player, has_predraft_baseline = resolve_predraft_player(profile)
            if player["player_id"] in seen:
                continue
            row = build_row(profile, source_profile, player, has_predraft_baseline)
            if not has_predraft_baseline:
                row["delta_reason_codes"] = ["baseline:predraft_missing_pass_through"]
            rows.append(row)
            seen.add(player["player_id"])

    rows.sort(key=lambda r: (-(r["post_draft_alpha"]), r["player_name"]))
    return rows


def build_missing_baseline_rows(
    rows: list[dict[str, Any]],
    *,
    reason: str = "predraft_baseline_not_found",
) -> list[dict[str, Any]]:
    missing_rows: list[dict[str, Any]] = []
    for row in rows:
        if "baseline:predraft_missing_pass_through" not in row["delta_reason_codes"]:
            continue
        missing_rows.append(
            {
                "player_id": row["player_id"],
                "player_name": row["player_name"],
                "position": row["position"],
                "draft_round": row["draft_round"],
                "draft_pick": row["draft_pick"],
                "team": row["team"],
                "source_profile": row["source_profile"],
                "source_status": row.get("source_status", "operator_seeded"),
                "translator_tags": row.get("translator_tags", []),
                "reason": reason,
            }
        )
    return sorted(missing_rows, key=lambda r: (r["draft_round"] or 99, r["draft_pick"] or 999, r["player_name"]))


def write_outputs(
    rows: list[dict[str, Any]],
    output_json: Path,
    output_csv: Path,
    output_missing_baselines: Path | None = None,
) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": "rookie-alpha-postdraft-v0",
        "season": 2026,
        "doctrine": {
            "pre_draft_alpha_frozen": True,
            "translator_adjustments_only": True,
            "deterministic_logic": True,
            "coverage_behavior": "Only Round 1 and Day 2 profile players are emitted in post-draft v0.",
        },
        "rows": rows,
    }
    output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS)
        writer.writeheader()
        for row in rows:
            csv_row = {
                **row,
                "delta_reason_codes": "|".join(row["delta_reason_codes"]),
                "translator_tags": "|".join(row["translator_tags"]),
                "remaining_risks": "|".join(row["remaining_risks"]),
            }
            writer.writerow(csv_row)

    if output_missing_baselines is not None:
        output_missing_baselines.parent.mkdir(parents=True, exist_ok=True)
        missing_rows = build_missing_baseline_rows(rows)
        output_missing_baselines.write_text(json.dumps(missing_rows, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build 2026 post-draft Rookie Alpha artifact")
    parser.add_argument(
        "--predraft-path",
        type=Path,
        default=Path("exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json"),
    )
    parser.add_argument(
        "--round1-path",
        type=Path,
        default=Path("data/processed/2026_round1_draft_signal_profiles.json"),
    )
    parser.add_argument(
        "--day2-path",
        type=Path,
        default=Path("data/processed/2026_day2_draft_signal_profiles.json"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_v0.json"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_v0.csv"),
    )
    parser.add_argument(
        "--output-missing-baselines",
        type=Path,
        default=Path("exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_missing_baselines_v0.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_post_draft_rows(args.predraft_path, args.round1_path, args.day2_path)
    write_outputs(rows, args.output_json, args.output_csv, args.output_missing_baselines)
    print(
        f"Wrote {len(rows)} rows to {args.output_json} and {args.output_csv}; "
        f"missing-baseline report: {args.output_missing_baselines}"
    )


if __name__ == "__main__":
    main()
