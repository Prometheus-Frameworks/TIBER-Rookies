# Rookie Transition Profile v0 — Promotion Review

**Date:** 2026-07-10
**Issue:** [#265](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/265)
**Reviews the candidate implemented in:** [#263](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/263) /
PR [#264](https://github.com/Prometheus-Frameworks/TIBER-Rookies/pull/264)

## Candidate under review

**Source commit:** `a0843a7ec3437c258109e58387165de524c2c423` ("Implement rookie_transition_profile_v0
governed candidate artifact (#263) (#264)")

**SHA-256 hashes (recorded before any review work):**

```text
2026_rookie_transition_profile_v0.json: 1ead2f82e9ef2d408d197863ed83e744bae89f8619f35b150753607bff019591
2026_rookie_transition_profile_v0.csv:  7474e859d90d934a68f21797b9c8409f790e53bc509c69e789216a2f8ecea9fa
2026_manifest.json:                     f9e4f31bb57f32f1e6ccf34bbd453bfd18b564e803565a51e9c18129e5a62b87
```

These hashes are unchanged by this review — no file under `exports/candidate/` or
`exports/promoted/` was modified. `git status` is clean at the end of this review.

## Gate-by-gate results

| # | Gate | Result | Evidence |
|---|---|---|---|
| 1 | Validator passes with input/output hash checking enabled | **PASS** | `python3 scripts/validate_rookie_transition_profile.py --export-json ... --manifest ...` → `ROOKIE TRANSITION PROFILE VALIDATION PASSED` (hash checks on by default, not skipped). |
| 2 | JSON/CSV represent the same 48-player population, no duplicates/missing identities | **PASS** | Independent script: JSON and CSV both have exactly 48 rows, identical `player_id` sets *and* order, zero duplicates, zero missing/empty ids, matches `coverage_summary.players_total`. |
| 3 | Manifest metadata/paths/hashes/coverage/schema/season/run ID/timestamps internally consistent | **PASS** | Manual cross-check of every field (`schema_version`, `season`, `generated_at`, `run_id`, `coverage_summary`, `source_files_used` vs. `input_files` paths) between export, `manifest.export_metadata`, and manifest top level — all identical. `output_files` hashes match the recorded hashes above exactly. |
| 4 | Every governed field follows `{value, provenance}` invariant | **PASS** | Independent script (not reusing the validator's own code path) checked all 48 rows × 4 families: every field has exactly `{value, provenance}` keys, every `provenance` has exactly the 7 expected keys. 0 problems. |
| 5 | Every present field uses a valid observed or inferred `source_type` | **PASS** | Same independent check: every non-unavailable field's `source_type` is one of the 7 non-`unavailable` enum values. 0 problems. |
| 6 | Every unavailable field is null and carries an explicit reason | **PASS** | Same independent check: every `unavailable` field has `value: null`, non-empty `notes`, and `confidence`/`confidence_band` both null. 0 problems. Counts match `coverage_summary` exactly (1 missing age, 16 missing athletic testing, 0 missing draft_capital/production). |
| 7 | `NEUTRAL_DEFAULT` athletic placeholders are not presented as measured evidence | **PASS** | Cross-referenced all 48 rows against the actual promoted Rookie Alpha export's `scores.athletic_source`. Every player with `athletic_source` `None`/`NEUTRAL_DEFAULT` (16 players) is `unavailable` with `value: null` in the candidate; every player with a real RAS/SPORQ-derived source (32 players) is `measured_combine` with `athletic_score_0_100`/`athletic_source`/`athletic_confidence` copied verbatim. 0 mismatches. |
| 8 | Draft-capital proxy values remain explicitly inferred, never described as realized draft capital | **FAIL** | See "Finding" below. |
| 9 | No role projection, landing-spot context, mixed-provenance route data, narrative evidence, ranking, or predictive claim entered the artifact | **FAIL (related to #8)** | No role/landing-spot/route-detail fields exist anywhere in the artifact (top-level keys and per-row keys checked exhaustively — only the four designed families plus identity are present). However, scanning every field's free-text `source_name`/`notes` surfaced narrative/outcome content inside `draft_capital.provenance.source_name` for 17 rows — see "Finding" below. This is the same underlying defect as gate 8, not a second independent one. |
| 10 | Candidate reproduces deterministically from documented inputs with a pinned timestamp | **PASS** | Re-ran `compute_rookie_transition_profile.py --season 2026 --generated-at "2026-07-10T00:00:00+00:00"` against the current repo state; diffed the regenerated JSON/CSV/manifest against the committed files byte-for-byte — **identical**. This also confirms the gate-8/9 finding is a reproducible producer-logic gap, not a one-off data glitch. |
| 11 | Full repository test suite passes | **PASS** | `pytest` → 421 passed. |

## Finding (gates 8 & 9): draft capital field misrepresents realized draft outcomes as an unresolved pre-draft proxy

Cross-referencing all 48 candidate rows against `data/processed/2026_draft_results.json` (the
real, source-verified 2026 draft-results artifact established in issues #257/#259):

- **47 of 48 candidate players (98%)** already have a verified draft record
  (`source_status: "external_verified"`, not a UDFA). Only `te-daequan-wright` has no draft
  record at all.
- Despite this, **every one of the 48 rows** classifies `draft_capital.provenance.source_type` as
  `market_derived_proxy` and carries the note *"Temporary pre-draft market-investment proxy. Not
  equivalent to realized NFL draft capital."*
- For **17 of the 48 rows**, the upstream `data/processed/2026_draft_capital_proxy.json` file's
  `draft_capital_proxy_source` text was itself edited to reference the real outcome, e.g.:

  ```text
  "2026 NFL Draft actual pick: Round 3, Pick 69"
  ```

  This string is copied verbatim into `draft_capital.provenance.source_name` by the producer,
  producing a single field whose `source_name` states a real, verified draft outcome while its
  own `notes` in the same object says that outcome is "not equivalent to realized NFL draft
  capital" — a direct internal contradiction within one provenance object.
- One of those 17, `wr-brenen-thompson`, is a further sub-case: his `source_name` is a **stale
  pre-draft estimate** ("Estimated from big_board_rank=137 (R4-5 projection...)") even though he
  has a verified real pick (Round 4, Pick 105) in `2026_draft_results.json` — the upstream note
  was simply never refreshed after the draft.
- The other 30 of the 47 already-drafted players have a `source_name` that still reads as generic
  pre-draft language, meaning `data/processed/2026_draft_capital_proxy.json` itself is only
  partially/inconsistently updated post-draft — but the underlying `draft_capital_proxy_0_100`
  *value* for all 48 rows is uniformly derived from `big_board_rank`, never from the real,
  observed round/pick.

**Root cause:** `scripts/compute_rookie_transition_profile.py` only reads
`data/processed/{season}_draft_capital_proxy.json` for this field family. It never reads
`data/processed/{season}_draft_results.json`, and has no code path to emit
`source_type: "official_draft_result"` — a value already reserved in the schema
(`scripts/validate_rookie_transition_profile.py`'s `SourceType` enum) and explicitly noted as
"not used by v0" in `docs/rookie-transition-profile-contract.md`, but with no mechanism to
promote a player into it once real draft results exist. The schema anticipated this gap; the
producer never closed it.

**Why this fails the gate, not just a cosmetic nit:** this is precisely the class of defect the
#255/#257/#259 chain exists to catch — data whose provenance classification actively
misrepresents its own certainty. A downstream reader trusting `provenance.source_type` (the
artifact's entire reason for existing) would treat 47 of 48 rows' draft capital as an unreliable
pre-draft guess when 47 of them are actually real, sourced, verified outcomes sitting one file
away in the same repository.

## Hard-boundary compliance during this review

- No artifact values, field families, confidence semantics, schema semantics, or producer logic
  were modified to make promotion pass.
- The candidate was not regenerated with materially different content — the one regeneration
  performed (gate 10) produced byte-identical output, used only to prove determinism.
- No files under `exports/promoted/` were created or modified.
- No changes to TIBER-Forecast, no Forecast mirror, no predictive-value evaluation, no downstream
  consumption authorized.

## Decision

```text
rookie_transition_profile_promotion_requires_followup
```

This candidate is **not promoted**. `exports/promoted/rookie-transition-profile/` remains
untouched. Gates 1–7, 10, and 11 pass cleanly; gates 8 and 9 fail on the same underlying defect.

This decision authorizes only the conclusion that a separate implementation-fix issue is needed
(per issue #265's own hard boundary: "Any required data or contract change must be handled by a
separate implementation-fix issue and a new candidate review"). It does not authorize promotion,
Forecast consumption, predictive use, cross-repo mirroring, or production binding.

## Recommended follow-up (for a separate implementation-fix issue)

1. Teach `scripts/compute_rookie_transition_profile.py` to check
   `data/processed/{season}_draft_results.json` for each player. Where a verified record exists
   (`source_status: "external_verified"`, not UDFA), emit `draft_capital` with
   `source_type: "official_draft_result"` and a `value` built from the real `draft_round`/
   `overall_pick`/`nfl_team`, not the big-board proxy.
2. Retain `market_derived_proxy` only for players with no verified draft record (as it already
   correctly does for `te-daequan-wright`).
3. Fix or drop the stale/inconsistent `draft_capital_proxy_source` post-draft edits in
   `data/processed/2026_draft_capital_proxy.json` regardless of (1), since a proxy-methodology
   field should not contain ad hoc draft-outcome text at all.
4. Regenerate the candidate, then open a new promotion-review issue against the corrected
   candidate.
