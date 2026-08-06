#!/usr/bin/env python3
"""Validate the issue #285 archived fixtures and candidate corrections.

This validator is intentionally candidate-scoped.  It never mutates seed or
promoted artifacts and it does not imply promotion authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path("data/candidate/2023_input_integrity/v0.1.0/manifest.json")
DEFAULT_ARCHIVE = Path("data/fixtures/archived/2023_input_integrity/contaminated_seed_rows_v0.json")
ATHLETIC_FIELDS = ("forty", "vertical", "broad", "three_cone", "shuttle", "bench")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _records(payload: dict[str, Any], label: str, errors: list[str]) -> list[dict[str, Any]]:
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        errors.append(f"{label}: records must be a non-empty list")
        return []
    return records


def _source_ref_present(record: dict[str, Any], label: str, errors: list[str]) -> None:
    source_ref = record.get("source_ref")
    if not isinstance(source_ref, dict):
        errors.append(f"{label}: source_ref is required")
        return
    if not source_ref.get("source_url"):
        errors.append(f"{label}: source_ref.source_url is required")
    if source_ref.get("source_status") not in {"verified_public_source", "governed_in_repo"}:
        errors.append(f"{label}: source_ref.source_status is not verified")


def validate_candidate_documents(
    combine: dict[str, Any],
    pro_day: dict[str, Any],
    production: dict[str, Any],
    context: dict[str, Any],
    outcomes: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    for label, payload in (
        ("combine", combine),
        ("pro_day", pro_day),
        ("production", production),
        ("context", context),
        ("outcomes", outcomes),
    ):
        if payload.get("status") != "candidate_only":
            errors.append(f"{label}: status must be candidate_only")
        if payload.get("promotion_authorized") is not False:
            errors.append(f"{label}: promotion_authorized must be false")
        if payload.get("model_facing") is not False:
            errors.append(f"{label}: model_facing must be false")

    combine_records = _records(combine, "combine", errors)
    combine_by_id = {row.get("player_id"): row for row in combine_records}
    for index, row in enumerate(combine_records):
        label = f"combine.records[{index}]"
        _source_ref_present(row, label, errors)
        if row.get("event_type") != "nfl_combine":
            errors.append(f"{label}: event_type must be nfl_combine")
        if row.get("testing_status") == "attended_no_scored_testing":
            populated = [field for field in ATHLETIC_FIELDS if row.get(field) is not None]
            if populated:
                errors.append(
                    f"{label}: combine DNP row contains athletic values {populated}; possible pro-day conflation"
                )

    puka_combine = combine_by_id.get("wr-puka-nacua")
    if not puka_combine:
        errors.append("combine: missing Puka Nacua correction row")
    elif puka_combine.get("testing_status") != "attended_no_scored_testing":
        errors.append(
            "combine: Puka Nacua must remain attended_no_scored_testing at the NFL combine"
        )

    flowers_combine = combine_by_id.get("wr-zay-flowers")
    if not flowers_combine:
        errors.append("combine: missing Zay Flowers correction row")
    elif (flowers_combine.get("vertical"), flowers_combine.get("broad")) != (35.5, 127):
        errors.append("combine: Zay Flowers must retain verified 35.5 vertical / 127 broad")

    for index, row in enumerate(_records(pro_day, "pro_day", errors)):
        label = f"pro_day.records[{index}]"
        _source_ref_present(row, label, errors)
        if row.get("event_type") != "pro_day":
            errors.append(f"{label}: event_type must be pro_day")
        if "combine" in str(row.get("measurement_status", "")).lower():
            errors.append(f"{label}: pro-day measurement_status must not claim combine provenance")

    production_records = _records(production, "production", errors)
    production_by_id = {row.get("player_id"): row for row in production_records}
    for index, row in enumerate(production_records):
        label = f"production.records[{index}]"
        _source_ref_present(row, label, errors)
        if row.get("stat_scope") != "single_season_receiving":
            errors.append(f"{label}: stat_scope must be single_season_receiving; aggregates are ambiguous")
        if not isinstance(row.get("source_season"), int):
            errors.append(f"{label}: integer source_season is required")
        if row.get("production_score_0_100") is not None:
            errors.append(f"{label}: contaminated production score must remain null pending re-score authority")
    puka_production = production_by_id.get("wr-puka-nacua")
    if not puka_production:
        errors.append("production: missing Puka Nacua correction row")
    elif (
        puka_production.get("source_season"),
        puka_production.get("receptions"),
        puka_production.get("receiving_yards"),
        puka_production.get("receiving_tds"),
    ) != (2022, 48, 625, 5):
        errors.append("production: Puka Nacua 2022 receiving line must be 48/625/5")

    context_records = _records(context, "context", errors)
    context_by_id = {row.get("player_id"): row for row in context_records}
    for index, row in enumerate(context_records):
        label = f"context.records[{index}]"
        _source_ref_present(row, label, errors)
        seasons = row.get("college_seasons_played")
        if seasons is None:
            continue
        if not isinstance(seasons, list) or not seasons or any(
            not isinstance(year, int) for year in seasons
        ):
            errors.append(f"{label}: college_seasons_played must be a non-empty integer list")
            continue
        if len(set(seasons)) >= 4 and row.get("early_declare_flag") is not False:
            errors.append(f"{label}: four-season player cannot be early_declare under candidate semantics")

    puka_context = context_by_id.get("wr-puka-nacua")
    if not puka_context:
        errors.append("context: missing Puka Nacua evidence-summary correction row")
    else:
        if puka_context.get("legacy_evidence_summary_action") != "replace_entire_value":
            errors.append("context: Puka Nacua contaminated evidence summary must be replaced entirely")
        facts = puka_context.get("candidate_evidence_facts", {})
        fact_values = (
            facts.get("source_season"),
            facts.get("games"),
            facts.get("receptions"),
            facts.get("receiving_yards"),
            facts.get("receiving_tds"),
            facts.get("rushing_attempts"),
            facts.get("rushing_yards"),
            facts.get("rushing_tds"),
        )
        if fact_values != (2022, 9, 48, 625, 5, 25, 209, 5):
            errors.append("context: Puka Nacua evidence facts must use scoped 2022 components")
        summary = str(puka_context.get("candidate_evidence_summary", "")).lower()
        forbidden = ("1594", "1,594", "nfl rookie", "pick #177", "rams (r5)")
        if not summary or any(token in summary for token in forbidden):
            errors.append("context: Puka Nacua candidate summary retains ambiguous or post-cutoff claims")

    flowers_context = context_by_id.get("wr-zay-flowers")
    if not flowers_context:
        errors.append("context: missing Zay Flowers correction row")
    elif flowers_context.get("early_declare_flag") is not False:
        errors.append("context: Zay Flowers early_declare_flag must be false")
    elif "early_declare" not in flowers_context.get("evidence_tags_remove", []):
        errors.append("context: stale Zay Flowers early_declare tag must be explicitly removed")

    source_ref = outcomes.get("source_ref")
    if not isinstance(source_ref, dict) or not source_ref.get("source_url"):
        errors.append("outcomes: shared source_ref.source_url is required")
    elif "stats_player_reg_2023" not in source_ref["source_url"]:
        errors.append("outcomes: source must be the season-specific regular-season release")
    outcome_records = _records(outcomes, "outcomes", errors)
    for index, row in enumerate(outcome_records):
        label = f"outcomes.records[{index}]"
        if row.get("season_type") != "REG":
            errors.append(f"{label}: season_type must be REG; REG/POST mixing is forbidden")
        if row.get("season") != 2023:
            errors.append(f"{label}: season must be 2023")
        games = row.get("games")
        if not isinstance(games, int) or not 0 <= games <= 17:
            errors.append(f"{label}: games must be an integer in regular-season range 0..17")

    return errors


def validate_manifest(repo_root: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("status") != "candidate_only":
        errors.append("manifest: status must be candidate_only")
    if manifest.get("promotion_authorized") is not False:
        errors.append("manifest: promotion_authorized must be false")
    if manifest.get("promoted_artifacts_regenerated") is not False:
        errors.append("manifest: promoted_artifacts_regenerated must be false")

    for field in ("candidate_files", "preserved_source_files"):
        entries = manifest.get(field)
        if not isinstance(entries, list) or not entries:
            errors.append(f"manifest: {field} must be a non-empty list")
            continue
        for index, entry in enumerate(entries):
            relative = entry.get("path")
            expected = entry.get("sha256")
            if not relative or not expected:
                errors.append(f"manifest: {field}[{index}] requires path and sha256")
                continue
            if field == "candidate_files" and str(relative).startswith("exports/promoted/"):
                errors.append(f"manifest: candidate file cannot live under exports/promoted: {relative}")
            path = repo_root / relative
            if not path.is_file():
                errors.append(f"manifest: missing file {relative}")
                continue
            actual = sha256_file(path)
            if actual != expected:
                errors.append(f"manifest: sha256 mismatch for {relative}: {actual} != {expected}")
    return errors


def validate_archive(repo_root: Path, archive: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if archive.get("status") != "archived_fixture_non_authoritative":
        errors.append("archive: status must be archived_fixture_non_authoritative")

    source_files = archive.get("source_files", [])
    for index, entry in enumerate(source_files):
        path = repo_root / entry.get("path", "")
        if not path.is_file():
            errors.append(f"archive: source_files[{index}] missing {entry.get('path')}")
            continue
        actual = sha256_file(path)
        if actual != entry.get("sha256"):
            errors.append(f"archive: preserved source changed: {entry.get('path')}")

    comparisons = (
        ("combine_results", "data/raw/2023_combine_results.json"),
        ("college_production", "data/processed/2023_college_production.json"),
        ("prospect_context", "data/processed/2023_prospect_context.json"),
    )
    archived_rows = archive.get("archived_rows", {})
    for key, relative in comparisons:
        live_rows = load_json(repo_root / relative)
        live_by_id = {row.get("player_id"): row for row in live_rows}
        for row in archived_rows.get(key, []):
            player_id = row.get("player_id")
            if live_by_id.get(player_id) != row:
                errors.append(f"archive: {key} row for {player_id} is not an exact source copy")
    return errors


def validate_bundle(repo_root: Path, manifest_path: Path, archive_path: Path) -> list[str]:
    manifest = load_json(repo_root / manifest_path)
    archive = load_json(repo_root / archive_path)
    errors = validate_manifest(repo_root, manifest)
    errors.extend(validate_archive(repo_root, archive))

    candidate_payloads = {
        Path(entry["path"]).name: load_json(repo_root / entry["path"])
        for entry in manifest.get("candidate_files", [])
    }
    required = {
        "combine_results_corrections.json",
        "pro_day_results_candidate.json",
        "college_production_corrections.json",
        "prospect_context_corrections.json",
        "nfl_outcome_regular_season_inputs.json",
    }
    missing = sorted(required - candidate_payloads.keys())
    if missing:
        errors.append(f"manifest: missing required candidate payloads: {missing}")
        return errors

    errors.extend(
        validate_candidate_documents(
            candidate_payloads["combine_results_corrections.json"],
            candidate_payloads["pro_day_results_candidate.json"],
            candidate_payloads["college_production_corrections.json"],
            candidate_payloads["prospect_context_corrections.json"],
            candidate_payloads["nfl_outcome_regular_season_inputs.json"],
        )
    )
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate issue #285 candidate 2023 input corrections")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate_bundle(REPO_ROOT, args.manifest, args.archive)
    if errors:
        print("2023 INPUT INTEGRITY VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("2023 INPUT INTEGRITY VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
