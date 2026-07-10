# Design Decision: Separating Pre-Draft Proxy from Official Post-Draft Outcome

**Date:** 2026-07-10
**Issue:** [#267](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/267)
**Follow-up to:** [#265](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/265) /
PR [#266](https://github.com/Prometheus-Frameworks/TIBER-Rookies/pull/266) (promotion review that
found this defect)

Recorded before the code changes it governs, per issue #267's explicit requirement.

## The problem being solved

The promotion review found that every one of the 48 candidate rows' `draft_capital` field is
classified `market_derived_proxy` — even though 47 players have a verified drafted outcome
(`data/processed/2026_draft_results.json`) and 1 (`te-daequan-wright`) has a verified UDFA-signing
outcome (`data/processed/2026_day3_udfa_draft_result_profiles.json`). This makes the `notes` field
("Not equivalent to realized NFL draft capital") false for all 48 rows.

## Options considered

1. **Rename/repurpose `draft_capital` itself** to sometimes mean proxy, sometimes mean official
   outcome, depending on data availability. **Rejected.** This is exactly the "polymorphic field"
   defect flagged in review: one field name would represent two different concepts across rows,
   discarding the pre-draft expectation for every player who has since been drafted, and silently
   changing the field's meaning under the same schema version — which issue #267 explicitly
   forbids.
2. **A new versioned post-draft companion artifact** (mirroring Rookie Alpha's own
   predraft/postdraft file split), carrying both the frozen pre-draft proxy and the observed
   outcome. **Rejected for v0.2.0**, not because it's wrong in principle, but because it's more
   than this fix requires: `rookie_transition_profile_v0` doesn't yet have a postdraft/predraft
   distinction at the artifact level (unlike Rookie Alpha), and introducing one now would be a
   larger shape change than the defect calls for. Worth revisiting if a genuine predraft/postdraft
   split becomes necessary later (e.g. if further predraft-only fields need freezing).
3. **Add a new, separate field family in the same artifact, leave `draft_capital` completely
   unchanged.** **Chosen.**

## Decision

- **`draft_capital` is not renamed, not restructured, and not touched in meaning or shape.** It
  continues to mean exactly what it means today: the pre-draft market-investment proxy, always
  `source_type: "market_derived_proxy"`, for every player, regardless of whether they've since
  been drafted. This preserves the historically useful pre-draft expectation independently, per
  the issue's explicit requirement.
- **A new field family, `official_postdraft_outcome`, is added** to represent the observed
  post-draft result separately. It follows the exact same `{value, provenance}` invariant as every
  other field family — no new wrapper shape, no special-casing in the validator's core invariant.
- **Schema version bumps `rookie-transition-profile-v0.1.0` → `rookie-transition-profile-v0.2.0`**
  — an additive minor bump (new optional field family; no existing field's meaning or shape
  changes), matching the precedent already established by Rookie Alpha's own
  `rookie-alpha-predraft-v0.2.0` bump ("adds optional context/evidence fields only").

## `official_postdraft_outcome` shape

```json
{
  "value": {
    "status": "drafted",
    "nfl_team": "LV",
    "draft_round": 1,
    "overall_pick": 1,
    "is_udfa": false,
    "source_status": "external_verified",
    "upstream_provenance_status": "source_verified"
  },
  "provenance": {
    "source_type": "official_draft_result",
    "source_name": "NBC Sports ProFootballTalk 2026 NFL Draft picks full tracker, published 2026-04-25",
    "source_url": "https://www.nbcsports.com/nfl/profootballtalk/news/2026-nfl-draft-picks-full-tracker-of-every-selection-rounds-1-7",
    "confidence": 0.95,
    "confidence_band": "HIGH",
    "last_verified_at": "2026-05-17",
    "notes": null
  }
}
```

- `value.status`: `"drafted"` or `"udfa_signed"` — the only two statuses currently observable.
- `value.draft_round` / `value.overall_pick`: integers for drafted players; `null` for
  `udfa_signed` (there is no round/pick for an undrafted signing).
- `value.is_udfa`: boolean, consistent with `status` (`false` for `drafted`, `true` for
  `udfa_signed`).
- `value.source_status` / `value.upstream_provenance_status`: carried through from the source row
  as descriptive value content (the same pattern `draft_capital.value` already uses for
  `big_board_rank` alongside the primary score) — these describe the underlying record's own
  verification chain, distinct from this artifact's own provenance object below.
  `upstream_provenance_status` is `null` when the source row doesn't carry one (the UDFA file has
  no equivalent field).
- `provenance.source_type` is always `"official_draft_result"` when present — an **observed**
  source type already reserved in the schema (`SourceType.OFFICIAL_DRAFT_RESULT`) since #263 but
  unused until now.
- `provenance.confidence`/`confidence_band` are a fixed `0.95`/`HIGH` constant for this family —
  higher than `age_at_entry` (0.9) and `college_production` (0.85), since `external_verified`
  sourced draft/signing outcomes are about as certain as this repo's provenance model gets. This
  mirrors how `draft_capital` (0.65) and `college_production` (0.85) already use reasoned fixed
  constants rather than a per-row varying signal (unlike `athletic_testing`, which reuses Rookie
  Alpha's already-variable `athletic_confidence`).
- `provenance.last_verified_at` uses the source row's own `ingested_at` field when present
  (`data/processed/2026_draft_results.json` rows carry one); falls back to the artifact's
  `generated_at` date when the source has no per-row timestamp (the UDFA file has none).
- When neither source has a record for a player, the field is `unavailable` (`value: null`,
  `notes` explaining that neither source was found) — this has not occurred for the current 2026
  population (48/48 covered) but the code path exists for future seasons/players.

## Canonical source handling

Checked in order, per player:

1. `data/processed/{season}_draft_results.json` — if a row exists with
   `source_status == "external_verified"`, use it. `status`/`is_udfa`/`draft_round`/`overall_pick`
   are derived from the row's own fields (not assumed to be `"drafted"`), so a verified row that is
   itself a UDFA signing is preserved correctly, not mislabeled.
2. Else, `data/processed/{season}_day3_udfa_draft_result_profiles.json` — if a row exists with
   `source_status == "external_verified"`, use it the same way (`status` taken from the row's own
   `draft_result_status`, which is `"udfa_signed"` for the one 2026 case).
3. Else, `unavailable`.

Investigated whether to introduce a single canonical unified outcome artifact instead, per the
issue's explicit option to do so "only if it preserves existing source lineage and validates all
48 player outcomes." Declined for this fix: `data/processed/2026_day3_udfa_draft_result_profiles.json`
is mostly redundant with `2026_draft_results.json` already (7 of its 8 rows are `"drafted"` players
who also appear in the comprehensive file — apparently kept there to avoid a silent gap in a
different consumer, `build_post_draft_alpha.py`'s Round1/Day2 translator scope) and only contributes
one genuinely unique record (`te-daequan-wright`'s UDFA signing). Merging or renaming these two
files would not add governance value and is explicitly out of scope for this issue
("Do not create a new canonical layer merely to rename or flatten the two files without adding
governance value").

## Pre-draft proxy provenance: computed, not copied (revised)

The first attempt at this fix edited `data/processed/2026_draft_capital_proxy.json`'s
`draft_capital_proxy_source` text in place for the 17 rows flagged in the #266 review. A later
review round found two problems with that approach:

1. **It touched a hash-locked shared input.** That file is also an input of the already-promoted
   Rookie Alpha export, so editing it broke `validate_promoted_export.py`'s hash lock and forced
   regenerating an already-promoted artifact — scope issue #267 never authorized.
2. **It was incomplete and, in five cases, itself wrong.** The repair only touched 6 of the 10 rows
   with `big_board_rank: null` (missing `wr-kendrick-law`, `wr-barion-brown`,
   `wr-kevin-coleman-jr`, and `te-daequan-wright`, the last of which was explicitly but wrongly left
   as an "acknowledged exception"), and gave the ranked-bands template text to 5 rows whose
   `big_board_rank` is present but whose `draft_capital_proxy_0_100` doesn't actually match that
   rank under the documented formula (`te-sam-roush`, `wr-zachariah-branch`,
   `te-nate-boerkircher`, `te-eli-raridon`, `te-marlin-klein`) — a hand-edited allowlist of text
   values, checked by nothing, will drift from the data it describes.

**Revised decision:** `data/processed/2026_draft_capital_proxy.json` is never edited at all — it
is reverted to its `origin/main` state. Instead, `build_draft_capital_field()` in
`scripts/compute_rookie_transition_profile.py` computes the `draft_capital.provenance.source_name`
text at generation time from the row's own `(big_board_rank, draft_capital_proxy_0_100)` pair via
a small `expected_band_score(rank)` helper that mirrors the documented 8-band formula:

- If `big_board_rank` is present and `draft_capital_proxy_0_100 == expected_band_score(big_board_rank)`,
  describe it as the ranked-bands mapping (the claim is true).
- If `big_board_rank` is `null`, describe it as "no recorded big_board_rank on file (rank unknown)"
  — never claim a band mapping without a rank to map from.
- If `big_board_rank` is present but the score doesn't match the formula, describe it as
  "inconsistent with the documented big_board_rank band mapping ... exact derivation unavailable"
  — an honest admission rather than a false claim either way.

This is correct-by-construction for the full 48-row candidate population (and for the other 53
rows in the 101-row proxy file, for any future population), never guesses or reconstructs a
missing rank, and — because it never edits the shared file — never invalidates Rookie Alpha's
promoted manifest, eliminating the need to regenerate anything under `exports/promoted/` for this
issue at all.

## Summary of what changes and what doesn't

| | Before | After |
|---|---|---|
| `draft_capital` field meaning | Pre-draft proxy | **Unchanged** — still pre-draft proxy |
| `draft_capital` field shape | `{value, provenance}` | **Unchanged** |
| New field | — | `official_postdraft_outcome`, `{value, provenance}`, `source_type: official_draft_result` |
| `schema_version` | `rookie-transition-profile-v0.1.0` | `rookie-transition-profile-v0.2.0` |
| `data/processed/2026_draft_capital_proxy.json` | — | **Untouched** — no longer edited; `draft_capital.provenance.source_name` is computed at generation time instead |
| `exports/promoted/rookie-alpha/*` | — | **Untouched** |
