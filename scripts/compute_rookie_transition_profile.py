#!/usr/bin/env python3
"""Build the rookie_transition_profile_v0 governed evidence artifact.

Implements the design recorded in docs/rookie-transition-profile-v0-design.md
(issue #261). This script repackages already-computed values from other
promoted/processed artifacts under one provenance-backed contract. It does
not compute any new score, rank, or predictive value — every governed field
is either copied verbatim from an existing artifact or a deterministic
lookup (e.g. age from a recorded date of birth).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_rookie_transition_profile import (
    ARTIFACT_TYPE,
    CURRENT_SCHEMA_VERSION,
    SourceType,
    confidence_to_band,
)

DISCLAIMER = (
    "This artifact is an evidence consolidation layer. It contains no scores, no rankings, "
    "and no predictive claims. It is not Rookie Alpha and does not replace it. See "
    "docs/rookie-transition-profile-v0-design.md and docs/rookie-transition-profile-contract.md."
)

DEFAULT_ROOKIE_ALPHA_INPUT = Path("exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.json")
DEFAULT_DRAFT_CAPITAL_INPUT = Path("data/processed/{season}_draft_capital_proxy.json")
DEFAULT_PRODUCTION_INPUT = Path("data/processed/{season}_college_production.json")
DEFAULT_CONTEXT_INPUT = Path("data/processed/{season}_prospect_context.json")
DEFAULT_DRAFT_RESULTS_INPUT = Path("data/processed/{season}_draft_results.json")
DEFAULT_UDFA_RESULTS_INPUT = Path("data/processed/{season}_day3_udfa_draft_result_profiles.json")
DEFAULT_OUTPUT_DIR = Path("exports/candidate/rookie-transition-profile")

POSTDRAFT_OUTCOME_CONFIDENCE = 0.95


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def index_by_player_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["player_id"]: row for row in rows if isinstance(row, dict) and row.get("player_id")}


def age_from_dob(dob: str, season: int) -> int | None:
    """Exact age as of September 1 of the given season.

    Mirrors scripts/compute_breakout_age.py::age_from_dob exactly, so this
    artifact never re-derives age with different logic than the rest of the
    repo already uses.
    """
    try:
        born = date.fromisoformat(dob)
        season_start = date(season, 9, 1)
        return season_start.year - born.year - ((season_start.month, season_start.day) < (born.month, born.day))
    except (ValueError, TypeError):
        return None


def _unavailable_field(notes: str) -> dict[str, Any]:
    return {
        "value": None,
        "provenance": {
            "source_type": SourceType.UNAVAILABLE.value,
            "source_name": None,
            "source_url": None,
            "confidence": None,
            "confidence_band": None,
            "last_verified_at": None,
            "notes": notes,
        },
    }



# Mirrors the documented big_board_rank -> draft_capital_proxy_0_100 banding
# formula (docs/export-contract.md 2026 proxy rule): (low, high, score).
DRAFT_CAPITAL_RANK_BANDS: tuple[tuple[int, int, int], ...] = (
    (1, 10, 95),
    (11, 20, 85),
    (21, 32, 75),
    (33, 50, 65),
    (51, 75, 55),
    (76, 100, 45),
    (101, 150, 35),
    (151, None, 25),
)


def expected_band_score(big_board_rank: int | None) -> int | None:
    """The documented banding formula's score for a given rank, or None if no rank."""
    if big_board_rank is None:
        return None
    for low, high, score in DRAFT_CAPITAL_RANK_BANDS:
        if big_board_rank >= low and (high is None or big_board_rank <= high):
            return score
    return None


