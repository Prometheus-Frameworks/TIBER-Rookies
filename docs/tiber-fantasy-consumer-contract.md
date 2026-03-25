# TIBER-Fantasy Consumer Contract (Rookie Alpha promoted export)

This document defines the **ingestion gate** for TIBER-Fantasy before importing a promoted Rookie Alpha artifact.

## Required files

For a season (example `2026`), TIBER-Fantasy ingestion requires all artifacts below from `exports/promoted/rookie-alpha/`:

1. `{season}_rookie_alpha_predraft_v0.json` (authoritative model export)
2. `{season}_rookie_alpha_predraft_v0.csv` (flat companion)
3. `{season}_manifest.json` (reproducibility + integrity record)
4. Optional convenience file: `{season}_rookie_alpha_predraft_v0.consumer_view.json` (normalized downstream view)

If any required file is missing, ingestion must fail fast.

## Required validation steps

Run validation before ingest:

```bash
python3 scripts/validate_promoted_export.py \
  --export-json exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
  --manifest exports/promoted/rookie-alpha/2026_manifest.json
```

Validation requirements:

1. Manifest and export are valid JSON objects.
2. Required top-level fields exist in both files.
3. Manifest metadata and export metadata match exactly.
4. Hashes listed in `manifest.input_files` and `manifest.output_files` match recomputed SHA-256 values.
5. Where `row_count` is present, JSON input row counts match the manifest.

## Expected metadata checks

The following values must be identical across export and manifest:

- `season`
- `model_version`
- `generated_at`
- `run_id`
- `coverage_summary`
- `source_files_used` (export) vs input file `path` sequence (manifest)

## Failure conditions

Treat any condition below as a hard ingest failure:

- Missing required files
- Export/manifest parse errors
- Required field omissions
- `export_metadata` mismatch
- Input hash mismatch
- Output hash mismatch
- Input `row_count` mismatch

Suggested downstream behavior: reject ingest, log full validation errors, and request a regenerated promoted export.

## Consumer-ready normalized view (optional convenience)

The promoted JSON is authoritative but nests scores under `players[].scores`, which can be awkward for consumers that want row-oriented ingestion.

A minimal optional convenience artifact is provided:

- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.consumer_view.json`

This file is non-authoritative and should only be used after the promoted export + manifest pass validation.
