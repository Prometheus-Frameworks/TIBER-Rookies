# Promoted Export Contract: Rookie Alpha (pre-draft v0)

The promoted export contract is the authoritative producer output of this repository.

## Canonical promoted path + filename contract

All promoted outputs live in:

- `exports/promoted/rookie-alpha/`

For a given `{season}`, filenames are fixed:

- `{season}_rookie_alpha_predraft_v0.json`
- `{season}_rookie_alpha_predraft_v0.csv`
- `{season}_manifest.json`

Example for season `2026`:

- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json`
- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.csv`
- `exports/promoted/rookie-alpha/2026_manifest.json`

Static rookie prototype routes in this repo may read mapped data derived from these artifacts, but they do not replace this contract as system-of-record output.

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
- `season`: integer season (example: `2026`)
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

CSV is a flattened companion artifact for row-oriented ingestion.

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
- `export_metadata` (must match export metadata exactly)
  - `season`
  - `model_version`
  - `generated_at`
  - `run_id`
  - `coverage_summary`
  - `source_files_used`

## Standard production + validation sequence (2026)

Run from repo root:

```bash
python3 scripts/compute_rookie_alpha.py \
  --season 2026 \
  --combine-input data/raw/2026_combine_results.json \
  --production-input data/processed/2026_college_production.json \
  --draft-proxy-input data/processed/2026_draft_capital_proxy.json \
  --output-json exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
  --output-csv exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.csv \
  --output-manifest exports/promoted/rookie-alpha/2026_manifest.json

python3 scripts/validate_promoted_export.py \
  --export-json exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
  --manifest exports/promoted/rookie-alpha/2026_manifest.json
```

Expected validator output:

```text
VALIDATION PASSED
```

## Downstream validation requirements

Consumers should reject an export if any of the following fail:

1. Missing companion files (`.json`, `.csv`, manifest).
2. Input/output hash mismatch against manifest.
3. `export_metadata` mismatch with manifest top-level metadata.
4. Coverage counts outside expected operating thresholds.

For TIBER-Fantasy-specific ingest gates and CLI workflow, see `docs/tiber-fantasy-consumer-contract.md`.

## Authoritative 2026 real-seed schema and canonical projections

For the 2026 real-seeded batch, `data/raw/2026_real_seed_pool.json` is the sole source of truth. The file is a manually curated transcription source and is projected into the three canonical compute inputs without inference.

### Seed schema (authoritative source file)

Each seed row may contain:

- Identity fields (copied exactly across all projections):
  - `player_id`
  - `player_name`
  - `position`
  - `school`
  - `class_year`
- Combine data + provenance:
  - `combine_invited`
  - `height_in`
  - `height_in_source`
  - `weight_lb`
  - `weight_lb_source`
  - `forty`
  - `forty_source`
  - `vertical`
  - `vertical_source`
  - `broad`
  - `broad_source`
- Production data + provenance:
  - `production_score_0_100`
  - `production_score_source`
- Draft proxy data + provenance:
  - `big_board_rank`
  - `big_board_source`
  - `draft_capital_proxy_0_100`
  - `draft_capital_proxy_source`
  - `draft_capital_proxy_pending_conversion`
- Metadata:
  - `notes`

### Field usage: metadata/provenance vs currently consumed model inputs

- Metadata/provenance fields that may be present but are **not consumed directly** by `scripts/compute_rookie_alpha.py`:
  - `school`
  - `class_year`
  - `combine_invited`
  - all `*_source` fields
  - `big_board_rank`
  - `big_board_source`
  - `draft_capital_proxy_pending_conversion`
  - `notes`
- Fields currently consumed by the compute pipeline:
  - Identity for merge alignment: `player_id`, `player_name`, `position`
  - RAS component inputs: `height_in`, `weight_lb`, `forty`, `vertical`, `broad`
  - Other scoring components: `production_score_0_100`, `draft_capital_proxy_0_100`

### Null policy and pending conversion

- Null numeric values are intentional in real-seed transcription and must remain null in canonical inputs unless explicitly provided by the seed source.
- Numeric values are never auto-filled, inferred, interpolated, or fabricated during projection.
- `big_board_rank` may be present while `draft_capital_proxy_0_100` remains null; in this case `draft_capital_proxy_pending_conversion` should remain `true` to indicate pending explicit conversion.
