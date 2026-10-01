# 2026 Devy Pulse — audit and design report (TIBER-Rookies #298)

**Status:** audit/design report. §3's contract has a **synthetic-only S3 candidate implementation** on branch `claude/298-s3-devy-evidence-pulse-candidate` (`scripts/validate_devy_evidence_pulse.py`, fixtures under `data/fixtures/devy_evidence_pulse/`, tests in `tests/test_validate_devy_evidence_pulse.py`); see §3.6. Nothing is scheduled, promoted, wired, or run against real players.
**Issue:** [TIBER-Rookies #298](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/298) (remains open; this report does not close it).
**Authority for this packet:** the operator's bounded grant superseding #298's no-branch/no-PR restriction narrowly: one isolated branch, documentation only, one docs-only draft PR. No implementation, no football-data acquisition, no provider calls, no seed change, no ML execution.
**Prepared:** 2026-09-30 (UTC) from fresh clones of the four in-scope repositories.

## 0. Exact heads and what was reconciled

| Repository | Branch | Exact head at audit | Head commit |
| --- | --- | --- | --- |
| TIBER-Rookies | `main` | `a6f8555e79f3fc562a6c5f533acee583eeb12a3a` | Merge PR #292 (2026-08-24) |
| TIBER-Data | `main` | `e1e92078c626b9e2e502e927ba0de79afd26f451` | Merge PR #275 (2026-09-23) |
| TIBER-Ops | `main` | `4b9a967e89df68890111d1ee145088b527ff1d4c` | Operating Charter v0 (#87, 2026-09-29) |
| TIBER-Research | `main` | `0952e3325fb610f9cdb22c5242397d223c7a6c26` | Research #15 (2026-09-04) |

`git fetch origin main` was run for Rookies and Data; `origin/main` equals the local head in both. Rookies worktree was clean before this branch was created.

**Existing-work recovery.** No branch, PR, issue comment, or report for #298 existed before this packet: #298 has zero comments; a PR search for `298 devy pulse` in TIBER-Rookies returned nothing; `git ls-remote --heads origin` lists no branch containing `298`; open PRs are #297 (TIBER Now link) and #295 (#294 shell repair, unmerged). Data #265 has zero comments. This report therefore does not duplicate an existing packet.

**Read before drafting:** Rookies `AGENTS.md` and `CLAUDE.md`; Data `AGENTS.md`, `TRUTH_SOURCES.md`, `docs/contracts/college-player-game-observations-v0.md`; Rookies #298, #294, #218, PR #295 (body, seven conversation comments, four Codex review submissions); Data #265 and PR #275 (body, four conversation comments, two Codex review submissions, five inline threads); Ops `docs/architecture/tiber-product-boundary-v1.md` §10 and `tiber-operating-charter-v0.md`; the Rookies Devy docs, scripts, data, ML lane archive, migration note, and CFBD precedent scripts named below.

### 0.1 Data PR #275 — unresolved post-merge findings treated as explicit dependencies

PR #275 (`codex/data-265-college-observation-foundation-20260924`, base `6732954b…`, head `c720ee7d…`) merged at 2026-09-24T01:29:40Z. Codex reviewed it twice. All five inline threads are **unresolved** on GitHub as of this audit. The Data validator is therefore **not treated as settled** anywhere in this report.

| ID | Thread (Codex, P2) | Reviewed commit | Posted | State verified in Data `main` |
| --- | --- | --- | --- | --- |
| D-1 | Include `source_record_type` in evidence-scope checks (`…v0.py` L87–91) | `88baa00` | 00:38:27Z | Repair commit `c720ee7` adds `"source_record_type": row["source_record_type"]` to the binding dict. Thread still unresolved on GitHub. |
| D-2 | Preindex attribution ancestors before validating them (L507–517) | `88baa00` | 00:38:27Z | Repair commit `c720ee7` splits the attribution loop into an index pass then a check pass. Thread still unresolved on GitHub. |
| D-3 | Bind game expectation evidence to its declared scope (L129) | `c720ee7` | 01:33:43Z, **after merge** | Not addressed in `main`: `references(scope["expectation_evidence_refs"], "/coverage/game_scope", "scope")` still checks existence/kind only. |
| D-4 | Reject cyclic `unresolved` / `older_discovered_later` source relationships (L215–217) | `c720ee7` | 01:33:43Z, **after merge** | Not addressed in `main`: no self-link or cycle rejection on `related_observation_id`. |
| D-5 | Enforce synthetic identity rules on attribution states (L524–527) | `c720ee7` | 01:33:43Z, **after merge** | Not addressed in `main`: synthetic name/ID checks run only on baseline observation identities (L294–311). |

Two facts about the #275 review record matter for any future review loop, including this PR's:

- At 01:14:04Z Codex posted "Didn't find any major issues" for `c720ee7`; at 01:33:43Z a second review of the **same commit** (trigger: draft marked ready) posted D-3..D-5. A clean Codex conversation comment at a head is not proof that the head is clean.
- The `e1e9207` merge carries D-3..D-5 into Data `main`. Consumers that rely on "validator-valid envelope" inherit those gaps until Data repairs them (successor step S1, §8).

Rookies' own focused tests could not be run here: `pytest` is not installed in this environment (`python3 -m pytest` → `No module named pytest`). The read-only validators that need no test runner were run and are recorded in §1.4.

## 1. Current-state inventory (Rookies `main` a6f8555)

### 1.1 Devy lane

| Component | Path | Kind | Real vs fixture | State on 2026-09-30 |
| --- | --- | --- | --- | --- |
| Signal registry + validator | `scripts/devy_signal_registry.py` (`devy-prospect-registry-v0.1.0`) | code | n/a | Validates enums, horizons, split provenance, intake audit. **Passes** on both artifacts below. |
| Fixture registry | `data/fixtures/devy_prospect_registry_v0_fixture.json` | fixture | placeholder rows | Schema demonstration only. |
| Seed watchlist | `data/devy/devy_seed_watchlist_2026.json` | manual/Codex curated (intake `codex_curated_task`, issue #227 / PR #228) | 24 real names | `as_of_year 2026`; every provenance `last_verified_year` = 2026 (year granularity only). Identity provenance: 4 `official_roster`, 20 `recruiting_profile`. Signal provenance: **24/24 `manual_curated_seed_signal`**; zero rows carry `production_data`. School `unknown` for `tristen-keys` and `kayden-dixon-wyatt`. Lifecycle: 12 `TRUE_FRESHMAN`, 7 `EMERGING`, 3 `NFL_TRACK`, 2 `BREAKOUT_WINDOW`. Projected class: 5×2027, 7×2028, 12×2029. |
| Monthly roster pulse v1 | `scripts/validate_devy_roster_pulse.py` (`devy-roster-pulse-v0.1.0`), `data/devy/monthly_pulse/devy_roster_pulse_2026_05.json` | validator + one artifact | **fixture only** ("Fixture Candidate One", `example.edu`) | Validator passes. No pulse artifact exists for June–September 2026. The monthly pulse has never run on real roster evidence. |
| Deep market snapshot + coverage diff | `data/devy/league_market_snapshots/*.json`, `scripts/validate_devy_league_market_snapshot.py`, `scripts/compute_devy_league_market_snapshot_diff.py` | validator + producer + fixture | `snapshot_scope: fixture_subset` | Validator passes. Operator-supplied market observation lane, not football evidence. |
| Devy UI | `cards/devy/index.html`, `lib/devy/exportDevyCsv.js` | runtime | reads the seed watchlist | Optionally fetches `/data/devy/devy_rookie_transition_map_2026.json`, which **does not exist**; every row therefore renders `active_devy`. Open PR #295 (#294 step 1) repairs this and is unmerged (last Codex review at `9d17b15`, visual acceptance incomplete). |
| Prospect discovery pipeline | `docs/prospect-discovery-pipeline-design.md` (2026-05-16), `data/raw/2027_watchlist_seed.json` (3 rows) | design + stub | n/a | `discover_shadow_pool.py` / `promote_shadow_to_seed.py` were never built. |

**Finding F-1 (identity/transition conflict inside Rookies `main`).** Three seed rows are projected to the 2027 draft class, but the repo's own `data/processed/2026_draft_results.json` (`source_status: external_verified`) records 2026 NFL Draft selections whose normalized identity matches them:

| Seed row (`class_year 2024`, `projected_draft_class 2027`) | 2026 draft-results row | 2026 seed-pool row |
| --- | --- | --- |
| `jeremiah-love`, Notre Dame RB | `rb-jeremiyah-love` "Jeremiah Love", R1 P3, ARI | `rb-jeremiyah-love` "Jeremiyah Love", Notre Dame, class 2026 |
| `carnell-tate`, Ohio State WR | `wr-carnell-tate` "Carnell Tate", R1 P4, TEN | — |
| `nicholas-singleton`, Penn State RB | `rb-nick-singleton` "Nicholas Singleton", R5 P165, TEN | `rb-nick-singleton` "Nick Singleton", Penn State, class 2026 |

No reviewed crosswalk in the repo binds a seed `player_id` to a rookie `player_id`, so this report does not assert the rows are the same people. Either the seed rows are stale, or two identities collide on normalized name; both readings require manual review, and in both the current Devy UI presents `active_devy` for them. No seed change is made here (excluded). This is the concrete case for §5 and §6.

### 1.2 Rookie Alpha boundaries (unchanged, verified)

- Deterministic formula as documented in `README.md` L122–124 and `AGENTS.md` §6: RAS 35%, Production 45%, draft-capital proxy 20%; age-at-entry not implemented.
- 2026 college production (`data/processed/2026_college_production.json`, 48 rows; `2026_player_stats.json`, 48 rows) is **CFBD 2025-season, season-level** totals for the 2026 *draft class*. It is not 2026 in-season evidence and not a Devy input.
- `docs/devy-signal-discovery.md` "Relationship to Rookie Alpha" and the seed `intake_audit.downstream_eligibility = blocked_until_rookie_transition` remain the governing boundary. No Devy → Rookie Alpha path exists; none is proposed here.
- `docs/rookie-transition-profile-contract.md` (`v0.2.0` promoted) is the only governed rookie evidence-consolidation layer; its design doc lists the Devy → rookie transition mechanism as an explicitly open question.
- Read-only integrity: `validate_promoted_integrity.py` **PASSED** (32 artifacts, 4 families).

### 1.3 Quarantined ML lane (unchanged, verified)

- Frozen archive `exports/experimental/rookie-ml-lane/` (10 artifacts incl. `experimental_status_v0.json`); demoted from `exports/promoted/` on 2026-08-23 under #286 WP-2 (`docs/migrations/2026-08-23-rookie-ml-lane-demotion.md`). `validate_experimental_integrity.py` **PASSED** (9 frozen digests verified against the pinned inventory).
- Producer `scripts/compute_rookie_ml_lane.py` writes only to `runs/rookie-ml-lane/` (gitignored) and refuses the archive and the promoted namespace. Not executed for this audit.
- Full component assessment in §7.

### 1.4 Established college acquisition paths (precedent only; none exercised)

| Script | CFBD endpoint | Grain | Used for |
| --- | --- | --- | --- |
| `scripts/compute_production_scores.py` | `/stats/player/season?year&category` | season | 2022–2026 draft-class production scores |
| `scripts/fetch_missing_stats.py` | `/stats/player/season` | season | targeted backfill |
| `scripts/compute_breakout_age.py` | `/roster?team&year` | roster | breakout age |
| `scripts/cfbd_plays.py` + `scripts/fetch_qb_play_profiles.py` (the only caller of `fetch_team_plays`) | `/plays?year&team&seasonType&week` | play | QB play profiles |
| `scripts/fetch_rb_play_profiles.py`, `scripts/fetch_wr_route_profiles.py` | `/stats/player/season?year&category` | season | RB/WR/TE profile proxies; targets **estimated** as receptions/0.70 when CFBD returns no `TGT` stat |

`CFBD_API_KEY` is read from the environment (`.env.example`); no key exists in this session and no call was made. Points that bound "established":

- `docs/draft-results-provenance.md` already assigns CFBD ingestion for draft results to **TIBER-Data**; Rookies must not maintain a second authoritative CFBD path for that artifact. The same ownership logic applies to game-level college observations (Data #265 §1).
- No document in either repo records CFBD terms, permitted automated use, retention or redistribution rights. Data's contract doc states explicitly: "No terms/entitlement decision or real data access occurred in this slice."
- `data/processed/wr_route_profiles/` shows the failure mode to avoid: rows with `source_url: null`, targets **estimated** as receptions/0.70, and a `source_name` naming an LLM cross-verification. The Data contract excludes exactly these from `observed`. Play-level acquisition precedent is therefore limited to the QB path; the RB/WR/TE profile fetchers are season-level.

### 1.5 Cross-repo positioning

- Ops product boundary v1 §10 Phase 1: "Record that Pulse depends on a governed World/event-change contract. Audit TIBER-Rookies Devy Pulse before inventing a duplicate architecture." This report is that Rookies-side audit; it proposes no Fantasy/Ops Pulse surface.
- Data #265 §1 places observed college facts, identity, finality and correction lineage in TIBER-Data and leaves Devy interpretation downstream. §3 below is designed as a **consumer** of Data's `college_player_game_observations` envelope, never as a second observation store.

## 2. 2026 college-evidence readiness matrix

Classification vocabulary is #298's. Two columns are deliberately separate: **contract capability** (what a schema can hold) and **2026 coverage** (what real 2026-season evidence exists in any TIBER repo). As of this audit, **zero 2026-season college player/game observations exist in TIBER-Rookies, TIBER-Data, TIBER-Ops or TIBER-Research.** The only real college-observation material is Data's synthetic fixture (9 synthetic observations, `evidence_mode=synthetic_fixture`, `population_status=partial`).

| Field | Classification | Exact evidence / contract | 2026 coverage | Permitted-use boundary | Missing information |
| --- | --- | --- | --- | --- | --- |
| Player identity (name) | `READY_NOW` (seed) | Seed watchlist 24 rows, `identity_provenance` with URL for `official_roster` rows | 24 curated names; not a universe | Public roster/recruiting profile identity only | No seed ↔ Data canonical college ID binding; Data has "no general identity allocator" |
| School / program | `READY_NOW` (seed, partial) | Seed `school`; Data event-time `game.team.source_program_id` per observation | 22/24 known, 2 `unknown` | As above | Event-time program per game requires observations |
| Position | `READY_NOW` (seed) | Seed `position` (QB/RB/WR/TE) | 24/24 | As above | Source position per game requires observations |
| Class / timeline | `READY_NOW` (manual context) | Seed `class_year`, `projected_draft_class`, `timeline_provenance` (`manual_eligibility_context` / `recruiting_profile`) | 24/24, year-granular | Framed as projected/earliest, never declaration prediction | F-1 shows timeline can be stale against official draft results; no re-verification date finer than year |
| Game / week identity, season scope | `REQUIRES_DATA_OWNED_DERIVATION` | Data contract: `game.season`, `source_game_id`, nullable `date`, status `scheduled|in_progress|final|suspended|cancelled|unknown`; no NFL-week field | none | Provider-scoped IDs; no provider admitted | Provider qualification (S2) |
| Passing (att/comp/yds/TD/INT) | `REQUIRES_DATA_OWNED_DERIVATION` | Data `observed.passing` cells with 8 availability states; CFBD season-level precedent in Rookies (2025 season only) | none for 2026 | Only source-credited game values; no season totals in `observed` | Provider field mapping, sack/kneel semantics, correction chronology |
| Rushing (carries/yds/TD) | `REQUIRES_DATA_OWNED_DERIVATION` | Data `observed.rushing` | none | as above | as above |
| Receiving (receptions/yds/TD) | `REQUIRES_DATA_OWNED_DERIVATION` | Data `observed.receiving` | none | as above | as above |
| Targets | `REQUIRES_DATA_OWNED_DERIVATION`, likely `unavailable_from_source` | Data `observed.receiving.targets` nullable; the `wr_route_profiles` fetcher estimates targets as REC/0.70 from season-level stats (its README describes play-text attribution; the two descriptions disagree) | none | Estimated targets are **excluded** from `observed` by the Data contract | Whether any qualified provider credits targets at box-score grain |
| Team denominators / opportunity share | `BLOCKED_OR_UNAVAILABLE` (no contract) | Data contract: "no opportunity score or derivations"; companion contract required with numerator, denominator, formula version, source-game refs, status | none | Rookies must not compute shares from partial team data | Team-level per-game totals contract (Data), denominator completeness |
| Touchdowns / scoring-area production | TD counts: `REQUIRES_DATA_OWNED_DERIVATION`; scoring-area splits: `OPTIONAL_FUTURE_ENRICHMENT` | TDs in each category; red-zone/scoring-area named as a future companion contract | none | — | Play-level source qualification |
| Games played / active participation | `BLOCKED_OR_UNAVAILABLE` | Data: `observed_game_ids` "measures source coverage, never player participation"; an absent row "is never … inactivity, participation, game played" | none | Pulse may say "games with an observed source row", never "games played" | Independent participation evidence contract (none exists) |
| Program / roster changes | `DERIVABLE_NOW` (manual only) | Roster pulse v1 statuses (`new_on_roster`, `still_present`, `missing_from_roster`, `program_changed`, `unresolved`); `/roster` precedent | none for 2026 (May pulse is fixture) | Operator-supplied, URL-cited roster observations | An automated roster source is not admitted; transfer facts are time-bounded only in Data's envelope |
| Evidence freshness / corrections / provenance | `REQUIRES_DATA_OWNED_DERIVATION` | Data three-clock model (`game.date`, `source_updated_at`, `retrieved_at`, `known_at`, `recorded_at`), `source_relationship` statuses, `retained_snapshot_digest`; Rookies has only `last_verified_year` | none | Correction lineage must be carried, never collapsed | D-3..D-5 leave expectation scope, cycles and synthetic-identity enforcement unsettled |
| Two-point conversions, fumbles, special teams | `OPTIONAL_FUTURE_ENRICHMENT` | Requested in Data #265 §3; **not** in contract v0.1.0 (`passing/rushing/receiving` only) | none | — | Contract version bump in Data |
| Market / operator observations | out of matrix (not football evidence) | League market snapshot fixture lane | fixture | Kept separate per #298 source boundary | — |

Legal boundary for every row: `docs/legal/external-source-hygiene-policy.md` and Rookies `AGENTS.md` §5. Nothing above admits a source, and the CFBD precedent is not a permission record.

## 3. Proposed Devy Pulse v2 contract (design only)

**Name:** `devy_evidence_pulse_checkpoint`, proposed `schema_version: devy-evidence-pulse-v0.1.0`. Additive to roster pulse v1 (`devy_roster_pulse_candidate_delta`), which continues to own roster/program deltas. Not implemented here; no validator exists yet.

### 3.1 Design rules

1. **Consumer, not store.** A checkpoint reads one or more TIBER-Data `college_player_game_observations` envelopes (`artifact_position=unpromoted` acceptable only while the checkpoint itself is non-promoted) and records their `generated_at` and a `sha256` of each envelope. It never fetches a provider and never holds observations Data does not hold.
2. **As-known cutoff.** Each checkpoint has `as_known_at`. It may cite only evidence whose `known_at`/`retrieved_at`/`recorded_at` ≤ `as_known_at`. A later checkpoint never rewrites an earlier one.
3. **Missing is not zero; absent is not inactive.** Cells copy Data's `availability` state verbatim. A prospect whose binding is `MATCHED` and who has no source row in the window gets `evidence_change_state = NO_OBSERVED_ROWS`, not zeros and not a participation claim. A prospect without a `MATCHED` binding never gets a coverage statement at all (rule 5).
4. **Corrections stay visible.** A change caused by a Data `established_supersession` is reported as `CORRECTED_EVIDENCE` with both `observation_id`s. Any `unresolved`/`older_discovered_later` relation in the window forces `CONFLICTING_EVIDENCE`, and the checkpoint must fail closed rather than pick a leaf (it must not rely on Data's validator alone for cycle rejection while D-4 is open).
5. **Identity is bound, never inferred.** Each row carries `identity_binding` whose `status` is derived only by the §6.2 mapping from the *effective* crosswalk decision at `as_known_at` (the latest reviewed decision for that seed `player_id` in the pinned crosswalk, following its supersession chain). The invariant holds in both directions: `identity_binding.status = MATCHED` if and only if `evidence_change_state ≠ IDENTITY_UNRESOLVED`. Every non-`MATCHED` row (`MATCH_CANDIDATE`, `UNBOUND_SEED`) carries `evidence_change_state = IDENTITY_UNRESOLVED` and **null** `evidence_window`, `observed`, `prior_observed`, `delta`, `coverage_state` and `coverage_flags`: the envelopes may hold that player under an identity the pulse cannot associate, so neither a delta, nor an absence claim, nor any evidence or coverage assertion about the player is permitted. `MATCH_CANDIDATE` rows may list candidate crosswalk evidence under `identity_binding.evidence_refs` for the reviewer, nothing more.
6. **No grades, no ranks, no predictions.** No numeric score, no ordering field, no draft-capital projection. Interpretive vocabulary is enumerated and coarse (§3.3).
7. **No seed mutation.** `auto_seed_watchlist_mutation: "none"` is required on every row, as in v1.
8. **Coverage is orthogonal to change, and belongs only to bound rows.** Every `MATCHED` row carries `coverage_state` and `coverage_flags`, computed by the §3.3 precedence from the checkpoint's `inputs.data_envelopes` and `window`, independent of `evidence_change_state`. A corrected row inside a partial envelope is `CORRECTED_EVIDENCE` with `coverage_state = INCOMPLETE`; neither fact hides the other. Checkpoint-level `coverage_warnings` describe the cited envelopes without reference to any seed row, so incomplete coverage stays visible even when every row is unresolved.

### 3.2 Envelope shape (sketch)

```text
artifact_type: devy_evidence_pulse_checkpoint
schema_version: devy-evidence-pulse-v0.1.0
checkpoint_id, as_known_at, generated_at
prior_checkpoint: {checkpoint_id, sha256} | null
inputs:
  data_envelopes: [{path_or_locator, generated_at, sha256, evidence_mode, population_status, competition_scope}]
  seed_watchlist: {path, sha256, as_of_year}
  identity_crosswalk: {path, sha256} | null   # complete pinned crosswalk; null ⇒ every row UNBOUND_SEED
window: {season, game_scope_source: "data_envelope", expected_game_ids | null, observed_game_ids}
coverage_warnings: [...]           # checkpoint-level: population partial/unknown, expectation unknown, envelope synthetic
rows: [
  seed_player_id
  identity_binding: {status: MATCHED|MATCH_CANDIDATE|UNBOUND_SEED,
                     crosswalk_row_ref | null, crosswalk_status | null,      # must equal the §6.2 effective decision
                     canonical_college_player_id | null, decision_known_at | null, evidence_refs}
  coverage_state: COMPLETE|INCOMPLETE|UNKNOWN | null, coverage_flags: [...] | null   # §3.3 precedence; null unless MATCHED
  evidence_window: {games_with_observed_rows, games_expected | null, finality_by_game} | null   # null unless MATCHED
  observed: {passing, rushing, receiving} | null    # per-cell {value, availability, observation_id, source_revision_id}; null unless MATCHED
  prior_observed: same shape from prior_checkpoint | null                                      # null unless MATCHED
  delta: null unless MATCHED; otherwise per category, per cell {prior_value, current_value, difference | null,
         basis: same_revision|corrected|new_rows|not_comparable, note}
         # difference = current_value - prior_value, integers only, non-null only when
         # both cells are observed_zero|observed_value, the row is MATCHED, and
         # evidence_change_state is not CONFLICTING_EVIDENCE or INSUFFICIENT_EVIDENCE;
         # a plain arithmetic derivation of copied cells, never a rate, share, score or grade
  opportunity: {status: unavailable, reason: no_denominator_contract}   # until a Data companion exists
  context: {program_state, roster_status, class_context}                # from v1 pulse or manual, with provenance
  evidence_change_state, context_change_state
  auto_seed_watchlist_mutation: "none"
  needs_manual_review: bool
]
seed_review_proposals: [...]       # §5
intake_audit: {intake_method, promotion_status: non_promoted_discovery_only, validation_command, downstream_block}
```

### 3.3 Change vocabulary (proposed enumerations)

`evidence_change_state`: `NEW_EVIDENCE` (new observed rows since prior checkpoint, same revision lineage) · `NO_NEW_EVIDENCE` (rows unchanged) · `NO_OBSERVED_ROWS` (binding `MATCHED`, no source row in window; says nothing about participation) · `CORRECTED_EVIDENCE` (an established supersession changed at least one cell) · `CONFLICTING_EVIDENCE` (unresolved source relation; no delta computed, `delta` empty) · `IDENTITY_UNRESOLVED` (binding not `MATCHED`, including seeds with no crosswalk decision; `evidence_window`, `observed`, `prior_observed`, `delta`, `coverage_state` and `coverage_flags` null; no absence or coverage claim) · `INSUFFICIENT_EVIDENCE` (fewer than the operator-declared minimum observed games; no delta computed, `delta` empty). Coverage is **not** a value of this enumeration.

`coverage_flags` are computed first, as the exact set of the following that hold for the checkpoint's `inputs.data_envelopes` and `window`: `population_unknown` (any envelope `population_status = unknown`) · `expected_games_unknown` (`window.expected_game_ids` null) · `population_partial` (any envelope `population_status = partial`) · `expected_game_missing` (an expected game in the window has no observed game entry) · `envelope_synthetic` (any envelope `evidence_mode = synthetic_fixture`; informational, never affects the state). `coverage_state` is then derived from the flags by strict precedence, so the predicates are mutually exclusive by construction: `UNKNOWN` if `population_unknown` or `expected_games_unknown` is set; otherwise `INCOMPLETE` if `population_partial` or `expected_game_missing` is set; otherwise `COMPLETE`. A `partial` envelope with null `expected_game_ids` therefore carries both `population_partial` and `expected_games_unknown` and is `UNKNOWN`, not `INCOMPLETE`. The validator recomputes the flag set and the state and rejects any difference. A row's `coverage_state` never alters its `evidence_change_state`: deltas are still reported under `INCOMPLETE` and `UNKNOWN` coverage, and the flags travel with them. In v0.1.0 the computation uses the whole checkpoint window, so every `MATCHED` row carries the same values; the fields are per row so that the **null** on non-`MATCHED` rows is explicit (rule 5) and so a future program-scoped envelope can narrow them. On `MATCH_CANDIDATE` and `UNBOUND_SEED` rows both fields are null; the envelopes' incompleteness is still visible through the checkpoint-level `coverage_warnings`, which name envelopes, never players.

`context_change_state`: `UNCHANGED` · `PROGRAM_CHANGED` · `ROSTER_STATUS_CHANGED` · `CLASS_CONTEXT_CHANGED` · `UNKNOWN`.

The #298 example words "stronger/stable/weaker" are intentionally **not** adopted: they read as a grade. If an interpretive band is later wanted, it must be a separate, manually assigned seed-signal field with `signal_provenance`, not a pulse output.

### 3.4 Validation (future `scripts/validate_devy_evidence_pulse.py`)

Fail closed on: any row whose `identity_binding.status` is not `MATCHED` and whose `evidence_change_state` is not `IDENTITY_UNRESOLVED`, or that carries a non-null `evidence_window`, `observed`, `prior_observed`, `delta`, `coverage_state` or `coverage_flags`; any `IDENTITY_UNRESOLVED` on a row whose binding is `MATCHED`; any `identity_binding` field that differs from the §6.2 *effective* decision for that seed `player_id`, recomputed by the validator from the complete pinned crosswalk (`inputs.identity_crosswalk.sha256`) at `as_known_at` — every decision-derived field is recomputed (`status`, `crosswalk_row_ref`, `crosswalk_status`, `canonical_college_player_id`, `decision_known_at`, `evidence_refs`), with nulls and `[]` when no decision exists; a cite of a superseded row, of a row with `decision_known_at > as_known_at`, or of a row absent from the pinned crosswalk is rejected, never degraded to `MATCH_CANDIDATE`; a crosswalk fork at the cutoff (§6.2) fails the checkpoint; checkpoint-level `coverage_warnings` that differ from the exact envelope-level set recomputed from every pinned envelope and the window (one `{flag, scope}` entry per applicable predicate, validated even when every row is unresolved); any `MATCHED` row missing `coverage_state` or `coverage_flags`, or whose flag set or state differs from the §3.3 recomputation (exact set equality for flags, strict precedence for the state); any cell value present with availability other than `observed_zero|observed_value`; any delta on a row whose binding is not `MATCHED`; any delta across a corrected pair without `CORRECTED_EVIDENCE`; `prior_checkpoint.sha256` mismatch; cited `known_at` later than `as_known_at`; any `opportunity` value while no denominator artifact is declared; missing `auto_seed_watchlist_mutation: "none"`; any `NO_OBSERVED_ROWS` on a row whose binding is not `MATCHED`; any non-null `delta.difference` on a row whose `evidence_change_state` is `CONFLICTING_EVIDENCE` or `INSUFFICIENT_EVIDENCE`; any score, rank, grade, probability, projection or ordering field. Numeric values are permitted only in copied observed cells (`observed`, `prior_observed`, `delta.prior_value`, `delta.current_value`), computed per-cell `delta.difference` values (integer `current_value − prior_value`; null unless both cells are observed and the row is `MATCHED`, and always null in the `CONFLICTING_EVIDENCE` and `INSUFFICIENT_EVIDENCE` states; the validator recomputes and rejects any mismatch), structural identifiers and clocks (`season`, game IDs, timestamps, digests) and coverage counts (`games_with_observed_rows`, `games_expected`). Rates, shares, per-game averages and any other derived number remain prohibited until a Data-owned denominator contract exists.

### 3.5 Specification examples (synthetic; checked against §3.1–§3.4, §5, §6.2)

All names and IDs are synthetic. Each example uses one checkpoint with `as_known_at = T`, one Data envelope `E` for the window, and the pinned crosswalk `X`. "Expected" rows are what a conforming producer emits; "Verdict" is what the §3.4 validator does with the row as described.

| # | Scenario | Crosswalk at `T` → effective decision → binding | `evidence_change_state` | `coverage_state` / `coverage_flags` | `evidence_window` · `observed` · `delta` | Verdict and rules exercised |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | Unresolved identity: seed `synthetic-seed-a` has no row in `X`; `E` is `population_status = partial`, `expected_game_ids` known | no row → `UNBOUND_SEED` | `IDENTITY_UNRESOLVED` | null / null | null · null · null | Accepted. §3.1 r5 (both directions), §3.3 (coverage null on non-`MATCHED`), §5 `UNBOUND_SEED`, §6.2 "no row". The envelope's partiality appears only in checkpoint-level `coverage_warnings` (§3.1 r8), never as a statement about seed A. |
| E2 | Stale crosswalk citation: `X` holds `R1` (`READY`, canonical `synthetic-college-b`, `decision_known_at = T−5d`) and `R2` (`TRANSFER_VERIFY`, `supersedes = R1`, `decision_known_at = T−1d`); the checkpoint cites `crosswalk_row_ref = R1` with binding `MATCHED` and a delta | effective decision = `R2` (R1 discarded as superseded) → `MATCH_CANDIDATE` | `NEW_EVIDENCE` as submitted | `COMPLETE` as submitted | populated as submitted | **Rejected**, two independent reasons: `crosswalk_row_ref ≠ R2` (stale cite, §3.4 / §6.2 effective decision) and `status = MATCHED ≠ MATCH_CANDIDATE` (§6.2 mapping). The conforming row is `MATCH_CANDIDATE`, `IDENTITY_UNRESOLVED`, all evidence and coverage fields null, `needs_manual_review = true`. Recomputing only from the cited `R1` would wrongly accept it. |
| E3 | Unknown expectations: seed C is `MATCHED` via qualified `READY` `R3`; `E` is `population_status = complete` but `window.expected_game_ids` is null; two observed source rows for C, both new since the prior checkpoint, same revision lineage | `R3` effective → `MATCHED` | `NEW_EVIDENCE` | `UNKNOWN` / [`expected_games_unknown`] | `{games_with_observed_rows: 2, games_expected: null}` · cells observed · `difference` integers where both cells observed | Accepted. §3.3 precedence (`expected_games_unknown` ⇒ `UNKNOWN` even though population is complete), §3.1 r8 (delta still reported, flag attached), §3.4 flag set equality. `games_with_observed_rows` counts source rows, not participation (§3.1 r3). |
| E4 | Known incomplete coverage: seed D is `MATCHED` via qualified `READY` `R4`; `E` is `partial`; `expected_game_ids` lists three games, `observed_game_ids` two; D's observed cells are unchanged from the prior checkpoint | `R4` effective → `MATCHED` | `NO_NEW_EVIDENCE` | `INCOMPLETE` / [`population_partial`, `expected_game_missing`] | `{games_with_observed_rows: 2, games_expected: 3}` · unchanged cells · `difference = 0` for observed pairs, `basis = same_revision` | Accepted. §3.3 (`INCOMPLETE` because no `UNKNOWN` flag is set), §3.1 r8 (coverage independent of change state), §3.4 exact flag set. Says nothing about whether D played the third game. |
| E5 | Corrected evidence with incomplete coverage: seed F is `MATCHED` via qualified `ALIAS_RESOLVED` `R5` whose alias claim is current; `E` is `partial` with all expected games observed; a Data `established_supersession` replaces F's passing yards 240 → 245 in one game | `R5` effective → `MATCHED` | `CORRECTED_EVIDENCE` (both `observation_id`s cited) | `INCOMPLETE` / [`population_partial`] | populated · both revisions' cells · `difference = 5`, `basis = corrected` | Accepted. §3.1 r4 (correction visible), r8 (`CORRECTED_EVIDENCE` and `INCOMPLETE` coexist), §3.3 precedence, §3.4 (delta across a corrected pair requires `CORRECTED_EVIDENCE`; `difference` permitted because the state is neither `CONFLICTING_EVIDENCE` nor `INSUFFICIENT_EVIDENCE`). |
| E6 | Precedence check: as E4 but `window.expected_game_ids` null | `MATCHED` | `NO_NEW_EVIDENCE` | `UNKNOWN` / [`population_partial`, `expected_games_unknown`] | as E4 with `games_expected: null` | Accepted only with state `UNKNOWN`; a producer emitting `INCOMPLETE` with the same flags is rejected (§3.3 strict precedence, §3.4). |

Cross-check summary: E1 and E2 exercise rule 5 in both directions and the null-coverage rule; E2 additionally proves that the validator must recompute from the complete pinned crosswalk; E3, E4 and E6 pin the three coverage states and the precedence; E5 proves coverage and correction remain simultaneously visible. No example emits a score, rank, rate, share or seed mutation, and every delta sits on a `MATCHED` row whose state permits it.

### 3.6 S3 candidate implementation and reconciliation (synthetic-only)

The §3 contract is implemented as a candidate on branch `claude/298-s3-devy-evidence-pulse-candidate`, stacked on this report's PR #299 head and kept out of that docs-only PR. Files: `scripts/validate_devy_evidence_pulse.py` (contract constants, effective-decision and coverage recomputation, fail-closed validator, read-only CLI), `data/fixtures/devy_evidence_pulse/` (two synthetic envelopes, a synthetic seed list, a synthetic crosswalk with a supersession chain, a prior and a current checkpoint), and `tests/test_validate_devy_evidence_pulse.py` (valid cases plus deliberate violations across identity resolution, supersession, cutoff timing, coverage precedence, corrections, null handling and prohibited numeric outputs). Validation command:

```bash
python3 scripts/validate_devy_evidence_pulse.py --checkpoint data/fixtures/devy_evidence_pulse/synthetic_checkpoint_2026_w03.json
python3 -m pytest tests/test_validate_devy_evidence_pulse.py -q
```

Where the implementation refines the prose above, the implementation governs and the prose has been reconciled:

| Topic | Implemented rule | Review lineage |
| --- | --- | --- |
| Binding fields | The validator recomputes **every** decision-derived `identity_binding` field from the effective decision and rejects any difference; `canonical_college_player_id` is non-null only on `MATCHED` rows; `evidence_refs` is the sorted list of the decision's evidence locators (`[]` without a decision) | R6-1 |
| Checkpoint-level coverage | `coverage_warnings` is the exact sorted set of `{flag, scope}` entries recomputed from every pinned envelope (`population_partial`, `population_unknown`, `envelope_synthetic` scoped to the envelope path) and the window (`expected_games_unknown` scoped `window`, `expected_game_missing` scoped `window:<season>:<game>`), required even when every row is `IDENTITY_UNRESOLVED` | R6-2 |
| Crosswalk fork | More than one unsuperseded decision at the cutoff fails the checkpoint (`CROSSWALK_FORK`); no synthetic `AMBIGUOUS` row is fabricated | R6-3 |
| Per-game cells | `observed`, `prior_observed` and `delta` are keyed by `"<season>:<source_game_id>"` so one checkpoint can hold several games and a correction stays attributable to one game | §3.2 refinement |
| No-delta states | `delta` is `{}` (not a structure of nulls) in `CONFLICTING_EVIDENCE`, `INSUFFICIENT_EVIDENCE` and `NO_OBSERVED_ROWS`; `observed` is `{}` and `finality_by_game` is `{}` in `CONFLICTING_EVIDENCE`, because the pulse must not pick a leaf | §3.3 refinement, R3-1 |
| Competing assertions | A prior-cited revision that is neither the current leaf nor one of its ancestors, or a prior-cited game absent from the current window, yields `CONFLICTING_EVIDENCE` | §3.1 rule 4 |
| Window | `window.observed_game_ids` and `expected_game_ids` are recomputed as the sorted unions over pinned envelopes for the season; any envelope with unknown expectations makes the window's expectations null | §3.2 |
| Operator parameter | `insufficient_evidence_min_games` (integer ≥ 1) is an explicit checkpoint field, so `INSUFFICIENT_EVIDENCE` is reproducible | §3.3 |
| Context | `context.source ∈ {none, seed_watchlist, devy_roster_pulse_v1, manual}`; with `none`, all context fields are null and `context_change_state = UNKNOWN`; the candidate fixtures use `none` | §3.2 |
| Cutoff on decision evidence | A crosswalk row citing evidence first known after its `decision_known_at` is a crosswalk defect; only refs known by `as_known_at` qualify a decision or appear in `evidence_refs` | PR #300 review C1 |
| Alias currency | `alias_claim` is exactly `{representative_observation_id}`; currency is recomputed from the pinned envelopes (present, known by cutoff, resolved to the decision's canonical, not superseded) | PR #300 review C2 |
| Prior lineage | The prior checkpoint is validated recursively against its own pinned inputs before any of its cells feed `prior_observed` or deltas; a failing or cyclic prior fails this checkpoint (`PRIOR_INVALID`) | PR #300 review C3 |
| Overlapping envelopes | Identical observations repeated across pinned envelopes are coalesced by `observation_id`; the same ID with different content is an input defect (`INPUT_CONFLICT`), never an evidence conflict | PR #300 review C4 |
| Synthetic provenance | `evidence_mode = synthetic_fixture` is forced whenever any pinned envelope is synthetic, and then seed names must start with `SYNTHETIC`, canonical and observation IDs must contain `synthetic`, and the crosswalk must be synthetic | Data contract convention |
| Strictness | Unknown keys anywhere fail (`UNKNOWN_FIELD`); keys containing score/rank/grade/probability/projection/forecast/tier fail (`PROHIBITED_FIELD`); numeric leaves outside copied cells, computed differences, structural identifiers, clocks and coverage counts fail (`PROHIBITED_NUMERIC`) | §3.1 rule 6, §3.4 |

What the candidate does **not** do: it does not run TIBER-Data's envelope validator (its fixtures are subset-shaped and prove nothing about D-1..D-5), does not qualify any provider, does not touch the real seed watchlist, does not create a crosswalk for real seeds, does not produce checkpoints (there is no producer; the validator recomputes everything), and is not wired to any runtime, Rookie Alpha, ML or downstream surface. Passing its tests establishes contract behaviour only, never 2026 coverage or real-player readiness.

## 4. Cadence recommendation (nothing scheduled)

**Recommendation:** a **weekly checkpoint capability** aligned to the college game week, with **monthly operator review** of roster/program context via pulse v1. Rationale: box-score corrections and finality settle on a days-scale, so a monthly window would collapse correction lineage and hide within-month changes; a weekly `as_known_at` preserves them. Roster/class context changes slowly and stays monthly.

**Qualification:** cadence is a property of a source that does not exist yet. Until a provider is qualified (S2) and a bounded sample exists (S5), a weekly checkpoint would be an empty artifact. No cron, workflow, trigger, or routine is proposed or created by this report; the first checkpoints should be operator-run, one at a time, against a named Data envelope.

## 5. Seed-watchlist relationship (no automatic mutation)

The seed watchlist is the pulse's **identity anchor**, never its output. Binding status is never assigned by the pulse itself; it is derived only by the §6.2 mapping from the *effective* crosswalk decision at `as_known_at`, and the validator recomputes that decision from the complete pinned crosswalk rather than trusting the cited row.

| Binding status | Derived from (§6.2) | Meaning | Pulse behaviour |
| --- | --- | --- | --- |
| `MATCHED` | qualified `READY` or qualified `ALIAS_RESOLVED` | reviewed crosswalk row binds `seed player_id` ↔ Data `canonical_college_player_id` | deltas computed; if the bound identity has no source row in the window, `NO_OBSERVED_ROWS` (not proof of inactivity or transfer) |
| `MATCH_CANDIDATE` | effective decision `AMBIGUOUS`, `POSSIBLE_DUPLICATE`, `TRANSFER_VERIFY`, or an unqualified `READY`/`ALIAS_RESOLVED` | a candidate identity exists but is not resolved (Data: names and school do not resolve identity) | `IDENTITY_UNRESOLVED`; candidate crosswalk evidence listed under `identity_binding.evidence_refs` for the reviewer; `evidence_window`, `observed`, `prior_observed`, `delta`, `coverage_state`, `coverage_flags` null; `needs_manual_review=true` |
| `UNBOUND_SEED` | effective decision `UNAVAILABLE`, or no crosswalk row known by `as_known_at` | seed row with no usable crosswalk decision | `IDENTITY_UNRESOLVED`; `evidence_window`, `observed`, `prior_observed`, `delta`, `coverage_state`, `coverage_flags` null, because the envelopes may contain the player under an identity the pulse cannot associate; `needs_manual_review=true` |
| `NON_SEED_CANDIDATE` | observed player not on the seed list who meets an operator-declared discovery rule | appears only in `seed_review_proposals` |

`seed_review_proposals` rows carry `proposal_kind` (`add_candidate`, `re_verify_identity`, `transition_review`, `school_update_candidate`), the evidence refs, and `auto_seed_watchlist_mutation: "none"`. Applying any proposal remains a manual issue → PR → `intake_audit` change validated by `devy_signal_registry.py`, exactly the #227 → #228 path. F-1 would be the first `transition_review` proposals.

## 6. Longitudinal prospect-history design

### 6.1 Ledger

`devy_prospect_history` (proposed, per prospect, append-only): an event list keyed by a **stable Devy history ID** with three clocks per event (football event time, source assertion time, TIBER knowledge time), mirroring Data. Event kinds: `seed_intake`, `seed_reverification`, `college_observation_checkpoint` (ref: checkpoint_id), `context_change` (program/roster/class), `transition_event` (declaration, transfer, graduation to rookie lane — each with its own provenance), `rookie_evidence` (combine/draft via the promoted rookie-transition-profile), `rookie_alpha_scored` (reference only; no value copied). Later events never edit earlier ones; a correction is a new event pointing at the corrected one.

### 6.2 Identity crosswalk (the actual blocker)

Three ID spaces exist today with no reviewed join: seed slugs (`jeremiah-love`), rookie slugs (`rb-jeremiyah-love`), and Data canonical college IDs (not yet allocated). Proposed `devy_identity_crosswalk` with statuses borrowed from Data #265 §6 (`READY`, `ALIAS_RESOLVED`, `AMBIGUOUS`, `POSSIBLE_DUPLICATE`, `TRANSFER_VERIFY`, `UNAVAILABLE`), each row citing evidence and a reviewer decision. Normalized-name matching may propose, never resolve.

**Effective decision at a cutoff.** Crosswalk rows are append-only; a row may name `supersedes` (the row ID of an earlier decision for the same seed `player_id`). For a checkpoint with cutoff `as_known_at`, the *effective* decision for a seed `player_id` is computed from the **complete pinned crosswalk** (`inputs.identity_crosswalk.sha256`), never from a row the checkpoint happens to cite: take every row for that `player_id` with `decision_known_at ≤ as_known_at`; discard every row that another row in that set supersedes; exactly one row must remain. If no row remains, the effective decision is "no row". If more than one remains (a fork, or two unlinked decisions), the crosswalk is inconsistent at that cutoff: there is no single effective row to cite, so the checkpoint **fails validation** for that seed (`CROSSWALK_FORK`, naming the surviving row IDs) rather than being mapped to a conforming `MATCH_CANDIDATE` row; the inconsistency is a crosswalk defect to be repaired by review, never resolved by the pulse. A checkpoint's `identity_binding.crosswalk_row_ref` must equal the effective decision's row ID; the §3.4 validator recomputes it and rejects a stale cite (a superseded row), a premature cite (`decision_known_at > as_known_at`) or a cite not present in the pinned crosswalk. Rejection, not degradation: a stale cite does not become an "unqualified `READY`".

**Crosswalk decision → pulse `identity_binding.status` (the only permitted derivation).** The effective decision is *qualified* only when all of the following hold at the checkpoint's `as_known_at`: it names a non-null `canonical_college_player_id`; it records a reviewer decision with `decision_known_at ≤ as_known_at`; and its `evidence_refs` cite at least one identity-class evidence item (for example an `official_roster` identity provenance on the seed side and a Data `identity` evidence item on the observation side) that is itself known by `as_known_at`. For `ALIAS_RESOLVED` the alias claim names a `representative_observation_id`, and its currency is **recomputed from the pinned envelopes**, never read from a self-declared flag: the representative must be present in a pinned envelope, known by `as_known_at`, resolved to the decision's canonical ID with eligible aggregation status, and not superseded by any established source correction known by the cutoff (the Data contract's alias-correction rule). A crosswalk row may not cite evidence first known after its own `decision_known_at`; only evidence known by `as_known_at` qualifies a decision or is copied into `identity_binding.evidence_refs`.

| Crosswalk status | Qualified | Pulse binding | Note |
| --- | --- | --- | --- |
| `READY` | yes | `MATCHED` | direct reviewed binding |
| `READY` | no (missing canonical ID, decision or evidence) | `MATCH_CANDIDATE` | never silently promoted to `MATCHED`; a row with `decision_known_at > as_known_at` is not effective at all and cannot be cited |
| `ALIAS_RESOLVED` | yes, alias claim current | `MATCHED` | binding through a reviewed Data alias representative |
| `ALIAS_RESOLVED` | no, or representative superseded / absent / not the decision's canonical | `MATCH_CANDIDATE` | mirrors Data's "corrected alias loses eligibility" rule; recomputed from envelopes |
| `AMBIGUOUS` | n/a | `MATCH_CANDIDATE` | competing identities; reviewer must decide |
| `POSSIBLE_DUPLICATE` | n/a | `MATCH_CANDIDATE` | quarantined until deduplicated |
| `TRANSFER_VERIFY` | n/a | `MATCH_CANDIDATE` | event-time program unverified |
| `UNAVAILABLE` | n/a | `UNBOUND_SEED` | explicit reviewed absence of a usable decision |
| no row known by `as_known_at` (or `inputs.identity_crosswalk` null) | n/a | `UNBOUND_SEED` | includes every seed row today, since no crosswalk exists |
| inconsistent (more than one unsuperseded row at the cutoff) | n/a | **checkpoint fails** (`CROSSWALK_FORK`) | no representable single row; crosswalk defect repaired by review, never by the pulse |

The mapping is evaluated at each checkpoint's `as_known_at`; a later crosswalk decision never retroactively changes an earlier checkpoint's binding. The §3.4 validator recomputes the effective decision from the complete pinned crosswalk, then the mapping, and rejects any row whose `crosswalk_row_ref` or `identity_binding.status` differs. Uncertain identities therefore stay `IDENTITY_UNRESOLVED` by construction; only an explicit, evidenced, reviewed `READY` or `ALIAS_RESOLVED` decision can produce a delta. The absent `devy_rookie_transition_map_2026.json` that `cards/devy/index.html` already looks for is the natural place for `transition_event` facts once a crosswalk exists; PR #295's truthful `unknown` transition state is the correct pre-crosswalk presentation.

### 6.3 Boundary

No Devy → Rookie Alpha input, no Devy value in the transition profile, no Forecast/Fantasy/FORGE wiring. The ledger references rookie artifacts by ID and digest only.

## 7. ML lane component dispositions

Evidence is read from the frozen archive (digests verified) and the producer source. Nothing was executed.

**Dataset facts.** 37 labeled rows: WR 25, TE 10, QB 2, **RB 0**; draft years 2018–2023 (7/7/8/7/7/1). Time-aware split: train 2018–2021 (29), validation 2022 (7), **test 2023 (1 row: Sam LaPorta, TE)**. 2 of 37 rows are synthetic scaffolds (`sample-qb-2018-a` etc.; outcomes file notes "synthetic dev scaffold label … replace with sourced outcomes"). Feature coverage: `draft_capital_proxy_0_100` 100%, `size_context_0_100` 100%, `athleticism_0_100` 89%, `speed_proxy_0_100` 89% (proxy falls back to athleticism), `production_0_100` 40.5% (TE 0%), `age_at_draft` 0%, `breakout_age` 0%, `early_declare_flag` 0%, `deterministic_grade_0_100` 0%. Validation ROC AUC: `draft_capital_only` (single-feature fitted logistic, listed under `ml_models`) 0.458, `logistic_full` 0.167 (n=7). The deterministic non-ML baselines are only `draft_capital_rescaled` and `deterministic_grade_rescaled` (`deterministic_non_ml_baseline()`, producer L900–905; built at L1451–1462), evaluated on the test slice only. Test metrics are computed on n=1 and are uninformative; `draft_capital_dominance_check` deltas are 0.0 for the same reason. Logistic coefficient on `production_0_100` is **negative** (−0.437), the largest magnitude in the model.

| Component | Disposition | Evidence | Uncertainty |
| --- | --- | --- | --- |
| Quarantine governance (experimental namespace, status sidecar, pinned digests, producer refusal of archive/promoted paths, `--replace-run` transaction) | **KEEP** | Migration note; validators pass; `test_experimental_demotion_references.py` guards old path | None material |
| Time-aware split by draft class | **KEEP (design) / UNRESOLVED (utility)** | `time_split` enforces ≥2 prior classes | Meaningless until test slices have >1 row per position |
| Non-ML baseline harness (`draft_capital_rescaled`, `deterministic_grade_rescaled`) | **KEEP** | `deterministic_non_ml_baseline()`; the standard any future model must beat | Only evaluated on the test slice (n=1 in the archive), so no comparison is currently possible |
| Historical labeled dataset (37 rows) | **DEPRECATE as evaluation basis; REPLACE** with governed outcome labels | 2 synthetic rows; RB absent; test n=1; the frozen labeled dataset carries no per-row label-source field | `exports/promoted/nfl-fantasy-outcomes/` exists in Rookies and TIBER-Data owns outcome data; whether either can supply per-player labels for 2018–2023 was not audited here |
| Feature set (9 columns) | **ADAPT** | 4 features at 0% coverage; speed proxy is athleticism fallback | Sourcing age/breakout/early-declare is a data task, not a model task |
| Fitted logistic models (`logistic_full`, `draft_capital_only`, `draft_capital_plus_age`, `draft_capital_plus_production`, all under `ml_models`) + `heldout_probabilities.*` | **DEPRECATE** | No evidence of signal beyond draft capital; validation AUC below 0.5; sign-inverted production weight | A larger dataset could change this; the frozen outputs cannot |
| Calibration metrics | **UNRESOLVED** | `calibration_mae` on n=1 and n=7 | Uncomputable at current size |
| Draft-capital dominance check | **KEEP (as a gate)** | Deltas reported per model | Only meaningful with ≥ tens of test rows |
| Lane ↔ Devy relationship | **none, keep none** | Contract doc: "No … experimental ML connection exists here" | In-season college evidence must not become an ML feature under #298 |

**2027-cycle retention:** retain the governance, split and the deterministic non-ML baseline harness (not the fitted `draft_capital_only` model); do not retain any output artifact as a signal. Retraining is a separate governed decision and is not recommended before a labeled dataset with recorded label provenance and non-trivial test slices exists.

## 8. Smallest ordered successor sequence and one recommended authorization

Each step is separately gated; none is authorized by this report.

| Step | Owner | Scope | Gate to start | Depends on |
| --- | --- | --- | --- | --- |
| S1 | TIBER-Data | Resolve D-3, D-4, D-5 in the college observation validator; close D-1/D-2 threads with evidence; independent exact-head review | Data operator authorization | — |
| S2 | TIBER-Data | Provider qualification **audit** (terms, permitted automated use, retention, endpoints, ID stability, correction chronology, finality, bounded test sample plan); audit-only, no acquisition | Data operator authorization | — (parallel to S1) |
| S3 | TIBER-Rookies | Devy Pulse v2 contract + validator + **synthetic-only** fixtures per §3, plus `devy_identity_crosswalk` contract per §6.2; consumes Data envelope shape unchanged. **Candidate prepared** (§3.6), awaiting independent review and operator acceptance | Rookies operator authorization (granted for the candidate only) | none for shape; S1 for relying on Data validity |
| S4 | TIBER-Rookies | Manual seed re-verification pass: F-1 transition review, 2 unknown schools, per-row `last_verified` date; transition map for reviewed graduations (after or with #295) | Rookies operator authorization; player-fact sourcing rules | — |
| S5 | TIBER-Data | Bounded one-week real sample under a qualified provider (#265 C1), immutable retention | S1, S2 | S1, S2 |
| S6 | TIBER-Rookies | First real v2 checkpoint from the S5 envelope; operator review of proposals | S3, S4, S5 | S3, S4, S5 |
| S7 | TIBER-Rookies | Longitudinal ledger per §6.1 fed by S6 checkpoints | S6 | S6 |

**One recommended bounded authorization: S3.** It is the only step that is Rookies-owned, needs no football data, no provider, no seed change and no Data repair to be built, and it converts this design into a validated contract with negative fixtures before any real evidence exists. Its authorization text should require: synthetic-only fixtures with unmistakably synthetic names; the fail-closed rules in §3.4; explicit refusal to compute any delta on a non-`MATCHED` binding; and a statement that a valid checkpoint over a synthetic envelope proves contract behaviour, not 2026 coverage. S1 and S2 are Data-owned prerequisites for any real checkpoint and should be raised as Data issues, not absorbed into Rookies work.

## 9. Terminal answer

> Can the 2026 Devy Pulse become a useful in-season evidence monitor now, using ordinary source-backed college-football observations, while remaining separate from Rookie Alpha rankings and the experimental ML lane?

**Not now.** Today the Devy Pulse can truthfully say nothing about 2026 in-season evidence, because no 2026 college player/game observation exists in any TIBER repository; the only college-observation artifact is Data's synthetic fixture, and Data's validator carries three unresolved post-merge findings. What exists is a curated 24-name seed watchlist with year-granular provenance, a roster-pulse validator that has only ever validated a fixture, and an established but unqualified CFBD precedent. It **can** become one later, in this order: Data repairs its validator (S1) and qualifies a provider (S2); Rookies freezes the v2 contract on synthetic fixtures (S3) and re-verifies the seed rows, including the three rows that conflict with the repo's own 2026 draft results (S4); Data retains a bounded real sample (S5); Rookies runs one operator-reviewed checkpoint (S6). Separation from Rookie Alpha and the ML lane is preserved by construction: the pulse copies observed cells and enumerated change states only, produces no score, and feeds nothing.

## Appendix A. Commands actually run (read-only)

```text
python3 scripts/devy_signal_registry.py --registry data/devy/devy_seed_watchlist_2026.json          # PASSED
python3 scripts/devy_signal_registry.py --registry data/fixtures/devy_prospect_registry_v0_fixture.json  # PASSED
python3 scripts/validate_devy_roster_pulse.py --artifact data/devy/monthly_pulse/devy_roster_pulse_2026_05.json  # PASSED
python3 scripts/validate_devy_league_market_snapshot.py --artifact data/devy/league_market_snapshots/deep_devy_draft_snapshot_2026_fixture.json  # PASSED
python3 scripts/validate_experimental_integrity.py     # PASSED (10 artifacts, 9 frozen verified)
python3 scripts/validate_promoted_integrity.py         # PASSED (32 artifacts, 4 families)
python3 -m pytest …                                    # NOT RUN: pytest unavailable in this environment
```

No producer, fetch, ML, or Data test command was executed. No file under `data/**`, `exports/**`, `scripts/**`, `lib/**`, `cards/**`, `.github/**` or deployment configuration was changed.

## Appendix B. Publication / deployment effects checked before opening the PR

- `.github/workflows/ci.yml` runs on `push` and `pull_request`: tests and validators only; no publish, deploy, or artifact upload step. A docs-only branch triggers CI and nothing else.
- `railway.json` / `railpack.json` define the start command and health check only; deployment triggers are configured in Railway, not in-repo, and cannot be inspected from the repository. Railway's default is deploy-from-default-branch; a draft PR to `main` does not merge.
- `.replit` defines a manual run/deploy configuration; not PR-triggered.
- No PR template exists under `.github/`.

## Appendix C. Independent review lineage (PR #299)

Round 1: Codex review at head `024938b4bcbecf34efbc06190ba0c620aeacf229`, submitted 2026-09-30T14:42:21Z (review 5367800235; summary status **Completed**, trigger: manual request). Four inline findings, each verified against the repository before repair.

| ID | Severity | Finding (Codex) | Verification | Repair in this revision |
| --- | --- | --- | --- | --- |
| R1-1 | P2 | §3.4 rejected every numeric field outside copied observations, contradicting the sketch's own `window.season` and coverage counts | Confirmed by reading §3.2 vs §3.4 | Prohibition narrowed to score/rank/grade/probability/projection/ordering fields; structural identifiers, clocks and coverage counts explicitly permitted |
| R1-2 | P1 | `UNMATCHED_SEED` → `NO_OBSERVED_ROWS` converted identity uncertainty into a coverage assertion, contradicting §3.1 rule 5 | Confirmed; an unbound seed may exist in an envelope under an unassociated identity | `NO_OBSERVED_ROWS` now requires binding `MATCHED`; `MATCH_CANDIDATE` and new `UNBOUND_SEED` yield `IDENTITY_UNRESOLVED` with no absence claim; §3.4 fails closed on the combination |
| R1-3 | P2 | §1.4 grouped `fetch_rb_play_profiles.py` / `fetch_wr_route_profiles.py` under `/plays`; they use `/stats/player/season` and estimate targets; only the QB path calls `fetch_team_plays` | Confirmed: `fetch_rb_play_profiles.py` L4/L33/L142, `fetch_wr_route_profiles.py` L4/L35/L196, `fetch_qb_play_profiles.py` L19/L141 | Table row split into play-level (QB) and season-level (RB/WR/TE) precedent; matrix `Targets` row and §1.4 bullet corrected |
| R1-4 | P2 | `draft_capital_only` listed as a non-ML baseline; it is a fitted logistic under `ml_models`, and the deterministic baselines are only the two `_rescaled` entries | Confirmed: producer L1443–1449 (`run_model`) vs L1451–1462 (`deterministic_non_ml_baseline`); archive `evaluation_report.json` keys | Disposition table corrected; fitted single-feature model moved to the DEPRECATE row; retention sentence corrected |

Round 2: Codex review at head `c41b1c1cdb9a649b5334acc8ffe67149207c6f61`, submitted 2026-09-30T14:48:10Z (review 5367873949; trigger: manual request). One inline finding.

| ID | Severity | Finding (Codex) | Verification | Repair in this revision |
| --- | --- | --- | --- | --- |
| R2-1 | P2 | The §3.4 numeric whitelist still excluded the computed values of the sketch's `delta` entries, so a literal S3 validator would reject every checkpoint with a numeric change for a `MATCHED` player | Confirmed: §3.2 `delta` implied a computed change but named no numeric field, and §3.4 allowed none | §3.2 `delta` now names `prior_value`, `current_value` and an integer `difference` (null unless both cells observed and the row `MATCHED`); §3.4 permits exactly those, requires the validator to recompute `difference`, and keeps rates, shares, averages, scores and ranks prohibited |

Round 3: Codex review at head `96d6cd69996b700e173bebb6ad76462e5b42f036`, submitted 2026-09-30T14:52:37Z (review 5367939937; trigger: manual request). One inline finding. Round 2 had exhausted the original two-round repair budget, so R3-1 was first returned to the operator as a blocker; the operator then separately authorized one additional docs-only repair round on 2026-09-30, under which this revision was made.

| ID | Severity | Finding (Codex) | Verification | Repair in this revision |
| --- | --- | --- | --- | --- |
| R3-1 | P2 | §3.4 permitted a numeric `delta.difference` on any `MATCHED` row with two observed cells, while §3.3 requires no delta for `CONFLICTING_EVIDENCE` and `INSUFFICIENT_EVIDENCE`; a literal validator could accept a contradictory checkpoint | Confirmed by reading §3.3 against §3.4 at `96d6cd6` | §3.2 comment, §3.3 state definitions and §3.4 now require `delta.difference` to be null in both states, and §3.4 fails closed on any non-null value there |

Round 4: Codex review at head `d35094fcddc8cc81cdb32d559e127115fe7ba218`, submitted 2026-09-30T17:49:26Z (review 5369946956; trigger: draft marked ready, after the operator had Codex resolve the six repaired threads and mark the PR ready at 17:44Z without changing the head). This second review of the same commit followed the clean manual-request result of 17:36:20Z, confirming the qualification recorded on PR #299 that a clean conversation comment at a head is not proof the head is clean. Three inline findings; the operator separately authorized one additional docs-only repair round on 2026-10-01.

| ID | Severity | Finding (Codex) | Verification | Repair in this revision |
| --- | --- | --- | --- | --- |
| R4-1 | P1 | §3.4 rejected only `NO_OBSERVED_ROWS` on a non-`MATCHED` row, so a `MATCH_CANDIDATE`/`UNBOUND_SEED` row with another evidence state and no delta would pass despite §3.1 rule 5 | Confirmed by reading §3.4 against §3.1 at `d35094f` | Rule 5 now states the two-way invariant (`MATCHED` ⇔ not `IDENTITY_UNRESOLVED`) and nulls `evidence_window`/`observed`/`prior_observed`/`delta` on non-`MATCHED` rows; §3.2 marks those fields null unless `MATCHED`; §3.4 fails closed on the inverse invariant, on any such non-null content, and on `IDENTITY_UNRESOLVED` applied to a `MATCHED` row |
| R4-2 | P2 | `COVERAGE_INCOMPLETE` lived inside the single `evidence_change_state`, so a corrected row in a partial envelope could not be both `CORRECTED_EVIDENCE` and coverage-flagged | Confirmed by reading §3.3 against §3.1 rule 4 | `COVERAGE_INCOMPLETE` removed from `evidence_change_state`; new per-row `coverage_state` (`COMPLETE`/`INCOMPLETE`/`UNKNOWN`) and `coverage_flags` added to §3.2/§3.3, orthogonal by rule 8; §3.4 validates `coverage_state` against the cited envelopes and flags |
| R4-3 | P2 | §6.2 defined six crosswalk statuses but no mapping to `MATCHED`/`MATCH_CANDIDATE`/`UNBOUND_SEED`, so S3 could neither derive bindings nor avoid inventing one | Confirmed by reading §6.2 against §5 and §3.1 | §6.2 now defines qualification conditions and a status-by-status mapping table evaluated at `as_known_at`; §5 table gains a "Derived from" column; §3.2 `identity_binding` carries `crosswalk_row_ref`, `crosswalk_status` and `decision_known_at`; §3.4 recomputes the mapping and rejects mismatches |

Round 5: Codex review at head `dc10519b378c915a7d1983cadddb9fba163accfc`, submitted 2026-10-01T01:20:09Z (review 5373840583; trigger: manual request). Three inline findings, first returned to the operator unrepaired per the round-4 grant, then repaired under a further operator authorization on 2026-10-01 that also required the §3.5 example table.

| ID | Severity | Finding (Codex) | Verification | Repair in this revision |
| --- | --- | --- | --- | --- |
| R5-1 | P1 | `coverage_state`/`coverage_flags` were required on every row, so non-`MATCHED` rows still carried coverage content despite §3.1's "no coverage assertion" | Confirmed by reading §3.2/§3.3/§3.4 against §3.1 rule 5 at `dc10519` | Both coverage fields are null on non-`MATCHED` rows (§3.1 r5, §3.2, §3.3, §5), §3.4 rejects non-null values there and requires them on `MATCHED` rows; rule 8 now ties coverage to bound rows and to the checkpoint-level `coverage_warnings`; rules renumbered 1–8 in order |
| R5-2 | P2 | The validator recomputed the mapping only from the cited crosswalk row, so a stale cite of a superseded `READY` row degraded to `MATCH_CANDIDATE` and passed | Confirmed by reading §3.4 against §6.2 and §5 at `dc10519` | §6.2 defines the *effective decision* from the complete pinned crosswalk with supersession history (`supersedes` chain, fork ⇒ `AMBIGUOUS`); `crosswalk_row_ref` must equal it; §3.4 rejects stale, premature or absent cites outright; example E2 demonstrates the rejection |
| R5-3 | P2 | `INCOMPLETE` and `UNKNOWN` predicates overlapped, so exact recomputation was undefined | Confirmed by reading §3.3 at `dc10519` | §3.3 computes the exact flag set first and derives the state by strict precedence `UNKNOWN` > `INCOMPLETE` > `COMPLETE`; §3.4 requires exact recomputation of both; examples E3, E4, E6 pin the three states and the precedence |

Round 6: Codex review at head `0693035dcb0fbbabe4b719029a4b5368f6ec934d`, submitted 2026-10-01T01:35:13Z (review 5373933939; trigger: manual request). Three P2 findings, reported unrepaired per that grant, then carried into the S3 candidate implementation under the operator's 2026-10-01 S3 authorization.

| ID | Severity | Finding (Codex) | Verification | Disposition |
| --- | --- | --- | --- | --- |
| R6-1 | P2 | §3.4 compared only `crosswalk_row_ref` and `status`; other decision-derived binding fields could carry stale values | Confirmed at `0693035` | Implemented and documented (§3.4, §3.6): every binding field is recomputed; tests `test_every_decision_derived_binding_field_is_recomputed`, `test_candidate_row_cannot_carry_a_canonical_id` |
| R6-2 | P2 | checkpoint-level `coverage_warnings` were never recomputed or required | Confirmed at `0693035` | Implemented and documented (§3.4, §3.6): exact envelope-level set, validated even when all rows are unresolved; test `test_checkpoint_level_warnings_are_required_even_when_all_rows_are_unresolved` |
| R6-3 | P2 | a fork had no representable single row ID yet was mapped to `MATCH_CANDIDATE` | Confirmed at `0693035` | Implemented and documented (§6.2, §3.6): fork fails the checkpoint (`CROSSWALK_FORK`); test `test_crosswalk_fork_fails_the_checkpoint_outright` |

Round 7 (S3 candidate, PR #300): Codex review at candidate commit `7811ac1b618c1e36064a63de79c232bb2659a15e`, submitted 2026-10-01T01:59:32Z (review 5374080665; trigger: manual request). Codex reported reproducing three findings by executing the validator against modified copies of the synthetic bundle. Four findings, all confirmed and repaired in the candidate's first repair round.

| ID | Severity | Finding (Codex) | Verification | Repair |
| --- | --- | --- | --- | --- |
| C1 | P1 | A decision with one timely identity ref and one ref known after `as_known_at` still qualified, and the premature locator had to be copied | Confirmed in `expected_binding` | Crosswalk rows may not cite evidence known after their decision (`CROSSWALK_ROW`); only refs known by the cutoff qualify or are copied; tests `test_evidence_known_after_the_cutoff_cannot_qualify_or_be_copied`, `test_only_identity_evidence_known_by_the_cutoff_qualifies` |
| C2 | P1 | `ALIAS_RESOLVED` trusted a self-declared `alias_claim.current` flag; a claim on a superseded observation still produced `MATCHED` | Confirmed | `alias_claim` is exactly `{representative_observation_id}`; currency recomputed from pinned envelopes; tests `test_alias_currency_is_recomputed_from_observation_lineage`, `test_self_declared_alias_currency_is_rejected` |
| C3 | P1 | The prior checkpoint's cells fed deltas without the prior being validated; a digest only authenticates bytes | Confirmed | Prior validated recursively against its own pinned inputs, cycles rejected (`PRIOR_INVALID`); tests `test_prior_checkpoint_is_validated_before_its_cells_are_trusted`, `test_cyclic_prior_lineage_fails` |
| C4 | P2 | Identical observations repeated across overlapping envelopes produced `CONFLICTING_EVIDENCE` | Confirmed in `_leaf` | Observations coalesced by `observation_id`; same ID with different content is `INPUT_CONFLICT`; test `test_identical_observations_across_envelopes_are_coalesced` |

No finding in any round changed the terminal answer (§9), the successor sequence (§8), the recommended authorization (S3), the Data dependencies (D-1..D-5) or the discovery-only boundaries (no seed mutation, no score, no ranking, no Rookie Alpha or ML connection).
