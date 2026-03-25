# TIBER-Fantasy Consumer Contract (Rookie Alpha promoted export)

This document defines the **ingestion gate** for TIBER-Fantasy before importing a promoted Rookie Alpha artifact.

## Required files

For a season (example `2026`), TIBER-Fantasy ingestion requires all artifacts below from `exports/promoted/rookie-alpha/`:

1. `{season}_rookie_alpha_predraft_v0.json` (authoritative model export)
2. `{season}_rookie_alpha_predraft_v0.csv` (flat companion)
3. `{season}_manifest.json` (reproducibility + integrity record)

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

## Consumer-ready normalized view (optional, derived)

The promoted JSON is authoritative but nests scores under `players[].scores`, which can be awkward for consumers that want row-oriented ingestion.

To avoid stale committed snapshots, consumers should derive a normalized view at ingest time (or in their own pipeline) rather than relying on a checked-in `.consumer_view.json` file.

Recommended normalized row shape:

```json
{
  "season": 2026,
  "model_version": "rookie-alpha-predraft-v0.1.0",
  "generated_at": "2026-03-25T01:46:12+00:00",
  "run_id": "rookie-alpha-2026-2026-03-25T01:46:12+00:00",
  "players": [
    {
      "rookie_alpha_rank": 1,
      "player_id": "wr-example",
      "player_name": "Example Player",
      "position": "WR",
      "rookie_alpha_0_100": 77.0,
      "ras_0_100": 62.0,
      "production_0_100": 88.0,
      "draft_capital_proxy_0_100": 82.0,
      "model_inputs_missing": [],
      "has_full_inputs": true
    }
  ]
}
```
