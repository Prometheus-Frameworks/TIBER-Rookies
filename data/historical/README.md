# Historical data lane (scaffold)

This directory is the canonical staging lane for **historical prospect comp inputs**.

The files currently committed here are **schema + partial fixture population** so the contract is explicit and testable in-repo.
WR now includes multiple real draft vintages (2020 + 2021) while QB/TE remain sample scaffolding. This is still not a fully populated historical warehouse.

## Canonical files

- `historical_prospect_features.schema.md`
- `historical_prospect_features.sample.json`
- `historical_player_outcomes.sample.json`

## Current WR pass limitations (intentional for v0)

- WR feature rows now include mixed coverage:
  - 2020 cohort includes sourced `ras_0_100`.
  - Some added WR rows still have `ras_0_100 = null` where clean sourcing was not available in this pass.
  - `size_context_0_100` is a deterministic size percentile context signal built from listed pre-draft height/weight across WR rows in this artifact.
- WR outcome rows for the seeded real cohort now include sourced PPR/G-based snapshots (`best_season_fantasy_ppg`, `years_1_to_3_summary`) plus deterministic label/band derivations.
- WR `production_0_100` is currently `normalization_scope = "class-local"` min-max over sourced receiving-yards values for the draft class slice represented in this artifact.
- Class-local min-max behavior means each represented WR class has a forced `production_0_100 = 0.0` floor at that slice's minimum raw-yardage row, even when the player's absolute production is still strong versus other classes.
- WR `career_outcome_label` and `top_finish_band` are currently deterministic derivations from each player's sourced peak `FPTS/G` (not yet a fully league-ranked finish model).
- The promoted comp artifact now exposes `effective_features_used` per comp row plus `comp_data_warnings` so partial feature overlap is visible in-artifact.
- As a result, current WR similarity behavior is improved versus one-vintage/one-proxy, but remains partial and not UI-ready.


- Current 2026 repro still emits a WR comp-data warning: one historical WR can remain the #1 comp for all eight 2026 WR prospects. This is currently driven by sparse WR RAS coverage and class-local normalization compression across partial vintages; do not fabricate rows or synthetic deltas to suppress this warning.

## Intentional posture

- Deterministic, machine-readable row contracts.
- Explicit `null` values for unavailable historical inputs.
- No fabricated claims of complete historical population.
- Local operators can continue expanding the lane position-by-position with real sourced rows that follow the same row shape.

## Naming note

`*.sample.json` is currently a mixed-state name: WR rows are real-sourced while other position groups in the same files can still be sample-backed. A future cleanup can rename/split files once more position groups are populated.

## Relationship to comp producer

`scripts/compute_historical_comps.py` consumes:

1. a promoted rookie export,
2. historical feature rows from this lane,
3. optional historical outcome rows from this lane.

The script outputs a promoted historical comp artifact at:

- `exports/promoted/historical-comps/{season}_historical_comps_v0.json`
