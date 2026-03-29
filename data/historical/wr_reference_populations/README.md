# Historical WR reference populations

This directory contains optional static WR season populations used by
`scripts/compute_historical_comps.py` to normalize historical WR
`production_0_100` against a season-level reference population.

## File naming

- `{season}_wr_receiving_population.json`
- Example: `2020_wr_receiving_population.json`

## Required row fields

Each row must include:

- `player_name` (string)
- `position` (must be `"WR"`)
- `source_season` (int, should match file season)
- `receptions` (int)
- `receiving_yards` (int)
- `receiving_tds` (int)
- `source_name` (string, e.g. `"CFBD"`)
- `source_url` (string URL provenance)

Only rows with `receptions >= 20` are included in the scoring population.

## Compatibility gate requirements

A season file only unlocks compatibility when at least **100 qualifying WR rows** are present.
If no valid season file is available for a historical WR row's `source_season`, the scorer falls
back to in-cohort normalization (`historical-wr-cfbd-method-v1`) and `methodology_compatible`
remains `false`.
