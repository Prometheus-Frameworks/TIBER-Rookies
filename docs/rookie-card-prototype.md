# Rookie Intelligence Prototype (static surfaces)

## Purpose and maturity

This prototype demonstrates rookie browsing/inspection flows on top of real promoted artifacts from the Rookie Alpha producer pipeline.

It is intentionally:

- static (no backend service)
- local-state-driven for shortlist queue behavior
- scoped as a prototype surface, not a production draft room

## Current routes and surfaces

- `/cards/rookies/index.html`
  - compact gallery for browse-first discovery
- `/cards/rookies/board/index.html`
  - ranking-first board with filters/sort/view controls and queue panel
- `/cards/rookies/player.html?slug=<player_id>`
  - detail view for a single rookie
- `/cards/rookies/compare/index.html?left=<slug>&right=<slug>`
  - two-player compare view
- `/cards/rookies/wr-malik-ford/index.html`
  - direct single-player entry example

## Data sources

Surface data is mapped from repository artifacts, including:

- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json`
- `data/raw/2026_combine_results.json`
- `data/processed/2026_college_production.json`
- `data/processed/2026_draft_capital_proxy.json`

Mapping/adaptation helpers live in `lib/rookies/`, including deterministic identity/profile enrichers (`normalizeRookieIdentity`, `deriveRookieProfileSummary`) used by board/detail/compare/queue surfaces.

## Board flow and URL state

Board route: `/cards/rookies/board/index.html`

Board control state syncs to URL params via `replaceState`:

- `sort=grade|rank|position`
- `position=ALL|QB|RB|WR|TE|…`
- `view=tiered|flat`

State is hydrated from URL on initial load. Unknown sort/view values are ignored; invalid position values are reset to `ALL`.

## Compare flow

Board and queue actions set compare sides and route to:

- `/cards/rookies/compare/index.html?left=<slug>&right=<slug>`

This is route-level glue to the existing compare surface; no separate compare backend or model variant is introduced.

## Shortlist queue behavior (browser-local)

Queue helper: `lib/rookies/rookieQueueStore.js`

Storage model:

- key: `tiber-rookie-queue-v1`
- local browser profile only
- no server writes, no auth, no cross-device sync
- portability is file-based JSON export/import (manual, not synced)

Supported queue operations:

- `loadRookieQueue()`
- `addRookieToQueue(item)`
- `removeRookieFromQueue(slug)`
- `moveQueuedRookie(slug, 'up' | 'down')`
- `clearRookieQueue()`
- `isRookieQueued(slug)`
- `serializeRookieQueue()`
- `importRookieQueue(payload, { mode: 'replace' | 'merge' })`
- `updateQueuedRookieNote(slug, note)` / `clearQueuedRookieNote(slug)`
- `updateQueuedRookieTag(slug, tag)` / `clearQueuedRookieTag(slug)`

### Queue annotations + portability (PR15)

Queue portability is intentionally a **local workflow tool**, not a platform feature.

- Export action downloads JSON from current browser-local queue state.
- Import action validates JSON before writing to local storage.
- Default import mode is **Replace queue** (with confirmation when queue is non-empty).
- Optional import mode **Merge imported first** keeps imported order, dedupes by `slug`, and appends existing non-imported players after imported items.
- Malformed/incompatible files fail with visible, concise errors and do not partially mutate queue state.

Queue annotation scope:

- Optional draft tag from a fixed list only: `Target`, `Fade`, `Compare later`, `Landing spot watch`, `Contingency`, `Tier break`, `Upside swing`, `Floor play`.
- Optional short queue note (`160` chars max, trimmed and whitespace-normalized before storage).
- Notes/tags are editable from the queue panel only; board/detail/gallery show read-only context when queued.

Export payload shape (v2):

- `version` (currently `2`)
- `exported_at` (ISO timestamp)
- `source` (surface note)
- `queue` (array of queue entries including optional `queueTag` and `queueNote`)
- `metadata` (lightweight context such as `total_items`, storage note, and annotation constraints)

Validation/version rules:

- Top-level value must be an object.
- `version` must be `1` or `2` (`1` imports still load, with no annotations).
- `queue` must be an array.
- each queue item must include a valid `slug`.
- optional fields are normalized through queue-store fallbacks.

Boundary note:

- this JSON is a **portability artifact for static UI state**
- it is **not** part of the producer/export contracts in `docs/export-contract.md`
- it does **not** imply auth/account identity or cloud persistence


## Mapped identity/context enrichment

The mapped rookie card object now carries additional deterministic fields (without changing producer weights):

- `identity.positionLabel`, `identity.roleLabel`, `identity.schoolDisplay`
- `summary.profileSummary`, `summary.identityNote`, `summary.boardSummary`
- `metrics[*].family`, `metrics[*].direction`, `metrics[*].source`
- `evidence.readinessLabel`, family availability, and missing-input context

These fields are derived from existing promoted + supporting artifacts only; no synthetic scouting claims are introduced.

## Missing-data and fallback behavior

Surfaces retain deterministic fallbacks where artifacts are incomplete:

- school now uses normalized source precedence and otherwise renders `School unavailable in current artifacts`
- profile summary now derives from deterministic score/evidence context before falling back to archetype/projection/tag data
- missing Rookie Grade renders as `N/A`
- queue rows use fallback labels for unavailable fields

## Current limitations

- Prototype reads from current artifact coverage; richer identity/context depends on producer-field expansion.
- Queue is local-only and should not be interpreted as shared draft state.
- Surface interactions are static-route UX scaffolding, not league workflow infrastructure.

## Next likely steps (grounded)

1. Enrich promoted rookie identity/context fields upstream.
2. Improve mapped evidence inputs for board/detail/compare clarity.
3. Add queue import/export portability for local workflows.
4. Consider account-backed draft-room features only when auth/persistence boundaries exist.
