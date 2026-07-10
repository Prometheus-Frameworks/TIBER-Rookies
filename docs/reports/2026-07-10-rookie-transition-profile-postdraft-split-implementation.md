# Rookie Transition Profile v0.2.0 — Post-Draft Outcome Split Implementation

**Date:** 2026-07-10
**Issue:** [#267](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/267)
**Follow-up to:** [#265](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/265) /
PR [#266](https://github.com/Prometheus-Frameworks/TIBER-Rookies/pull/266) (promotion review that
found and blocked this defect)
**Design decision recorded separately in:**
[`2026-07-10-rookie-transition-profile-postdraft-split-design.md`](2026-07-10-rookie-transition-profile-postdraft-split-design.md)

## What was implemented

1. **Design decision recorded first** (see linked doc above): a new, additive field family
   (`official_postdraft_outcome`) rather than repurposing `draft_capital`. Schema version bumps
   `rookie-transition-profile-v0.1.0` → `rookie-transition-profile-v0.2.0`.
2. **`scripts/validate_rookie_transition_profile.py`**: bumped `CURRENT_SCHEMA_VERSION`, added
   `official_postdraft_outcome` to `GOVERNED_FIELD_FAMILIES`, and added
   `validate_official_postdraft_outcome_value()` enforcing status enum membership,
   `is_udfa`/`status` agreement, and drafted-requires-round/pick vs.
   udfa-signed-forbids-round/pick.
3. **`scripts/compute_rookie_transition_profile.py`**: added
   `build_official_postdraft_outcome_field()`, which checks
   `data/processed/{season}_draft_results.json` first, then
   `data/processed/{season}_day3_udfa_draft_result_profiles.json`, then falls back to
   `unavailable`. `build_draft_capital_field()` is completely untouched — same code, same
   behavior, same meaning.
4. **`data/processed/2026_draft_capital_proxy.json` repaired**: 17 rows' `draft_capital_proxy_source`
   text (the ones flagged in the #266 review) replaced with the file's own existing
   proxy-methodology template. Only the free-text field changed;
   `draft_capital_proxy_0_100`/`big_board_rank`/`draft_capital_proxy_pending_conversion` are
   byte-identical to before for all 101 rows in the file.
5. **`docs/rookie-transition-profile-contract.md` updated**: new field family documented, schema
   version bumped, known-limitations section extended.
6. **Regenerated the 2026 candidate** under `exports/candidate/rookie-transition-profile/` only —
   no file under `exports/promoted/` was touched.
7. **15 new regression tests** (436 total, up from 421): 8 in
   `tests/test_validate_rookie_transition_profile.py` (drafted/UDFA-signed/invalid-status/
   is_udfa-mismatch/round-pick-consistency semantics, plus two tests against the real committed
   artifact — full 48/48 coverage and draft-capital-never-leaks-outcome-text), 7 in
   `tests/test_compute_rookie_transition_profile.py` (drafted, UDFA-signed, unavailable,
   draft-results-take-priority-over-UDFA-file, and updates to the existing full/sparse-population
   tests to cover the new family without weakening prior assertions).

## Required validation — results

| Requirement | Result |
|---|---|
| 48/48 player identity coverage | **48/48** |
| 47 `drafted` + 1 `udfa_signed` outcome | **Confirmed exactly**: `te-daequan-wright` is the one `udfa_signed` row |
| No row where official outcome data is labeled `market_derived_proxy` | **Confirmed**: `official_postdraft_outcome.provenance.source_type` is `official_draft_result` for all 48 rows |
| No row where the pre-draft proxy is overwritten by official results | **Confirmed**: `draft_capital.provenance.source_type` is `market_derived_proxy` for all 48 rows, unchanged from before this fix |
| No contradictory provenance text within a field | **Confirmed**: 0 of 48 `draft_capital.provenance.source_name` values contain "actual pick" (17 rows were repaired: 16 "actual pick" leaks + 1 stale pre-draft narrative estimate for `wr-brenen-thompson`); all 48 `notes` still correctly say "not equivalent to realized" |
| JSON/CSV population and semantic parity | **Confirmed**: 48 rows in both, identical `player_id` sets and order |
| Manifest/input/output hash consistency | **Confirmed**: `ROOKIE TRANSITION PROFILE VALIDATION PASSED` with hash checking enabled |
| Deterministic byte-identical regeneration with pinned timestamp | **Confirmed**: regenerated twice with `--generated-at` pinned; second run's JSON and manifest are byte-identical to the first |
| Full repository test suite passes | **436 passed** |

## Cascading consequence: Rookie Alpha promoted manifest refresh

Repairing `data/processed/2026_draft_capital_proxy.json`'s text changed that file's SHA-256 hash.
That file is also a hash-locked input of the **already-promoted** Rookie Alpha export
(`exports/promoted/rookie-alpha/2026_manifest.json`), so CI's existing
`validate_promoted_export.py` check failed after this PR's first push — a real consequence, not a
flake.

Before regenerating anything, a dry run of `scripts/compute_rookie_alpha.py` against current
inputs was diffed against the committed Rookie Alpha export: **all 48 players' `scores` blocks
were byte-identical** — this repair changed no numeric value Rookie Alpha's own scoring consumes,
so regeneration would import zero unrelated drift (unlike the #259 historical-comps case, where
a similar regeneration surfaced ~9 commits of accumulated, unrelated changes). On that basis,
`exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json` and its manifest were
regenerated for real. The resulting diff is confirmed to be **only** `generated_at`/`run_id` in
the JSON and the corresponding hash entries in the manifest — the CSV is byte-identical, and every
player's `scores` are unchanged. `scripts/validate_promoted_export.py` now passes again.

Regenerating Rookie Alpha's export changed *its own* file hash, which is in turn a hash-locked
input of the `rookie_transition_profile_v0` candidate's manifest — so that candidate was
regenerated a second time to pick up the new (legitimate) hash. Its content (all field values,
`coverage_summary`) is unchanged; only the manifest's recorded hash for the Rookie Alpha input
file updated.

This is the only place this PR touches anything under `exports/promoted/`, and it touches
`exports/promoted/rookie-alpha/`, not `exports/promoted/rookie-transition-profile/` — the
directory issue #267's hard boundary actually names. It was necessary to keep an existing,
already-promoted artifact's integrity chain honest after a data repair this issue explicitly
required, and was verified to carry zero scoring or population drift before being applied.

## Hard-boundary compliance

- No files created or modified under `exports/promoted/rookie-transition-profile/` —
  `git status` confirms all changes are under `exports/candidate/`, `scripts/`, `tests/`, `docs/`,
  the one repaired `data/processed/` file, and (per the cascading-consequence section above)
  `exports/promoted/rookie-alpha/`, whose manifest hash-locks that repaired file.
- No changes to TIBER-Forecast, no Forecast mirror.
- No predictive value evaluated or claimed.
- No downstream consumption or production binding authorized.
- No role projection, landing-spot evaluation, rankings, or new composite scores added.
  `nfl_team` appears only inside `official_postdraft_outcome` as an observed fact of the outcome
  itself (which team drafted/signed the player), not as modeled landing-spot analysis.

## Decision

```text
may_open_corrected_rookie_transition_profile_promotion_review_issue
```

This authorizes only a new promotion-review issue against this corrected candidate. It does not
authorize promotion, Forecast consumption, cross-repo mirroring, predictive use, or production
binding.
