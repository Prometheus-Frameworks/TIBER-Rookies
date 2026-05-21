#!/usr/bin/env python3
"""Validate operator-supplied deep Devy league draft snapshot artifacts.

Discovery-only guardrail: snapshot artifacts are market/coverage intelligence and
must never be treated as scouting truth, rankings, Rookie Alpha inputs, or
automatic seed-watchlist mutations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CURRENT_SCHEMA_VERSION = "devy-league-market-snapshot-v0.1.0"
ARTIFACT_TYPE = "operator_supplied_devy_draft_snapshot"
ALLOWED_SOURCE_TYPES = frozenset({"operator_supplied_league_draft"})
ALLOWED_LEAGUE_FORMATS = frozenset({"deep_devy"})


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_list_of_non_empty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_is_non_empty_string(item) for item in value)


def validate_devy_league_market_snapshot(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if payload.get("schema_version") != CURRENT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CURRENT_SCHEMA_VERSION!r}")
    if payload.get("artifact_type") != ARTIFACT_TYPE:
        errors.append(f"artifact_type must be {ARTIFACT_TYPE!r}")

    if payload.get("source_type") not in ALLOWED_SOURCE_TYPES:
        errors.append(f"source_type must be one of {sorted(ALLOWED_SOURCE_TYPES)!r}")
    if payload.get("league_format") not in ALLOWED_LEAGUE_FORMATS:
        errors.append(f"league_format must be one of {sorted(ALLOWED_LEAGUE_FORMATS)!r}")

    if not _is_int(payload.get("snapshot_year")):
        errors.append("snapshot_year must be an integer")

    for field in ("league_identifier",):
        if not _is_non_empty_string(payload.get(field)):
            errors.append(f"{field} must be a non-empty string")

    for field in ("privacy_notes", "warnings"):
        if not _is_list_of_non_empty_strings(payload.get(field)):
            errors.append(f"{field} must be a non-empty list of non-empty strings")

    intake_audit = payload.get("intake_audit")
    if not isinstance(intake_audit, dict):
        errors.append("intake_audit must be an object")
    else:
        for field in ("intake_method", "promotion_status", "downstream_block", "source_label"):
            if not _is_non_empty_string(intake_audit.get(field)):
                errors.append(f"intake_audit.{field} must be a non-empty string")

    drafts = payload.get("drafts")
    if not isinstance(drafts, list) or not drafts:
        errors.append("drafts must be a non-empty list")
        return errors

    for draft_idx, draft in enumerate(drafts):
        prefix = f"drafts[{draft_idx}]"
        if not isinstance(draft, dict):
            errors.append(f"{prefix} must be an object")
            continue

        for field in ("draft_id", "draft_label"):
            if not _is_non_empty_string(draft.get(field)):
                errors.append(f"{prefix}.{field} must be a non-empty string")

        picks = draft.get("picks")
        if not isinstance(picks, list) or not picks:
            errors.append(f"{prefix}.picks must be a non-empty list")
            continue

        for pick_idx, pick in enumerate(picks):
            pick_prefix = f"{prefix}.picks[{pick_idx}]"
            if not isinstance(pick, dict):
                errors.append(f"{pick_prefix} must be an object")
                continue

            for field in (
                "draft_id",
                "pick",
                "player_name_raw",
                "player_name_normalized",
                "school_raw",
                "school_normalized",
                "position_raw",
                "position_normalized",
            ):
                if not _is_non_empty_string(pick.get(field)):
                    errors.append(f"{pick_prefix}.{field} must be a non-empty string")

            for int_field in ("round", "slot"):
                if not _is_int(pick.get(int_field)):
                    errors.append(f"{pick_prefix}.{int_field} must be an integer")

            notes = pick.get("operator_notes")
            if notes is not None and not _is_non_empty_string(notes):
                errors.append(f"{pick_prefix}.operator_notes must be null or a non-empty string")

    return errors


def load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate deep Devy league market snapshot artifact")
    parser.add_argument("--artifact", type=Path, required=True, help="Path to snapshot artifact JSON")
    args = parser.parse_args()

    errors = validate_devy_league_market_snapshot(load_payload(args.artifact))
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f" - {error}")
        return 1

    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
