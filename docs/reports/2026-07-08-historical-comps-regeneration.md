# Historical-Comps Export Regeneration

**Date:** 2026-07-08
**Issue:** [#259](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/259)
**Follow-up to:** [#257](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/257) /
`docs/reports/2026-07-08-te-reference-population-repair.md`

## What changed

Ran `python3 scripts/compute_historical_comps.py` (default arguments — current rookie-alpha
predraft export, current historical features/outcomes, current reference population
directories) and committed the regenerated
`exports/promoted/historical-comps/2026_historical_comps_v0.json`.

- Previous `generated_at`: `2026-04-03T20:39:43+00:00`
- New `generated_at`: `2026-07-08T21:35:14+00:00`
- `model` block (weights, distance model, comp mode) is unchanged.
- No player was removed; 28 new players were added (players present in both versions are
  unchanged in identity — `player_id` sets are a strict superset).

Full test suite (`pytest`, 380 tests) passes.

## Change 1: TE quarantine reaches the promoted export (the actual goal of this issue)

| Field | Before | After |
|---|---|---|
| `methodology_compatibility_by_position.TE` | `true` | `false` |
| `similarity_quality_by_position.TE.status` | `"ui_safe"` | `"directional_only"` |
| `similarity_quality_by_position.TE.reason` | `"all_checks_passed"` | `"no_lane_warning: false; methodology_compatible: false"` |
| `ui_display_allowed.TE` | `true` | `false` |
| Per-comp `feature_snapshot.normalization_scope` for TE historical comps (e.g. the top comp for `te-eli-stowers`) | `"historical-te-cfbd-season-pop-v1"` (TE_POPULATION_SCOPE — the corrupted reference population) | `"historical-te-cfbd-method-v1"` (conservative in-cohort fallback) |
| TE rookies covered | 3 | 11 |

This is the direct, verified confirmation that issue #257's quarantine (emptying
`data/historical/te_reference_populations/*.json`) reached the artifact that downstream
consumers actually read — not just the documentation. Before this regeneration, the promoted
JSON file itself still asserted TE was `ui_safe` on the strength of data that no longer exists;
it no longer does.

## Change 2: unrelated rookie-alpha drift (pre-existing, not caused by the TE fix)

The committed artifact was last generated 2026-04-03, roughly nine commits before the current
rookie-alpha predraft export. Regenerating against current inputs surfaced that drift:

| Field | Before | After |
|---|---|---|
| `lane_coverage_by_position.WR.total_promoted_wrs` | 8 | 23 |
| `lane_coverage_by_position.WR.coverage_sufficient` | `true` | `false` |
| `lane_coverage_by_position.WR.failed_checks` | `[]` | `rookie_wr_with_comps, max_top1_count, unique_top1_count, pct_all_comps_with_3plus_features, pct_top1_comps_with_3plus_features` |
| `comp_data_warnings.WR` | absent | `"WR lane coverage is insufficient for differentiation breadth/feature depth checks..."` |
| `similarity_quality_by_position.WR.status` | `"ui_safe"` | `"directional_only"` |
| `ui_display_allowed.WR` | `true` | `false` |
| `lane_coverage_by_position.TE.total_promoted_tes` | 3 | 11 |

**This WR regression is not related to the TE reference-population quarantine.**
`methodology_compatibility_by_position.WR` is still `true` — the WR reference-population
methodology itself is unaffected. What changed is that the current (larger) WR rookie pool has
genuinely weaker comp/feature-depth coverage against the historical cohort than the smaller
pool this artifact was last generated against. QB and RB were already `directional_only` before
and after this regeneration (no change in their gating status).

This is recorded here as a separate, pre-existing data-coverage finding per this issue's
requirement to distinguish it from the TE-quarantine effect. Per this issue's hard boundary, no
scoring or gating logic was changed to address it — it is reported, not fixed, here.

## Verification performed

- Confirmed `data/historical/te_reference_populations/*.json` are still quarantined (`[]`)
  before regenerating.
- Diffed the full before/after JSON programmatically (top-level keys, per-position gating
  fields, player ID sets, and per-comp `normalization_scope` for a shared TE player) to isolate
  which changes trace to the TE quarantine versus which trace to rookie-alpha drift.
- Two pre-existing tests in `tests/test_compute_historical_comps.py`
  (`test_similarity_quality_wr_ui_safe_when_coverage_is_sufficient` and
  `test_artifact_wr_contract_flags_align_with_ui_safe_status`) asserted the real committed
  export's WR lane was `ui_safe`, reading the live file directly. That assumption is no longer
  true given the current (accurate) WR coverage — updated both to use a synthetic fixture
  guaranteeing sufficient coverage, matching the pattern already used by
  `test_compute_historical_comps_wr_warning_absent_when_coverage_sufficient`, so they test the
  gating invariant itself rather than depending on ambient season data that will keep changing.
- Ran the full `pytest` suite (380 tests) after regenerating and after the test updates: all pass.

## Scope notes

- No Forecast files were touched.
- No new rookie evaluation logic or scoring changes were introduced — `compute_historical_comps.py`
  and its weights/thresholds are unchanged; only its inputs (quarantined TE files, current
  rookie-alpha export) changed.
- Real TE reference-population data was not backfilled here — that still requires a
  `CFBD_API_KEY` and remains tracked in `data/historical/te_reference_populations/README.md`.
- The WR coverage regression is documented, not remediated, per this issue's scope.
