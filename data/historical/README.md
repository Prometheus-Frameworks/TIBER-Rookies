# Historical data lane (scaffold)

This directory is the canonical staging lane for **historical prospect comp inputs**.

The files currently committed here are **schema + partial fixture population** so the contract is explicit and testable in-repo.
WR now includes multiple real draft vintages (2018 + 2020 + 2021) while QB/TE remain sample scaffolding. This is still not a fully populated historical warehouse.

## Canonical files

- `historical_prospect_features.schema.md`
- `historical_prospect_features.sample.json`
- `historical_player_outcomes.sample.json`
- `wr_reference_populations/README.md`
- `wr_reference_populations/template_wr_receiving_population.json`

## Current WR pass limitations (intentional for v0)

- WR feature rows now include mixed coverage:
  - 2020 cohort includes sourced `ras_0_100`.
  - Some added WR rows still have `ras_0_100 = null` where clean sourcing was not available in this pass.
  - `size_context_0_100` is a deterministic height/weight percentile signal. Formula: `50 + composite_z * 15` where `composite_z = 0.55 * height_z + 0.45 * weight_z` against WR reference anchors (72.5 in / 197 lb). Historical WR rows were seeded from the same ingredients; 2026 rookie WR scores are sourced from `data/raw/2026_combine_results.json`.
- WR outcome rows for the seeded real cohort now include sourced PPR/G-based snapshots (`best_season_fantasy_ppg`, `years_1_to_3_summary`) plus deterministic label/band derivations.
- WR `production_0_100` now uses `normalization_scope = "historical-wr-cfbd-method-v1"` when scoreable:
  - metric methodology now matches 2026 WR production (YPR + total yards + TD rate, same weights and score transform),
  - population scope does **not** match by default (in-repo WR cohort fallback vs. full CFBD WR population), so compatibility remains blocked unless valid season population files are added.
- WR rows that cannot be scored (opt-out/missing required receiving components/threshold miss/partial-season policy) use `normalization_scope = "historical-wr-cfbd-method-v1-null"` and keep `production_0_100 = null`.
- WR rows preserve prior score in `production_0_100_legacy` to retain traceability to the prior `cross-class-wr-v0` pass.
- Legacy `normalization_anchor` metadata from `cross-class-wr-v0` has been removed from WR rows to avoid stale min/max semantics under the new z-score method.
- Historical WR season population infrastructure now exists at `data/historical/wr_reference_populations/`:
  - file pattern: `{season}_wr_receiving_population.json`,
  - minimum bar for compatibility: >=100 sourced WR rows (with `receptions >= 20`) for each target season,
  - current committed state: 2019/2020/2021 population files are populated (560/379/567 qualifying rows respectively); `methodology_compatible["WR"]` is `true` when these files are present.
- `scripts/compute_historical_comps.py` assigns `normalization_scope = "historical-wr-cfbd-season-pop-v1"` to scored WR rows when a valid season population is loaded; null-scored rows (opt-out / partial-season) retain `"historical-wr-cfbd-method-v1-null"`, which is included in the compatible set alongside `WR_POPULATION_SCOPE` when populations are active.
- WR `career_outcome_label` and `top_finish_band` are currently deterministic derivations from each player's sourced peak `FPTS/G` (not yet a fully league-ranked finish model).
- The promoted comp artifact now exposes `effective_features_used` per comp row plus `comp_data_warnings` so partial feature overlap is visible in-artifact.
- As a result, current WR similarity behavior is improved versus one-vintage/one-proxy, but remains partial and not UI-ready.


- Current 2026 repro emits a WR comp-data warning (coverage / partial lane): comp concentration dropped to max 3 prospects per #1 comp after `size_context_0_100` was added to the 2026 rookie WR profiles. The lane remains directional-only until broader cross-class and outcomes coverage is added; do not fabricate rows or synthetic deltas to suppress the warning.


- 2018 WR cohort was added with source season 2017 (D.J. Moore, Calvin Ridley, Courtland Sutton, Christian Kirk).
  - `production_0_100` is intentionally left null in the input rows and computed by pipeline methodology.
  - `production_0_100_legacy` is intentionally absent for new 2018 rows because there is no prior cross-class seed score for that cohort.
  - `ras_0_100` remains null only for D.J. Moore in this pass due to approved-source constraints; other 2018 rows use player-level ras.football sourcing.
- A 2017 WR reference population placeholder file is committed as an empty array (`data/historical/wr_reference_populations/2017_wr_receiving_population.json`).
  - This keeps fallback behavior active for source season 2017 and therefore keeps `methodology_compatibility_by_position["WR"] = false` until local operators fetch/populate 2017 data.
  - To restore WR methodology compatibility locally, run `python scripts/fetch_wr_reference_populations.py --years 2017` and commit the populated file.

## Intentional posture

- Deterministic, machine-readable row contracts.
- Explicit `null` values for unavailable historical inputs.
- WR `ras_0_100` backfill is player-level only: acceptable sources are a player-specific `ras.football` page or a player Wikipedia page that explicitly states that player's RAS; team pages, roster tables, and compilation/roundup pages are explicitly excluded.
- No fabricated claims of complete historical population.
- Partial-season policy: if a row reflects an injury-curtailed season (`< 6` games), keep sourced raw stats but leave `production_0_100` null and annotate in `notes`. In this committed WR slice, no row is currently tagged with an injury-curtailed partial-season override.
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
