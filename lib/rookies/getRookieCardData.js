import { mapRookieToCard } from './mapRookieToCard.js';
import {
  getRookieSeasons,
  rookieAlphaExportPath,
  rookieDisplaySupplementPaths,
} from './rookieDataContract.js';

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

async function loadSeasonCards(season) {
  const alphaExport = await loadJson(rookieAlphaExportPath(season)).catch(() => null);
  if (!alphaExport || !Array.isArray(alphaExport.players)) return [];

  const supplementPaths = rookieDisplaySupplementPaths(season);
  const [statsRows, pprRows, dynastyRows, trendRows] = await Promise.all([
    loadJson(supplementPaths.playerStats).catch(() => []),
    loadJson(supplementPaths.pprProjections).catch(() => []),
    loadJson(supplementPaths.dynastyAdp).catch(() => []),
    loadJson(supplementPaths.yoyTrends).catch(() => []),
  ]);

  const statsById = keyByPlayerId(statsRows);
  const pprById = keyByPlayerId(pprRows);
  const dynastyById = keyByPlayerId(dynastyRows);
  const trendById = keyByPlayerId(trendRows);

  return alphaExport.players.map((alphaPlayer, idx) => {
    const playerId = String(alphaPlayer.player_id ?? '').toLowerCase();
    const playerWithClass = alphaPlayer?.context?.class_year != null
      ? alphaPlayer
      : {
        ...alphaPlayer,
        context: {
          ...(alphaPlayer?.context ?? {}),
          class_year: season,
        },
      };

    return mapRookieToCard({
      alphaPlayer: playerWithClass,
      statsRow: statsById.get(playerId),
      pprRow: pprById.get(playerId),
      dynastyRow: dynastyById.get(playerId),
      trendRow: trendById.get(playerId),
      rank: alphaPlayer.rookie_alpha_rank ?? idx + 1,
    });
  });
}

async function loadAllRookieCards() {
  const perSeasonArrays = await Promise.all(getRookieSeasons().map(loadSeasonCards));
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
