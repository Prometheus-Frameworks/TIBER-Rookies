#!/usr/bin/env python3
"""Schema, provenance, and manifest validation for rookie_transition_profile_v0.

Implements the contract designed in docs/rookie-transition-profile-v0-design.md
(issue #261). This artifact is an evidence-consolidation layer only — it
carries no scores, no rankings, and makes no predictive claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Any

CURRENT_SCHEMA_VERSION = "rookie-transition-profile-v0.1.0"
ARTIFACT_TYPE = "rookie_transition_profile"

REQUIRED_ARTIFACT_TOP_LEVEL = {
    "schema_version",
    "artifact_type",
    "season",
    "generated_at",
    "run_id",
    "disclaimer",
    "source_files_used",
    "coverage_summary",
    "rows",
}

REQUIRED_MANIFEST_TOP_LEVEL = {
    "season",
    "schema_version",
    "generated_at",
    "run_id",
    "input_files",
    "coverage_summary",
    "output_files",
    "export_metadata",
}

REQUIRED_ROW_IDENTITY_FIELDS = ("player_id", "player_name", "position", "school", "class_year")

# Field families defined by the #261 design. A row need not carry every family
# (e.g. a player with no dob on file), but any family that IS present must be
# a {value, provenance} pair.
GOVERNED_FIELD_FAMILIES = ("draft_capital", "age_at_entry", "athletic_testing", "college_production")


class SourceType(StrEnum):
    MEASURED_COMBINE = "measured_combine"
    MEASURED_PRODUCTION_STATS = "measured_production_stats"
    MEASURED_IDENTITY_FACT = "measured_identity_fact"
    OFFICIAL_DRAFT_RESULT = "official_draft_result"
    MARKET_DERIVED_PROXY = "market_derived_proxy"
    OPERATOR_SEEDED = "operator_seeded"
    ESTIMATED_MANUAL_RESEARCH = "estimated_manual_research"
    UNAVAILABLE = "unavailable"


OBSERVED_SOURCE_TYPES = frozenset({
    SourceType.MEASURED_COMBINE.value,
    SourceType.MEASURED_PRODUCTION_STATS.value,
    SourceType.MEASURED_IDENTITY_FACT.value,
    SourceType.OFFICIAL_DRAFT_RESULT.value,
})
INFERRED_SOURCE_TYPES = frozenset({
    SourceType.MARKET_DERIVED_PROXY.value,
    SourceType.OPERATOR_SEEDED.value,
    SourceType.ESTIMATED_MANUAL_RESEARCH.value,
})
VALID_SOURCE_TYPES = frozenset(item.value for item in SourceType)


class ConfidenceBand(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


VALID_CONFIDENCE_BANDS = frozenset(item.value for item in ConfidenceBand)


def confidence_to_band(confidence: float) -> str:
    """Coarse, UI-facing bucketing of a continuous confidence float.

    Matches the observed range of existing per-field confidence values in
    compute_rookie_alpha.py (0.50 neutral-default up to 1.00 full RAS).
    """
    if confidence >= 0.85:
        return ConfidenceBand.HIGH.value
    if confidence >= 0.65:
        return ConfidenceBand.MEDIUM.value
    return ConfidenceBand.LOW.value


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_provenance_object(provenance: Any, *, prefix: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(provenance, dict):
        return [f"{prefix} must be an object"]

    source_type = provenance.get("source_type")
    if source_type not in VALID_SOURCE_TYPES:
        errors.append(f"{prefix}.source_type has invalid value {source_type!r}")

    if source_type == SourceType.UNAVAILABLE.value:
        if not provenance.get("notes"):
            errors.append(f"{prefix}.notes is required when source_type is 'unavailable'")
        return errors

    if not isinstance(provenance.get("source_name"), str) or not provenance["source_name"].strip():
        errors.append(f"{prefix}.source_name must be a non-empty string")

    confidence = provenance.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not (0.0 <= confidence <= 1.0):
        errors.append(f"{prefix}.confidence must be a number in [0.0, 1.0]")

    confidence_band = provenance.get("confidence_band")
    if confidence_band not in VALID_CONFIDENCE_BANDS:
        errors.append(f"{prefix}.confidence_band has invalid value {confidence_band!r}")
    elif isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
        expected_band = confidence_to_band(float(confidence))
        if confidence_band != expected_band:
            errors.append(
                f"{prefix}.confidence_band {confidence_band!r} does not match confidence "
                f"{confidence!r} (expected {expected_band!r})"
            )

    last_verified_at = provenance.get("last_verified_at")
    if not isinstance(last_verified_at, str) or not last_verified_at.strip():
        errors.append(f"{prefix}.last_verified_at must be a non-empty date string")

    return errors


def validate_field(field: Any, *, prefix: str) -> list[str]:
    """A governed field family must be either absent, or a {value, provenance} pair.

    This is the artifact's signature invariant: no value may appear without a
    provenance object, and every provenance object must declare a valid
    source_type. This directly targets the class of defect found in #257
    (data whose real nature was undiscoverable without reading source code).
    """
    if not isinstance(field, dict) or "value" not in field or "provenance" not in field:
        return [f"{prefix} must be an object with 'value' and 'provenance' keys"]

    errors = validate_provenance_object(field["provenance"], prefix=f"{prefix}.provenance")

    source_type = field["provenance"].get("source_type")
    if source_type == SourceType.UNAVAILABLE.value and field["value"] is not None:
        errors.append(f"{prefix}.value must be null when provenance.source_type is 'unavailable'")
    if source_type != SourceType.UNAVAILABLE.value and field["value"] is None:
        errors.append(f"{prefix}.value must not be null unless provenance.source_type is 'unavailable'")

    return errors


def validate_row(row: Any, *, index: int, season: int) -> list[str]:
    prefix = f"rows[{index}]"
    if not isinstance(row, dict):
        return [f"{prefix} must be an object"]

    errors: list[str] = []
    for field in REQUIRED_ROW_IDENTITY_FIELDS:
        if field not in row:
            errors.append(f"{prefix}.{field} is required")

    player_id = row.get("player_id")
    if not isinstance(player_id, str) or not player_id.strip():
        errors.append(f"{prefix}.player_id must be a non-empty string")

    for family in GOVERNED_FIELD_FAMILIES:
        if family in row:
            field_errors = validate_field(row[family], prefix=f"{prefix}.{family}")
            errors.extend(field_errors)
            if not field_errors:
                last_verified_at = row[family]["provenance"].get("last_verified_at")
                if isinstance(last_verified_at, str) and len(last_verified_at) >= 4:
                    try:
                        verified_year = int(last_verified_at[:4])
                        if verified_year > season:
                            errors.append(
                                f"rows[{index}].{family}.provenance.last_verified_at "
                                f"({last_verified_at}) is later than season {season}"
                            )
                    except ValueError:
                        errors.append(
                            f"rows[{index}].{family}.provenance.last_verified_at "
                            f"({last_verified_at}) must start with a 4-digit year"
                        )

    return errors


def validate_artifact_shape(payload: Any) -> list[str]:
    """Validate schema_version, required top-level fields, and every row."""
    if not isinstance(payload, dict):
        return ["Artifact payload must be a JSON object."]

    errors: list[str] = []
    if payload.get("schema_version") != CURRENT_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {CURRENT_SCHEMA_VERSION!r}; got {payload.get('schema_version')!r}"
        )
    if payload.get("artifact_type") != ARTIFACT_TYPE:
        errors.append(f"artifact_type must be {ARTIFACT_TYPE!r}; got {payload.get('artifact_type')!r}")

    missing = REQUIRED_ARTIFACT_TOP_LEVEL - set(payload.keys())
    if missing:
        errors.append(f"Artifact missing required top-level fields: {sorted(missing)}")

    disclaimer = payload.get("disclaimer")
    if not isinstance(disclaimer, str) or not disclaimer.strip():
        errors.append("disclaimer must be a non-empty string")

    season = payload.get("season")
    if not isinstance(season, int) or isinstance(season, bool):
        errors.append("season must be an integer")
        return errors

    rows = payload.get("rows")
    if not isinstance(rows, list):
        errors.append("rows must be a list")
        return errors

    seen_ids: set[str] = set()
    for index, row in enumerate(rows):
        errors.extend(validate_row(row, index=index, season=season))
        if isinstance(row, dict):
            player_id = row.get("player_id")
            if isinstance(player_id, str):
                if player_id in seen_ids:
                    errors.append(f"rows[{index}].player_id duplicates {player_id!r}")
                seen_ids.add(player_id)

    return errors


def find_repo_root(start_path: Path) -> Path:
    current = start_path.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return current


def resolve_path(path_str: str, manifest_path: Path) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    repo_root = find_repo_root(manifest_path.parent)
    from_repo_root = (repo_root / path).resolve()
    if from_repo_root.exists():
        return from_repo_root
    from_manifest_dir = (manifest_path.parent / path).resolve()
    if from_manifest_dir.exists():
        return from_manifest_dir
    return from_repo_root


def validate_export_manifest(
    export_path: Path,
    manifest_path: Path,
    *,
    check_input_hashes: bool = True,
    check_output_hashes: bool = True,
) -> list[str]:
    errors: list[str] = []
    required_companion_files = {export_path, export_path.with_suffix(".csv"), manifest_path}
    for required_file in required_companion_files:
        if not required_file.exists():
            errors.append(f"Required companion file not found: {required_file}")
    if errors:
        return errors

    try:
        export_payload = load_json(export_path)
    except Exception as exc:  # pragma: no cover - defensive user-facing error
        return [f"Failed to parse export JSON: {exc}"]
    try:
        manifest_payload = load_json(manifest_path)
    except Exception as exc:  # pragma: no cover - defensive user-facing error
        return [f"Failed to parse manifest JSON: {exc}"]

    if not isinstance(export_payload, dict) or not isinstance(manifest_payload, dict):
        return ["Export and manifest payloads must be JSON objects."]

    errors.extend(validate_artifact_shape(export_payload))

    missing_manifest_fields = REQUIRED_MANIFEST_TOP_LEVEL - set(manifest_payload.keys())
    if missing_manifest_fields:
        errors.append(f"Manifest missing required fields: {sorted(missing_manifest_fields)}")

    export_metadata_expected = {
        "season": export_payload.get("season"),
        "schema_version": export_payload.get("schema_version"),
        "generated_at": export_payload.get("generated_at"),
        "run_id": export_payload.get("run_id"),
        "coverage_summary": export_payload.get("coverage_summary"),
        "source_files_used": export_payload.get("source_files_used"),
    }
    if manifest_payload.get("export_metadata") != export_metadata_expected:
        errors.append("manifest.export_metadata does not exactly match export JSON metadata.")

    if check_output_hashes:
        output_entries = manifest_payload.get("output_files", [])
        if not isinstance(output_entries, list):
            errors.append("manifest.output_files must be a list.")
        else:
            output_paths = {
                str(resolve_path(str(entry.get("path")), manifest_path))
                for entry in output_entries
                if isinstance(entry, dict) and entry.get("path")
            }
            expected_output_paths = {
                str(export_path.resolve()),
                str(export_path.with_suffix(".csv").resolve()),
            }
            if not expected_output_paths.issubset(output_paths):
                errors.append("manifest.output_files is missing required JSON/CSV output entries.")
            for output in output_entries:
                if not isinstance(output, dict):
                    errors.append("manifest.output_files entries must be objects.")
                    continue
                path_str = output.get("path")
                expected_hash = output.get("sha256")
                if not path_str or not expected_hash:
                    errors.append(f"Invalid output_files entry: {output}")
                    continue
                resolved = resolve_path(path_str, manifest_path)
                if not resolved.exists():
                    errors.append(f"Output file listed in manifest is missing: {path_str}")
                    continue
                actual_hash = sha256_file(resolved)
                if actual_hash != expected_hash:
                    errors.append(f"Output hash mismatch for {path_str}: expected {expected_hash}, got {actual_hash}")

    if check_input_hashes:
        input_entries = manifest_payload.get("input_files", [])
        if not isinstance(input_entries, list):
            errors.append("manifest.input_files must be a list.")
        else:
            for input_file in input_entries:
                if not isinstance(input_file, dict):
                    errors.append("manifest.input_files entries must be objects.")
                    continue
                path_str = input_file.get("path")
                expected_hash = input_file.get("sha256")
                expected_rows = input_file.get("row_count")
                if not path_str or not expected_hash:
                    errors.append(f"Invalid input_files entry: {input_file}")
                    continue
                resolved = resolve_path(path_str, manifest_path)
                if not resolved.exists():
                    errors.append(f"Input file listed in manifest is missing: {path_str}")
                    continue
                actual_hash = sha256_file(resolved)
                if actual_hash != expected_hash:
                    errors.append(f"Input hash mismatch for {path_str}: expected {expected_hash}, got {actual_hash}")
                if expected_rows is not None:
                    try:
                        loaded = load_json(resolved)
                    except Exception as exc:
                        errors.append(f"Unable to read input file for row_count check {path_str}: {exc}")
                        continue
                    if isinstance(loaded, list) and len(loaded) != expected_rows:
                        errors.append(
                            f"Input row_count mismatch for {path_str}: expected {expected_rows}, got {len(loaded)}"
                        )

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a rookie_transition_profile_v0 export and manifest")
    parser.add_argument("--export-json", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--skip-input-hashes", action="store_true")
    parser.add_argument("--skip-output-hashes", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    errors = validate_export_manifest(
        export_path=args.export_json,
        manifest_path=args.manifest,
        check_input_hashes=not args.skip_input_hashes,
        check_output_hashes=not args.skip_output_hashes,
    )
    if errors:
        print("ROOKIE TRANSITION PROFILE VALIDATION FAILED")
        for err in errors:
            print(f"- {err}")
        raise SystemExit(1)
    print("ROOKIE TRANSITION PROFILE VALIDATION PASSED")


if __name__ == "__main__":
    main()
