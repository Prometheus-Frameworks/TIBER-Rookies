import { mapRookieToCard } from './mapRookieToCard.js';

let rookieCardsPromise = null;

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

async function loadAllRookieCards() {
  const [alphaExport, combineRows, productionRows, draftRows, statsRows] = await Promise.all([
    loadJson('/exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json'),
    loadJson('/data/raw/2026_combine_results.json'),
    loadJson('/data/processed/2026_college_production.json'),
    loadJson('/data/processed/2026_draft_capital_proxy.json'),
    loadJson('/data/processed/2026_player_stats.json'),
  ]);

  const combineById = keyByPlayerId(combineRows);
  const productionById = keyByPlayerId(productionRows);
  const draftById = keyByPlayerId(draftRows);
  const statsById = keyByPlayerId(statsRows);

  return alphaExport.players.map((alphaPlayer, idx) => {
    const playerId = String(alphaPlayer.player_id ?? '').toLowerCase();
    return mapRookieToCard({
      alphaPlayer,
      combineRow: combineById.get(playerId),
      productionRow: productionById.get(playerId),
      draftRow: draftById.get(playerId),
      statsRow: statsById.get(playerId),
      rank: alphaPlayer.rookie_alpha_rank ?? idx + 1,
    });
  });
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
