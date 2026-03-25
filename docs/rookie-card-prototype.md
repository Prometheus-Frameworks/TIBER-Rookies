# Rookie Card Prototype Handoff (2026 class)

## PR10 update summary (first honest rookie shortlist queue)

- Added a local rookie shortlist queue workflow on top of the rookie board route.
- Added queue controls on board rows (`Add to queue` / `Queued`) with duplicate prevention and visible queued state.
- Added queue actions on detail cards and compact gallery cards for quick shortlist updates from inspect surfaces.
- Added a dedicated queue panel on the board page with:
  - queue summary strip
  - queued player context rows (rank, name, position, school, Rookie Grade, tier, identity note)
  - remove actions
  - move up / move down ordering
  - compare pairing controls (set left / set right) + quick compare launch
- Added browser-local persistence through `localStorage` (no auth, no backend, no league sync implied).
- Added a clear queue action with explicit confirmation prompt.

## Routes

- `/cards/rookies/index.html` (browse-first compact card gallery)
- `/cards/rookies/board/index.html` (ranking-first rookie board + local shortlist queue panel)
- `/cards/rookies/player.html?slug=<player_id>` (full detail route + shortlist action)
- `/cards/rookies/compare/index.html?left=<slug>&right=<slug>` (two-player compare surface)
- `/cards/rookies/wr-malik-ford/index.html` (direct single-player entry for one real rookie)

## Source data used (unchanged)

- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json`
- `data/raw/2026_combine_results.json`
- `data/processed/2026_college_production.json`
- `data/processed/2026_draft_capital_proxy.json`

## Queue state + persistence

Helper: `lib/rookies/rookieQueueStore.js`

Queue state is intentionally small and browser-local:

- Storage key: `tiber-rookie-queue-v1`
- Stored record fields:
  - `slug`
  - `name`
  - `position`
  - `school`
  - `rookieGrade`
  - `classRank`
  - `tierLabel`
  - `identityNote`

Supported store operations:

- `loadRookieQueue()`
- `addRookieToQueue(item)` (deduped by `slug`)
- `removeRookieFromQueue(slug)`
- `moveQueuedRookie(slug, 'up' | 'down')`
- `clearRookieQueue()`
- `isRookieQueued(slug)`

No server writes are introduced. Queue is scoped to the current browser profile.

## Board + queue behavior

Board route: `/cards/rookies/board/index.html`

- Board rows now include queue action controls in the existing action column.
- Queued rows receive a subtle visual highlight.
- Queue panel appears below the board and is fed from local queue state.
- Summary strip includes:
  - total queued players
  - position mix
  - highest-ranked queued player
  - explicit local-storage disclaimer
- Each queued row includes:
  - rank
  - player identity
  - rookie grade + tier
  - identity note
  - detail jump link
  - remove action
  - move up/down actions
  - compare side assignment actions

## Compare-from-queue behavior

- Queue rows support `Set Left` and `Set Right` markers.
- Queue toolbar exposes `Compare selected pair` when both sides are set and distinct.
- Compare launch reuses existing compare route/query model:
  - `/cards/rookies/compare/index.html?left=<slug>&right=<slug>`

No new compare engine is added; this is routing glue into the existing compare page.

## Missing data handling

- Queue entries preserve current data honesty:
  - missing school renders as `School N/A`
  - missing grade renders as `N/A`
  - missing notes fall back to `Profile note unavailable`
  - missing tier label falls back to `Tier N/A`

## Next likely expansion path (toward draft-room)

1. Add optional queue notes (short deterministic text only) per queued rookie in local state.
2. Add URL persistence for board filter/view state to share exact board + queue context snapshots.
3. Add lightweight import/export for queue JSON so users can move shortlist state between browsers.
4. Add account-backed persistence only when draft-room auth and tenancy boundaries are real (not simulated in prototype).