def build_draft_capital_field(
    alpha_scores: dict[str, Any],
    proxy_row: dict[str, Any] | None,
    *,
    as_of_date: str,
) -> dict[str, Any]:
    draft_capital_proxy_0_100 = alpha_scores.get("draft_capital_proxy_0_100")
    if draft_capital_proxy_0_100 is None:
        return _unavailable_field("No draft_capital_proxy_0_100 in the promoted Rookie Alpha export for this player.")

    big_board_rank = proxy_row.get("big_board_rank") if proxy_row else None
    if proxy_row is None:
        source_name = "compute_rookie_alpha.py draft_capital_proxy_0_100 (upstream big_board_rank row not found)"
    elif big_board_rank is not None and expected_band_score(big_board_rank) == draft_capital_proxy_0_100:
        # The row's own (big_board_rank, draft_capital_proxy_0_100) pair is
        # internally consistent with the documented banding formula, so it's
        # safe to describe the mapping — computed here rather than trusting
        # the upstream draft_capital_proxy_source free-text field verbatim,
        # since that field has been found to drift from the actual data
        # (leaked post-draft text, stale narrative estimates).
        source_name = (
            "Temporary pre-draft proxy mapped from seeded big_board_rank bands "
            "(1-10=95,11-20=85,21-32=75,33-50=65,51-75=55,76-100=45,101-150=35,151+=25)"
        )
    elif big_board_rank is None:
        source_name = (
            "Temporary pre-draft proxy score with no recorded big_board_rank on file (rank unknown); "
            "score reflects a manual pre-draft classification, not a specific big-board band mapping."
        )
    else:
        source_name = (
            f"Temporary pre-draft proxy score inconsistent with the documented big_board_rank band "
            f"mapping for rank {big_board_rank} (expected {expected_band_score(big_board_rank)}, got "
            f"{draft_capital_proxy_0_100}); exact derivation for this score is unavailable."
        )
    return {
        "value": {"big_board_rank": big_board_rank, "draft_capital_proxy_0_100": draft_capital_proxy_0_100},
        "provenance": {
            "source_type": SourceType.MARKET_DERIVED_PROXY.value,
            "source_name": source_name,
            "source_url": None,
            "confidence": 0.65,
            "confidence_band": confidence_to_band(0.65),
            "last_verified_at": as_of_date,
            "notes": (
                "Temporary pre-draft market-investment proxy. Not equivalent to realized NFL "
                "draft capital — see docs/export-contract.md 2026 proxy rule."
            ),
        },
    }


def build_age_field(context_row: dict[str, Any] | None, *, season: int, as_of_date: str) -> dict[str, Any]:
    dob = context_row.get("dob") if context_row else None
    if not dob:
        return _unavailable_field("No recorded date of birth in prospect context data for this player.")

    age = age_from_dob(dob, season)
    if age is None:
        return _unavailable_field(f"Recorded dob {dob!r} could not be parsed as YYYY-MM-DD.")

    return {
        "value": age,
        "provenance": {
            "source_type": SourceType.MEASURED_IDENTITY_FACT.value,
            "source_name": f"dob from data/processed/{season}_prospect_context.json",
            "source_url": None,
            "confidence": 0.9,
            "confidence_band": confidence_to_band(0.9),
            "last_verified_at": as_of_date,
            "notes": "Computed via age_from_dob(dob, season): exact age as of September 1 of the season.",
        },
    }


