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
  - `draft_capital_proxy_0_100`: **market investment context only** — normalized from overall NFL draft pick or pre-draft big board rank (all positions). Not suitable as a positional consensus comparison target because overall boards include defenders, OL, and QBs that crowd skill-position slots. Kept as a market-investment signal.
  - `talent_score_0_100`: RAS and production blended without draft capital proxy (RAS weight 0.4375, production weight 0.5625); null inputs default to 50.0
  - `rookie_alpha_0_100`
  - `consensus_position_rank_blended`: blended positional rank from all available positional consensus sources (integer; `null` when no source data). E.g. `1` = consensus WR1/RB1/etc. for this class.
  - `consensus_position_rank_sources_count`: number of consensus sources contributing to the blended rank (`null` when no data).
  - `consensus_score_positional_0_100`: expected score on the 0-100 alpha scale for a player at their blended positional consensus rank, derived from per-position rank curves. **This is the correct comparison target for model vs. consensus.** `null` when no positional source data.
  - `consensus_delta_positional`: `rookie_alpha_0_100 − consensus_score_positional_0_100`. Positive = model more bullish than positional consensus; negative = model more bearish. `null` when no positional source data. **This replaces `consensus_delta` as the canonical model-vs-consensus signal.**
  - `market_investment_delta_legacy`: **(deprecated)** formerly `consensus_delta`. `rookie_alpha_0_100 − draft_capital_proxy_0_100`. Structurally misleading for positional interpretation — overall draft capital compresses skill-player slots against defenders and QBs. Retained for backward compatibility only; consumers should migrate to `consensus_delta_positional`.
- `model_inputs_missing`: list of missing components (`ras`, `production`, `draft_capital_proxy`)
- `context` (optional additive block with deterministic translation/context fields; unavailable values stay `null`)
- `evidence` (optional additive block)
  - `evidence_tags` (fixed vocabulary)
  - `context_flags` (fixed vocabulary)
  - `translation_flags` (fixed surfaced subset for board/detail/compare)
  - `evidence_summary` (template-style deterministic summary)
  - `context_source` (provenance label)

### Semantic distinction: market investment vs. positional consensus

These are two different concepts and must not be conflated:

| Field | What it measures | Basis |
|---|---|---|
| `draft_capital_proxy_0_100` | Market investment / overall board slot | Overall NFL draft pick or big-board rank (all positions) |
| `consensus_score_positional_0_100` | Positional consensus quality expectation | Positional rank (WR1, RB1…) mapped through per-position score curves |
| `consensus_delta_positional` | TIBER vs. positional consensus | `alpha − consensus_score_positional` |
| `market_investment_delta_legacy` | (deprecated) alpha vs. overall draft capital | `alpha − draft_capital_proxy` — structurally biased for skill players |

Additive compatibility note:

- Existing score fields and rank behavior are unchanged.
- Rookie Alpha formula/weights are unchanged.
- Consumers may ignore `context` and `evidence` without breaking ingest.
- `consensus_delta_positional` is `null` for players without positional consensus source data.

## CSV contract

Columns:

1. `rookie_alpha_rank`
2. `player_id`
3. `player_name`
4. `position`
5. `ras_0_100`
6. `athletic_score_0_100`
7. `athletic_source`
8. `production_0_100`
9. `draft_capital_proxy_0_100`
10. `talent_score_0_100`
11. `rookie_alpha_0_100`
12. `consensus_position_rank_blended`
13. `consensus_score_positional_0_100`
14. `consensus_delta_positional`
15. `market_investment_delta_legacy` *(deprecated; formerly `consensus_delta`)*
16. `talent_rank`
17. `draft_proxy_delta`
18. `model_inputs_missing`
19. `market_conviction_ras_override`
20. `wr_translation_penalty`

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
  --positional-consensus-input data/processed/2026_positional_consensus.json \
  --output-json exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
  --output-csv exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.csv \
  --output-manifest exports/promoted/rookie-alpha/2026_manifest.json

python3 scripts/validate_promoted_export.py \
  --export-json exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
  --manifest exports/promoted/rookie-alpha/2026_manifest.json
```

The `--positional-consensus-input` flag defaults to `data/processed/{season}_positional_consensus.json` when omitted. When the file is absent, all positional consensus fields (`consensus_position_rank_blended`, `consensus_score_positional_0_100`, `consensus_delta_positional`) are `null` in the export.

### Positional consensus input format

Positional consensus data lives in `data/processed/{season}_positional_consensus.json`. The schema supports multiple sources per class year so blending improves as more boards are ingested:

```json
{
  "class_year": 2026,
  "sources": [
    {
      "source": "source_name",
      "snapshot_date": "YYYY-MM-DD",
      "notes": "Human-readable provenance description",
      "entries": [
        {
          "player_id": "wr-jordyn-tyson",
          "player_name": "Jordyn Tyson",
          "position": "WR",
          "positional_rank": 1,
          "overall_rank": 6
        }
      ]
    }
  ]
}
```

When multiple sources are present, ranks are averaged (mean) and rounded to the nearest integer for `consensus_position_rank_blended`.

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
