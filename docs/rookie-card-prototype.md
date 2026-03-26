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

Supported queue operations:

- `loadRookieQueue()`
- `addRookieToQueue(item)`
- `removeRookieFromQueue(slug)`
- `moveQueuedRookie(slug, 'up' | 'down')`
- `clearRookieQueue()`
- `isRookieQueued(slug)`


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