def build_athletic_testing_field(alpha_scores: dict[str, Any], *, as_of_date: str) -> dict[str, Any]:
    athletic_source = alpha_scores.get("athletic_source")
    if athletic_source is None or athletic_source == "NEUTRAL_DEFAULT":
        # NEUTRAL_DEFAULT is Rookie Alpha's internal scoring placeholder (a fixed
        # 50.0) for players with no usable RAS/SPORQ data. It is not a
        # measurement and would misrepresent absence of evidence as evidence,
        # so it is intentionally treated as unavailable here rather than copied.
        return _unavailable_field(
            "No usable RAS/SPORQ combine data. Rookie Alpha uses a neutral default score "
            "(NEUTRAL_DEFAULT) internally for scoring purposes only; that placeholder is not "
            "evidence and is intentionally omitted from this artifact."
        )

    return {
        "value": {
            "athletic_score_0_100": alpha_scores.get("athletic_score_0_100"),
            "athletic_source": athletic_source,
        },
        "provenance": {
            "source_type": SourceType.MEASURED_COMBINE.value,
            "source_name": "RAS/SPORQ blend per scripts/compute_rookie_alpha.py",
            "source_url": None,
            "confidence": alpha_scores.get("athletic_confidence"),
            "confidence_band": confidence_to_band(alpha_scores.get("athletic_confidence") or 0.0),
            "last_verified_at": as_of_date,
            "notes": (
                (alpha_scores.get("athletic_explainer") or "")
                + " Caveat: this is an in-house composite, not the Kent Lee Platte RAS percentile "
                "the field name may suggest — see docs/athletic-score-normalization-audit.md."
            ).strip(),
        },
    }


def build_college_production_field(
    alpha_scores: dict[str, Any],
    production_row: dict[str, Any] | None,
    *,
    as_of_date: str,
) -> dict[str, Any]:
    production_0_100 = alpha_scores.get("production_0_100")
    if production_0_100 is None:
        return _unavailable_field("No production_0_100 in the promoted Rookie Alpha export for this player.")

    source_name = (
        production_row.get("production_score_source")
        if production_row and production_row.get("production_score_source")
        else "compute_rookie_alpha.py production_0_100 (upstream college-production row not found)"
    )
    return {
        "value": {"production_score_0_100": production_0_100},
        "provenance": {
            "source_type": SourceType.MEASURED_PRODUCTION_STATS.value,
            "source_name": source_name,
            "source_url": None,
            "confidence": 0.85,
            "confidence_band": confidence_to_band(0.85),
            "last_verified_at": as_of_date,
            "notes": None,
        },
    }


def _postdraft_outcome_from_row(
    row: dict[str, Any], *, default_source_name: str, last_verified_at: str, notes: str | None = None
) -> dict[str, Any]:
    """Build the {value, provenance} pair from a verified source row.

    Derives status/is_udfa/round/pick from the row's own fields rather than
    assuming "drafted" — a source row may itself record a udfa_signed (or
    other non-drafted) outcome, and that must be preserved, not overwritten.
    """
    status = row.get("draft_result_status") or ("udfa_signed" if row.get("is_udfa") else "drafted")
    is_udfa = bool(row.get("is_udfa"))
    return {
        "value": {
            "status": status,
            "nfl_team": row.get("nfl_team"),
            "draft_round": row.get("draft_round") if status == "drafted" else None,
            "overall_pick": row.get("overall_pick") if status == "drafted" else None,
            "is_udfa": is_udfa,
            "source_status": row.get("source_status"),
            "upstream_provenance_status": row.get("upstream_provenance_status"),
        },
        "provenance": {
            "source_type": SourceType.OFFICIAL_DRAFT_RESULT.value,
            "source_name": row.get("source_name") or row.get("source_note") or default_source_name,
            "source_url": row.get("source_url"),
            "confidence": POSTDRAFT_OUTCOME_CONFIDENCE,
            "confidence_band": confidence_to_band(POSTDRAFT_OUTCOME_CONFIDENCE),
            "last_verified_at": last_verified_at,
            "notes": notes,
        },
    }


