#!/usr/bin/env python3
"""Compute deterministic historical rookie comps (producer-only scaffold, v0)."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_ROOKIE_FIELDS = {"player_id", "player_name", "position", "scores"}
REQUIRED_HISTORICAL_FEATURE_FIELDS = {
    "player_id",
    "player_name",
    "position",
    "school",
    "draft_year",
    "source_season",
    "ras_0_100",
    "production_0_100",
    "draft_capital_proxy_0_100",
    "normalization_scope",
}
REQUIRED_HISTORICAL_OUTCOME_FIELDS = {
    "player_id",
    "player_name",
    "position",
    "draft_year",
    "career_outcome_label",
    "best_season_fantasy_ppg",
    "top_finish_band",
    "years_1_to_3_summary",
}

TALENT_WEIGHTS = {
    "ras_0_100": 0.45,
    "production_0_100": 0.45,
    "size_context_0_100": 0.10,
}
MARKET_WEIGHTS = {
    "ras_0_100": 0.35,
    "production_0_100": 0.35,
    "size_context_0_100": 0.10,
    "draft_capital_proxy_0_100": 0.20,
}
PRODUCTION_SCOPE_COMPATIBLE: frozenset[str] = frozenset()
WR_POPULATION_SCOPE = "historical-wr-cfbd-season-pop-v1"
WR_POPULATION_MIN_ROWS = 100
WR_REFERENCE_POPULATION_DIR = Path("data/historical/wr_reference_populations")
REQUIRED_WR_REFERENCE_POPULATION_FIELDS = {
    "player_name",
    "position",
    "source_season",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "source_name",
    "source_url",
}


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc.msg} (line {exc.lineno}, column {exc.colno})") from exc


def coerce_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_required_fields(rows: list[dict[str, Any]], required_fields: set[str], dataset_name: str) -> None:
    for i, row in enumerate(rows, start=1):
        missing = [field for field in sorted(required_fields) if field not in row]
        if missing:
            raise SystemExit(f"{dataset_name} row {i} missing required fields: {missing}")


def normalize_historical_feature_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validate_required_fields(rows, REQUIRED_HISTORICAL_FEATURE_FIELDS, "historical features")
    normalized: list[dict[str, Any]] = []
    for row in rows:
        production_value = coerce_float_or_none(row.get("production_0_100"))
        opt_out_season_flag = bool(row.get("opt_out_season_flag", False))
        if opt_out_season_flag:
            # Treat opt-out years as unavailable production context so distance math does not
            # penalize the profile as a literal zero-production season.
            production_value = None

        normalized_row = (
            {
                "player_id": str(row["player_id"]),
                "player_name": str(row["player_name"]),
                "position": str(row["position"]),
                "school": row.get("school"),
                "draft_year": row.get("draft_year"),
                "source_season": row.get("source_season"),
                "ras_0_100": coerce_float_or_none(row.get("ras_0_100")),
                "production_0_100": production_value,
                "draft_capital_proxy_0_100": coerce_float_or_none(row.get("draft_capital_proxy_0_100")),
                "size_context_0_100": coerce_float_or_none(row.get("size_context_0_100")),
                "source_name": row.get("source_name"),
                "source_url": row.get("source_url"),
                "normalization_scope": row.get("normalization_scope"),
                "opt_out_season_flag": opt_out_season_flag,
                "receptions": row.get("receptions"),
                "receiving_yards": row.get("receiving_yards"),
                "receiving_tds": row.get("receiving_tds"),
                "production_0_100_legacy": coerce_float_or_none(row.get("production_0_100_legacy")),
                "notes": row.get("notes"),
            }
        )
        normalized.append(normalized_row)
    return normalized


def _to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _zscore(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((item - mean) ** 2 for item in values) / len(values)
    if math.isclose(variance, 0.0):
        return 0.0
    std_dev = variance**0.5
    return (value - mean) / std_dev


def _load_wr_reference_populations(population_dir: Path) -> dict[int, list[dict[str, float]]]:
    if not population_dir.exists():
        return {}

    populations_by_season: dict[int, list[dict[str, float]]] = {}
    for path in sorted(population_dir.glob("*_wr_receiving_population.json")):
        payload = load_json(path)
        if not isinstance(payload, list):
            raise SystemExit(f"WR reference population file must be a JSON array: {path}")

        season_population: list[dict[str, float]] = []
        for i, row in enumerate(payload, start=1):
            if not isinstance(row, dict):
                raise SystemExit(f"WR reference population row {i} in {path} must be an object")
            missing = [field for field in sorted(REQUIRED_WR_REFERENCE_POPULATION_FIELDS) if field not in row]
            if missing:
                raise SystemExit(f"WR reference population row {i} in {path} missing required fields: {missing}")
            if str(row.get("position")) != "WR":
                continue

            source_season = _to_int_or_none(row.get("source_season"))
            receptions = _to_int_or_none(row.get("receptions"))
            receiving_yards = _to_int_or_none(row.get("receiving_yards"))
            receiving_tds = _to_int_or_none(row.get("receiving_tds"))
            source_name = str(row.get("source_name") or "").strip()
            source_url = str(row.get("source_url") or "").strip()
            if source_season is None or receptions is None or receiving_yards is None or receiving_tds is None:
                continue
            if not source_name or not source_url:
                continue
            if receptions < 20:
                continue

            season_population.append(
                {
                    "yards_per_reception": receiving_yards / receptions,
                    "td_rate": receiving_tds / receptions,
                    "total_yards": float(receiving_yards),
                }
            )
            populations_by_season.setdefault(source_season, [])

        season_from_name = _to_int_or_none(path.name.split("_", 1)[0])
        if season_from_name is None:
            continue
        populations_by_season[season_from_name] = season_population

    valid_populations = {
        season: rows for season, rows in populations_by_season.items() if len(rows) >= WR_POPULATION_MIN_ROWS
    }
    return valid_populations


def apply_wr_historical_production_methodology(
    historical_features: list[dict[str, Any]],
    *,
    wr_reference_populations: dict[int, list[dict[str, float]]] | None = None,
) -> tuple[list[dict[str, Any]], frozenset[str]]:
    wr_rows = [row for row in historical_features if row.get("position") == "WR"]
    scored_rows: list[dict[str, Any]] = []
    metrics_population: list[dict[str, float]] = []
    has_valid_reference_population = bool(wr_reference_populations)

    for row in wr_rows:
        receptions = _to_int_or_none(row.get("receptions"))
        receiving_yards = _to_int_or_none(row.get("receiving_yards"))
        receiving_tds = _to_int_or_none(row.get("receiving_tds"))
        opt_out_season_flag = bool(row.get("opt_out_season_flag", False))
        notes_text = str(row.get("notes") or "").lower()
        partial_season_flag = "partial season" in notes_text

        if row.get("production_0_100_legacy") is None:
            row["production_0_100_legacy"] = row.get("production_0_100")
        row["normalization_scope"] = "historical-wr-cfbd-method-v1-null"
        row["production_0_100"] = None

        if (
            opt_out_season_flag
            or partial_season_flag
            or receptions is None
            or receiving_yards is None
            or receiving_tds is None
            or receptions < 20
        ):
            scored_rows.append(row)
            continue

        yards_per_reception = receiving_yards / receptions
        td_rate = receiving_tds / receptions
        total_yards = float(receiving_yards)
        row["_wr_metrics"] = {
            "yards_per_reception": yards_per_reception,
            "td_rate": td_rate,
            "total_yards": total_yards,
        }
        metrics_population.append(row["_wr_metrics"])
        scored_rows.append(row)

    fallback_ypr_values = [row["yards_per_reception"] for row in metrics_population]
    fallback_td_rate_values = [row["td_rate"] for row in metrics_population]
    fallback_total_yards_values = [row["total_yards"] for row in metrics_population]

    for row in scored_rows:
        metrics = row.get("_wr_metrics")
        if not isinstance(metrics, dict):
            continue

        source_season = _to_int_or_none(row.get("source_season"))
        season_population = (
            wr_reference_populations.get(source_season, [])
            if has_valid_reference_population and source_season is not None
            else []
        )
        if season_population:
            row["normalization_scope"] = WR_POPULATION_SCOPE
            ypr_values = [entry["yards_per_reception"] for entry in season_population]
            td_rate_values = [entry["td_rate"] for entry in season_population]
            total_yards_values = [entry["total_yards"] for entry in season_population]
        else:
            ypr_values = fallback_ypr_values
            td_rate_values = fallback_td_rate_values
            total_yards_values = fallback_total_yards_values

        ypr_z = _zscore(metrics["yards_per_reception"], ypr_values)
        total_yards_z = _zscore(metrics["total_yards"], total_yards_values)
        td_rate_z = _zscore(metrics["td_rate"], td_rate_values)
        composite_z = (0.40 * ypr_z) + (0.35 * total_yards_z) + (0.25 * td_rate_z)
        score = max(0.0, min(100.0, round(50.0 + (composite_z * 15.0), 1)))
        row["production_0_100"] = score
        if row.get("normalization_scope") != WR_POPULATION_SCOPE:
            row["normalization_scope"] = "historical-wr-cfbd-method-v1"
        del row["_wr_metrics"]

    compatible_scopes = (
        frozenset({WR_POPULATION_SCOPE}) if any(row.get("normalization_scope") == WR_POPULATION_SCOPE for row in wr_rows) else PRODUCTION_SCOPE_COMPATIBLE
    )
    return historical_features, compatible_scopes


def normalize_outcome_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    validate_required_fields(rows, REQUIRED_HISTORICAL_OUTCOME_FIELDS, "historical outcomes")
    normalized: dict[str, dict[str, Any]] = {}
    for row in rows:
        pid = str(row["player_id"])
        normalized[pid] = {
            "player_id": pid,
            "player_name": str(row["player_name"]),
            "position": str(row["position"]),
            "draft_year": row.get("draft_year"),
            "career_outcome_label": row.get("career_outcome_label"),
            "best_season_fantasy_ppg": coerce_float_or_none(row.get("best_season_fantasy_ppg")),
            "top_finish_band": row.get("top_finish_band"),
            "years_1_to_3_summary": row.get("years_1_to_3_summary"),
            "source_name": row.get("source_name"),
            "source_url": row.get("source_url"),
        }
    return normalized


def load_rookies(rookie_export_path: Path) -> tuple[int, list[dict[str, Any]]]:
    payload = load_json(rookie_export_path)
    if not isinstance(payload, dict):
        raise SystemExit("Rookie export must be a JSON object.")
    for field in sorted(REQUIRED_ROOKIE_FIELDS):
        if field not in payload and field != "scores":
            continue
    season = payload.get("season")
    players = payload.get("players")
    if not isinstance(players, list):
        raise SystemExit("Rookie export must include players list.")

    rookies: list[dict[str, Any]] = []
    for i, row in enumerate(players, start=1):
        missing = [field for field in sorted(REQUIRED_ROOKIE_FIELDS) if field not in row]
        if missing:
            raise SystemExit(f"rookie export player row {i} missing required fields: {missing}")
        scores = row["scores"]
        if not isinstance(scores, dict):
            raise SystemExit(f"rookie export player row {i} scores must be an object")
        rookies.append(
            {
                "player_id": str(row["player_id"]),
                "player_name": str(row["player_name"]),
                "position": str(row["position"]),
                "ras_0_100": coerce_float_or_none(scores.get("ras_0_100")),
                "production_0_100": coerce_float_or_none(scores.get("production_0_100")),
                "draft_capital_proxy_0_100": coerce_float_or_none(scores.get("draft_capital_proxy_0_100")),
                "size_context_0_100": coerce_float_or_none(scores.get("size_context_0_100")),
            }
        )
    if not isinstance(season, int):
        raise SystemExit("Rookie export season must be an integer.")
    return season, rookies


def weighted_distance(
    rookie_row: dict[str, Any], historical_row: dict[str, Any], weights: dict[str, float]
) -> tuple[float, list[str]]:
    squared_sum = 0.0
    used_weight = 0.0
    effective_features_used: list[str] = []
    for feature, weight in weights.items():
        rookie_value = coerce_float_or_none(rookie_row.get(feature))
        historical_value = coerce_float_or_none(historical_row.get(feature))
        if rookie_value is None or historical_value is None:
            continue
        diff = (rookie_value - historical_value) / 100.0
        squared_sum += weight * (diff * diff)
        used_weight += weight
        effective_features_used.append(feature)

    if used_weight == 0.0:
        return float("inf"), []
    return (squared_sum / used_weight) ** 0.5, effective_features_used


def similarity_score(distance: float) -> float:
    if distance == float("inf"):
        return 0.0
    return round(max(0.0, 100.0 - (distance * 100.0)), 4)


def build_comp_candidates(
    rookie_row: dict[str, Any],
    historical_rows: list[dict[str, Any]],
    outcomes_by_player_id: dict[str, dict[str, Any]],
    *,
    comp_mode: str,
    top_n: int,
) -> list[dict[str, Any]]:
    weights = TALENT_WEIGHTS if comp_mode == "talent_comp" else MARKET_WEIGHTS
    position_matches = [row for row in historical_rows if row["position"] == rookie_row["position"]]

    ranked: list[tuple[float, str, dict[str, Any], list[str]]] = []
    for historical_row in position_matches:
        distance, effective_features_used = weighted_distance(rookie_row, historical_row, weights)
        if distance == float("inf"):
            continue
        if rookie_row["position"] == "WR" and len(effective_features_used) < 2:
            continue
        ranked.append((distance, historical_row["player_id"], historical_row, effective_features_used))

    ranked.sort(key=lambda item: (item[0], item[1]))
    output: list[dict[str, Any]] = []
    for distance, _, row, effective_features_used in ranked[:top_n]:
        outcome = outcomes_by_player_id.get(row["player_id"])
        feature_snapshot = {
            "ras_0_100": row.get("ras_0_100"),
            "production_0_100": row.get("production_0_100"),
            "draft_capital_proxy_0_100": row.get("draft_capital_proxy_0_100"),
            "size_context_0_100": row.get("size_context_0_100"),
            "normalization_scope": row.get("normalization_scope"),
            "opt_out_season_flag": bool(row.get("opt_out_season_flag", False)),
        }
        if row.get("position") == "WR":
            feature_snapshot.update(
                {
                    "production_0_100_legacy": row.get("production_0_100_legacy"),
                    "receptions": row.get("receptions"),
                    "receiving_yards": row.get("receiving_yards"),
                    "receiving_tds": row.get("receiving_tds"),
                }
            )

        output.append(
            {
                "historical_player_id": row["player_id"],
                "player_name": row["player_name"],
                "draft_year": row.get("draft_year"),
                "position": row["position"],
                "similarity_score": similarity_score(distance),
                "distance": round(distance, 6),
                "feature_snapshot": feature_snapshot,
                "effective_features_used": effective_features_used,
                "outcome_snapshot": None
                if outcome is None
                else {
                    "career_outcome_label": outcome.get("career_outcome_label"),
                    "best_season_fantasy_ppg": outcome.get("best_season_fantasy_ppg"),
                    "top_finish_band": outcome.get("top_finish_band"),
                    "years_1_to_3_summary": outcome.get("years_1_to_3_summary"),
                },
            }
        )
    return output




def build_ui_display_allowed(
    players: list[dict[str, Any]],
    comp_data_warnings: dict[str, Any],
    methodology_compatible_by_position: dict[str, bool],
) -> dict[str, bool]:
    """Emit conservative per-position UI gating for downstream consumers."""
    ui_display_allowed: dict[str, bool] = {}
    positions = sorted({str(player.get("position")) for player in players if player.get("position") is not None})

    for position in positions:
        has_warning = False
        if isinstance(comp_data_warnings, dict) and position in comp_data_warnings:
            warning_value = comp_data_warnings.get(position)
            has_warning = bool(warning_value)

        position_players = [player for player in players if player.get("position") == position]
        position_comps = [comp for player in position_players for comp in player.get("comps", [])]

        has_min_features = bool(position_comps) and all(
            len(comp.get("effective_features_used", [])) >= 2 for comp in position_comps
        )
        has_outcome_labels = bool(position_comps) and all(
            (comp.get("outcome_snapshot") or {}).get("career_outcome_label") is not None
            for comp in position_comps
        )
        has_non_market_dimension = bool(position_comps) and all(
            bool({"ras_0_100", "size_context_0_100"}.intersection(comp.get("effective_features_used", [])))
            for comp in position_comps
        )
        is_methodology_compatible = bool(methodology_compatible_by_position.get(position))

        ui_display_allowed[position] = (
            (not has_warning)
            and has_min_features
            and has_outcome_labels
            and has_non_market_dimension
            and is_methodology_compatible
        )

    return ui_display_allowed


def build_methodology_compatible_by_position(
    positions: set[str], historical_features: list[dict[str, Any]], production_scope_compatible: frozenset[str] = PRODUCTION_SCOPE_COMPATIBLE
) -> dict[str, bool]:
    output: dict[str, bool] = {}
    for position in sorted(positions):
        position_rows = [row for row in historical_features if row.get("position") == position]
        output[position] = bool(position_rows) and all(
            row.get("normalization_scope") in production_scope_compatible for row in position_rows
        )
    return output


def build_similarity_quality_by_position(
    players: list[dict[str, Any]],
    comp_data_warnings: dict[str, Any],
    methodology_compatible_by_position: dict[str, bool],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    positions = sorted({str(player.get("position")) for player in players if player.get("position") is not None})
    for position in positions:
        position_players = [player for player in players if player.get("position") == position]
        position_comps = [comp for player in position_players for comp in player.get("comps", [])]
        requirements_checked = {
            "no_lane_warning": not (isinstance(comp_data_warnings, dict) and bool(comp_data_warnings.get(position))),
            "min_effective_feature_count_met": bool(position_comps)
            and all(len(comp.get("effective_features_used", [])) >= 2 for comp in position_comps),
            "outcomes_present": bool(position_comps)
            and all((comp.get("outcome_snapshot") or {}).get("career_outcome_label") is not None for comp in position_comps),
            "non_market_dimension_present": bool(position_comps)
            and all(
                bool({"ras_0_100", "size_context_0_100"}.intersection(comp.get("effective_features_used", [])))
                for comp in position_comps
            ),
            "methodology_compatible": bool(methodology_compatible_by_position.get(position)),
        }

        if all(requirements_checked.values()):
            status = "ui_safe"
        elif (not requirements_checked["no_lane_warning"]) or (not requirements_checked["methodology_compatible"]):
            status = "directional_only"
        else:
            status = "partial"

        failed = [f"{name}: false" for name, is_true in requirements_checked.items() if not is_true]
        reason = "; ".join(failed) if failed else "all_checks_passed"
        if position == "WR":
            reason = (
                "metric methodology matches; population scope incompatible "
                "(in-repo WR cohort fallback vs. full CFBD season population); lane warning present"
            )
        output[position] = {
            "status": status,
            "reason": reason,
            "requirements_checked": requirements_checked,
        }
    return output
def compute_historical_comps(
    season: int,
    rookies: list[dict[str, Any]],
    historical_features: list[dict[str, Any]],
    outcomes_by_player_id: dict[str, dict[str, Any]],
    *,
    comp_mode: str,
    top_n: int,
    source_files_used: list[str],
    generated_at: str,
    production_scope_compatible: frozenset[str] = PRODUCTION_SCOPE_COMPATIBLE,
) -> dict[str, Any]:
    if comp_mode not in {"talent_comp", "market_comp"}:
        raise SystemExit(f"Unsupported comp mode: {comp_mode}")

    players = []
    for rookie in sorted(rookies, key=lambda row: row["player_id"]):
        players.append(
            {
                "player_id": rookie["player_id"],
                "player_name": rookie["player_name"],
                "position": rookie["position"],
                "comp_mode": comp_mode,
                "comps": build_comp_candidates(
                    rookie,
                    historical_features,
                    outcomes_by_player_id,
                    comp_mode=comp_mode,
                    top_n=top_n,
                ),
            }
        )

    wr_top_1_counter: Counter[str] = Counter()
    for player in players:
        if player["position"] != "WR" or not player["comps"]:
            continue
        wr_top_1_counter[player["comps"][0]["player_name"]] += 1
    wr_max_top_1 = max(wr_top_1_counter.values(), default=0)

    warnings = {}
    if wr_max_top_1 > 3:
        # Known v0 behavior: even with added 2021/2022 WR rows, the promoted 2026 rookie WR
        # feature cluster can still collapse to one nearest neighbor when RAS/size coverage is
        # sparse or class-local normalization compresses variance across cohorts. Keep warning
        # explicit rather than forcing synthetic differentiation in historical rows.
        warnings["WR"] = (
            "WR lane remains insufficiently differentiated for UI use: at least one historical WR is the #1 comp for "
            f"{wr_max_top_1} prospects (>3 threshold). Similarities remain directional only."
        )
    else:
        warnings["WR"] = (
            "WR lane is still partial and directional; do not surface in UI until broader cross-class and outcomes "
            "coverage is added."
        )

    positions = {str(player.get("position")) for player in players if player.get("position") is not None}
    methodology_compatible_by_position = build_methodology_compatible_by_position(
        positions,
        historical_features,
        production_scope_compatible,
    )
    similarity_quality_by_position = build_similarity_quality_by_position(
        players,
        warnings,
        methodology_compatible_by_position,
    )
    methodology_compatibility_by_position = {
        position: bool(quality.get("requirements_checked", {}).get("methodology_compatible"))
        for position, quality in similarity_quality_by_position.items()
    }
    ui_display_allowed = build_ui_display_allowed(players, warnings, methodology_compatible_by_position)

    return {
        "model": {
            "name": "historical_comps",
            "model_version": "v0",
            "comp_mode": comp_mode,
            "distance_model": "weighted_euclidean",
            "weights": TALENT_WEIGHTS if comp_mode == "talent_comp" else MARKET_WEIGHTS,
            "notes": "v0 emits talent_comp by default; market_comp support is scaffolded and optional.",
        },
        "generated_at": generated_at,
        "season": season,
        "source_files_used": source_files_used,
        "comp_data_warnings": warnings,
        "similarity_quality_by_position": similarity_quality_by_position,
        "methodology_compatibility_by_position": methodology_compatibility_by_position,
        "ui_display_allowed": ui_display_allowed,
        "players": players,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute deterministic historical comps for promoted rookies")
    parser.add_argument(
        "--rookie-export",
        type=Path,
        default=Path("exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json"),
    )
    parser.add_argument(
        "--historical-features",
        type=Path,
        default=Path("data/historical/historical_prospect_features.sample.json"),
    )
    parser.add_argument(
        "--historical-outcomes",
        type=Path,
        default=Path("data/historical/historical_player_outcomes.sample.json"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("exports/promoted/historical-comps/2026_historical_comps_v0.json"),
    )
    parser.add_argument("--comp-mode", choices=["talent_comp", "market_comp"], default="talent_comp")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument(
        "--generated-at",
        type=str,
        default=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        help="Optional deterministic timestamp override for tests/repro runs.",
    )
    parser.add_argument(
        "--allow-missing-outcomes",
        action="store_true",
        help="Allow missing outcomes file and emit comps without outcome snapshots.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    season, rookies = load_rookies(args.rookie_export)

    historical_features_payload = load_json(args.historical_features)
    if not isinstance(historical_features_payload, list):
        raise SystemExit("Historical features payload must be a JSON array.")
    historical_features = normalize_historical_feature_rows(historical_features_payload)
    wr_reference_populations = _load_wr_reference_populations(WR_REFERENCE_POPULATION_DIR)
    historical_features, production_scope_compatible = apply_wr_historical_production_methodology(
        historical_features,
        wr_reference_populations=wr_reference_populations,
    )

    outcomes_by_player_id: dict[str, dict[str, Any]] = {}
    source_files_used = [str(args.rookie_export), str(args.historical_features)]

    if args.historical_outcomes.exists():
        outcomes_payload = load_json(args.historical_outcomes)
        if not isinstance(outcomes_payload, list):
            raise SystemExit("Historical outcomes payload must be a JSON array.")
        outcomes_by_player_id = normalize_outcome_rows(outcomes_payload)
        source_files_used.append(str(args.historical_outcomes))
    elif not args.allow_missing_outcomes:
        raise SystemExit(
            f"Historical outcomes file not found: {args.historical_outcomes}. "
            "Use --allow-missing-outcomes to continue without outcomes."
        )

    artifact = compute_historical_comps(
        season=season,
        rookies=rookies,
        historical_features=historical_features,
        outcomes_by_player_id=outcomes_by_player_id,
        comp_mode=args.comp_mode,
        top_n=args.top_n,
        source_files_used=source_files_used,
        generated_at=args.generated_at,
        production_scope_compatible=production_scope_compatible,
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(f"{json.dumps(artifact, indent=2)}\n", encoding="utf-8")
    print(f"Wrote historical comps artifact: {args.output_json}")


if __name__ == "__main__":
    main()
