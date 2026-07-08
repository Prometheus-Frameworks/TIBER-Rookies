# TIBER-Rookies Machine-Readable Artifact Audit

**Date:** 2026-07-08
**Issue:** [#255](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/255)
**Scope:** Audit only. No Forecast consumption was implemented, no Rookies artifacts were
redesigned or rewritten, and no player evaluations were altered as part of this work.

## Purpose

TIBER-Forecast asked whether TIBER-Rookies — built quickly around rookie-draft needs and
containing a large volume of player writeups and qualitative claims — actually produces
structured evidence with provenance, stable contracts, and testable fields, or whether it is
mostly narrative content that has not yet earned governed-artifact status. This report answers
that question directly, artifact family by artifact family, without judging whether the prose
"sounds good."

## Methodology

The repository was reviewed in three passes: (1) all 24 files under `docs/` plus root-level
`README.md`/`AGENTS.md`/`CLAUDE.md`; (2) every subdirectory of `data/` and `exports/promoted/`,
sampling representative files within large near-identical families (e.g. `wr_route_profiles/`
has 66 per-player-season files — 2-3 were read in full and the pattern was confirmed to hold
across the rest by filename/structure); (3) the code layer — `scripts/`, `lib/rookies/`,
`lib/devy/`, `tests/`, `components/rookies/`, `cards/`, `main.py`, `runtime-server.js` — to see
which artifacts are backed by tested, schema-enforcing code versus ad hoc or hand-authored
logic. Where a whole family shares one governance pattern, this report describes the family
once rather than re-listing every file.

---

## Answers to the audit questions

### 1. What artifacts currently exist in TIBER-Rookies?

Roughly six layers:

- **Raw inputs** (`data/raw/`) — combine results and seed pools, largely per-field sourced.
- **Processed/derived data** (`data/processed/`) — ~34 top-level files plus four
  per-player-season subfamilies (`qb_play_profiles/`, `rb_play_profiles/`,
  `te_production_profiles/`, `wr_route_profiles/`).
- **Historical staging** (`data/historical/`) — a self-described "canonical staging lane" of
  partial real data mixed with fixture rows, plus reference population files.
- **Devy discovery layer** (`data/devy/`) — the most rigorously self-governed family in the
  repo, explicitly disclaimed as non-authoritative.
- **Operator journal layer** (`data/operator-journal/`) — raw human notes plus a semi-structured
  extraction pass over them.
- **Promoted exports** (`exports/promoted/`) — `rookie-alpha/` (predraft/postdraft + manifests),
  `historical-comps/`, `nfl-fantasy-outcomes/`, `rookie-ml-lane/` (explicitly experimental).
- **Code/docs layer** — build/compute scripts, two real schema validators
  (`validate_promoted_export.py`, `devy_signal_registry.py`), a UI mapping layer
  (`lib/rookies/*.js`), and ~24 markdown docs (contracts, policies, audits, runbooks, a design
  doc, and one personal journal entry).

### 2. Which are prose/writeups only?

- `docs/concepts/daily/2026-06-13-tiber-concept-daily.md` — personal reflection/strategy notes,
  not a data or pipeline document.
- `evidence_summary` / `context_source` free-text fields embedded inside otherwise-structured
  rookie-alpha rows — explicitly declared by policy (`docs/evidence-summary-provenance-policy.md`)
  to be non-canonical: *"`evidence_summary` is NOT a canonical model-input truth surface... The
  model score is computed from canonical inputs; it is not derived from the prose."*
- `data/operator-journal/raw/2026_rookie_journal_entries.json` — freeform journal prose with a
  `review_status: "raw"` field, not scored or structured beyond entry metadata.
- `data/processed/te_production_profiles/*.json` — heavily hand-curated narrative career
  profiles with inline transcription-correction notes; confidence and quality are conveyed only
  through prose (`methodology_notes`), not a structured field.
- Runbooks (`docs/runbooks/*.md`) and most audit docs (`athletic-score-normalization-audit.md`,
  `repo-state-audit-2026-postdraft.md`, `pr153-prototype-rollout-audit.md`,
  `source-of-truth-audit.md`, `2026-evidence-summary-provenance-audit.md`) are process/finding
  narratives about the pipeline, not artifacts a downstream consumer would ingest.

### 3. Which are machine-readable JSON/CSV/TS/other structured outputs?

Nearly everything under `data/` and `exports/` is JSON or CSV. The relevant distinction is not
"is it a file format a machine can parse" but whether the *fields* are stable, typed, versioned,
and enforced — see question 4.

### 4. Which artifacts have stable contracts or schemas?

Only a small subset has a written schema *and* code that enforces it:

| Artifact family | Contract doc | Enforcing code | Test coverage |
|---|---|---|---|
| `exports/promoted/rookie-alpha/{year}_rookie_alpha_predraft_v0.{json,csv}` + `{year}_manifest.json` | `docs/export-contract.md`, `docs/tiber-fantasy-consumer-contract.md` | `scripts/validate_promoted_export.py` (re-hashes every input/output file against the manifest, checks required top-level fields) — confirmed each manifest's `output_files` covers only the predraft JSON/CSV pair, not postdraft | `tests/test_validate_promoted_export.py` (4 tests) |
| `data/devy/*` (seed watchlist, market snapshots, roster pulse) | `docs/devy-signal-discovery.md` | `scripts/devy_signal_registry.py` (`CURRENT_DEVY_SCHEMA_VERSION`, enum/field/provenance validation), plus separate validators for roster pulse and market snapshots | `tests/test_devy_signal_registry.py` (24 tests) |
| `data/processed/2026_day2_draft_signal_profiles.json`, `2026_round1_draft_signal_profiles.json` | No standalone doc, but a real field/enum contract lives in the validator code itself | `scripts/validate_day2_draft_signal_profiles.py`, `scripts/validate_round1_draft_signal_profiles.py` (both enforce required-field sets and enum membership — e.g. `TALENT_SIGNALS`, `OPPORTUNITY_SIGNALS`, `ALLOWED_SOURCE_STATUS` — against the committed files) | `tests/test_day2_draft_signal_profiles.py`, `tests/test_round1_draft_signal_profiles.py` |
| `exports/promoted/historical-comps/2026_historical_comps_v0.json` | `docs/historical-comps-contract.md` (detailed field/gating spec) | Partial — `tests/test_compute_historical_comps.py` checks UI-safe contract-flag alignment, but the underlying data is explicitly "scaffold fixtures," not a full historical warehouse | Partial |
| `data/processed/wr_route_profiles/` | `data/processed/wr_route_profiles/README.md` (explicit field list + limitations) | `scripts/fetch_wr_route_profiles.py` regenerates it | No dedicated schema test found |
| `data/historical/` (identity/outcome features) | `data/historical/historical_prospect_features.schema.md` (explicit null policy) | None found — no validator enforces this doc against the actual sample files | None |

Everything else (draft-capital proxies, positional consensus, YoY trends, age-adjusted
production, dynasty ADP, player stats, operator-journal candidates, `te_production_profiles/`)
has consistent field *naming* but no written schema doc, no `schema_version` field in the JSON
itself, and no validator. (Day2/Round1 signal profiles are excluded from this "no validator"
group — see the table above; they do have validator + test coverage, even though their
*content* is still self-labeled `operator_seeded`/unreconciled per question 6.)

**Important negative finding:** `lib/rookies/rookieDataContract.js` — despite its name — is not
a schema or validator. It is a 34-line path/URL builder (`rookieAlphaExportPath()`,
`rookieDisplaySupplementPaths()`) plus a hardcoded season-availability lookup table. It performs
zero field-level validation, is imported by exactly one file
(`lib/rookies/getRookieCardData.js`), and has zero test coverage. If Forecast or any other
consumer were pointed at this file expecting a governed contract, it would find none.

### 5. Which artifacts preserve source/provenance?

Provenance quality varies sharply by family and is **not standardized** — there is no
repo-wide convention:

- **Strongest:** `exports/promoted/rookie-alpha/{year}_manifest.json` (SHA-256 hashes of every
  predraft input/output file, `run_id`, `generated_at`, `coverage_summary` — verified the hashes
  actually match the files on disk); `data/processed/2026_draft_results.json` (`source_name`,
  `source_url`, `source_status`, `upstream_provenance_status` enum, `ingested_from`,
  `ingested_at`); `qb_play_profiles/`, `rb_play_profiles/` (literal CFBD API query URLs +
  methodology notes); `data/devy/*` (three-way provenance object with `source_type`,
  `source_notes`, `last_verified_year`, plus an `intake_audit` block tying rows back to specific
  issues/PRs). `wr_route_profiles/` is **mixed, not uniformly strong**: of the 66 files, 54 have
  `source_url: null` with `source_name` values indicating estimated/manual research (e.g.
  "Grok/Sports-Reference cross-verification... targets estimated") rather than a CFBD API URL —
  only a minority are genuinely CFBD-sourced with a live query URL. A consumer needs to check
  `source_url` per file rather than assume the family-wide claim in the family's own README.
- **Weak or absent:** `data/processed/2026_player_stats.json`, `2026_yoy_trends.json`,
  `2026_age_adjusted_production.json`, `2026_dynasty_adp.json`, and the top-level
  `exports/promoted/nfl-fantasy-outcomes/*.{json,csv}` files (no file-level metadata block);
  `build_historical_comparison.py` and `build_sporq_historical.py` write no run-level
  provenance metadata for their outputs.
- **Ad hoc/hand-authored, not derived from data:** `scripts/build_operator_signal_candidates.py`
  builds its "candidate" outputs via a hardcoded chain of
  `if "<player-name-substring>" in entry_id:` branches with manually written tags and prose per
  named player — its own tests pin those specific hardcoded values rather than testing a
  general transformation from the raw journal text.

### 6. Which artifacts distinguish observed data from inference/opinion?

Some do, via at least four different (non-interoperable) mechanisms:

- Numeric confidence: `athletic_confidence: 0.5`, `breakout_confidence`.
- Enum bands: `confidence_band: "LOW"`, `data_confidence: "high"`, devy's
  `signal_strength_band`/`actionability_band`/`volatility_band`.
- Boolean/status flags: `draft_capital_proxy_pending_conversion`, `methodology_compatible`,
  `data_gap_flag`, `needs_verification`, `review_status: "needs_human_review"`.
- Prose only, with no structured flag: `te_production_profiles/` correction notes,
  `operator-journal` raw entries.

The clearest and most rigorous version of this distinction in the repo is
`docs/evidence-summary-provenance-policy.md`, which draws a hard boundary between the canonical
scored fields (model truth) and the `evidence_summary` prose (never model truth) — but this is a
policy statement, not a machine-enforced check; no validator confirms a given `evidence_summary`
was actually excluded from scoring.

Two concrete defects work against this goal:

- `data/historical/historical_prospect_features.sample.json` and `.ml_sample.json` mix real,
  sourced rows with synthetic fixture rows (`source_name: "sample_fixture"`) in the same file
  that its own README calls canonical — distinguishable only by reading the `source_name`
  string, not a structured `is_fixture` flag. These fixture rows propagate into
  `exports/promoted/rookie-ml-lane/historical_labeled_dataset.json` and `feature_table.json`.
- `exports/promoted/nfl-fantasy-outcomes/player_year_ppr_outcomes_v1.{json,csv}` contains 18 of
  9,766 rows with a `SIM`-prefixed `player_id` (synthetic/simulated) embedded in a promoted
  export with no `is_synthetic` field — detectable only by the `SIM` prefix convention.

### 7. Which artifacts could plausibly become Forecast inputs?

Ranked by current governance maturity, not by data quality alone:

1. **`exports/promoted/rookie-alpha/{year}_rookie_alpha_{predraft,postdraft}_v0.json` +
   manifest** — the only artifact family with a written contract, a hash-verifying validator,
   test coverage, and a documented handoff runbook. This is the strongest candidate structurally.
   Caveat: `docs/athletic-score-normalization-audit.md` documents that the exported
   `athletic_score_0_100`/`athletic_source` fields do not mean what their names imply (an
   in-house composite, not the Kent Lee Platte RAS percentile a consumer would likely assume) —
   a semantic-drift risk any consumer must know about before trusting the field name.
2. **`exports/promoted/historical-comps/2026_historical_comps_v0.json`** — has an explicit
   contract and a machine-readable `similarity_quality_by_position` gating field (e.g.
   `status: "directional_only"` for QB), but is self-described as scaffold/sample output with
   "no UI integration in this phase," and several position lanes are explicitly not yet
   methodology-compatible with historical vintages.
3. **`data/processed/qb_play_profiles/`, `rb_play_profiles/`** — real, CFBD-sourced, with URLs
   and documented limitations, but no schema_version, partial player coverage, and no validator.
   **`wr_route_profiles/`** is a weaker version of this candidate than it first appears: 54 of
   66 files are `source_url: null` estimated/manual-research rows, not CFBD-sourced observations
   — any Forecast use would need to filter to the CFBD-backed subset specifically rather than
   treat the family as uniformly observed data.
4. **`exports/promoted/nfl-fantasy-outcomes/*`** — a genuine public-data (nflverse) outcome
   calibration lane with a real freshness gate (`--fail-on-stale-source`), but needs the SIM-row
   and blank-`player_name` issues resolved before an external consumer should treat it as clean.

### 8. Which artifacts are explanation-only rather than model-input candidates?

`evidence_summary`/`context_source` prose fields; `data/operator-journal/*` (both raw entries and
processed candidates — explicitly "suggestions, not scoring truth" pending human review);
`data/processed/te_production_profiles/*` (manually curated narrative, not a repeatable
pipeline); `data/processed/2026_day2_draft_signal_profiles.json` and
`2026_round1_draft_signal_profiles.json` (translator/interpretation layer, `operator_seeded`
until reconciled, self-declared "no promoted alpha outputs are regenerated" by these files);
the role-opportunity and team-context post-draft joins (explicitly documented as inspect-only,
non-scoring, "does not mutate upstream model artifacts"); `exports/promoted/rookie-ml-lane/*`
(explicitly labeled `"lane": "parallel_ml_evaluation_only"`, non-production); the
`cards/`/`components/rookies/`/`prototype/` UI layer (pure presentation, produces nothing);
`docs/rookie-card-prototype.md`'s browser-local queue export (explicitly documented as "not part
of the producer/export contracts").

### 9. What gaps prevent Forecast from consuming any Rookies evidence today?

1. **No cross-repo promotion path exists yet.** `docs/source-of-truth-audit.md` proposes a
   versioned per-domain promotion into TIBER-Data, but this is a specification only —
   `docs/repo-state-audit-2026-postdraft.md` confirms it has not been executed.
2. **No repo-wide schema/provenance/observed-vs-inferred convention.** Each artifact family
   invented its own pattern; a generic Forecast ingester would need bespoke parsing per family,
   the same way `docs/tiber-fantasy-consumer-contract.md` had to be hand-written specifically for
   the rookie-alpha triplet and would not generalize to, say, `wr_route_profiles/`.
3. **`rookieDataContract.js` cannot be relied on as a contract** — it is unenforced path-building
   code, not a schema.
4. **Fixture/synthetic rows leak into nominally canonical/promoted files** without a machine
   checkable flag (`historical_prospect_features.sample.json`/`.ml_sample.json` and their
   downstream `rookie-ml-lane` derivatives; `SIM`-prefixed rows in
   `nfl-fantasy-outcomes/player_year_ppr_outcomes_v1.*`).
5. **A known data-quality defect**: every file in `data/historical/te_reference_populations/`
   contains WR player data mislabeled `"position": "TE"` — real TE reference-population data does
   not appear to exist in the repo. Consuming this today would silently corrupt any
   TE-specific normalization. **Update:** investigated and quarantined in issue
   [#257](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/257) — see
   `docs/reports/2026-07-08-te-reference-population-repair.md` and
   `data/historical/te_reference_populations/README.md`. No real TE population was found
   anywhere in the repo's history; the files are now emptied rather than left mislabeled.
6. **At least one operationally broken join.** `docs/repo-state-audit-2026-postdraft.md` (an
   internal audit dated May 2026) marks the team-context post-draft join as **BROKEN** due to a
   missing cross-repo path, with stale output left committed. This audit did not re-verify
   whether that has since been fixed; it is flagged here as a status that needs re-confirmation,
   not as a currently-observed-live break.
7. **Documentation drift.** `data/historical/README.md` claims the 2017 WR reference population
   file is an empty placeholder; it actually contains ~460 real rows. This is a minor instance of
   a broader pattern: docs describe intended/past state that may not match current file contents,
   which any Forecast integration would need to verify against the artifacts directly rather than
   trust the docs alone.
8. **Explicit non-runtime-dependency posture.** `README.md` and `docs/architecture.md` state
   Rookies is "not a runtime dependency" for downstream consumers and "should not depend on this
   repository as a live backend" — consumption today is designed to be a manual, versioned
   handoff (`docs/runbooks/draft-week-handoff-2026.md`), not an automated pull, unless a
   dedicated ingestion adapter analogous to `tiber-fantasy-consumer-contract.md` is written for
   Forecast specifically.

**Bottom line: Forecast cannot consume anything from Rookies today without first building a
dedicated ingestion adapter (mirroring what TIBER-Fantasy did) for one specific artifact family
— most plausibly the rookie-alpha predraft/postdraft export + manifest — and that adapter would
still need to account for the athletic-score semantic-drift issue and the manual-handoff
posture. No artifact in this repo is currently both (a) governed end-to-end and (b) designed for
automated external consumption.**

---

## Artifact classification

Using the enum from the issue. Families sharing one governance pattern are grouped; individual
paths are given where the file count is small enough to be meaningful.

### `machine_readable_governed_artifact`

| Path | Format | Owner/source | Provenance | Schema/contract | Obs-vs-inferred | Next action |
|---|---|---|---|---|---|---|
| `exports/promoted/rookie-alpha/{2022-2026}_rookie_alpha_predraft_v0.{json,csv}` + `{year}_manifest.json` | JSON+CSV+manifest | `scripts/compute_rookie_alpha.py` | SHA-256 hashes verified against disk, `run_id`, `generated_at` — confirmed each `{year}_manifest.json`'s `output_files` lists only the predraft JSON/CSV pair | `docs/export-contract.md`, validated by `scripts/validate_promoted_export.py` | `athletic_confidence`, `athletic_explainer`, `athletic_source` enum | Fix the athletic-score naming/semantic-drift issue before any external consumer trusts the field name (see `docs/athletic-score-normalization-audit.md`) |
| `exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_v0.{json,csv}` | JSON+CSV | `scripts/build_post_draft_alpha.py` | `source_profile`/`source_status` per row; **not** covered by `2026_manifest.json` (its `output_files` list only the predraft pair) and has no manifest of its own | `tests/test_build_post_draft_alpha.py::test_write_outputs_contract` checks output row shape (fixed `ROW_FIELDS`), but there is no hash/provenance manifest | Row-level shape only | Postdraft exists only for 2026 (no 2022-2025 equivalents) — treat as ungoverned relative to the manifest-verified predraft family; a Forecast adapter must not assume postdraft is hash-verified or that 2022-2025 postdraft files exist |
| `data/devy/devy_seed_watchlist_2026.json`, `data/devy/monthly_pulse/*`, real (non-fixture) `data/devy/league_market_snapshots/*` | JSON | `scripts/devy_signal_registry.py` and sibling validators | Three-way structured provenance + `intake_audit` issue/PR lineage | `schema_version` field + validator + 24 tests | `confidence_band`/`signal_strength_band`/`actionability_band` | Governance is strong; the data itself is explicitly non-authoritative by design — no action needed for audit purposes |
| `data/processed/2026_draft_results.json` | JSON | `docs/cross-repo-draft-results-ingestion.md` adapter | `source_name`, `source_url`, `source_status`, `upstream_provenance_status`, `ingested_from`/`ingested_at` (confirmed against actual rows — the upstream ingest input uses `provenance_status`, but the processed artifact itself carries `source_status`/`upstream_provenance_status`) | Upstream contract `tiber-data.nfl-draft-results.v1.0.0` cited explicitly | `upstream_provenance_status: source_verified` vs `needs_verification` vs `fixture_only` | Confirm this file is still current; prior years (2022-2025) are empty `[]` |

### `machine_readable_ungoverned_artifact`

| Path/family | Format | Provenance | Gap |
|---|---|---|---|
| `data/processed/qb_play_profiles/`, `rb_play_profiles/` | JSON | Real CFBD URLs + methodology notes | Has a README describing fields but no `schema_version` field, no validator, no test |
| `data/processed/wr_route_profiles/` | JSON | Mixed: 12 of 66 files have a real CFBD API `source_url`; the other 54 have `source_url: null` with `source_name` describing estimated/manual research (e.g. Grok/Sports-Reference cross-verification) | Has a README describing fields and a regeneration script, but no `schema_version`, no validator, no per-file flag distinguishing CFBD-observed rows from estimated ones |
| `data/processed/2026_player_stats.json`, `2026_yoy_trends.json`, `2026_age_adjusted_production.json`, `2026_dynasty_adp.json` | JSON | None or filename-implied only | No schema doc, no provenance fields, no validator |
| `exports/promoted/nfl-fantasy-outcomes/*.{json,csv}` | JSON+CSV | Row-level `source: "nflverse_public_release"` but no file-level metadata block | Contains unflagged `SIM`-prefixed synthetic rows; `player_name` blank on every sampled row |
| `data/processed/te_production_profiles/*.json` | JSON | Narrative `source_name` (no URL) | Manually curated, not a repeatable pipeline; confidence conveyed only in prose |
| `data/processed/2026_day2_draft_signal_profiles.json`, `2026_round1_draft_signal_profiles.json`, `2026_day3_udfa_draft_result_profiles.json` | JSON | Mixed — some `operator_seeded`, some `canonical_draft_results_reconciled` | Heavily narrative fields mixed with structured ones; not a strict flat-record contract |
| `data/raw/*_combine_results.json`, `*_real_seed_pool.json` | JSON | Per-field free-text `*_source` string, not a URL | No `schema_version`; derived proxy scores sit in the same row as observed measurables with no structural flag distinguishing them |
| `exports/promoted/historical-comps/2026_historical_comps_v0.json` | JSON | `source_files_used[]` lineage list | Has a contract doc and a gating field, but underlying data is self-described scaffold/sample — placed here rather than fully governed because the QB lane is explicitly `directional_only` and not methodology-compatible |

### `prose_only_context`

- `docs/concepts/daily/2026-06-13-tiber-concept-daily.md`
- `evidence_summary` / `context_source` fields across rookie-alpha rows
- `data/operator-journal/raw/2026_rookie_journal_entries.json`
- Most of `docs/` (contracts, policies, audits, runbooks) — these are governance prose *about*
  the pipeline, valuable for a human auditor, but not artifacts a machine would ingest

### `fixture_or_demo_only`

- `data/fixtures/devy_prospect_registry_v0_fixture.json`, `nfl_draft_results_v1_fixture.json`
- `data/devy/league_market_snapshots/deep_devy_draft_snapshot_2026_fixture.json`
- Sample rows inside `data/historical/historical_prospect_features.sample.json` and
  `.ml_sample.json` (marked `source_name: "sample_fixture"`, coexisting with real rows in the
  same file — flagged above as a defect, not just a category label)
- `prototype/` directory (confirmed by `docs/pr153-prototype-rollout-audit.md` to be an isolated,
  fabricated-sample-data surface, never wired into production)

### `not_forecast_consumable`

- `components/rookies/*.js`, `cards/**/*.html`, `rookieCardStyles.css` — pure presentation
- `lib/rookies/convictionStore.js`, `rookieQueueStore.js` — browser-local state, no server
  artifact
- `exports/promoted/rookie-ml-lane/*` — explicitly `"lane": "parallel_ml_evaluation_only"`,
  n_test_rows as low as 1, and contains leaked fixture rows in its training set
- Role-opportunity and team-context post-draft joins — explicitly inspect-only/non-scoring by
  their own docs

### `unknown_requires_followup`

- ~~`data/historical/te_reference_populations/*.json` — all five files contain WR data mislabeled
  as TE; whether any real TE reference population exists anywhere is unresolved~~ **Resolved by
  issue #257**: no real TE population exists anywhere in the repo's history (checked branches
  beyond `main` too); the files are now quarantined (empty) rather than mislabeled.
- Whether `docs/repo-state-audit-2026-postdraft.md`'s "BROKEN" status for the team-context join
  still holds today (this audit did not re-run the pipeline to check)
- Whether the `SIM`-prefixed rows in `nfl-fantasy-outcomes` were an intentional test fixture that
  was never stripped before promotion, or a pipeline bug

---

## Candidate capability ideas — evaluated against current evidence

| Candidate | Does Rookies have supporting governed data today? |
|---|---|
| Rookie transition profile | No dedicated artifact; would draw from rookie-alpha scores + play profiles, neither purpose-built for this |
| Draft capital context | Partial — `draft_capital_proxy_0_100` exists but is explicitly labeled a *temporary proxy*, not real draft capital, until `2026_draft_results.json` fully reconciles |
| College production translation | Partial — `*_college_production.json` is real and sourced but ungoverned (no schema_version/validator); `wr_route_profiles/` is only partly sourced (12 of 66 files are CFBD-observed, the rest are estimated) and equally ungoverned |
| First-year adaptation curve | No artifact exists; `nfl-fantasy-outcomes` could seed this but needs the SIM-row/blank-name cleanup first |
| Archetype / role projection | Explicitly out of scope today — the role-opportunity join is inspect-only and non-scoring by design |
| Landing spot context | Explicitly out of scope today — the team-context join is inspect-only, non-scoring, and was marked broken as of the last internal audit |
| Confidence / evidence quality rating | Closest thing that exists is devy's band taxonomy and rookie-alpha's `athletic_confidence`, but there is no repo-wide standardized version of this |

None of these currently exist as implemented Forecast-consumable capabilities; this list remains
candidates only, consistent with the issue's framing.

---

## Proposed bounded follow-up issues

Each is scoped narrowly and does not itself authorize Forecast consumption:

1. ~~**Fix TE reference population mislabeling**~~ — **Done in issue #257**: investigated,
   root-caused, and quarantined (see `docs/reports/2026-07-08-te-reference-population-repair.md`).
   Sourcing real TE data still requires a `CFBD_API_KEY`, which remains a genuine follow-up.
2. **Flag or strip synthetic rows in promoted exports** — add an explicit `is_synthetic`/
   `is_fixture` boolean to `exports/promoted/nfl-fantasy-outcomes/player_year_ppr_outcomes_v1.*`
   (currently only detectable via `SIM`-prefixed IDs) and to
   `data/historical/historical_prospect_features.sample.json`/`.ml_sample.json` (currently only
   detectable via `source_name: "sample_fixture"` string matching), and confirm whether fixture
   rows should be excluded from `exports/promoted/rookie-ml-lane/*` training data.
3. **Re-verify the team-context post-draft join status** — confirm whether the "BROKEN" finding
   in `docs/repo-state-audit-2026-postdraft.md` still holds, since that audit is now over a
   month old relative to this one.
4. **Reconcile `data/historical/README.md` against actual file contents** — the doc's claim that
   the 2017 WR reference population is an empty placeholder is stale; either the doc or file
   history should be corrected so future audits don't have to re-discover this.
5. **If Forecast consumption is later authorized**, a dedicated ingestion-adapter issue
   (mirroring `docs/tiber-fantasy-consumer-contract.md`) scoped specifically to the rookie-alpha
   predraft/postdraft export + manifest — the only artifact family with an end-to-end governed
   chain today — including an explicit review of the athletic-score semantic-drift finding
   before any field is trusted at face value.

---

## Decision

```text
rookies_machine_readable_artifact_audit_complete
```

This audit is complete: all nine questions above were answered directly against the repository's
actual contents (not its self-description), every artifact family was classified, and bounded
follow-up issues are proposed. This decision does not authorize Forecast consumption of any
Rookies artifact — per the gaps in question 9, no artifact in this repo is both fully governed
and designed for automated external consumption today.
