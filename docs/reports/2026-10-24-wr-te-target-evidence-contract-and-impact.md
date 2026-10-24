# WR/TE target-evidence contract and consumer impact (#303)

- **Base inspected:** `main` @ `b9c2d871e69f3c2230fe5c1447d9242f27f7c79a`
- **Scope:** first, bounded provenance/contract slice. No committed profile,
  score, rank, promoted export, manifest or ML artifact is rewritten. No
  producer was run against committed paths. No data was fetched.

## 1. Contract: `wr_te_target_evidence_v0`

`scripts/target_evidence.py` defines the block. The producer
(`scripts/fetch_wr_route_profiles.py`) writes it into new files.
`qualify_profile()` infers it for legacy files from `source_name` /
`methodology_notes`.

```json
"target_evidence": {
  "contract_version": "wr_te_target_evidence_v0",
  "qualification_origin": "producer | legacy_inferred",
  "targets": {"status": "...", "method": "...", "assumed_catch_rate": 0.70},
  "receptions": {"status": "..."},
  "yards_per_target": {"status": "derived", "denominator_status": "...", "observed_denominator": false},
  "scheme_fields": {"status": "unsupported", "fields": ["screen_targets", "screen_target_rate", "deep_target_rate", "depth_tag_coverage_rate"]},
  "lineage": {"source_name": "...", "source_url": "..."}
}
```

