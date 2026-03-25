# Rookie Card Prototype Handoff (2026 class)

## PR9 update summary (first dedicated rookie board)

- Added a dedicated 2026 rookie board route that is ranking-first and distinct from the browse-first gallery.
- Added deterministic rookie board helpers for row building, tier derivation, sorting/filtering, and tier grouping.
- Added a board surface with rank, position, school availability state, Rookie Grade, tier label, and short profile summary.
- Added restrained board controls: sort, position filter, and tiered-vs-flat board view toggle.
- Added quick board actions to jump directly into full detail (`player.html`) and compare (`compare/index.html?left=...`) flows.
- Added a board header summary showing class coverage, position mix, tier count, and explicit tier rule bands.

## Routes

- `/cards/rookies/index.html` (browse-first compact card gallery)
- `/cards/rookies/board/index.html` (ranking-first rookie board surface)
- `/cards/rookies/player.html?slug=<player_id>` (full detail route)
- `/cards/rookies/compare/index.html?left=<slug>&right=<slug>` (two-player compare surface)
- `/cards/rookies/wr-malik-ford/index.html` (direct single-player entry for one real rookie)

## Source data used (unchanged)

- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json`
- `data/raw/2026_combine_results.json`
- `data/processed/2026_college_production.json`
- `data/processed/2026_draft_capital_proxy.json`

## Board sort/filter behavior

Helper: `lib/rookies/buildRookieBoardRows.js`

- Default sort is `grade` (Rookie Grade descending, then class rank tiebreak).
- Alternate sorts:
  - `rank` (class rank ascending)
  - `position` (position alpha, then grade desc, then class rank)
- Position filter supports `ALL` + available class positions from mapped card objects.
- View mode supports:
  - `tiered` (grouped sections)
  - `flat` (single ranked list)

## Tier/group logic (deterministic + inspectable)

Helper: `lib/rookies/deriveRookieTier.js`

Tier labels are intentionally coarse and score-band based:

- `Top cluster`: Rookie Grade >= 75
- `Strong starter tier`: Rookie Grade >= 70
- `Development tier`: Rookie Grade >= 65
- `Swing tier`: Rookie Grade < 65
- `Unscored cluster`: Rookie Grade missing

Grouping helper: `lib/rookies/groupRookiesByTier.js`

- Rows inherit the tier object from `deriveRookieTier`.
- Tiered board sections are grouped by tier key and rendered in fixed bucket order.
- No model-generated or opaque clustering is used.

## Quick action flow wiring

Board row actions intentionally reinforce:

`board -> inspect -> compare`

- `Detail` action links to `/cards/rookies/player.html?slug=<slug>`
- `Compare` action links to `/cards/rookies/compare/index.html?left=<slug>`

This reuses existing route/query behavior and avoids introducing a parallel state system.

## Missing data handling

- School remains honest to current artifact scope: board shows `School N/A` where school is not present in promoted data.
- Profile summary falls back deterministically in this order:
  1. archetype
  2. projection
  3. first tag
  4. `Profile still forming`
- Missing Rookie Grade is rendered as `N/A` and routed to `Unscored cluster`.

## Next likely expansion path (toward draft-room)

1. Add URL query-param persistence for board state (`sort`, `position`, `view`) so links can preserve board context.
2. Add a lightweight compare queue (pick first, pick second from board rows) without simulating live draft mechanics.
3. Expand promoted profile artifact with school/bio and position-native evidence so board rows can surface richer but still honest scouting signals.
4. Layer in draft-room interactions (queue, targets, notes) on top of this board rather than replacing this deterministic board foundation.
