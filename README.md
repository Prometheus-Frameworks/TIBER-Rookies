# TIBER-Rookies

Standalone rookie grading lab for the **current implemented pre-draft Rookie Alpha model (v0)**.

## Why this repo exists

This repository extracts the rookie scoring path out of TIBER-Fantasy into a minimal, honest handoff artifact pipeline:

- no frontend
- no Express routes
- no Drizzle/Postgres dependency
- no dependency on TIBER-Fantasy runtime services

Primary output is a **promoted export** that TIBER-Fantasy (or any consumer) can ingest later.

## Repository layout

- `README.md`
- `docs/`
  - `architecture.md`
  - `export-contract.md`
- `scripts/`
  - `compute_rookie_alpha.py`
- `data/raw/`
  - combine inputs (example 2026 artifact)
- `data/processed/`
  - college production and draft-capital-proxy artifacts
- `exports/promoted/rookie-alpha/`
  - generated promoted JSON + CSV outputs

## Current model implementation (pre-draft v0)

The formula preserved in this standalone pipeline is:

- **RAS 35%**
- **Production 45%**
- **Draft capital proxy 20%**
- **No age-at-entry support yet**

This is explicitly labeled as `pre-draft v0` in export metadata.

## Inputs

By default, inputs are resolved from the `--season` flag (defaults to current UTC year):

- `data/raw/{season}_combine_results.json`
- `data/processed/{season}_college_production.json`
- `data/processed/{season}_draft_capital_proxy.json`

## Run

```bash
python3 scripts/compute_rookie_alpha.py
```

Optional flags:

```bash
python3 scripts/compute_rookie_alpha.py \
  --season 2026 \
  --combine-input data/raw/2026_combine_results.json \
  --production-input data/processed/2026_college_production.json \
  --draft-proxy-input data/processed/2026_draft_capital_proxy.json \
  --output-json exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
  --output-csv exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.csv
```

## Outputs (promoted contract)

- `exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.json`
- `exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.csv`
- `exports/promoted/rookie-alpha/{season}_manifest.json`

Export metadata includes:

- `model_version`
- `generated_at`
- `run_id`
- `season`
- `coverage_summary`
- `source_files_used`

The manifest is a machine-readable reproducibility record that includes:

- `season`, `model_version`, `generated_at`, `run_id`
- input file paths + SHA-256 hashes + row counts
- output file paths + SHA-256 hashes
- coverage summary and export metadata mirror for consistency checks

Full field-level contract is documented in `docs/export-contract.md`.

## Downstream validation checklist

Before ingesting a promoted export, downstream systems (such as TIBER-Fantasy) should:

1. Confirm all three files exist for the season (`.json`, `.csv`, and `_manifest.json`).
2. Recompute SHA-256 for each listed input/output file and verify hashes exactly match manifest values.
3. Verify manifest and export metadata agree exactly (`season`, `model_version`, `generated_at`, and coverage/source-file metadata).
4. Validate row/coverage expectations from `coverage_summary` before import.

## Known v0 caveats

- Small-group positional samples (especially when very few prospects test) can distort relative RAS separation.
- If any upstream input artifact changes, committed exports must be regenerated so promoted outputs remain in sync with source files.

## How TIBER-Fantasy should consume this later

TIBER-Fantasy should treat this repo as a producer and ingest the promoted JSON export as input data, not as a live service dependency.

Recommended handoff pattern:

1. Run this repo's pipeline for the season.
2. Publish/version the promoted JSON artifact.
3. TIBER-Fantasy import job reads the export and maps by `player_id`.
4. Keep downstream UI/runtime logic separate from this model computation pipeline.

## Future roadmap (not implemented yet)

- Landing spot adjustment phase
- NFL transition blending phase

Those phases should extend the promoted artifact chain without breaking the pre-draft v0 contract.
