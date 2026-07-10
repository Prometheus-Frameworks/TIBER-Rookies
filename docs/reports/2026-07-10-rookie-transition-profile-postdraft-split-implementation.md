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
   `is_udfa`/`status` agreement, drafted-requires-round/pick vs. udfa-signed-forbids-round/pick,
   `source_status` must be exactly `"external_verified"`, and `upstream_provenance_status` must be
   `null` or one of TIBER-Data's documented `provenance_status` enum values (see
   `docs/cross-repo-draft-results-ingestion.md`). `validate_row()` additionally requires
   `official_postdraft_outcome.provenance.source_type == "official_draft_result"` whenever the
   field's value is not null.
3. **`scripts/compute_rookie_transition_profile.py`**: added
   `build_official_postdraft_outcome_field()`, which checks
   `data/processed/{season}_draft_results.json` first, then
   `data/processed/{season}_day3_udfa_draft_result_profiles.json`, then falls back to
   `unavailable`. Both sources go through a shared `_postdraft_outcome_from_row()` helper that
   derives `status`/`is_udfa`/`draft_round`/`overall_pick` from the row's own fields, so a verified
   row that is itself a UDFA signing is never mislabeled `"drafted"`. `build_draft_capital_field()`'s
   **value** (the pre-draft proxy score) is completely untouched — same meaning, same numbers.
   Its provenance **text** is now computed from the row's own `(big_board_rank,
   draft_capital_proxy_0_100)` pair via a new `expected_band_score()` helper, rather than copied
   verbatim from `data/processed/2026_draft_capital_proxy.json`'s free-text field (see the review
   round below); that data file itself is never edited.
4. **`docs/rookie-transition-profile-contract.md` updated**: new field family documented, schema
   version bumped, known-limitations section extended.
5. **Regenerated the 2026 candidate** under `exports/candidate/rookie-transition-profile/` only —
   no file under `exports/promoted/` is touched anywhere in this issue's final form.
6. **23 new regression tests** (444 total, up from 421 before this issue's first commit) covering:
   `official_postdraft_outcome` status/is_udfa/round-pick semantics, the tightened
   `source_status`/`upstream_provenance_status` enums, the `source_type` enforcement, the computed
   `draft_capital` provenance-text behavior (band match, band mismatch, null rank), and an
   artifact-wide invariant checked against the real committed artifact's full 48-row population.

## Required validation — results

| Requirement | Result |
|---|---|
| 48/48 player identity coverage | **48/48** |
| 47 `drafted` + 1 `udfa_signed` outcome | **Confirmed exactly**: `te-daequan-wright` is the one `udfa_signed` row |
| No row where official outcome data is labeled `market_derived_proxy` | **Confirmed**: `official_postdraft_outcome.provenance.source_type` is `official_draft_result` for all 48 rows, enforced by the validator |
| No row where the pre-draft proxy is overwritten by official results | **Confirmed**: `draft_capital.provenance.source_type` is `market_derived_proxy` for all 48 rows, unchanged from before this fix |
| No contradictory provenance text within a field | **Confirmed for the full 48-row population**: every `draft_capital.provenance.source_name` that claims the ranked-bands mapping has a `big_board_rank` whose `expected_band_score()` matches the row's actual `draft_capital_proxy_0_100`; every null-rank or formula-mismatched row is described honestly instead — checked by `test_2026_artifact_draft_capital_never_claims_a_rank_mapping_without_a_rank` across all 48 rows, not a subset |
| JSON/CSV population and semantic parity | **Confirmed**: 48 rows in both, identical `player_id` sets and order |
| Manifest/input/output hash consistency | **Confirmed**: `ROOKIE TRANSITION PROFILE VALIDATION PASSED` with hash checking enabled, and `validate_promoted_export.py` on Rookie Alpha's untouched, still-promoted export also passes |
| Deterministic byte-identical regeneration with pinned timestamp | **Confirmed**: regenerated with `--generated-at` pinned |
| Full repository test suite passes | **444 passed** |

## Review round: computing provenance text instead of editing shared data

The first version of this fix repaired `data/processed/2026_draft_capital_proxy.json`'s
`draft_capital_proxy_source` free-text field in place for the 17 rows flagged in the #266 review.
A subsequent, more substantial review round found three problems with that approach, all verified
against the actual repo before being acted on:

1. **Unauthorized scope into an already-promoted artifact.** That file is a hash-locked input of
   the already-promoted Rookie Alpha export. Editing it broke `validate_promoted_export.py`'s hash
   check, which required regenerating `exports/promoted/rookie-alpha/*` to fix — scope issue #267
   never authorized (its hard boundary is about `exports/promoted/rookie-transition-profile/`
   specifically, but touching any promoted artifact was still more than this issue called for).
2. **Incomplete repair.** Only 6 of the 10 candidate rows with `big_board_rank: null` were fixed;
   `wr-kendrick-law`, `wr-barion-brown`, and `wr-kevin-coleman-jr` were missed entirely, and
   `te-daequan-wright` was explicitly (and wrongly) left as an "acknowledged exception" rather than
   fixed, even though the artifact-wide requirement is that no field contain contradictory
   provenance — "pre-existing" does not exempt a row from that requirement in a freshly regenerated
   candidate.
3. **Incorrect for 5 additional rows.** `te-sam-roush`, `wr-zachariah-branch`,
   `te-nate-boerkircher`, `te-eli-raridon`, and `te-marlin-klein` all have a real `big_board_rank`
   but a `draft_capital_proxy_0_100` that does not match the documented banding formula for that
   rank — yet the first repair gave them the ranked-bands template text anyway, which is a false
   claim.
4. Two smaller validator/semantics gaps: the validator never required
   `official_postdraft_outcome.provenance.source_type == "official_draft_result"`, and
   `source_status`/`upstream_provenance_status` accepted any non-empty string rather than the
   actual enum values these fields carry.

**Fix:** `data/processed/2026_draft_capital_proxy.json` and
`exports/promoted/rookie-alpha/*` were reverted to their `origin/main` state, and
`build_draft_capital_field()` was rewritten to compute the provenance description at generation
time via `expected_band_score(big_board_rank)`, checking whether the row's own
`(big_board_rank, draft_capital_proxy_0_100)` pair is actually consistent with the documented
formula before describing it that way. This is correct-by-construction for the entire candidate
population — no hand-maintained per-player-ID list, no missed rows, no need to touch the shared
data file or any promoted artifact at all. The regression test for this invariant now iterates
every row in the committed artifact rather than a fixed set of IDs.
The validator gaps were closed by adding the `source_type` check to `validate_row()` and
tightening `validate_official_postdraft_outcome_value()`'s `source_status`/
`upstream_provenance_status` checks to the actual enums.

An earlier, smaller review round (before this one) also found and fixed a P2: the post-draft
outcome builder hard-coded `status: "drafted"` for any verified `draft_results.json` row without
checking the row's own `is_udfa`/`draft_result_status` fields. Fixed by extracting the shared
`_postdraft_outcome_from_row()` helper used uniformly for both source files.

## Hard-boundary compliance

- No files created or modified under `exports/promoted/` anywhere — `git status` confirms all
  changes are under `exports/candidate/`, `scripts/`, `tests/`, and `docs/`.
  `data/processed/2026_draft_capital_proxy.json` is unmodified from `origin/main`.
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
