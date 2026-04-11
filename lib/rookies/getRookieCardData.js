import { mapRookieToCard } from './mapRookieToCard.js';

let rookieCardsPromise = null;

const SEASONS = [2026, 2025, 2024, 2023, 2022];

async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`);
  }
  return response.json();
}

function keyByPlayerId(rows) {
  return new Map(rows.map((row) => [String(row.player_id ?? '').toLowerCase(), row]));
}

async function loadSeasonCards(season) {
  const alphaExport = await loadJson(
    `/exports/promoted/rookie-alpha/${season}_rookie_alpha_predraft_v0.json`,
  ).catch(() => null);

  if (!alphaExport) return [];

  const [combineRows, productionRows, draftRows, statsRows, pprRows, dynastyRows, trendRows] =
    await Promise.all([
      loadJson(`/data/raw/${season}_combine_results.json`).catch(() => []),
      loadJson(`/data/processed/${season}_college_production.json`).catch(() => []),
      loadJson(`/data/processed/${season}_draft_capital_proxy.json`).catch(() => []),
      loadJson(`/data/processed/${season}_player_stats.json`).catch(() => []),
      loadJson(`/data/processed/${season}_ppr_projections.json`).catch(() => []),
      loadJson(`/data/processed/${season}_dynasty_adp.json`).catch(() => []),
      loadJson(`/data/processed/${season}_yoy_trends.json`).catch(() => []),
    ]);

  const combineById = keyByPlayerId(combineRows);
  const productionById = keyByPlayerId(productionRows);
  const draftById = keyByPlayerId(draftRows);
  const statsById = keyByPlayerId(statsRows);
  const pprById = keyByPlayerId(pprRows);
  const dynastyById = keyByPlayerId(dynastyRows);
  const trendById = keyByPlayerId(trendRows);

  return alphaExport.players.map((alphaPlayer, idx) => {
    const playerId = String(alphaPlayer.player_id ?? '').toLowerCase();
    // Inject class_year so identity.classYear reflects the correct draft class
    const playerWithClass = alphaPlayer.class_year != null
      ? alphaPlayer
      : { ...alphaPlayer, class_year: season };
    return mapRookieToCard({
      alphaPlayer: playerWithClass,
      combineRow: combineById.get(playerId),
      productionRow: productionById.get(playerId),
      draftRow: draftById.get(playerId),
      statsRow: statsById.get(playerId),
      pprRow: pprById.get(playerId),
      dynastyRow: dynastyById.get(playerId),
      trendRow: trendById.get(playerId),
      rank: alphaPlayer.rookie_alpha_rank ?? idx + 1,
    });
  });
}

async function loadAllRookieCards() {
  const perSeasonArrays = await Promise.all(SEASONS.map(loadSeasonCards));
  return perSeasonArrays.flat();
}

export async function getAllRookieCards() {
  if (!rookieCardsPromise) {
    rookieCardsPromise = loadAllRookieCards();
  }
  return rookieCardsPromise;
}

export async function getRookieCardBySlug(slug) {
  const cards = await getAllRookieCards();
  return cards.find((card) => card.slug === slug) ?? null;
}
