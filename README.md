# TIBER-Rookies

TIBER-Rookies is the **authoritative Rookie Alpha producer lab** and now also has a **minimal standalone static runtime** so the rookie prototype can be deployed independently (including Railway).

It is intentionally not a full draft room, not a live backend, and not a runtime dependency for TIBER-Fantasy.

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
- `scripts/`
  - `compute_rookie_alpha.py`
  - `validate_promoted_export.py`
- `lib/rookies/`
  - mapping/adaptation and prototype helpers
- `cards/rookies/`
  - static gallery/board/detail/compare surfaces
- `data/raw/`
  - combine inputs (example 2026 artifact)
- `data/processed/`
  - production and draft-capital-proxy artifacts
- `exports/promoted/rookie-alpha/`
  - generated promoted outputs

## Current model implementation (pre-draft v0)

Implemented formula:

- **RAS 35%**
- **Production 45%**
- **Draft capital proxy 20%**
- **Age-at-entry not implemented yet**

This is explicitly labeled `pre-draft v0` in export metadata.

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
  --output-json exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
  --output-csv exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.csv
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

See the operator runbook: `docs/runbooks/standalone-railway-rookie-lab.md`.

## Current limitations

- Model is still **pre-draft v0** (no landing-spot or NFL transition phase yet).
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
- `docs/rookie-card-prototype.md`
