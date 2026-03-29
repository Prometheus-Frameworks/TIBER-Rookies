# Historical data lane (scaffold)

This directory is the canonical staging lane for **historical prospect comp inputs**.

The files currently committed here are **schema + partial fixture population** so the contract is explicit and testable in-repo.
WR is now seeded with a small real historical cohort while QB/TE remain sample scaffolding. This is still not a fully populated historical warehouse.

## Canonical files

- `historical_prospect_features.schema.md`
- `historical_prospect_features.sample.json`
- `historical_player_outcomes.sample.json`

## Intentional posture

- Deterministic, machine-readable row contracts.
- Explicit `null` values for unavailable historical inputs.
- No fabricated claims of complete historical population.
- Local operators can continue expanding the lane position-by-position with real sourced rows that follow the same row shape.

## Relationship to comp producer

`scripts/compute_historical_comps.py` consumes:

1. a promoted rookie export,
2. historical feature rows from this lane,
3. optional historical outcome rows from this lane.

The script outputs a promoted historical comp artifact at:

- `exports/promoted/historical-comps/{season}_historical_comps_v0.json`
