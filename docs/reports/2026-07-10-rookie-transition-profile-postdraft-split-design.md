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
   `source_status == "external_verified"` and `is_udfa` false, use it (`status: "drafted"`).
2. Else, `data/processed/{season}_day3_udfa_draft_result_profiles.json` — if a row exists with
   `source_status == "external_verified"`, use it (`status` taken from the row's own
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

## Pre-draft proxy repair (text only, not the value)

Separately, `data/processed/2026_draft_capital_proxy.json`'s `draft_capital_proxy_source` field
for the 17 players flagged in the #266 review is repaired to contain proxy-methodology text only,
matching the file's own existing canonical templates:

- 11 rows with a real `big_board_rank` → the standard ranked template already used by 45 other
  rows: `"Temporary pre-draft proxy mapped from seeded big_board_rank bands (1-10=95,11-20=85,21-32=75,33-50=65,51-75=55,76-100=45,101-150=35,151+=25)"`.
- 6 rows whose `big_board_rank` is currently `null` (`wr-dezhaun-stribling`, `rb-kaelon-black`,
  `wr-malachi-fields`, `wr-caleb-douglas`, `wr-zavion-thomas`, `te-will-kacmarek`): their
  `draft_capital_proxy_0_100` values (45–65) are consistent with the *ranked* banding methodology,
  not the file's separate "unranked band" convention (which always pairs with
  `draft_capital_proxy_0_100 == 25`, confirmed against other rows using that template). Using the
  "unranked" text for these would misrepresent their actual stored score, so they also receive the
  ranked template text above — their `big_board_rank` field itself is left as `null` (not
  reconstructed; that would be guessing a value, which is out of scope) but the source text no
  longer claims something false.

**Only the `draft_capital_proxy_source` text field is edited.** `draft_capital_proxy_0_100`,
`big_board_rank`, and `draft_capital_proxy_pending_conversion` are untouched for all 101 rows in
the file, satisfying "Do not rewrite the proxy value using the actual pick."

## Summary of what changes and what doesn't

| | Before | After |
|---|---|---|
| `draft_capital` field meaning | Pre-draft proxy | **Unchanged** — still pre-draft proxy |
| `draft_capital` field shape | `{value, provenance}` | **Unchanged** |
| New field | — | `official_postdraft_outcome`, `{value, provenance}`, `source_type: official_draft_result` |
| `schema_version` | `rookie-transition-profile-v0.1.0` | `rookie-transition-profile-v0.2.0` |
| `data/processed/2026_draft_capital_proxy.json` values | 17 rows have leaked outcome/narrative text in `draft_capital_proxy_source` | Same numeric values; text repaired to proxy-methodology-only |