| `targets.status` | Meaning |
| --- | --- |
| `source_reported` | The source returned a target count (CFBD `TGT`). A reported `0` is an observed zero. |
| `parsed_partial` | Counted from play text by name matching. Observed but possibly incomplete (#146). |
| `estimated` | Computed from an assumption. `method` and `assumed_catch_rate` are recorded. |
| `unavailable` | No target evidence: null value, or player lookup failed. A stored `0` here is a placeholder, not an observation. |
| `unknown` | Legacy derivation could not be determined. It is never promoted to a stronger state. |

- `scheme_fields.status` is `unsupported` when the generating path carries no
  route/scheme descriptors. It is always `unsupported` for estimated or
  unavailable rows, because those have no play-level data. Genuinely parsed
  values are not marked `unsupported`.
- `yards_per_target.observed_denominator` is true only for `source_reported` /
  `parsed_partial` denominators.
- A `source_url` is never used as evidence of measured targets.
- **Stored blocks are validated before they are trusted** (`validate_target_evidence`).
  The checks are:
  - the recognized `contract_version` and `qualification_origin`;
  - the required object shape;
  - valid statuses;
  - `yards_per_target.denominator_status` equal to `targets.status`, with
    `observed_denominator` consistent with it;
  - `method` plus `assumed_catch_rate` in (0, 1] for estimates;
  - null `targets` ⇒ `unavailable`.

  An invalid block is degraded to `unknown` (`unavailable` when `targets` is
  null), with `invalid_stored_block` listing the violations. It is never
  promoted to observed evidence, and it is not re-inferred from prose.
- **Legacy inference reads only the per-row `source_name` derivation label**
  (`targets=CFBD TGT stat`, `targets estimated (REC / x)`, `CFBD play-by-play`).
  The producer's methodology note describes the REC/0.70 fallback
  conditionally on every row, so it is never read as a claim that the
  fallback was used.
- **Producer `receptions.status` follows field presence.** It is
  `source_reported` only when CFBD returned `REC`. With `TGT` but no `REC`,
  targets stay `source_reported` and receptions are `unavailable`. With
  neither, targets are `unavailable` (`method: missing_tgt_and_rec`), not an
  estimate. The numeric `0` placeholders are unchanged.
- No coverage or confidence value is invented. Legacy lineage copies the
  existing `source_name` / `source_url` verbatim.

The block is **additive**. Existing fields and their values are unchanged.

## 2. Inventory of committed profiles (66 files)

| Status | Method | Files | Notes |
| --- | --- | --- | --- |
| `estimated` | `receptions_div_assumed_catch_rate` (0.70) | 51 | Includes `wr-ted-hurst_2025` (101 targets from 71 rec; 9.9 YPT is estimate-derived). `receptions.status = unknown` (manual research, not re-verified here). |
| `estimated` | `synthetic_receptions_div_assumed_catch_rate` | 2 | `wr-antonio-williams_2024/2025`. Receptions are career-split estimates. Stored `0.0` screen/depth rates are qualified `unsupported`. |
| `parsed_partial` | CFBD play-by-play name matching | 12 | Notes already say screen/depth "carry no signal" → `unsupported`. |
| `unavailable` | — | 1 | `te-kenyon-sadiq_2025` (invalidated, all nulls). |
| `source_reported` | — | 0 | No committed file carries a CFBD `TGT` count. |
| `unknown` | — | 0 | |

## 3. Consumer audit

Chain: route profiles → `compute_breakout_age.py` (→ `2026_prospect_context.json`)
and `compute_age_adjusted_production.py` (→ `2026_age_adjusted_production.json`)
→ `compute_rookie_alpha.py` → promoted `2026_rookie_alpha_predraft_v0.json`.

### `compute_yoy_trends.py`: changed (metadata only)

- WR/TE rows gain `target_status_2024`, `target_status_2025`, `target_basis`
  (a status or `mixed`) and `efficiency_observed_denominators`.
- `validate_wr_te_rows()` fails generation if a WR/TE row lacks them or if
  they are inconsistent. `target_basis` must equal the shared status (or
  `mixed`), and `efficiency_observed_denominators` must be exactly
  `True`/`False` as derived from both statuses.
- Numeric fields and trend tags are computed exactly as before.
- Current committed inputs give 19 WR/TE pairs: 9 all-estimated, 7 mixed
  (estimated ↔ parsed/unavailable), 3 parsed-only. Only those 3 (`te-oscar-delp`,
  `wr-carnell-tate`, `wr-chris-brazzell-ii`) compare observed denominators.
  The other 16 YPT trends are not observed-efficiency evidence.
- **Pre-existing staleness:** committed `data/processed/2026_yoy_trends.json`
  has 13 WR/TE rows. Re-running today gives 19 rows, and 10 of the 13 committed
  rows differ numerically from the current profiles. The file was **not
  regenerated** here. It is a display-only artifact; regenerating it is a
  separate reviewed step.

### `compute_breakout_age.py`: audited, unchanged

- Line 308: `stat_value = profile.get("targets") or 0`, against the fallback
  thresholds WR ≥ 50 and TE ≥ 35.
- Estimates decide breakouts: among the 2026 WR/TE context rows, 43
  player-seasons meet the volume threshold **only via estimated targets**
  (share fields are absent from this family, so the fallback path is the
  operative one).
- Null becomes zero: `te-kenyon-sadiq_2025` (unavailable) is read as 0, i.e.
  "below threshold", not "unknown".
- `breakout_confidence` does not consider target evidence status.

### `compute_age_adjusted_production.py`: audited, unchanged

- Line 257: `float(profile.get(field) or 0.0)`. A missing file also returns 0.0
  (line 249).
- Of the 74 WR/TE rows in 2026 context: 37 all-estimated, 7 mixed with
  estimates, 3 parsed-only, 27 with **no profile file**. The 27 get volume 0
  and therefore a min-max-normalized score at the floor, not "unavailable".

### `compute_rookie_alpha.py` / promoted export: audited, unchanged

- `blend_production_rows` sets `production = 0.60 × age_adjusted + 0.40 × existing`.
  Breakout/BOAR fields flow into export `context`.
- The promoted 2026 predraft export has 34 WR/TE players:
  - 18 rely on all-estimated target rows.
  - 7 rely on mixed rows.
  - 3 rely on parsed-only rows.
  - 6 have no profile files and carry `age_adjusted_production_0_100 = 0.0`:
    `wr-deion-burks`, `wr-caleb-douglas`, `wr-jakobi-lane`,
    `wr-zavion-thomas`, `wr-kendrick-law`, `wr-barion-brown`.
- 23 export WR/TE rows carry a `breakout_age`; all of them rest on estimated
  or parsed rows.
- Observation: the 2026 manifest's `input_files` does not list
  `2026_age_adjusted_production.json`, although it influences production scores.
- **Current-score impact of a migration is not measured here.** Nothing above
  claims current scores are invalid.

## 4. What this PR repairs vs. defers

**Repaired (metadata/contract only)**

- Hurst's 101 targets and 9.9 YPT are machine-readably `estimated` /
  estimate-derived. Stored `screen_targets: 0` is `unsupported`.
- The producer distinguishes reported, estimated and unavailable (not found), and
  a genuinely reported zero.
- YoY output preserves per-season status and fails generation without it.
- README now describes the active producer and the mixed legacy family.

**Deferred: needs explicit review before any numeric change**

1. Whether `targets` should hold only observed counts (estimates moved to an
   `estimated_targets` field or nulled). This must not happen while consumers
   convert null to 0.
2. Breakout policy: treat `unavailable` as unknown rather than below threshold.
   Decide whether estimate-only breakouts should lower `breakout_confidence`
   or be excluded.
3. Age-adjusted production: treat missing/unavailable volume as unavailable
   rather than 0 (affects the 6 export WRs above and min-max normalization for
   everyone in the position group).
4. Regenerating `2026_yoy_trends.json` (display-only, stale) and the downstream
   context/age-adjusted/Alpha chain, each with a before/after numeric diff.
5. Embedding `target_evidence` into legacy files (vs. reader-inferred), and
   adding `2026_age_adjusted_production.json` to manifest inputs. Both are
   contract changes.
6. Updating TIBER-Research #55 after merge (maintainers).
