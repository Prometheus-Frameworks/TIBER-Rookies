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
  "similarity_quality_by_position": {
    "WR": {
      "status": "directional_only",
      "reason": "metric methodology matches; population scope incompatible (in-repo WR cohort fallback vs. full CFBD season population); lane warning present",
      "requirements_checked": {
        "no_lane_warning": false,
        "min_effective_feature_count_met": true,
        "outcomes_present": true,
        "non_market_dimension_present": true,
        "methodology_compatible": false
      }
    }
  },
  "methodology_compatibility_by_position": {
    "WR": false
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
  - `production_0_100_legacy` (WR-only; present when method-v1 replacement occurs)
  - `receptions` (WR-only)
  - `receiving_yards` (WR-only)
  - `receiving_tds` (WR-only)
- `effective_features_used` (array of strings): exact non-null feature keys actually used in this comparison distance
- `outcome_snapshot` (object | null)
  - `career_outcome_label`
  - `best_season_fantasy_ppg`
  - `top_finish_band`
  - `years_1_to_3_summary`


## UI gating field (`ui_display_allowed`)

Producer emits an additive top-level field:

```json
"ui_display_allowed": {
  "WR": false,
  "QB": false
}
```

Shape and semantics:

- Object keyed by position string.
- Value is a conservative boolean computed per position.
- `true` is allowed **only** when all conditions below hold for that position:
  1. `comp_data_warnings` has no entry for the position (or warnings object is empty),
  2. every emitted comp has `effective_features_used` length `>= 2`,
  3. every emitted comp has non-null `outcome_snapshot.career_outcome_label`,
  4. every emitted comp includes at least one non-market dimension in `effective_features_used` (`ras_0_100` or `size_context_0_100`),
  5. the position is methodology-compatible with current production normalization.
- Any uncertainty or failed condition must resolve to `false`.

Consumer requirement:

- Downstream/UI consumers must check `ui_display_allowed[position]` before surfacing comps in any UI flow.
- Binary gating alone is insufficient. Consumers should also read `similarity_quality_by_position[position]` to understand *why* a lane is blocked or partial.

## Similarity quality signaling (`similarity_quality_by_position`)

Producer emits an additive top-level field:

```json
"similarity_quality_by_position": {
  "WR": {
    "status": "directional_only",
    "reason": "no_lane_warning: false; methodology_compatible: false",
    "requirements_checked": {
      "no_lane_warning": false,
      "min_effective_feature_count_met": true,
      "outcomes_present": true,
      "non_market_dimension_present": true,
      "methodology_compatible": false
    }
  }
}
```

Status derivation rules:

- `ui_safe`: all five booleans in `requirements_checked` are true.
- `directional_only`: `no_lane_warning` is false **or** `methodology_compatible` is false.
- `partial`: both hard blockers above pass, but at least one remaining check fails.

Field definitions in `requirements_checked`:

1. `no_lane_warning`: no entry for that position in `comp_data_warnings`.
2. `min_effective_feature_count_met`: every emitted comp for the position has at least two features in `effective_features_used`.
3. `outcomes_present`: every emitted comp has non-null `outcome_snapshot.career_outcome_label`.
4. `non_market_dimension_present`: every emitted comp includes at least one of `ras_0_100` or `size_context_0_100` in `effective_features_used`.
5. `methodology_compatible`: all historical feature rows for the position have `normalization_scope` values in `PRODUCTION_SCOPE_COMPATIBLE`.

`reason` is always a non-empty string that enumerates failed checks (`<check>: false; ...`) or `all_checks_passed`.
For WR in the current v1 pass, reason is explicitly pinned to: `metric methodology matches; population scope incompatible (in-repo WR cohort fallback vs. full CFBD season population); lane warning present`.

## Methodology compatibility projection (`methodology_compatibility_by_position`)

Producer emits:

```json
"methodology_compatibility_by_position": {
  "WR": false,
  "QB": false
}
```

This field is a convenience projection from:

- `similarity_quality_by_position[position].requirements_checked.methodology_compatible`

It must not be independently computed from different logic.

## Comp modes

- `talent_comp` (default v0 output): weighted by athleticism + production + optional size context.
- `market_comp` (deferred output mode but supported in script): uses explicit normalized weights that sum to 1.0 (`ras=0.35`, `production=0.35`, `size_context=0.10`, `draft_capital_proxy=0.20`).

## Historical WR reference population infrastructure

- Optional static reference files are read from `data/historical/wr_reference_populations/{season}_wr_receiving_population.json`.
- Required fields per row: `player_name`, `position`, `source_season`, `receptions`, `receiving_yards`, `receiving_tds`, `source_name`, `source_url`.
- A file is considered valid for compatibility only when at least 100 rows qualify (`position == "WR"`, `receptions >= 20`, and sourced provenance present).
- When valid population files are present for a row's `source_season`, WR rows are normalized using scope `historical-wr-cfbd-season-pop-v1`.
- When absent, scoring falls back to `historical-wr-cfbd-method-v1` / `historical-wr-cfbd-method-v1-null` and compatibility remains conservative.

## WR production harmonization scope (historical-wr-cfbd-method-v1)

- Historical WR rows now compute `production_0_100` using the same **metric methodology** as `scripts/compute_production_scores.py` for 2026 WR:
  - threshold: `receptions >= 20`,
  - metrics: `yards_per_reception`, `total_yards`, `td_rate`,
  - z-composite: `0.40*ypr_z + 0.35*total_yards_z + 0.25*td_rate_z`,
  - transform: `max(0.0, min(100.0, round(50.0 + (z * 15.0), 1)))`.
- Population scope remains intentionally different in this pass:
  - historical WR z-scores use the in-repo WR cohort fallback unless a valid season population file is provided (not full-season CFBD population by default),
  - therefore `methodology_compatibility_by_position.WR` remains `false`.
- `normalization_scope` values:
  - `historical-wr-cfbd-method-v1`: row met the raw-stat and threshold requirements and has a computed replacement score.
  - `historical-wr-cfbd-method-v1-null`: row could not be scored (opt-out / missing stat component / threshold miss / partial-season policy).

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
- `production_0_100` includes an explicit `normalization_scope` marker (`historical-wr-cfbd-method-v1`, `historical-wr-cfbd-method-v1-null`, or `historical-wr-cfbd-season-pop-v1` when valid population files exist).
- `career_outcome_label` and `top_finish_band` for seeded WR rows are deterministic peak-`FPTS/G` bucket derivations, not yet a league-wide finalized finish model.
- `effective_features_used` must be used when reading similarities; metadata weights are not equivalent to active dimensions for every row.

Interpret current WR comp similarities accordingly: upgraded beyond one-vintage/one-proxy behavior, but still not a fully featured historical nearest-neighbor space and still blocked for UI surfacing.

## Local population posture

Because sandbox environments may not populate live historical APIs, this contract supports local operator population of historical files with real data while preserving the exact same row shape and artifact interface.

The committed `exports/promoted/historical-comps/2026_historical_comps_v0.json` file is now partially populated with real WR historical cohort rows while other positions may still be scaffold/sample-backed. It is not yet a fully populated historical warehouse artifact.
