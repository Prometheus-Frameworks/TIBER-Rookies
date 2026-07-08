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
    "WR": "artifact-visible caveat string that appears only when WR lane coverage thresholds fail"
  },
  "lane_coverage_by_position": {
    "WR": {
      "total_promoted_wrs": 8,
      "rookie_wr_with_comps": 8,
      "max_top1_count": 3,
      "unique_top1_count": 4,
      "unique_comp_pool_count": 9,
      "all_comps_count": 40,
      "all_comps_with_3plus_features_count": 23,
      "top1_comps_count": 8,
      "top1_comps_with_3plus_features_count": 3,
      "pct_all_comps_with_3plus_features": 0.575,
      "pct_top1_comps_with_3plus_features": 0.375,
      "coverage_sufficient": false,
      "failed_checks": [
        "unique_top1_count",
        "pct_all_comps_with_3plus_features",
        "pct_top1_comps_with_3plus_features"
      ]
    }
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
- Clearing WR lane warning **alone** does not imply `ui_display_allowed["WR"] == true`; methodology compatibility and every other gating check still apply.

## WR lane coverage diagnostics (`lane_coverage_by_position.WR`)

Producer now emits deterministic WR lane diagnostics used for warning gating:

- `coverage_sufficient` is true only if all six checks pass:
  1. `rookie_wr_with_comps == total_promoted_wrs`
  2. `max_top1_count <= 3`
  3. `unique_top1_count >= 5`
  4. `unique_comp_pool_count >= 8`
  5. `pct_all_comps_with_3plus_features >= 0.75`
  6. `pct_top1_comps_with_3plus_features >= 0.50`
- If any check fails:
  - `comp_data_warnings["WR"]` is present and includes `failed_checks`,
  - `lane_coverage_by_position.WR.failed_checks` enumerates the failing threshold names.
- If all checks pass:
  - `comp_data_warnings["WR"]` is omitted from the artifact.

This warning answers lane breadth/differentiation only; it must not be conflated with methodology compatibility checks.

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
4. `non_market_dimension_present`: every emitted comp includes at least one of `ras_0_100` or `size_context_0_100` in `effective_features_used`. Note: for the current WR lane this check passes via `size_context_0_100`, not `ras_0_100` — `ras_0_100` remains null for 8/15 historical WR rows and does not appear in WR comp `effective_features_used`.
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
- Historical WR cohort coverage now includes draft classes 2018, 2020, and 2021 (with 2018 sourced from source season 2017).
- Required fields per row: `player_name`, `position`, `source_season`, `receptions`, `receiving_yards`, `receiving_tds`, `source_name`, `source_url`.
- A file is considered valid for compatibility only when at least 100 rows qualify (`position == "WR"`, `receptions >= 20`, and sourced provenance present).
- When valid population files are present for a row's `source_season`, WR rows are normalized using scope `historical-wr-cfbd-season-pop-v1`.
- When absent, scoring falls back to `historical-wr-cfbd-method-v1` / `historical-wr-cfbd-method-v1-null` and compatibility remains conservative.

## Historical TE reference population infrastructure

- Optional static reference files are read from `data/historical/te_reference_populations/{season}_te_receiving_population.json`.
- Required fields per row: `player_name`, `position`, `source_season`, `receptions`, `receiving_yards`, `receiving_tds`, `source_name`, `source_url`.
- A file is considered valid for compatibility only when at least 30 rows qualify (`position` in `{"TE", "H-BACK", "FB"}`, `receptions >= 20`, and sourced provenance present).
- **Quarantine status (issue [#257](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/257)):** all five committed season files are currently empty (`[]`). The previously committed content was found to be WR reference-population rows with only `position` relabeled to `"TE"` — see `data/historical/te_reference_populations/README.md` for the full investigation. No valid TE season population currently exists anywhere in this repository's history, so `methodology_compatibility_by_position.TE` and `similarity_quality_by_position.TE.status` should not be treated as `true`/`ui_safe` until real CFBD TE data is fetched and populated.
- When absent (as is currently the case), TE scoring falls back to `historical-te-cfbd-method-v1` / `historical-te-cfbd-method-v1-null` and compatibility remains conservative, the same treatment already applied to WR when no population file is present.

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

**Resolved (issue #259):** the artifact was regenerated from current inputs. TE now correctly
shows `methodology_compatibility_by_position.TE: false` /
`similarity_quality_by_position.TE.status: "directional_only"` /
`ui_display_allowed.TE: false`, confirming the issue #257 reference-population quarantine reached
the actual promoted export, not just the docs. Per-comp `feature_snapshot.normalization_scope`
for TE historical comps changed from `historical-te-cfbd-season-pop-v1` (the corrupted
population) to the conservative in-cohort fallback `historical-te-cfbd-method-v1`.

Regenerating also pulled in unrelated, pre-existing rookie-alpha drift (the rookie-alpha
predraft export had grown by ~28 players since this artifact was last generated): WR rookie
count went from 8 to 23 and TE from 3 to 11. As a side effect, **WR also lost its `ui_safe`
status** (`similarity_quality_by_position.WR.status` is now `directional_only`,
`ui_display_allowed.WR: false`) — this is unrelated to the TE quarantine and reflects that the
larger current WR rookie pool has genuinely insufficient comp/feature-depth coverage against the
historical cohort (`lane_coverage_by_position.WR.coverage_sufficient: false`). See
`docs/reports/2026-07-08-historical-comps-regeneration.md` for the full before/after diff.
