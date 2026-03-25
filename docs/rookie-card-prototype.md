# Rookie Card Prototype Handoff (2026 class)

## PR7 update summary (since PR5)

- Promoted the gallery from a demo list into a class board with deterministic sort/filter controls.
- Added a compact rookie card variant intended for gallery use now and social/share surfaces later.
- Added position-aware evidence selection so full and compact cards choose metrics by position profile.
- Tightened fallback behavior so missing data is omitted cleanly (no null/debug dumps).

## Routes

- `/cards/rookies/index.html` (class board + compact cards + controls)
- `/cards/rookies/player.html?slug=<player_id>` (full detail route)
- `/cards/rookies/wr-malik-ford/index.html` (direct single-player entry for one real rookie)

## Source data used (unchanged)

- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json`
- `data/raw/2026_combine_results.json`
- `data/processed/2026_college_production.json`
- `data/processed/2026_draft_capital_proxy.json`

## Gallery behavior (v2)

- Default sort: `Rookie Grade` descending.
- Optional sort: `Position` (QB, RB, WR, TE ordering).
- Filter: single position or all positions.
- Optional profile-tag filter using deterministic tags already derived from existing score bands.
- Ranking context line shows visible count and clarifies class rank source (promoted export ordering).

## Compact/share card purpose

Compact card is not an export engine. It is a reusable visual format for:

- gallery tiles now,
- future social/share surface,
- future export pathways once a stable renderer is chosen.

Compact card includes:

- player identity (name, position, school when available),
- Rookie Grade + class rank,
- 3–4 key evidence metrics,
- archetype/projection snippet,
- up to 3 tags.

## Position-aware evidence selection

Helper: `lib/rookies/selectRookieEvidenceMetrics.js`

- Input: mapped rookie card view model.
- Output: deterministic metric list for `full` and `compact` variants.
- Uses position priority maps:
  - WR/TE prioritize production + athletic receiving-adjacent indicators available in artifacts.
  - RB prioritizes production + draft capital + rushing-athletic proxies available in artifacts.
  - QB fallback prefers available passing-proxy friendly fields if present.
- Missing metric values are omitted rather than filled with fabricated values.

## Data honesty constraints still enforced

- No fabricated school/age/comps/season rows.
- No fake export claims (PNG/PDF is still TODO).
- If artifacts do not carry a metric, card sections omit it or show explicit unavailable copy.

## Next obvious expansion path

1. Add a richer processed rookie profile artifact (school/age/bio).
2. Add position-native stat features (target share, YPRR, rushing share, etc.) from pipeline outputs.
3. Add compare-mode layout reusing compact card blocks.
4. Add URL query-state persistence for board controls when moved to app runtime.
