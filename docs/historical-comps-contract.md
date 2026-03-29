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

## Local population posture

Because sandbox environments may not populate live historical APIs, this contract supports local operator population of historical files with real data while preserving the exact same row shape and artifact interface.

The committed `exports/promoted/historical-comps/2026_historical_comps_v0.json` file is now partially populated with real WR historical cohort rows while other positions may still be scaffold/sample-backed. It is not yet a fully populated historical warehouse artifact.
