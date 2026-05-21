# TIBER-Rookies

TIBER-Rookies is the **authoritative Rookie Alpha producer lab** and now also has a **minimal standalone static runtime** so the rookie prototype can be deployed independently (including Railway).

It is intentionally not a full draft room, not a live backend, and not a runtime dependency for TIBER-Fantasy.

## External source hygiene

TIBER-Rookies uses external analyst commentary only as qualitative context unless explicit written permission/licensing is documented. Do not scrape, copy, store, or model on third-party proprietary/paywalled analyst content.

See [docs/legal/external-source-hygiene-policy.md](docs/legal/external-source-hygiene-policy.md) for full requirements.

## Draft-week readiness (March 27, 2026)

This repository is **draft-week ready for promoted artifact handoff** when an operator can complete the documented 2026 rehearsal path:

1. generate the promoted artifact set,
2. validate the artifact + manifest,
3. verify standalone TIBER-Rookies routes and smoke checks,
4. manually hand those same files to TIBER-Fantasy ingest,
5. verify `/rookies` in TIBER-Fantasy after ingest.

What is still manual on purpose:

- cross-repo file transfer from TIBER-Rookies to TIBER-Fantasy,
- running TIBER-Fantasy-side ingest/verification commands,
- final production promotion decision by operator.

## Operator quickstart (2026)

Run from repository root:

```bash
npm run ops:rehearse-2026
```

Expected output signals:

- generated artifact files are listed under `exports/promoted/rookie-alpha/`,
- validator prints `VALIDATION PASSED`,
- runtime smoke test exits successfully,
- script ends with `Draft-week rehearsal for 2026 completed.`

For deployed URL checks in the same sequence:

```bash
RUN_REMOTE_CURLS=1 BASE_URL="https://<deployed-rookies-url>" npm run ops:rehearse-2026
```

## Repository framing

This repo has two intentionally separated layers:

1. **Producer layer (authoritative)**
   - computes the pre-draft Rookie Alpha model (`v0`)
   - emits promoted JSON/CSV plus a reproducibility manifest
   - supports validation before downstream ingest
2. **Standalone static lab layer (deployable)**
   - serves static rookie surfaces from existing artifact-backed files
   - provides gallery, board, detail, compare, shortlist queue, queue import/export, and local note/tag behavior
   - does not recompute model logic at request time

## Current capabilities

### Producer + contract capabilities

- Standalone promoted export pipeline via `scripts/compute_rookie_alpha.py`
- Promoted artifact set per season:
  - `exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.json`
  - `exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.csv`
  - `exports/promoted/rookie-alpha/{season}_manifest.json`
- Manifest + validation contract documented in `docs/export-contract.md`
- Consumer ingest gate helper: `scripts/validate_promoted_export.py`

### Standalone rookie lab capabilities

- Runtime entrypoint: `runtime-server.js` (small Node HTTP static server)
- Health endpoint: `GET /health`
- Root redirect: `/` → `/cards/rookies/board/index.html`
- Served rookie surfaces:
  - `/cards/rookies/index.html`
  - `/cards/rookies/board/index.html`
  - `/cards/rookies/player.html?slug=<player_id>`
  - `/cards/rookies/compare/index.html?left=<slug>&right=<slug>`
- Browser-local shortlist queue (`localStorage`) with add/remove/reorder/import/export and local note/tag annotations

## Repository layout

- `README.md`
- `runtime-server.js`
- `package.json`
- `railway.json`
- `docs/`
  - `architecture.md`
  - `export-contract.md`
  - `rookie-card-prototype.md`
  - `tiber-fantasy-consumer-contract.md`
  - `runbooks/standalone-railway-rookie-lab.md`
  - `runbooks/draft-week-handoff-2026.md`
- `scripts/`
  - `compute_rookie_alpha.py`
  - `validate_promoted_export.py`
  - `rehearse_draft_week_handoff_2026.sh`
- `lib/rookies/`
  - mapping/adaptation and prototype helpers
- `cards/rookies/`
  - static gallery/board/detail/compare surfaces
- `data/raw/`
  - canonical combine inputs projected from the 2026 real seed pool
- `data/processed/`
  - canonical production + draft-capital-proxy inputs aligned to the same 2026 real seed pool
  - optional deterministic context scaffold (`2026_prospect_context.json`) for additive translation/evidence enrichment
- `exports/promoted/rookie-alpha/`
  - generated promoted outputs

## Current model implementation (pre-draft v0)

Implemented formula (unchanged):

- **RAS 35%**
- **Production 45%**
- **Draft capital proxy 20%**
- **Age-at-entry not implemented yet**

This is explicitly labeled `pre-draft v0` in export metadata. Current model version `rookie-alpha-predraft-v0.2.0` adds additive deterministic `context`/`evidence` player fields only; Rookie Alpha weights and ranking formula are unchanged.

## 2026 temporary pre-draft draft-capital proxy conversion

For the real 2026 seed pool, `draft_capital_proxy_0_100` is currently a temporary pre-draft proxy derived from seeded `big_board_rank` values (not true NFL draft capital outcomes).

