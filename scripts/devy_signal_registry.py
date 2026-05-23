#!/usr/bin/env python3
"""Canonical Devy signal-discovery registry definitions and validation.

This module intentionally models interpretive state and uncertainty bands only.
It does not rank prospects, predict NFL draft capital, or run Rookie Alpha scoring.
"""

from __future__ import annotations

import argparse
import json
from enum import StrEnum
from pathlib import Path
from typing import Any

CURRENT_DEVY_SCHEMA_VERSION = "devy-prospect-registry-v0.1.0"
VALID_ARTIFACT_TYPES = frozenset({
    "fixture_only_devy_signal_discovery_registry",
    "devy_seed_watchlist",
})
SEED_WATCHLIST_ARTIFACT_TYPE = "devy_seed_watchlist"
SEED_WATCHLIST_IDENTITY_FIELDS = frozenset({"player_name", "school", "position"})
SEED_WATCHLIST_TIMELINE_FIELDS = frozenset({"projected_draft_class", "earliest_possible_draft_class", "class_year", "years_to_projected_draft"})
SEED_WATCHLIST_SIGNAL_FIELDS = frozenset({"development_tags", "signal_strength_band", "confidence_band", "actionability_band", "volatility_band"})
CANONICAL_PROVENANCE_SOURCE_TYPES = frozenset({
    "official_roster",
    "manual_eligibility_context",
    "manual_curated_seed_signal",
    "recruiting_profile",
    "production_data",
    "team_context_artifact",
})
ALLOWED_PROVENANCE_SOURCE_TYPES_BY_CATEGORY: dict[str, frozenset[str]] = {
    "identity_provenance": frozenset({"official_roster", "recruiting_profile"}),
    "timeline_provenance": frozenset({"manual_eligibility_context", "recruiting_profile"}),
    "signal_provenance": frozenset({
        "manual_curated_seed_signal",
        "recruiting_profile",
        "production_data",
        "team_context_artifact",
    }),
}


SEED_WATCHLIST_ALLOWED_INTAKE_METHODS = frozenset({
    "manual_curated_seed_watchlist",
    "codex_curated_task",
    "future_script_generated_candidate",
})
SEED_WATCHLIST_ALLOWED_PROMOTION_STATUSES = frozenset({
    "non_promoted_discovery_only",
    "blocked_from_downstream_use",
})
SEED_WATCHLIST_ALLOWED_DOWNSTREAM_ELIGIBILITY = frozenset({
    "blocked_until_rookie_transition",
    "blocked",
})


class DevyPosition(StrEnum):
    QB = "QB"
    RB = "RB"
    WR = "WR"
    TE = "TE"


class DevyDevelopmentHorizon(StrEnum):
    NEAR_TERM = "NEAR_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"
    LONG_HORIZON = "LONG_HORIZON"
    PREP_OR_FUTURE = "PREP_OR_FUTURE"


class DevyLifecycleStage(StrEnum):
    PREP = "PREP"
    TRUE_FRESHMAN = "TRUE_FRESHMAN"
    ROTATIONAL = "ROTATIONAL"
    EMERGING = "EMERGING"
    BREAKOUT_WINDOW = "BREAKOUT_WINDOW"
    NFL_TRACK = "NFL_TRACK"
    DECLARE_RISK = "DECLARE_RISK"
    SENIOR_HOLD = "SENIOR_HOLD"
    STALLED = "STALLED"


