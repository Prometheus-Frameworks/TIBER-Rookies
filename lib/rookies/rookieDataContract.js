const ROOKIE_SEASONS = [2026, 2025, 2024, 2023, 2022];
const WATCHLIST_SEASONS = [2027];

export function rookieAlphaExportPath(season) {
  return `/exports/promoted/rookie-alpha/${season}_rookie_alpha_predraft_v0.json`;
}

export function rookieWatchlistPath(season) {
  return `/data/raw/${season}_watchlist_seed.json`;
}

export function rookieDisplaySupplementPaths(season) {
  return {
    playerStats: `/data/processed/${season}_player_stats.json`,
    pprProjections: `/data/processed/${season}_ppr_projections.json`,
    dynastyAdp: `/data/processed/${season}_dynasty_adp.json`,
    yoyTrends: `/data/processed/${season}_yoy_trends.json`,
    draftResults: `/data/processed/${season}_draft_results.json`,
  };
}

export function getRookieSeasons() {
  return [...ROOKIE_SEASONS];
}

export function getWatchlistSeasons() {
  return [...WATCHLIST_SEASONS];
}