Deterministic conversion bands:

- ranks `1–10` → `95`
- ranks `11–20` → `85`
- ranks `21–32` → `75`
- ranks `33–50` → `65`
- ranks `51–75` → `55`
- ranks `76–100` → `45`
- rank missing or out of range (`>100`) → `null`

This conversion only applies where a seeded `big_board_rank` exists. Missing ranks remain missing for draft-capital proxy.

## Run producer pipeline

```bash
python3 scripts/compute_rookie_alpha.py
```

Optional explicit inputs/outputs:

```bash
python3 scripts/compute_rookie_alpha.py \
  --season 2026 \
  --combine-input data/raw/2026_combine_results.json \
  --production-input data/processed/2026_college_production.json \
  --draft-proxy-input data/processed/2026_draft_capital_proxy.json \
  --context-input data/processed/2026_prospect_context.json \
  --output-json exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
  --output-csv exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.csv \
  --output-manifest exports/promoted/rookie-alpha/2026_manifest.json
```

## Validate promoted export before ingest

```bash
python3 scripts/validate_promoted_export.py \
  --export-json exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
  --manifest exports/promoted/rookie-alpha/2026_manifest.json
```

Validation checks field presence, metadata consistency, hashes, and row-count expectations.


## Devy signal discovery foundation

TIBER-Devy is an additive signal-discovery layer for prospects whose Rookie Alpha
inputs are not stable enough for deterministic scoring. It models development
horizon, lifecycle stage, development tags, and uncertainty/actionability bands;
it does not produce rankings, predictive ML, future NFL draft capital, or
precision grades.

Canonical definitions and validation live in `scripts/devy_signal_registry.py`.
The fixture-only registry at `data/fixtures/devy_prospect_registry_v0_fixture.json`
uses illustrative placeholder rows to validate schema behavior without creating
unsourced player facts. Run:

```bash
python3 scripts/devy_signal_registry.py --registry data/fixtures/devy_prospect_registry_v0_fixture.json
```

See `docs/devy-signal-discovery.md` for the lifecycle vocabulary, horizon logic,
and guardrails that keep 2029-type long-horizon assets from being treated as
next-cycle rookie prospects.

The real seed watchlist (`data/devy/devy_seed_watchlist_2026.json`) is a curated
non-promoted discovery artifact with an artifact-level `intake_audit` trail
(issue/PR lineage, intake method, validator command, and downstream block status).



## Monthly Devy roster pulse (candidate delta, discovery-only)

The `monthly_devy_roster_pulse` lane is a quarantined discovery workflow that
surfaces roster/program/class-context deltas for operator review. It does **not**
mutate the curated seed watchlist automatically and is blocked from Rookie Alpha,
NFL scoring, FORGE, Point Prediction, and TIBER-Fantasy active NFL surfaces.

Validate the pulse artifact with:

```bash
python3 scripts/validate_devy_roster_pulse.py --artifact data/devy/monthly_pulse/devy_roster_pulse_2026_05.json
```

## Parallel ML evaluation lane (phase 1, experimental)

This repo now includes an **experimental parallel ML lane** that evaluates rookie hit probabilities from historical labeled rows. It is strictly additive and does **not** replace deterministic Rookie Alpha scoring.

Run from repo root:

```bash
python3 scripts/compute_rookie_ml_lane.py
```

Default outputs are written to `exports/promoted/rookie-ml-lane/`:

- `historical_outcomes_canonical.json`
- `historical_label_provenance_report.json`
- `historical_feature_consistency_report.json`
- `historical_class_coverage_report.json`
- `historical_position_slices_report.json`
- `historical_labeled_dataset.json` / `.csv`
- `feature_table.json`
- `dataset_diagnostics.json`
- `feature_coverage_report.json`
- `feature_importance_report.json`
- `evaluation_report.json`
- `heldout_probabilities.json` / `.csv`

The evaluator uses time-aware draft-class splits, logistic baselines, required feature-subset baselines, and non-ML baseline comparisons.

### Historical truth layer checklist (inspect before trusting ML metrics)

Use the artifacts above to decide whether the lane is trustworthy enough to keep iterating. The intent is explicit, provenance-aware historical truth, not extra model complexity:

- **Canonical outcomes first:** inspect `historical_outcomes_canonical.json` to verify each player row has explicit by-year-3 outcome fields, a canonical hit label, an outcome bucket, and `label_source_fields_used`.
- **Label provenance honesty:** inspect `historical_label_provenance_report.json` for row counts by label source, position+source breakdown, weak fallback usage counts, and unresolved-canonical-label counts.
- **Feature consistency + fallback visibility:** inspect `historical_feature_consistency_report.json` for feature availability by year/position/(position+year), plus fallback/proxy usage counts for derived fields.
- **Class coverage realism:** inspect `historical_class_coverage_report.json` for usable rows and thin cohorts by draft year, position, and year+position, including rows with strong feature completeness and rows surviving split filters.
- **Position readiness slices:** inspect `historical_position_slices_report.json` for WR/RB/TE/QB labeled counts, canonical outcome counts, feature completeness, hit rate, draft year representation, and warnings.

