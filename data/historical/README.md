# Historical data lane (scaffold)

This directory is the canonical staging lane for **historical prospect comp inputs**.

The files currently committed here are **schema + partial fixture population** so the contract is explicit and testable in-repo.
WR is now seeded with a small real historical cohort while QB/TE remain sample scaffolding. This is still not a fully populated historical warehouse.

## Canonical files

- `historical_prospect_features.schema.md`
- `historical_prospect_features.sample.json`
- `historical_player_outcomes.sample.json`

## Current WR pass limitations (intentional for v0)

- WR feature rows currently have `ras_0_100 = null` and `size_context_0_100 = null` across the seeded real cohort.
- WR outcome rows for the seeded real cohort now include sourced PPR/G-based snapshots (`best_season_fantasy_ppg`, `years_1_to_3_summary`) plus deterministic label/band derivations.
- WR `production_0_100` is a **cohort-local min-max normalization** over sourced receiving-yards values; it is a narrow proxy, not a full historical production model.
- WR `career_outcome_label` and `top_finish_band` are currently deterministic derivations from each player's sourced peak `FPTS/G` (not yet a fully league-ranked finish model).
- As a result, current WR similarity behavior is driven by a draft anchor plus narrow production proxy, not a fully populated historical feature set.

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
