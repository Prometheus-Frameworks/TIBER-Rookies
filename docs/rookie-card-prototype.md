# Rookie Card Prototype Handoff (2026 class)

## Routes added

- `/cards/rookies/index.html` (gallery)
- `/cards/rookies/player.html?slug=<player_id>` (reusable detail route)
- `/cards/rookies/wr-malik-ford/index.html` (direct single-player entry for one real rookie)

## Source data used

- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json`
- `data/raw/2026_combine_results.json`
- `data/processed/2026_college_production.json`
- `data/processed/2026_draft_capital_proxy.json`

## Fields currently available and rendered

- Identity: `player_name`, `position`, `classYear` (2026), `height_in`, `weight_lb`
- Summary: `rookie_alpha_0_100`, class rank derived from export ordering
- Core scores: rookie alpha, RAS, production score, draft capital proxy
- Evidence metrics: same model features plus combine drill metrics (`forty`, `vertical`, `broad`)
- Tags: deterministic score-band tags derived from score thresholds

## Fields missing in current artifacts (hidden or N/A)

- School
- Age
- Position-specific advanced evidence metrics (e.g., target share, YPRR)
- Season-by-season stat lines
- Data-backed player comps

## What v2 would need

1. A richer processed artifact with player bio and school info.
2. Position-specific metric payloads from college stat pipelines.
3. Optional comps dataset (model-driven or scout-curated) to populate comp tiles honestly.
4. Season table rows in a normalized format for each player.
5. Optional app-framework integration (if this prototype is moved into the main TIBER product runtime).
