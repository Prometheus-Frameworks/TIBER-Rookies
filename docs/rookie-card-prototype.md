# Rookie Card Prototype Handoff (2026 class)

## PR11 update summary (URL state + compare-side quick actions)

- Added URL query-param persistence for board control state (`sort`, `position`, `view`) so board links retain context.
- Added `Set Left` / `Set Right` direct-nav actions on each board row, replacing the generic `Compare` link.
- Added position validation guard in `render()` so a stale URL position param that falls outside the available class is reset to `ALL` rather than producing an empty board.

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

## Board URL state

Board route: `/cards/rookies/board/index.html`

Board control state syncs to URL params on every render via `replaceState`:

- `sort=grade|rank|position`
- `position=ALL|QB|RB|WR|TE|…`
- `view=tiered|flat`

State is hydrated from URL on initial load. Unknown sort/view values are ignored; unknown position values are reset to `ALL` at render time.

## Board row quick actions

Board row actions reinforce the `board → inspect → compare` flow:

- `Detail` links to `/cards/rookies/player.html?slug=<slug>`
- `Set Left` links to `/cards/rookies/compare/index.html?left=<slug>`
- `Set Right` links to `/cards/rookies/compare/index.html?right=<slug>`
- `Add to queue` / `Queued` toggles local shortlist membership

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

- Board rows include queue action controls alongside Set Left / Set Right in the action column.
- Queued rows receive a subtle visual highlight.
- Queue panel appears below the board with a jump link above the board rows.
- Summary strip includes:
  - total queued players
  - position mix
  - highest-ranked queued player
  - explicit local-storage disclaimer
- Each queued row includes rank, player identity, rookie grade + tier, identity note, detail jump link, remove action, move up/down actions, and compare side assignment actions.

## Compare-from-queue behavior

- Queue rows support `Set Left` and `Set Right` markers.
- Queue toolbar exposes `Compare selected pair` when both sides are set and distinct.
- Compare launch reuses existing compare route/query model:
  - `/cards/rookies/compare/index.html?left=<slug>&right=<slug>`

No new compare engine is added; this is routing glue into the existing compare page.

## Missing data handling

- School remains honest to current artifact scope: board shows `School N/A` where not in promoted data.
- Profile summary falls back deterministically: archetype → projection → first tag → `Profile still forming`.
- Missing Rookie Grade renders as `N/A` and routes to `Unscored cluster`.
- Queue entries: missing school → `School N/A`, missing grade → `N/A`, missing notes → `Profile note unavailable`, missing tier → `Tier N/A`.

## Next likely expansion path (toward draft-room)

1. Add optional queue notes (short deterministic text only) per queued rookie in local state.
2. Add lightweight import/export for queue JSON so users can move shortlist state between browsers.
3. Expand promoted profile artifact with school/bio and position-native evidence so board rows can surface richer but still honest scouting signals.
4. Add account-backed persistence only when draft-room auth and tenancy boundaries are real (not simulated in prototype).
5. Layer in draft-room interactions (queue, targets, notes) on top of this board rather than replacing this deterministic board foundation.
