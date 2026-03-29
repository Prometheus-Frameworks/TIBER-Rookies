# Historical comps promoted artifact contract (v0 scaffold)

This contract defines the producer-only historical comps artifact.

## Output path

- `exports/promoted/historical-comps/{season}_historical_comps_v0.json`

Example:

- `exports/promoted/historical-comps/2026_historical_comps_v0.json`

## Scope boundary

- This contract is for **producer output only**.
- Static rookie UI wiring is intentionally out of scope for this phase.

## Top-level shape

```json
{
  "model": {
    "name": "historical_comps",
    "model_version": "v0",
    "comp_mode": "talent_comp",
    "distance_model": "weighted_euclidean",
    "weights": {
      "ras_0_100": 0.45,
      "production_0_100": 0.45,
      "size_context_0_100": 0.1
    },
    "notes": "v0 emits talent_comp by default; market_comp support is scaffolded and optional."
  },
  "generated_at": "ISO-8601 UTC timestamp",
  "season": 2026,
  "source_files_used": [
    "exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json",
    "data/historical/historical_prospect_features.sample.json",
    "data/historical/historical_player_outcomes.sample.json"
  ],
  "comp_data_warnings": {
    "WR": "artifact-visible caveat string for partial lane quality (and explicit non-differentiation warning when #1 comp concentration exceeds threshold)"
  },
  "players": [
    {
      "player_id": "...",
      "player_name": "...",
      "position": "QB",
      "comp_mode": "talent_comp",
      "comps": []
    }
  ]
}
```

## Per-player comp row shape

Each row in `players[].comps[]`:

- `historical_player_id` (string)
- `player_name` (string)
- `draft_year` (number)
- `position` (string)
- `similarity_score` (number, 0-100; higher is better)
- `distance` (number | null; null means no comparable shared features)
- `feature_snapshot` (object)
  - `ras_0_100`
  - `production_0_100`
  - `draft_capital_proxy_0_100`
  - `size_context_0_100`
  - `normalization_scope`
- `effective_features_used` (array of strings): exact non-null feature keys actually used in this comparison distance
- `outcome_snapshot` (object | null)
  - `career_outcome_label`
  - `best_season_fantasy_ppg`
  - `top_finish_band`
  - `years_1_to_3_summary`

## Comp modes

- `talent_comp` (default v0 output): weighted by athleticism + production + optional size context.
- `market_comp` (deferred output mode but supported in script): uses explicit normalized weights that sum to 1.0 (`ras=0.35`, `production=0.35`, `size_context=0.10`, `draft_capital_proxy=0.20`).

## Validation expectations

Producer must validate:

1. rookie export has required fields (`player_id`, `player_name`, `position`, `scores`),
2. historical feature rows include required canonical fields,
3. historical outcome rows include required canonical fields when provided,
4. matching is position-only,
5. candidates with no shared comparable feature values are excluded (no zero-score/no-distance pseudo-comps),
6. similarity ordering is deterministic (stable tie-break by `historical_player_id`),
7. artifact is machine-readable JSON and deterministic for identical inputs and `generated_at`.


## Current WR cohort caveat (v0)

The seeded real WR cohort in `data/historical/historical_prospect_features.sample.json` remains partial, but now spans more than one vintage:

- WR rows now include 2020 and 2021 class coverage in this artifact slice.
- 2020 WR rows include sourced `ras_0_100`; some later rows preserve `ras_0_100 = null` where clean sourcing was not available.
- `size_context_0_100` is now populated as a deterministic height/weight percentile context dimension.
- Outcome fields for the seeded real WR cohort are now partially populated from sourced FantasyData PPR season rows.
- `production_0_100` includes an explicit `normalization_scope` marker (currently class-local for WR rows in this pass), and should not be assumed cross-class comparable unless scope states so.
- `career_outcome_label` and `top_finish_band` for seeded WR rows are deterministic peak-`FPTS/G` bucket derivations, not yet a league-wide finalized finish model.
- `effective_features_used` must be used when reading similarities; metadata weights are not equivalent to active dimensions for every row.

Interpret current WR comp similarities accordingly: upgraded beyond one-vintage/one-proxy behavior, but still not a fully featured historical nearest-neighbor space and still blocked for UI surfacing.

## Local population posture

Because sandbox environments may not populate live historical APIs, this contract supports local operator population of historical files with real data while preserving the exact same row shape and artifact interface.

The committed `exports/promoted/historical-comps/2026_historical_comps_v0.json` file is now partially populated with real WR historical cohort rows while other positions may still be scaffold/sample-backed. It is not yet a fully populated historical warehouse artifact.
