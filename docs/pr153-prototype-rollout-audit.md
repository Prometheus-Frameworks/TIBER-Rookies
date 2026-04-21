# PR153 Prototype Rollout Audit

Date: 2026-04-21

## Question
Did PR #153's HTML prototype become the implementation used across all rookie player card surfaces in this repository?

## Conclusion
No. PR #153 introduced an isolated prototype implementation under `prototype/`, while production-like rookie card routes under `cards/rookies/` use a separate component/data pipeline.

## Evidence

1. **PR #153 implementation scope was `prototype/` only**
   - Commit `f3f6629` (`Add interactive rookie card prototype`) touched only:
     - `prototype/card.js`
     - `prototype/data.js`
     - `prototype/index.html`
     - `prototype/styles.css`
     - `prototype/tweaks.js`

2. **Prototype is explicitly documented as prototype/static**
   - `docs/rookie-card-prototype.md` describes this surface as static and explicitly “scoped as a prototype surface, not a production draft room.”

3. **Isolated prototype data model is distinct from routed surfaces**
   - The isolated `prototype/` directory uses fabricated local sample data via `window.ROOKIES`.
   - Routed `/cards/rookies/*` surfaces are documented and implemented as artifact-backed flows.

4. **Live rookie card route uses canonical module pipeline, not prototype files**
   - `cards/rookies/player.html` imports `getAllRookieCards` from `lib/rookies/getRookieCardData.js` and renders with `components/rookies/RookieCard.js`.
   - It does not import anything under `prototype/`.

5. **Canonical loader is multi-season and artifact-backed**
   - `lib/rookies/getRookieCardData.js` loads promoted exports and supplements.
   - `lib/rookies/rookieDataContract.js` defines seasons `[2026, 2025, 2024, 2023, 2022]`.

## Coverage snapshot (current repo state)
- Prototype sample players: 6
- Promoted export players across 2022–2026: 210

## Practical implication
Any desired visual/system improvements from the PR153 prototype need intentional porting into the active `components/rookies/*` + `cards/rookies/*` stack; they are not automatically inherited from `prototype/`.
