import { mapRookieToCard } from './mapRookieToCard.js';

let rookieCardsPromise = null;

async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`);
  }
  return response.json();
}

async function loadAllRookieCards() {
  const [alphaExport, combineRows, productionRows, draftRows] = await Promise.all([
    loadJson('/exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json'),
    loadJson('/data/raw/2026_combine_results.json'),
    loadJson('/data/processed/2026_college_production.json'),
    loadJson('/data/processed/2026_draft_capital_proxy.json'),
  ]);

  const combineById = new Map(combineRows.map((row) => [row.player_id, row]));
  const productionById = new Map(productionRows.map((row) => [row.player_id, row]));
  const draftById = new Map(draftRows.map((row) => [row.player_id, row]));

  return alphaExport.players.map((alphaPlayer, idx) =>
    mapRookieToCard({
      alphaPlayer,
      combineRow: combineById.get(alphaPlayer.player_id),
      productionRow: productionById.get(alphaPlayer.player_id),
      draftRow: draftById.get(alphaPlayer.player_id),
      rank: idx + 1,
    })
  );
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
