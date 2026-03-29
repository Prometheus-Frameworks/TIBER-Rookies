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
- WR `production_0_100` now uses `normalization_scope = "historical-wr-cfbd-method-v1"` when scoreable:
  - metric methodology now matches 2026 WR production (YPR + total yards + TD rate, same weights and score transform),
  - population scope does **not** match (15-row historical cohort vs. full CFBD WR population), so compatibility remains blocked.
- WR rows that cannot be scored (opt-out/missing required receiving components/threshold miss/partial-season policy) use `normalization_scope = "historical-wr-cfbd-method-v1-null"` and keep `production_0_100 = null`.
- WR rows preserve prior score in `production_0_100_legacy` to retain traceability to the prior `cross-class-wr-v0` pass.
- Legacy `normalization_anchor` metadata from `cross-class-wr-v0` has been removed from WR rows to avoid stale min/max semantics under the new z-score method.
- `scripts/compute_historical_comps.py` keeps `PRODUCTION_SCOPE_COMPATIBLE` intentionally empty in this pass, so `methodology_compatible` remains `false` by contract.
- `historical-wr-cfbd-method-v1` is intentionally **not** added to the compatible set yet, because population scope parity is not established.
- WR `methodology_compatible` remains false until both metric methodology and population scope are aligned.
- WR `career_outcome_label` and `top_finish_band` are currently deterministic derivations from each player's sourced peak `FPTS/G` (not yet a fully league-ranked finish model).
- The promoted comp artifact now exposes `effective_features_used` per comp row plus `comp_data_warnings` so partial feature overlap is visible in-artifact.
- As a result, current WR similarity behavior is improved versus one-vintage/one-proxy, but remains partial and not UI-ready.


- Current 2026 repro still emits a WR comp-data warning: one historical WR can remain the #1 comp for all eight 2026 WR prospects. This is currently driven by sparse WR RAS coverage and remaining feature-shape compression across partial vintages; do not fabricate rows or synthetic deltas to suppress this warning.

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