def build_official_postdraft_outcome_field(
    draft_result_row: dict[str, Any] | None,
    udfa_row: dict[str, Any] | None,
    *,
    as_of_date: str,
) -> dict[str, Any]:
    """Observed post-draft outcome, kept entirely separate from draft_capital.

    Checks data/processed/{season}_draft_results.json first, then
    data/processed/{season}_day3_udfa_draft_result_profiles.json, per the
    #267 design decision. draft_capital (the pre-draft proxy) is never
    touched by this function or overwritten with these values.
    """
    if draft_result_row is not None and draft_result_row.get("source_status") == "external_verified":
        return _postdraft_outcome_from_row(
            draft_result_row,
            default_source_name="data/processed draft_results.json",
            last_verified_at=draft_result_row.get("ingested_at") or as_of_date,
        )

    if udfa_row is not None and udfa_row.get("source_status") == "external_verified":
        return _postdraft_outcome_from_row(
            udfa_row,
            default_source_name="data/processed day3_udfa_draft_result_profiles.json",
            last_verified_at=as_of_date,
            notes=(
                "last_verified_at reflects this artifact's generation date, not a per-row source "
                "verification timestamp — data/processed/{season}_day3_udfa_draft_result_profiles.json "
                "does not record one."
            ),
        )

    return _unavailable_field(
        "No verified post-draft outcome found in either data/processed/{season}_draft_results.json "
        "or data/processed/{season}_day3_udfa_draft_result_profiles.json for this player."
    )