- **Historical data volume:** open `dataset_diagnostics.json` for total labeled rows, rows by position/year, split counts, and hit rates.
- **Feature completeness:** open `feature_coverage_report.json` for per-feature null/non-null counts plus coverage by position and draft year.
- **Thin-data warnings:** `evaluation_report.json` includes `dataset_warnings`, `historical_truth_summary`, and `missingness_summary` (including warnings for weak label provenance, sparse positions, and frequent fallback usage).
- **Position stability:** check `test_by_position` metrics (WR/RB/TE/QB) under each model and non-ML baseline in `evaluation_report.json`.
- **Draft-capital dominance:** inspect `draft_capital_dominance_check` in `evaluation_report.json` to see test PR-AUC deltas between `logistic_full` and:
  - `draft_capital_only`
  - `draft_capital_plus_production`
  - `deterministic_grade_only`
- **Coefficient interpretability:** use `feature_importance_report.json` for coefficient sign, absolute magnitude ranking, and normalized importance ordering for `logistic_full`.

If warnings indicate very sparse position slices, weak feature coverage, or tiny pre-holdout history, treat the ML lane as directional diagnostics rather than production-grade forecasting.

## Run standalone static lab locally

Requires Node.js 20+.

```bash
npm start
```

Then open:

- `http://localhost:3000/` (redirects to rookie board)
- `http://localhost:3000/cards/rookies/index.html`
- `http://localhost:3000/cards/rookies/board/index.html`
- `http://localhost:3000/cards/rookies/player.html?slug=wr-jordyn-tyson`
- `http://localhost:3000/cards/rookies/compare/index.html?left=wr-jordyn-tyson&right=te-kenyon-sadiq`
- `http://localhost:3000/health`

## Railway deploy contract

This repo is Railway-ready with an explicit start contract:

- `package.json` script: `npm start`
- runtime binds to `PORT` from environment
- `railway.json` sets:
  - `startCommand: npm start`
  - `healthcheckPath: /health`

Deployment flow:

1. Create a Railway project from this repo.
2. Ensure Node 20+ runtime.
3. Deploy with default command (`npm start`).
4. Verify `/health` and rookie routes after deploy.

See the operator runbooks:

- `docs/runbooks/standalone-railway-rookie-lab.md`
- `docs/runbooks/draft-week-handoff-2026.md`

## Current limitations

- Model is still **pre-draft v0** (no landing-spot or NFL transition phase yet).
- 2026 canonical inputs are aligned to the **24-player real seed pool**, not synthetic placeholder identities.
- 2026 remains **proxy-limited** (college production and draft capital are normalized proxy inputs, not final NFL outcomes).
- Missing `production_score_0_100` values are expected for some players in this phase; identity alignment does not imply production-score completeness.
- Queue is **browser-local only** (no auth, no multi-device sync, no league persistence).
- Runtime is intentionally **static-only** (no database, no model recompute, no live room).
- Surface richness depends on available promoted/source artifact fields.
- Missing player identity/context fields can still produce deterministic fallback states.

## TIBER-Fantasy handoff stance

TIBER-Fantasy (or any downstream consumer) should ingest promoted exports as versioned artifacts. It should not treat this repository as a live runtime dependency.

See:

- `docs/architecture.md`
- `docs/export-contract.md`
- `docs/tiber-fantasy-consumer-contract.md`
- `docs/runbooks/draft-week-handoff-2026.md`
- `docs/rookie-card-prototype.md`

## Historical comps foundation (producer-only scaffold)

This repo now includes a **producer-only historical comps foundation lane** with no UI integration in this phase.

Canonical scaffold files:

- `data/historical/README.md`
- `data/historical/historical_prospect_features.schema.md`
- `data/historical/historical_prospect_features.sample.json`
- `data/historical/historical_player_outcomes.sample.json`
- `docs/historical-comps-contract.md`

Run the historical comps producer with sample scaffold data:

```bash
python3 scripts/compute_historical_comps.py \
  --rookie-export exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
  --historical-features data/historical/historical_prospect_features.sample.json \
  --historical-outcomes data/historical/historical_player_outcomes.sample.json \
  --output-json exports/promoted/historical-comps/2026_historical_comps_v0.json \
  --comp-mode talent_comp
```

If outcomes are not yet locally populated:

```bash
python3 scripts/compute_historical_comps.py \
  --historical-outcomes data/historical/local_historical_player_outcomes.json \
  --allow-missing-outcomes
```

Emitted artifact path:

- `exports/promoted/historical-comps/{season}_historical_comps_v0.json`

Notes:

- Sample historical files are scaffold fixtures, not a complete historical warehouse.
- The committed `exports/promoted/historical-comps/2026_historical_comps_v0.json` is also sample/scaffold output generated from those fixtures.
- Local operators can replace sample files with real locally prepared historical datasets that satisfy the documented schema and contract.
- UI integration for comp pills/card surfaces is intentionally out of scope for this PR.