class DevyDevelopmentTag(StrEnum):
    LONG_HORIZON = "LONG_HORIZON"
    LONG_HORIZON_WATCHLIST = "LONG_HORIZON_WATCHLIST"
    HIGH_RECRUITING_CAPITAL = "HIGH_RECRUITING_CAPITAL"
    MULTI_SPORT_PROFILE = "MULTI_SPORT_PROFILE"
    INJURY_REHAB_WATCH = "INJURY_REHAB_WATCH"
    INSULATED_PROGRAM = "INSULATED_PROGRAM"
    SIZE_PROFILE = "SIZE_PROFILE"
    EARLY_DECLARE_CANDIDATE = "EARLY_DECLARE_CANDIDATE"
    PATHWAY_BLOCKED = "PATHWAY_BLOCKED"
    PATHWAY_CLEARING = "PATHWAY_CLEARING"
    TRANSFER_RISK = "TRANSFER_RISK"
    ASCENDING = "ASCENDING"
    STALLED_SIGNAL = "STALLED_SIGNAL"
    RAW_TRAITS = "RAW_TRAITS"
    PRODUCTION_PENDING = "PRODUCTION_PENDING"
    ROLE_UNCERTAIN = "ROLE_UNCERTAIN"


class DevySignalStrengthBand(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    ELITE = "ELITE"


class DevyConfidenceBand(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DevyActionabilityBand(StrEnum):
    WATCHLIST = "WATCHLIST"
    MONITOR = "MONITOR"
    TARGET = "TARGET"
    PRIORITY = "PRIORITY"


class DevyVolatilityBand(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


VALID_POSITIONS = frozenset(item.value for item in DevyPosition)
VALID_DEVELOPMENT_HORIZONS = frozenset(item.value for item in DevyDevelopmentHorizon)
VALID_LIFECYCLE_STAGES = frozenset(item.value for item in DevyLifecycleStage)
VALID_DEVELOPMENT_TAGS = frozenset(item.value for item in DevyDevelopmentTag)
VALID_SIGNAL_STRENGTH_BANDS = frozenset(item.value for item in DevySignalStrengthBand)
VALID_CONFIDENCE_BANDS = frozenset(item.value for item in DevyConfidenceBand)
VALID_ACTIONABILITY_BANDS = frozenset(item.value for item in DevyActionabilityBand)
VALID_VOLATILITY_BANDS = frozenset(item.value for item in DevyVolatilityBand)

BAND_FIELDS: dict[str, frozenset[str]] = {
    "signal_strength_band": VALID_SIGNAL_STRENGTH_BANDS,
    "confidence_band": VALID_CONFIDENCE_BANDS,
    "actionability_band": VALID_ACTIONABILITY_BANDS,
    "volatility_band": VALID_VOLATILITY_BANDS,
}

REQUIRED_PROSPECT_FIELDS = (
    "player_id",
    "player_name",
    "school",
    "position",
    "projected_draft_class",
    "earliest_possible_draft_class",
    "class_year",
    "years_to_projected_draft",
    "development_horizon",
    "lifecycle_stage",
    "development_tags",
    "signal_strength_band",
    "confidence_band",
    "actionability_band",
    "volatility_band",
    "summary",
    "why_it_matters",
    "source_notes",
)


def enum_snapshot() -> dict[str, list[str]]:
    """Return stable lists for docs, fixtures, and UI consumers."""

    return {
        "positions": sorted(VALID_POSITIONS),
        "development_horizons": [item.value for item in DevyDevelopmentHorizon],
        "lifecycle_stages": [item.value for item in DevyLifecycleStage],
        "development_tags": [item.value for item in DevyDevelopmentTag],
        "signal_strength_bands": [item.value for item in DevySignalStrengthBand],
        "confidence_bands": [item.value for item in DevyConfidenceBand],
        "actionability_bands": [item.value for item in DevyActionabilityBand],
        "volatility_bands": [item.value for item in DevyVolatilityBand],
    }


def expected_horizon_band(years_to_projected_draft: int | None, lifecycle_stage: str | None = None) -> str | None:
    """Map draft timeline distance to a coarse horizon band.

    Time is treated as risk. A prospect three or more years away from projected
    draft liquidity is never considered near-term actionable by this layer.
    """

    if years_to_projected_draft is None:
        return None
    if lifecycle_stage == DevyLifecycleStage.PREP.value or years_to_projected_draft >= 4:
        return DevyDevelopmentHorizon.PREP_OR_FUTURE.value
    if years_to_projected_draft >= 3:
        return DevyDevelopmentHorizon.LONG_HORIZON.value
    if years_to_projected_draft == 2:
        return DevyDevelopmentHorizon.MEDIUM_TERM.value
    if years_to_projected_draft in (0, 1):
        return DevyDevelopmentHorizon.NEAR_TERM.value
    return None


def _is_int_or_null(value: Any) -> bool:
    return value is None or (isinstance(value, int) and not isinstance(value, bool))


def validate_devy_registry(payload: dict[str, Any]) -> list[str]:
    """Validate a Devy prospect registry payload without mutating it."""

    errors: list[str] = []
    if payload.get("schema_version") != CURRENT_DEVY_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {CURRENT_DEVY_SCHEMA_VERSION!r}; got {payload.get('schema_version')!r}"
        )

    artifact_type = payload.get("artifact_type")
    if artifact_type not in VALID_ARTIFACT_TYPES:
        errors.append(f"artifact_type has invalid value {artifact_type!r}")

    disclaimer = payload.get("disclaimer")
    if not isinstance(disclaimer, str) or not disclaimer.strip():
        errors.append("disclaimer must be a non-empty string")
    elif artifact_type == SEED_WATCHLIST_ARTIFACT_TYPE:
        disclaimer_lower = disclaimer.lower()
        for required_phrase in ("seed watchlist", "not rankings", "not rookie alpha inputs"):
            if required_phrase not in disclaimer_lower:
                errors.append(f"seed watchlist disclaimer must include {required_phrase!r}")

    as_of_year = payload.get("as_of_year")
    if not isinstance(as_of_year, int) or isinstance(as_of_year, bool):
        errors.append("as_of_year must be an integer season/year")
        as_of_year = None

    if artifact_type == SEED_WATCHLIST_ARTIFACT_TYPE:
        intake_audit = payload.get("intake_audit")
        if not isinstance(intake_audit, dict):
            errors.append("intake_audit must be an object for seed watchlist artifacts")
        else:
            intake_method = intake_audit.get("intake_method")
            if intake_method not in SEED_WATCHLIST_ALLOWED_INTAKE_METHODS:
                errors.append(
                    f"intake_audit.intake_method must be one of {sorted(SEED_WATCHLIST_ALLOWED_INTAKE_METHODS)!r}"
                )
            for field in ("introduced_by_issue", "introduced_by_pr"):
                value = intake_audit.get(field)
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    errors.append(f"intake_audit.{field} must be a positive integer")

            validation_command = intake_audit.get("validation_command")
            if not isinstance(validation_command, str) or not validation_command.strip():
                errors.append("intake_audit.validation_command must be a non-empty string")

            promotion_status = intake_audit.get("promotion_status")
            if promotion_status not in SEED_WATCHLIST_ALLOWED_PROMOTION_STATUSES:
                errors.append(
                    f"intake_audit.promotion_status must be one of {sorted(SEED_WATCHLIST_ALLOWED_PROMOTION_STATUSES)!r}"
                )

            downstream_eligibility = intake_audit.get("downstream_eligibility")
            if downstream_eligibility not in SEED_WATCHLIST_ALLOWED_DOWNSTREAM_ELIGIBILITY:
                errors.append(
                    "intake_audit.downstream_eligibility must be one of "
                    f"{sorted(SEED_WATCHLIST_ALLOWED_DOWNSTREAM_ELIGIBILITY)!r}"
                )

            notes = intake_audit.get("notes")
            if not isinstance(notes, list) or not notes:
                errors.append("intake_audit.notes must be a non-empty list")
            else:
                for note in notes:
                    if not isinstance(note, str) or not note.strip():
                        errors.append("intake_audit.notes entries must be non-empty strings")

    prospects = payload.get("prospects")
    if not isinstance(prospects, list):
        errors.append("prospects must be a list")
        return errors

    seen_ids: set[str] = set()
    for index, prospect in enumerate(prospects):
        prefix = f"prospects[{index}]"
        if not isinstance(prospect, dict):
            errors.append(f"{prefix} must be an object")
            continue

        missing_fields = [field for field in REQUIRED_PROSPECT_FIELDS if field not in prospect]
        for field in missing_fields:
            errors.append(f"{prefix}.{field} is required")

        player_id = prospect.get("player_id")
        if not isinstance(player_id, str) or not player_id.strip():
            errors.append(f"{prefix}.player_id must be a non-empty string")
        elif player_id in seen_ids:
            errors.append(f"{prefix}.player_id duplicates {player_id!r}")
        else:
            seen_ids.add(player_id)

        for field in ("player_name", "summary", "why_it_matters"):
            value = prospect.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")

        school = prospect.get("school")
        if school is not None and not isinstance(school, str):
            errors.append(f"{prefix}.school must be a string or null")

        position = prospect.get("position")
        if position not in VALID_POSITIONS:
            errors.append(f"{prefix}.position has invalid value {position!r}")

        lifecycle_stage = prospect.get("lifecycle_stage")
        if lifecycle_stage not in VALID_LIFECYCLE_STAGES:
            errors.append(f"{prefix}.lifecycle_stage has invalid value {lifecycle_stage!r}")

        development_horizon = prospect.get("development_horizon")
        if development_horizon not in VALID_DEVELOPMENT_HORIZONS:
            errors.append(f"{prefix}.development_horizon has invalid value {development_horizon!r}")

        development_tags = prospect.get("development_tags")
        if not isinstance(development_tags, list) or not development_tags:
            errors.append(f"{prefix}.development_tags must be a non-empty list")
        else:
            for tag in development_tags:
                if tag not in VALID_DEVELOPMENT_TAGS:
                    errors.append(f"{prefix}.development_tags has invalid value {tag!r}")

        for field, valid_values in BAND_FIELDS.items():
            value = prospect.get(field)
            if value not in valid_values:
                errors.append(f"{prefix}.{field} has invalid value {value!r}")

        for field in (
            "projected_draft_class",
            "earliest_possible_draft_class",
            "class_year",
            "years_to_projected_draft",
            "recruiting_stars",
            "recruiting_rank_national",
            "recruiting_rank_position",
        ):
            if field in prospect and not _is_int_or_null(prospect.get(field)):
                errors.append(f"{prefix}.{field} must be an integer or null")

        projected = prospect.get("projected_draft_class")
        earliest = prospect.get("earliest_possible_draft_class")
        years_to_projected = prospect.get("years_to_projected_draft")
        if isinstance(projected, int) and isinstance(earliest, int) and earliest > projected:
            errors.append(f"{prefix}.earliest_possible_draft_class cannot exceed projected_draft_class")
        if isinstance(projected, int) and isinstance(as_of_year, int):
            expected_years = projected - as_of_year
            if years_to_projected != expected_years:
                errors.append(
                    f"{prefix}.years_to_projected_draft must equal projected_draft_class - as_of_year "
                    f"({expected_years}); got {years_to_projected!r}"
                )
        if isinstance(years_to_projected, int):
            expected_horizon = expected_horizon_band(years_to_projected, lifecycle_stage)
            if development_horizon != expected_horizon:
                errors.append(
                    f"{prefix}.development_horizon must be {expected_horizon!r} for "
                    f"years_to_projected_draft={years_to_projected}; got {development_horizon!r}"
                )
            if years_to_projected >= 3:
                if development_horizon == DevyDevelopmentHorizon.NEAR_TERM.value:
                    errors.append(f"{prefix} long-horizon prospect cannot be tagged NEAR_TERM")
                if prospect.get("actionability_band") in {
                    DevyActionabilityBand.TARGET.value,
                    DevyActionabilityBand.PRIORITY.value,
                }:
                    errors.append(f"{prefix} long-horizon prospect cannot be TARGET or PRIORITY actionable")

        source_notes = prospect.get("source_notes")
        if not isinstance(source_notes, list) or not source_notes:
            errors.append(f"{prefix}.source_notes must be a non-empty list")
        else:
            for note in source_notes:
                if not isinstance(note, str) or not note.strip():
                    errors.append(f"{prefix}.source_notes entries must be non-empty strings")

        if artifact_type == SEED_WATCHLIST_ARTIFACT_TYPE:
            required_map = {
                "identity_provenance": SEED_WATCHLIST_IDENTITY_FIELDS,
                "timeline_provenance": SEED_WATCHLIST_TIMELINE_FIELDS,
                "signal_provenance": SEED_WATCHLIST_SIGNAL_FIELDS,
            }
            for provenance_key, expected_fields in required_map.items():
                provenance = prospect.get(provenance_key)
                if not isinstance(provenance, dict):
                    errors.append(f"{prefix}.{provenance_key} must be an object for seed watchlist rows")
                    continue

                source_type = provenance.get("source_type")
                if source_type not in CANONICAL_PROVENANCE_SOURCE_TYPES:
                    errors.append(
                        f"{prefix}.{provenance_key}.source_type must be one of "
                        f"{sorted(CANONICAL_PROVENANCE_SOURCE_TYPES)!r}"
                    )
                else:
                    allowed_source_types = ALLOWED_PROVENANCE_SOURCE_TYPES_BY_CATEGORY[provenance_key]
                    if source_type not in allowed_source_types:
                        errors.append(
                            f"{prefix}.{provenance_key}.source_type {source_type!r} is not allowed for "
                            f"{provenance_key}; allowed values are {sorted(allowed_source_types)!r}"
                        )

                provenance_fields = provenance.get("supports_fields")
                if provenance_fields is not None:
                    if not isinstance(provenance_fields, list) or not provenance_fields:
                        errors.append(f"{prefix}.{provenance_key}.supports_fields must be a non-empty list when present")
                    elif set(provenance_fields) != expected_fields:
                        errors.append(f"{prefix}.{provenance_key}.supports_fields must match canonical field scope")

                provenance_notes = provenance.get("source_notes")
                if not isinstance(provenance_notes, list) or not provenance_notes:
                    errors.append(f"{prefix}.{provenance_key}.source_notes must be a non-empty list")
                else:
                    for note in provenance_notes:
                        if not isinstance(note, str) or not note.strip():
                            errors.append(f"{prefix}.{provenance_key}.source_notes entries must be non-empty strings")

                source_urls = provenance.get("source_urls")
                if source_urls is not None:
                    if not isinstance(source_urls, list) or not source_urls:
                        errors.append(f"{prefix}.{provenance_key}.source_urls must be a non-empty list when present")
                    else:
                        for url in source_urls:
                            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                                errors.append(f"{prefix}.{provenance_key}.source_urls entries must be HTTP(S) URLs")

                last_verified_year = provenance.get("last_verified_year")
                if (
                    not isinstance(last_verified_year, int)
                    or isinstance(last_verified_year, bool)
                    or (isinstance(as_of_year, int) and last_verified_year > as_of_year)
                ):
                    errors.append(f"{prefix}.{provenance_key}.last_verified_year must be an integer no later than as_of_year")

    return errors


def load_devy_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Devy prospect registry payload.")
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("data/fixtures/devy_prospect_registry_v0_fixture.json"),
        help="Path to a Devy prospect registry JSON payload.",
    )
    args = parser.parse_args()

    errors = validate_devy_registry(load_devy_registry(args.registry))
    if errors:
        print("DEVY REGISTRY VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("DEVY REGISTRY VALIDATION PASSED")


if __name__ == "__main__":
    main()