def build_rows(
    *,
    season: int,
    alpha_players: list[dict[str, Any]],
    draft_capital_by_id: dict[str, dict[str, Any]],
    production_by_id: dict[str, dict[str, Any]],
    context_by_id: dict[str, dict[str, Any]],
    draft_results_by_id: dict[str, dict[str, Any]],
    udfa_results_by_id: dict[str, dict[str, Any]],
    as_of_date: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for player in alpha_players:
        player_id = player["player_id"]
        alpha_scores = player.get("scores", {})
        alpha_context = player.get("context") or {}
        proxy_row = draft_capital_by_id.get(player_id)
        production_row = production_by_id.get(player_id)
        context_row = context_by_id.get(player_id)
        draft_result_row = draft_results_by_id.get(player_id)
        udfa_row = udfa_results_by_id.get(player_id)

        school = (
            alpha_context.get("school")
            or (proxy_row or {}).get("school")
            or (production_row or {}).get("school")
            or (context_row or {}).get("school")
        )
        class_year = (
            alpha_context.get("class_year")
            or (proxy_row or {}).get("class_year")
            or (production_row or {}).get("class_year")
            or (context_row or {}).get("class_year")
            or season
        )

        rows.append(
            {
                "player_id": player_id,
                "player_name": player["player_name"],
                "position": player["position"],
                "school": school,
                "class_year": class_year,
                "draft_capital": build_draft_capital_field(alpha_scores, proxy_row, as_of_date=as_of_date),
                "age_at_entry": build_age_field(context_row, season=season, as_of_date=as_of_date),
                "athletic_testing": build_athletic_testing_field(alpha_scores, as_of_date=as_of_date),
                "college_production": build_college_production_field(
                    alpha_scores, production_row, as_of_date=as_of_date
                ),
                "official_postdraft_outcome": build_official_postdraft_outcome_field(
                    draft_result_row, udfa_row, as_of_date=as_of_date
                ),
            }
        )
    return rows


def build_coverage_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    def has_value(row: dict[str, Any], family: str) -> bool:
        return row[family]["value"] is not None

    return {
        "players_total": len(rows),
        "players_with_draft_capital": sum(1 for row in rows if has_value(row, "draft_capital")),
        "players_with_age_at_entry": sum(1 for row in rows if has_value(row, "age_at_entry")),
        "players_with_athletic_testing": sum(1 for row in rows if has_value(row, "athletic_testing")),
        "players_with_college_production": sum(1 for row in rows if has_value(row, "college_production")),
        "players_with_official_postdraft_outcome": sum(
            1 for row in rows if has_value(row, "official_postdraft_outcome")
        ),
        "players_with_all_families": sum(
            1
            for row in rows
            if all(
                has_value(row, family)
                for family in (
                    "draft_capital",
                    "age_at_entry",
                    "athletic_testing",
                    "college_production",
                    "official_postdraft_outcome",
                )
            )
        ),
    }


def flatten_row_for_csv(row: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {
        "player_id": row["player_id"],
        "player_name": row["player_name"],
        "position": row["position"],
        "school": row["school"],
        "class_year": row["class_year"],
    }
    for family in (
        "draft_capital",
        "age_at_entry",
        "athletic_testing",
        "college_production",
        "official_postdraft_outcome",
    ):
        field = row[family]
        value = field["value"]
        if isinstance(value, dict):
            for key, val in value.items():
                flat[f"{family}.value.{key}"] = val
        else:
            flat[f"{family}.value"] = value
        for key, val in field["provenance"].items():
            flat[f"{family}.provenance.{key}"] = val
    return flat


CSV_FIELD_ORDER = [
    "player_id",
    "player_name",
    "position",
    "school",
    "class_year",
    "draft_capital.value",
    "draft_capital.value.big_board_rank",
    "draft_capital.value.draft_capital_proxy_0_100",
    "draft_capital.provenance.source_type",
    "draft_capital.provenance.source_name",
    "draft_capital.provenance.source_url",
    "draft_capital.provenance.confidence",
    "draft_capital.provenance.confidence_band",
    "draft_capital.provenance.last_verified_at",
    "draft_capital.provenance.notes",
    "age_at_entry.value",
    "age_at_entry.provenance.source_type",
    "age_at_entry.provenance.source_name",
    "age_at_entry.provenance.source_url",
    "age_at_entry.provenance.confidence",
    "age_at_entry.provenance.confidence_band",
    "age_at_entry.provenance.last_verified_at",
    "age_at_entry.provenance.notes",
    "athletic_testing.value",
    "athletic_testing.value.athletic_score_0_100",
    "athletic_testing.value.athletic_source",
    "athletic_testing.provenance.source_type",
    "athletic_testing.provenance.source_name",
    "athletic_testing.provenance.source_url",
    "athletic_testing.provenance.confidence",
    "athletic_testing.provenance.confidence_band",
    "athletic_testing.provenance.last_verified_at",
    "athletic_testing.provenance.notes",
    "college_production.value",
    "college_production.value.production_score_0_100",
    "college_production.provenance.source_type",
    "college_production.provenance.source_name",
    "college_production.provenance.source_url",
    "college_production.provenance.confidence",
    "college_production.provenance.confidence_band",
    "college_production.provenance.last_verified_at",
    "college_production.provenance.notes",
    "official_postdraft_outcome.value",
    "official_postdraft_outcome.value.status",
    "official_postdraft_outcome.value.nfl_team",
    "official_postdraft_outcome.value.draft_round",
    "official_postdraft_outcome.value.overall_pick",
    "official_postdraft_outcome.value.is_udfa",
    "official_postdraft_outcome.value.source_status",
    "official_postdraft_outcome.value.upstream_provenance_status",
    "official_postdraft_outcome.provenance.source_type",
    "official_postdraft_outcome.provenance.source_name",
    "official_postdraft_outcome.provenance.source_url",
    "official_postdraft_outcome.provenance.confidence",
    "official_postdraft_outcome.provenance.confidence_band",
    "official_postdraft_outcome.provenance.last_verified_at",
    "official_postdraft_outcome.provenance.notes",
]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELD_ORDER)
        writer.writeheader()
        for row in rows:
            writer.writerow(flatten_row_for_csv(row))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the rookie_transition_profile_v0 governed artifact")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--rookie-alpha-input", type=Path, default=None)
    parser.add_argument("--draft-capital-input", type=Path, default=None)
    parser.add_argument("--production-input", type=Path, default=None)
    parser.add_argument("--context-input", type=Path, default=None)
    parser.add_argument("--draft-results-input", type=Path, default=None)
    parser.add_argument("--udfa-results-input", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--generated-at",
        type=str,
        default=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        help="Optional deterministic timestamp override for tests/repro runs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    season = args.season
    rookie_alpha_input = args.rookie_alpha_input or Path(
        str(DEFAULT_ROOKIE_ALPHA_INPUT).format(season=season)
    )
    draft_capital_input = args.draft_capital_input or Path(str(DEFAULT_DRAFT_CAPITAL_INPUT).format(season=season))
    production_input = args.production_input or Path(str(DEFAULT_PRODUCTION_INPUT).format(season=season))
    context_input = args.context_input or Path(str(DEFAULT_CONTEXT_INPUT).format(season=season))
    draft_results_input = args.draft_results_input or Path(str(DEFAULT_DRAFT_RESULTS_INPUT).format(season=season))
    udfa_results_input = args.udfa_results_input or Path(str(DEFAULT_UDFA_RESULTS_INPUT).format(season=season))

    alpha_export = load_json(rookie_alpha_input)
    alpha_players = alpha_export["players"]
    draft_capital_by_id = index_by_player_id(load_json(draft_capital_input))
    production_by_id = index_by_player_id(load_json(production_input))
    context_by_id = index_by_player_id(load_json(context_input))
    draft_results_by_id = index_by_player_id(load_json(draft_results_input))
    udfa_results_by_id = index_by_player_id(load_json(udfa_results_input))

    as_of_date = args.generated_at[:10]
    rows = build_rows(
        season=season,
        alpha_players=alpha_players,
        draft_capital_by_id=draft_capital_by_id,
        production_by_id=production_by_id,
        context_by_id=context_by_id,
        draft_results_by_id=draft_results_by_id,
        udfa_results_by_id=udfa_results_by_id,
        as_of_date=as_of_date,
    )

    run_id = f"rookie-transition-profile-{season}-{args.generated_at}"
    source_files_used = [
        str(rookie_alpha_input),
        str(draft_capital_input),
        str(production_input),
        str(context_input),
        str(draft_results_input),
        str(udfa_results_input),
    ]

    artifact = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": ARTIFACT_TYPE,
        "season": season,
        "generated_at": args.generated_at,
        "run_id": run_id,
        "disclaimer": DISCLAIMER,
        "source_files_used": source_files_used,
        "coverage_summary": build_coverage_summary(rows),
        "rows": rows,
    }

    output_json = args.output_dir / f"{season}_rookie_transition_profile_v0.json"
    output_csv = args.output_dir / f"{season}_rookie_transition_profile_v0.csv"
    output_manifest = args.output_dir / f"{season}_manifest.json"

    write_json(output_json, artifact)
    write_csv(output_csv, rows)

    input_files = []
    for path, rows_payload in (
        (rookie_alpha_input, None),
        (draft_capital_input, load_json(draft_capital_input)),
        (production_input, load_json(production_input)),
        (context_input, load_json(context_input)),
        (draft_results_input, load_json(draft_results_input)),
        (udfa_results_input, load_json(udfa_results_input)),
    ):
        entry: dict[str, Any] = {"path": str(path), "sha256": sha256_file(path)}
        if isinstance(rows_payload, list):
            entry["row_count"] = len(rows_payload)
        input_files.append(entry)

    export_metadata = {
        "season": season,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "generated_at": args.generated_at,
        "run_id": run_id,
        "coverage_summary": artifact["coverage_summary"],
        "source_files_used": source_files_used,
    }
    manifest = {
        "season": season,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "generated_at": args.generated_at,
        "run_id": run_id,
        "input_files": input_files,
        "coverage_summary": artifact["coverage_summary"],
        "output_files": [
            {"path": str(output_json), "sha256": sha256_file(output_json)},
            {"path": str(output_csv), "sha256": sha256_file(output_csv)},
        ],
        "export_metadata": export_metadata,
    }
    write_json(output_manifest, manifest)

    print(f"Wrote rookie transition profile artifact: {output_json}")
    print(f"Wrote rookie transition profile manifest: {output_manifest}")


if __name__ == "__main__":
    main()
