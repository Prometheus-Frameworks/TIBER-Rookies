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
  - `model_version`: semantic version for handoff safety (`rookie-alpha-predraft-v0.2.0` adds optional context/evidence fields only)
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
  - `players_with_context_fields` (additive count of players with deterministic context rows attached)
- `source_files_used`: list of artifact file paths used for the run
- `players`: ordered list, highest `rookie_alpha_0_100` first

Player fields:

- `rookie_alpha_rank`
- `talent_rank`: rank within the promoted cohort by talent_score_0_100 descending; ties broken by player_id ascending
- `draft_proxy_delta`: talent_rank minus rookie_alpha_rank; positive = draft capital suppressing score (potential value); negative = draft capital boosting score; zero = no ranking movement
- `player_id`
- `player_name`
- `position`
- `scores`
  - `ras_0_100`
  - `production_0_100`
  - `draft_capital_proxy_0_100`
  - `talent_score_0_100`: RAS and production blended without draft capital proxy (RAS weight 0.4375, production weight 0.5625); null inputs default to 50.0
  - `rookie_alpha_0_100`
- `model_inputs_missing`: list of missing components (`ras`, `production`, `draft_capital_proxy`)
- `context` (optional additive block with deterministic translation/context fields; unavailable values stay `null`)
- `evidence` (optional additive block)
  - `evidence_tags` (fixed vocabulary)
  - `context_flags` (fixed vocabulary)
  - `translation_flags` (fixed surfaced subset for board/detail/compare)
  - `evidence_summary` (template-style deterministic summary)
  - `context_source` (provenance label)

Additive compatibility note:

- Existing score fields and rank behavior are unchanged.
- Rookie Alpha formula/weights are unchanged.
- Consumers may ignore `context` and `evidence` without breaking ingest.

## CSV contract

Columns:

1. `rookie_alpha_rank`
2. `player_id`
3. `player_name`
4. `position`
5. `ras_0_100`
6. `production_0_100`
7. `draft_capital_proxy_0_100`
8. `talent_score_0_100`
9. `rookie_alpha_0_100`
10. `talent_rank`
11. `draft_proxy_delta`
12. `model_inputs_missing`

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

### 2026 temporary pre-draft draft-capital proxy rule

For the real 2026 seed pool, `draft_capital_proxy_0_100` is a temporary pre-draft conversion from seeded `big_board_rank` values. It is explicitly not equivalent to realized NFL draft capital.

Optional deterministic context artifact (additive only):

- `data/processed/2026_prospect_context.json`

Applied deterministic mapping:

- `1–10` => `95`
- `11–20` => `85`
- `21–32` => `75`
- `33–50` => `65`
- `51–75` => `55`
- `76–100` => `45`
- missing or `>100` => `null`

Only entries with a seeded `big_board_rank` are eligible for conversion.

Run from repo root:

```bash
python3 scripts/compute_rookie_alpha.py \
  --season 2026 \
  --combine-input data/raw/2026_combine_results.json \
  --production-input data/processed/2026_college_production.json \
  --draft-proxy-input data/processed/2026_draft_capital_proxy.json \
  --context-input data/processed/2026_prospect_context.json \
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
