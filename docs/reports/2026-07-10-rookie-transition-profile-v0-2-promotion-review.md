# Promotion Review: rookie_transition_profile v0.2.0 Candidate

**Date:** 2026-07-10
**Issue:** [#269](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/269)
**Reviews the artifact implemented in:** [#267](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/267) /
PR [#268](https://github.com/Prometheus-Frameworks/TIBER-Rookies/pull/268) (squash-merged to `main`)

## Review source lock

- **Source commit on `main`:** `0bf363aab85b5e7489e6c55a0e87e680f7060750`
- **Candidate JSON:** `exports/candidate/rookie-transition-profile/2026_rookie_transition_profile_v0.json`
  SHA-256 `c95b941c7855612daccfc2226fc51e0e34dbb2ebe8a2487596675d2522a22f37`
- **Candidate CSV:** `exports/candidate/rookie-transition-profile/2026_rookie_transition_profile_v0.csv`
  SHA-256 `3005bcd6ad4ffc87a312c6926e20c5e3658747012855aa9d8ccfa33d898545e6`
- **Candidate manifest:** `exports/candidate/rookie-transition-profile/2026_manifest.json`
  SHA-256 `77be8245ade9e5b9ff9660cacefe7d2d27e65940c2c107acd2deac4f50da7243`
- **Schema version:** `rookie-transition-profile-v0.2.0`
- **Season:** `2026`
- **Generated timestamp:** `2026-07-10T12:00:00+00:00`
- **Run ID:** `rookie-transition-profile-2026-2026-07-10T12:00:00+00:00`
- **Row count:** 48
- **Coverage summary:**
  ```json
  {
    "players_total": 48,
    "players_with_draft_capital": 48,
    "players_with_age_at_entry": 47,
    "players_with_athletic_testing": 32,
    "players_with_college_production": 48,
    "players_with_official_postdraft_outcome": 48,
    "players_with_all_families": 32
  }
  ```
- **Manifest input files and hashes** (all confirmed to match the actual files on disk at
  `0bf363a`):

  | Path | SHA-256 |
  |---|---|
  | `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json` | `5a7c6c945ad477c1a54e61e7337e9f5bd6b5e69455669ca4700d7668fe9816e3` |
  | `data/processed/2026_draft_capital_proxy.json` | `5622f5ab86d8db812a3c98fd67b74960943d687fa323f7e9592533f8d058738f` |
  | `data/processed/2026_college_production.json` | `c4c15efd609fef982e417817148b1b7bc090f53896791eb2cb85cf1bf665fb0d` |
  | `data/processed/2026_prospect_context.json` | `bdf16633076bb5fb28e9451028fc476fadf6ff727dc06bdb106eb026e741de0e` |
  | `data/processed/2026_draft_results.json` | `ae6b037845f5b6bcd87e17185d1086a3de1cf6a915571f3da1d5d716965f01bd` |
  | `data/processed/2026_day3_udfa_draft_result_profiles.json` | `1f9b3a3c592bbc94f42c3d361461372b104f3f320fa9d11ebc5bcdb6511822ec` |

The candidate did not change during this review; the review is against exactly the above
snapshot.

## Gate-by-gate results

### 1. Candidate integrity — PASS

- All three governed candidate files exist at their governed paths.
- `schema_version == "rookie-transition-profile-v0.2.0"`, `season == 2026`.
- `validate_artifact_shape()` returns no errors; manifest top-level fields agree with
  `export_metadata`, which agrees with the artifact's own top-level fields (`schema_version`,
  `season`, `generated_at`, `run_id`, `coverage_summary`) — all confirmed equal by direct
  comparison.
- `scripts/validate_rookie_transition_profile.py --export-json ... --manifest ...` →
  `ROOKIE TRANSITION PROFILE VALIDATION PASSED` (input and output hash checks enabled).
- JSON and CSV contain the same 48 `player_id` values in the same order (confirmed by direct
  comparison of both files' ID sequences).
- No duplicate `player_id` values (48 unique of 48 rows).

### 2. Field-governance invariant — PASS

Checked programmatically across every row and all five governed families
(`draft_capital`, `age_at_entry`, `athletic_testing`, `college_production`,
`official_postdraft_outcome`):

- Every present field has a valid `{value, provenance}` pair; no `unavailable` field has a
  non-null value or missing `notes`.
- No `NEUTRAL_DEFAULT` athletic placeholder is represented as `measured_combine` evidence — all
  such rows are correctly `unavailable`.
- Every `confidence_band` matches `confidence_to_band(confidence)` for every present field.
- No `last_verified_at` exceeds season 2026.
- Every null `last_verified_at` (the `te-daequan-wright` UDFA case) carries a non-empty
  explanatory `notes`.

Zero violations found.

### 3. Pre-draft proxy preservation — PASS

Checked across all 48 rows using `expected_band_score()` from
`scripts/compute_rookie_transition_profile.py` (the same formula the producer itself uses):

- `draft_capital.provenance.source_type == "market_derived_proxy"` for all 48 rows.
- No `draft_capital.provenance.source_name` contains "actual pick" text.
- Every row claiming the ranked-bands mapping has a present `big_board_rank` whose
  `expected_band_score()` equals the row's `draft_capital_proxy_0_100` exactly.
- Every null-`big_board_rank` row is described as rank-unknown/manual classification, not a band
  mapping.
- Every row with a present rank but a formula-inconsistent score is described honestly as
  inconsistent, not as a band mapping.

Zero violations found. This gate was checked against the artifact only — no upstream shared file
was read, edited, or otherwise touched during this review.

### 4. Official post-draft outcome coverage — PASS

- Exactly 48 total players, 47 `status == "drafted"`, 1 `status == "udfa_signed"`, 0 unresolved.
- All 47 drafted rows confirmed to have: non-empty `nfl_team`, integer `draft_round`, integer
  `overall_pick`, `is_udfa == false`, `source_status == "external_verified"`,
  `upstream_provenance_status == "source_verified"`, `provenance.source_type ==
  "official_draft_result"`. Zero violations across all 47.
- The one UDFA-signed row is `te-daequan-wright`, confirmed with exactly:
  ```json
  {
    "value": {
      "status": "udfa_signed", "nfl_team": "PHI", "draft_round": null, "overall_pick": null,
      "is_udfa": true, "source_status": "external_verified", "upstream_provenance_status": null
    },
    "provenance": {
      "source_type": "official_draft_result",
      "source_name": "Eagles announced Wright among their signed undrafted free agents.",
      "source_url": "https://www.philadelphiaeagles.com/news/eagles-sign-eight-undrafted-free-agents",
      "confidence": 0.95, "confidence_band": "HIGH", "last_verified_at": null,
      "notes": "last_verified_at is null: no per-row source verification timestamp exists in data/processed/{season}_day3_udfa_draft_result_profiles.json, and the artifact's own generation date is not a substitute for one."
    }
  }
  ```
- No row carries `upstream_provenance_status` of `source_verified_player_id_unresolved`,
  `needs_verification`, or `fixture_only`.

### 5. Source lineage — PASS

- The manifest hash-locks both `data/processed/2026_draft_results.json` and
  `data/processed/2026_day3_udfa_draft_result_profiles.json` as inputs.
- All 47 drafted outcomes carry the same `source_name`/`source_url` pointing at the drafted-results
  tracker (`NBC Sports ProFootballTalk 2026 NFL Draft picks full tracker`), confirming they come
  from the drafted-results source.
- `te-daequan-wright`'s outcome carries a distinct `source_name`/`source_url` pointing at the
  Eagles' own announcement, confirming it comes from the UDFA source, not the drafted-results file.
- `build_official_postdraft_outcome_field()` (reviewed in source, not re-derived) checks
  `draft_results.json` first and only falls back to the UDFA file when the player is absent from
  the first — an absence from one source is never treated as `unavailable` before the second
  source is checked.

### 6. Candidate-only implementation boundary — PASS

- `git diff --stat c6a81b0 0bf363a -- data/processed/2026_draft_capital_proxy.json
  exports/promoted/rookie-alpha/` returns empty — PR #268 modified neither file.
- This review itself did not modify either file (confirmed via `git status` before/after; see
  below).

### 7. Deterministic reproduction — PASS

Regenerated in a clean temporary directory **inside the repository worktree**
(`.tmp/rookie-transition-profile-promotion-repro/`, so `resolve_path()` can find the `.git` root
and resolve all six manifest input paths), using the committed producer and the candidate's own
pinned timestamp:

```bash
$ mkdir -p .tmp/rookie-transition-profile-promotion-repro
$ python3 -m scripts.compute_rookie_transition_profile \
    --season 2026 --generated-at "2026-07-10T12:00:00+00:00" \
    --output-dir .tmp/rookie-transition-profile-promotion-repro
Wrote rookie transition profile artifact: .tmp/rookie-transition-profile-promotion-repro/2026_rookie_transition_profile_v0.json
Wrote rookie transition profile manifest: .tmp/rookie-transition-profile-promotion-repro/2026_manifest.json
```

- `diff .tmp/.../2026_rookie_transition_profile_v0.json exports/candidate/.../2026_rookie_transition_profile_v0.json`
  → no output (byte-identical).
- `diff .tmp/.../2026_rookie_transition_profile_v0.csv exports/candidate/.../2026_rookie_transition_profile_v0.csv`
  → no output (byte-identical).
- `diff .tmp/.../2026_manifest.json exports/candidate/.../2026_manifest.json` → differs only in
  `output_files[].path` (expected: the temp directory vs. the candidate directory); every other
  field, including all recorded hashes, is identical.
- Ran the dedicated validator against the regenerated files, from inside the repo worktree, with
  both input and output hash checks enabled:
  ```bash
  $ python3 -m scripts.validate_rookie_transition_profile \
      --export-json .tmp/rookie-transition-profile-promotion-repro/2026_rookie_transition_profile_v0.json \
      --manifest .tmp/rookie-transition-profile-promotion-repro/2026_manifest.json
  ROOKIE TRANSITION PROFILE VALIDATION PASSED
  ```
- The temporary directory (`.tmp/rookie-transition-profile-promotion-repro/`) was removed after
  this gate and does not appear in this PR's diff.

(An earlier version of this report ran the reproduction in a temp directory *outside* the repo
worktree, which produced six "Input file listed in manifest is missing" errors — a
path-resolution artifact of `resolve_path()` not finding a `.git` ancestor from that location, not
a defect in the candidate. That run substituted validation of the already-committed candidate at
its normal path, which proved the committed candidate valid but did not complete the requested
clean-reproduction validation gate itself. Re-running inside the worktree, as recorded above,
completes it directly.)

### 8. Full validation — PASS

```bash
$ python3 -m scripts.validate_rookie_transition_profile \
    --export-json exports/candidate/rookie-transition-profile/2026_rookie_transition_profile_v0.json \
    --manifest exports/candidate/rookie-transition-profile/2026_manifest.json
ROOKIE TRANSITION PROFILE VALIDATION PASSED

$ python3 -m scripts.validate_promoted_export \
    --export exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
    --manifest exports/promoted/rookie-alpha/2026_manifest.json
VALIDATION PASSED

$ python3 -m pytest tests/ -q
453 passed
```

(453 = the 449 tests present at PR #268's merge, plus 4 new promoted/candidate-parity regression
tests added by this review — see Gate 10.)

### 9. Scope and semantic review — PASS

- No rankings, row-level composite evidence score, predictive claims, role/archetype projection,
  landing-spot evaluation, granular route-profile expansion, or Forecast-specific binding anywhere
  in the artifact — confirmed by direct inspection of every field family and a full-text scan for
  scope-creep terms. The only incidental matches ("rankings", "predictive", "composite") are
  the artifact's own disclaimer explicitly *denying* rankings/predictive claims, and the
  pre-existing `athletic_testing` caveat noting the athletic score is an "in-house composite"
  (language already established before this issue, not a new composite score field).
- `nfl_team` appears only inside `official_postdraft_outcome.value` as an observed fact of the
  outcome itself — not present in any other field family.

### 10. Conditional promotion — EXECUTED

All nine gates above passed, so the artifact was promoted:

1. `exports/candidate/rookie-transition-profile/2026_rookie_transition_profile_v0.json` and
   `.csv` were copied byte-for-byte (verified via `diff`, and via SHA-256 equality below) to
   `exports/promoted/rookie-transition-profile/`.
2. A promoted manifest was written with schema version, season, generated timestamp, run ID,
   input paths/hashes, coverage summary, and output content hashes identical to the candidate
   manifest — only `output_files[].path` differs (points at `exports/promoted/...` instead of
   `exports/candidate/...`). No payload was regenerated, recomputed, normalized, or reordered.
3. The promoted triplet was validated independently:
   ```bash
   $ python3 -m scripts.validate_rookie_transition_profile \
       --export-json exports/promoted/rookie-transition-profile/2026_rookie_transition_profile_v0.json \
       --manifest exports/promoted/rookie-transition-profile/2026_manifest.json
   ROOKIE TRANSITION PROFILE VALIDATION PASSED
   ```
4. Regression coverage was added (`PromotedArtifactMatchesReviewedSnapshotTests` in
   `tests/test_validate_rookie_transition_profile.py`) asserting the promoted JSON/CSV hashes and
   the manifest's recorded output hashes match the exact SHA-256 values reviewed above, and that
   the promoted triplet independently passes full validation. This is pinned against those
   hardcoded reviewed hashes rather than the live `exports/candidate/` directory, since a future
   revision's candidate is expected to diverge from this promoted snapshot while it's mid-revision
   for its own later promotion review — comparing against the live candidate path would produce a
   false failure in that ordinary case, not a real regression.
5. This report is that promotion-review report.

**Promoted file hashes** (confirming byte-for-byte identity with the candidate):

| File | SHA-256 |
|---|---|
| `exports/promoted/rookie-transition-profile/2026_rookie_transition_profile_v0.json` | `c95b941c7855612daccfc2226fc51e0e34dbb2ebe8a2487596675d2522a22f37` (matches candidate) |
| `exports/promoted/rookie-transition-profile/2026_rookie_transition_profile_v0.csv` | `3005bcd6ad4ffc87a312c6926e20c5e3658747012855aa9d8ccfa33d898545e6` (matches candidate) |
| `exports/promoted/rookie-transition-profile/2026_manifest.json` | `0acf361c6d2d8cc6f684026481a5aa279e9f7fa718256fad78da0366d5804413` (differs from candidate manifest's hash only because of the `output_files[].path` change described above) |

## Hard-boundary compliance

- No changes to TIBER-Forecast, no Forecast mirror.
- No downstream consumption authorized.
- No predictive value evaluated or claimed.
- No production binding.
- The candidate was not changed to make this review pass — every gate above was checked against
  the artifact exactly as it existed at `0bf363a`, and passed without modification.
- `data/processed/2026_draft_capital_proxy.json` and `exports/promoted/rookie-alpha/*` are
  unmodified by this review (confirmed via `git status`/`git diff` showing only new files under
  `exports/promoted/rookie-transition-profile/`, plus this doc and the added regression tests).

## Decision

```text
rookie_transition_profile_v0_2_promoted
```

This makes `rookie_transition_profile_v0.2.0` a governed, promoted TIBER-Rookies source artifact
only. It does not authorize Forecast mirroring, predictive evaluation, downstream consumption, or
production/UI activation — any of those requires a separate, future issue and review.
