# TIBER-Rookies Architecture

## Current state of the repository

TIBER-Rookies is currently a **dual-layer repository**:

1. **Producer layer (authoritative contract surface)**
2. **Static UI/product-surface layer (prototype consumer of mapped artifacts)**

This keeps model computation and downstream ingestion integrity intact while allowing fast UX iteration against real outputs.

## Layer 1: Producer layer (authoritative)

Core scripts:

- `scripts/compute_rookie_alpha.py`
- `scripts/validate_promoted_export.py`

Producer responsibilities:

- compute pre-draft Rookie Alpha (`v0`) scores from local artifacts
- emit promoted outputs (`json`, `csv`) and manifest (`*_manifest.json`)
- maintain reproducibility and integrity metadata (hashes, row counts, run metadata)

Model formula currently implemented:

- RAS 35%
- Production 45%
- Draft capital proxy 20%
- Age-at-entry not implemented yet

Promoted artifacts are authoritative for downstream consumers.

## Layer 2: Mapping/adaptation layer

Core adaptation helpers live under `lib/rookies/`.

Responsibilities:

- map promoted/source artifacts into display-ready rookie card and board shapes
- normalize/fallback incomplete fields into deterministic UI-safe values
- derive reusable identity/context summaries (`normalizeRookieIdentity`, `deriveRookieProfileSummary`) for board/detail/compare/queue consumers
- provide compare and queue-supporting helpers without changing producer contract authority

This layer intentionally sits between raw exports and static UI so prototype surfaces do not drift into a second model source of truth.

## Layer 3: Static UI/product-surface layer (prototype)

Static HTML routes under `cards/rookies/` currently include:

- gallery: `/cards/rookies/index.html`
- board: `/cards/rookies/board/index.html`
- detail: `/cards/rookies/player.html?slug=<player_id>`
- compare: `/cards/rookies/compare/index.html?left=<slug>&right=<slug>`
- direct player page example: `/cards/rookies/wr-malik-ford/index.html`

Behavioral scope today:

- browse and inspect rookie cards/rows from mapped real artifacts
- compare two rookies via query-param routing
- maintain browser-local shortlist queue state (`localStorage`)

This is a static prototype surface, not a draft-room service.

## Downstream consumer boundary (TIBER-Fantasy and others)

Downstream systems should consume **promoted exports** and validate them using the manifest contract before ingest.

Boundary rule:

- downstream consumers should ingest versioned exports
- downstream consumers should not depend on this repository as a live backend

See `docs/tiber-fantasy-consumer-contract.md` for ingest-gate requirements.

## Limitations and intended evolution

Current limitations:

- pre-draft v0 only (no landing-spot/NFL transition layers)
- static UI with browser-local queue only
- surfaced richness constrained by available promoted/source fields

Intended near-term direction:

- enrich promoted identity/context fields
- improve evidence mapping quality
- add queue import/export portability before account-backed persistence
- only layer true draft-room capabilities when auth/persistence boundaries are real
