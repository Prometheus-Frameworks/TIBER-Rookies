const ROOKIE_SEASONS = [2026, 2025, 2024, 2023, 2022];

// Minimum season (inclusive) for which each supplement file exists.
// Fetches are skipped for seasons below these thresholds, eliminating
// guaranteed 404s for historical classes that will never have that data.
const SUPPLEMENT_FIRST_SEASON = {
  playerStats:     2024,
  pprProjections:  2026,
  dynastyAdp:      2026,
  yoyTrends:       2026,
  draftResults:    2022,
};

export function rookieAlphaExportPath(season) {
  return `/exports/promoted/rookie-alpha/${season}_rookie_alpha_predraft_v0.json`;
}

// Returns a path string for supplements that exist for the given season,
// or null when the file is known not to exist. Callers should skip null paths.
export function rookieDisplaySupplementPaths(season) {
  const has = (key) => season >= SUPPLEMENT_FIRST_SEASON[key];
  return {
    playerStats:    has('playerStats')    ? `/data/processed/${season}_player_stats.json`    : null,
    pprProjections: has('pprProjections') ? `/data/processed/${season}_ppr_projections.json` : null,
    dynastyAdp:     has('dynastyAdp')     ? `/data/processed/${season}_dynasty_adp.json`     : null,
    yoyTrends:      has('yoyTrends')      ? `/data/processed/${season}_yoy_trends.json`      : null,
    draftResults:   has('draftResults')   ? `/data/processed/${season}_draft_results.json`   : null,
  };
}

export function getRookieSeasons() {
  return [...ROOKIE_SEASONS];
}
