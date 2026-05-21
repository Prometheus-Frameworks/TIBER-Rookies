#!/usr/bin/env python3
"""Validate monthly Devy roster pulse candidate-delta artifacts.

Discovery-only guardrail: these artifacts surface candidate changes for manual
review and must not mutate the curated seed watchlist directly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CURRENT_PULSE_SCHEMA_VERSION = "devy-roster-pulse-v0.1.0"
PULSE_ARTIFACT_TYPE = "devy_roster_pulse_candidate_delta"

ALLOWED_ROSTER_STATUSES = frozenset({
    "new_on_roster",
    "still_present",
    "missing_from_roster",
    "program_changed",
    "unresolved",
})
ALLOWED_CLASS_YEAR_SOURCES = frozenset({"roster", "recruiting_profile", "manual", "unknown"})
ALLOWED_CONFIDENCE_BANDS = frozenset({"LOW", "MEDIUM", "HIGH"})
ALLOWED_FRESHMAN_STATUSES = frozenset({"confirmed", "unconfirmed", "unknown"})
ALLOWED_AUTO_MUTATIONS = frozenset({"none"})


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _is_list_of_non_empty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_is_non_empty_string(item) for item in value)


def validate_devy_roster_pulse(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if payload.get("schema_version") != CURRENT_PULSE_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {CURRENT_PULSE_SCHEMA_VERSION!r}; got {payload.get('schema_version')!r}"
        )

    if payload.get("artifact_type") != PULSE_ARTIFACT_TYPE:
        errors.append(f"artifact_type must be {PULSE_ARTIFACT_TYPE!r}")

    for field in ("pulse_month", "generated_at", "comparison_basis"):
        if not _is_non_empty_string(payload.get(field)):
            errors.append(f"{field} must be a non-empty string")

    for field in ("input_sources", "warnings", "intake_audit"):
        value = payload.get(field)
        if field == "intake_audit":
            if not isinstance(value, dict):
                errors.append("intake_audit must be an object")
        elif not _is_list_of_non_empty_strings(value):
            errors.append(f"{field} must be a non-empty list of non-empty strings")

    intake_audit = payload.get("intake_audit") if isinstance(payload.get("intake_audit"), dict) else {}
    if intake_audit:
        for field in ("intake_method", "promotion_status", "validation_command", "downstream_block"):
            if not _is_non_empty_string(intake_audit.get(field)):
                errors.append(f"intake_audit.{field} must be a non-empty string")

    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        errors.append("candidates must be a non-empty list")
        return errors

    for idx, candidate in enumerate(candidates):
        prefix = f"candidates[{idx}]"
        if not isinstance(candidate, dict):
            errors.append(f"{prefix} must be an object")
            continue

        for field in ("player_name", "school", "position", "roster_status", "class_year_source", "confidence_band"):
            if not _is_non_empty_string(candidate.get(field)):
                errors.append(f"{prefix}.{field} must be a non-empty string")

        roster_status = candidate.get("roster_status")
        if roster_status not in ALLOWED_ROSTER_STATUSES:
            errors.append(f"{prefix}.roster_status must be one of {sorted(ALLOWED_ROSTER_STATUSES)!r}")

        class_year_source = candidate.get("class_year_source")
        if class_year_source not in ALLOWED_CLASS_YEAR_SOURCES:
            errors.append(f"{prefix}.class_year_source must be one of {sorted(ALLOWED_CLASS_YEAR_SOURCES)!r}")

        confidence_band = candidate.get("confidence_band")
        if confidence_band not in ALLOWED_CONFIDENCE_BANDS:
            errors.append(f"{prefix}.confidence_band must be one of {sorted(ALLOWED_CONFIDENCE_BANDS)!r}")

        if not _is_bool(candidate.get("existing_seed_watchlist_match")):
            errors.append(f"{prefix}.existing_seed_watchlist_match must be a boolean")
        if not _is_bool(candidate.get("needs_manual_review")):
            errors.append(f"{prefix}.needs_manual_review must be a boolean")

        prior_found = candidate.get("prior_college_production_found")
        if prior_found not in (True, False, None):
            errors.append(f"{prefix}.prior_college_production_found must be true/false/null")

        for list_field in ("candidate_tags", "source_urls", "source_notes"):
            if not _is_list_of_non_empty_strings(candidate.get(list_field)):
                errors.append(f"{prefix}.{list_field} must be a non-empty list of non-empty strings")

        freshman_status = candidate.get("freshman_status", "unknown")
        if freshman_status not in ALLOWED_FRESHMAN_STATUSES:
            errors.append(f"{prefix}.freshman_status must be one of {sorted(ALLOWED_FRESHMAN_STATUSES)!r}")

        auto_mutation = candidate.get("auto_seed_watchlist_mutation", "none")
        if auto_mutation not in ALLOWED_AUTO_MUTATIONS:
            errors.append(f"{prefix}.auto_seed_watchlist_mutation must be 'none'")

        tags = candidate.get("candidate_tags") if isinstance(candidate.get("candidate_tags"), list) else []
        if prior_found is False and "confirmed_freshman" in tags:
            errors.append(
                f"{prefix} cannot set confirmed_freshman from missing prior stats alone"
            )
        if prior_found is False and freshman_status == "confirmed" and class_year_source == "unknown":
            errors.append(
                f"{prefix} cannot mark freshman_status='confirmed' when class_year_source is unknown and prior stats are missing"
            )

    return errors


def load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate monthly Devy roster pulse candidate-delta artifact")
    parser.add_argument("--artifact", type=Path, required=True, help="Path to devy roster pulse artifact JSON")
    args = parser.parse_args()

    errors = validate_devy_roster_pulse(load_payload(args.artifact))
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f" - {error}")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
