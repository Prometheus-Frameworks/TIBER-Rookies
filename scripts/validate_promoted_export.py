#!/usr/bin/env python3
"""Validate promoted Rookie Alpha export + manifest for downstream ingestion."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_EXPORT_TOP_LEVEL = {
    "model",
    "generated_at",
    "run_id",
    "season",
    "coverage_summary",
    "source_files_used",
    "players",
}

REQUIRED_MANIFEST_TOP_LEVEL = {
    "season",
    "model_version",
    "generated_at",
    "run_id",
    "input_files",
    "coverage_summary",
    "output_files",
    "export_metadata",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(path_str: str, manifest_path: Path) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    manifest_parent = manifest_path.parent
    repo_root_guess = manifest_parent
    if len(manifest_parent.parts) >= 3:
        try:
            repo_root_guess = manifest_parent.parents[2]
        except IndexError:
            repo_root_guess = manifest_parent
    from_repo_root_guess = (repo_root_guess / path).resolve()
    if from_repo_root_guess.exists():
        return from_repo_root_guess
    from_manifest_dir = (manifest_parent / path).resolve()
    if from_manifest_dir.exists():
        return from_manifest_dir
    from_cwd = (Path.cwd() / path).resolve()
    if from_cwd.exists():
        return from_cwd
    return from_repo_root_guess / path


def validate_export_manifest(
    export_path: Path,
    manifest_path: Path,
    *,
    check_input_hashes: bool = True,
    check_output_hashes: bool = True,
) -> list[str]:
    errors: list[str] = []

    if not export_path.exists():
        return [f"Export file not found: {export_path}"]
    if not manifest_path.exists():
        return [f"Manifest file not found: {manifest_path}"]

    try:
        export_payload = load_json(export_path)
    except Exception as exc:  # pragma: no cover - defensive user-facing error
        return [f"Failed to parse export JSON: {exc}"]

    try:
        manifest_payload = load_json(manifest_path)
    except Exception as exc:  # pragma: no cover - defensive user-facing error
        return [f"Failed to parse manifest JSON: {exc}"]

    if not isinstance(export_payload, dict):
        errors.append("Export payload must be a JSON object.")
        return errors
    if not isinstance(manifest_payload, dict):
        errors.append("Manifest payload must be a JSON object.")
        return errors

    missing_export_fields = REQUIRED_EXPORT_TOP_LEVEL - set(export_payload.keys())
    if missing_export_fields:
        errors.append(f"Export missing required fields: {sorted(missing_export_fields)}")

    missing_manifest_fields = REQUIRED_MANIFEST_TOP_LEVEL - set(manifest_payload.keys())
    if missing_manifest_fields:
        errors.append(f"Manifest missing required fields: {sorted(missing_manifest_fields)}")

    export_model = export_payload.get("model", {})
    export_metadata_expected = {
        "season": export_payload.get("season"),
        "model_version": export_model.get("model_version") if isinstance(export_model, dict) else None,
        "generated_at": export_payload.get("generated_at"),
        "run_id": export_payload.get("run_id"),
        "coverage_summary": export_payload.get("coverage_summary"),
        "source_files_used": export_payload.get("source_files_used"),
    }

    manifest_metadata_expected = {
        "season": manifest_payload.get("season"),
        "model_version": manifest_payload.get("model_version"),
        "generated_at": manifest_payload.get("generated_at"),
        "run_id": manifest_payload.get("run_id"),
        "coverage_summary": manifest_payload.get("coverage_summary"),
        "source_files_used": [
            entry.get("path")
            for entry in manifest_payload.get("input_files", [])
            if isinstance(entry, dict)
        ],
    }

    if manifest_payload.get("export_metadata") != export_metadata_expected:
        errors.append("manifest.export_metadata does not exactly match export JSON metadata.")

    if manifest_payload.get("export_metadata") != manifest_metadata_expected:
        errors.append("manifest.export_metadata does not match top-level manifest metadata fields.")

    if check_output_hashes:
        output_entries = manifest_payload.get("output_files", [])
        if not isinstance(output_entries, list):
            errors.append("manifest.output_files must be a list.")
        else:
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
                    errors.append(
                        f"Output hash mismatch for {path_str}: expected {expected_hash}, got {actual_hash}"
                    )

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
                    errors.append(
                        f"Input hash mismatch for {path_str}: expected {expected_hash}, got {actual_hash}"
                    )
                try:
                    rows = load_json(resolved)
                    if isinstance(rows, list) and expected_rows is not None and len(rows) != expected_rows:
                        errors.append(
                            f"Input row_count mismatch for {path_str}: expected {expected_rows}, got {len(rows)}"
                        )
                except Exception as exc:
                    errors.append(f"Unable to read input file for row_count check {path_str}: {exc}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate promoted Rookie Alpha export and manifest")
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
        print("VALIDATION FAILED")
        for err in errors:
            print(f"- {err}")
        raise SystemExit(1)

    print("VALIDATION PASSED")


if __name__ == "__main__":
    main()
