# Promoted Export Contract: Rookie Alpha (2026 pre-draft v0)

This repository's primary artifact is a promoted export under:

- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json`
- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.csv`
- `exports/promoted/rookie-alpha/2026_manifest.json`

## JSON contract

Top-level fields:

- `model`
  - `name`: `tiber-rookie-alpha`
  - `stage`: `pre-draft`
  - `label`: `pre-draft v0`
  - `model_version`: semantic version for handoff safety
  - `formula`
    - `ras_weight` (0.35)
    - `production_weight` (0.45)
    - `draft_capital_proxy_weight` (0.20)
    - `age_at_entry_supported` (false in v0)
- `generated_at`: ISO-8601 UTC timestamp
- `run_id`: run identifier shared with manifest
- `season`: integer season, e.g. `2026`
- `coverage_summary`
  - `players_total`
  - `players_with_any_missing_input`
  - `players_with_full_inputs`
- `source_files_used`: list of artifact file paths used for the run
- `players`: ordered list, highest `rookie_alpha_0_100` first

Player fields:

- `rookie_alpha_rank`
- `player_id`
- `player_name`
- `position`
- `scores`
  - `ras_0_100`
  - `production_0_100`
  - `draft_capital_proxy_0_100`
  - `rookie_alpha_0_100`
- `model_inputs_missing`: list of missing components (`ras`, `production`, `draft_capital_proxy`)

## CSV contract

Columns:

1. `rookie_alpha_rank`
2. `player_id`
3. `player_name`
4. `position`
5. `ras_0_100`
6. `production_0_100`
7. `draft_capital_proxy_0_100`
8. `rookie_alpha_0_100`
9. `model_inputs_missing`

CSV is a flattened companion artifact for simpler downstream ingestion.

## Manifest contract (`*_manifest.json`)

Top-level fields:

- `season`
- `model_version`
- `generated_at`
- `run_id`
- `input_files`: list of
  - `path`
  - `sha256`
  - `row_count`
- `coverage_summary`
  - `players_total`
  - `players_with_any_missing_input`
  - `players_with_full_inputs`
- `output_files`: list of
  - `path`
  - `sha256`
- `export_metadata` (must match exactly)
  - `season`
  - `model_version`
  - `generated_at`
  - `run_id`
  - `coverage_summary`
  - `source_files_used`

## Downstream validation requirements

Consumers should reject an export if any of the following fail:

1. Missing companion files (`.json`, `.csv`, manifest).
2. Any input/output file hash mismatch against manifest.
3. `export_metadata` mismatch with manifest top-level metadata.
4. Coverage counts outside expected operating thresholds.

For TIBER-Fantasy specific ingestion gates and CLI validation workflow, see `docs/tiber-fantasy-consumer-contract.md`.
