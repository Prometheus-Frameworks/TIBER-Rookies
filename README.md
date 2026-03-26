# TIBER-Rookies

TIBER-Rookies is a **standalone Rookie Alpha producer lab** with a **static rookie intelligence prototype** layered on top of real promoted artifacts.

It is intentionally not a full draft room or live backend service.

## Repository framing

This repo currently has two aligned layers:

1. **Producer layer (authoritative)**
   - computes the pre-draft Rookie Alpha model (`v0`)
   - emits promoted JSON/CSV plus a reproducibility manifest
   - supports validation before downstream ingest
2. **Static product-surface layer (prototype)**
   - reads mapped artifact data into static HTML surfaces
   - provides gallery, board, detail, compare, and browser-local shortlist queue flows
   - exists to validate UX direction on top of real artifacts, not to replace downstream ingestion contracts

## Current capabilities

### Producer + contract capabilities

- Standalone promoted export pipeline via `scripts/compute_rookie_alpha.py`
- Promoted artifact set per season:
  - `exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.json`
  - `exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.csv`
  - `exports/promoted/rookie-alpha/{season}_manifest.json`
- Manifest + validation contract documented in `docs/export-contract.md`
- Consumer ingest gate helper: `scripts/validate_promoted_export.py`

### Static rookie prototype capabilities

- Gallery route: `/cards/rookies/index.html`
- Board route: `/cards/rookies/board/index.html`
- Detail route: `/cards/rookies/player.html?slug=<player_id>`
- Compare route: `/cards/rookies/compare/index.html?left=<slug>&right=<slug>`
- Browser-local shortlist queue (`localStorage`) with add/remove/reorder and compare-side assignment

## Repository layout

- `README.md`
- `docs/`
  - `architecture.md`
  - `export-contract.md`
  - `rookie-card-prototype.md`
  - `tiber-fantasy-consumer-contract.md`
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

## Current limitations

- Model is still **pre-draft v0** (no landing-spot or NFL transition phase yet).
- Queue is **browser-local only** (no auth, no multi-device sync, no league persistence).
- Repo is **not** a full draft room or live service.
- Surface richness depends on available promoted/source artifact fields.
- Missing player identity/context fields can still produce deterministic fallback states.

## Next likely steps

- Enrich promoted rookie identity/context fields in producer artifacts.
- Improve mapped evidence inputs used by static surfaces.
- Add queue portability (import/export) before any account-backed persistence.
- Consider draft-room layering only after real auth/persistence boundaries exist.

## TIBER-Fantasy handoff stance

TIBER-Fantasy (or any downstream consumer) should ingest promoted exports as versioned artifacts. It should not treat this repository as a live runtime dependency.

See:

- `docs/architecture.md`
- `docs/export-contract.md`
- `docs/tiber-fantasy-consumer-contract.md`
- `docs/rookie-card-prototype.md`
