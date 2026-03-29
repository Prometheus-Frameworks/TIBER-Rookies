# TIBER-Rookies

TIBER-Rookies is the **authoritative Rookie Alpha producer lab** and now also has a **minimal standalone static runtime** so the rookie prototype can be deployed independently (including Railway).

It is intentionally not a full draft room, not a live backend, and not a runtime dependency for TIBER-Fantasy.

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

## Run standalone static lab locally

Requires Node.js 20+.

```bash
npm start
```

Then open:

- `http://localhost:3000/` (redirects to rookie board)
- `http://localhost:3000/cards/rookies/index.html`
- `http://localhost:3000/cards/rookies/board/index.html`
- `http://localhost:3000/cards/rookies/player.html?slug=wr-malik-ford`
- `http://localhost:3000/cards/rookies/compare/index.html?left=wr-malik-ford&right=te-owen-hale`
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
- 2026 canonical inputs are aligned to the **23-player real seed pool**, not synthetic placeholder identities.
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
