import { mapRookieToCard } from './mapRookieToCard.js';
import { keyByPlayerId as keyDraftResultsByPlayerId } from './draftResults.js';
import {
  getRookieSeasons,
  rookieAlphaExportPath,
  rookieDisplaySupplementPaths,
  rookieTransitionProfilePath,
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
  const transitionProfilePath = rookieTransitionProfilePath(season);
  const loadOrSkip = (path) => path ? loadJson(path).catch(() => []) : Promise.resolve([]);
  const [statsRows, pprRows, dynastyRows, trendRows, draftResultRows, transitionProfile] = await Promise.all([
    loadOrSkip(supplementPaths.playerStats),
    loadOrSkip(supplementPaths.pprProjections),
    loadOrSkip(supplementPaths.dynastyAdp),
    loadOrSkip(supplementPaths.yoyTrends),
    loadOrSkip(supplementPaths.draftResults),
    transitionProfilePath ? loadJson(transitionProfilePath).catch(() => null) : Promise.resolve(null),
  ]);

  const statsById = keyByPlayerId(statsRows);
  const pprById = keyByPlayerId(pprRows);
  const dynastyById = keyByPlayerId(dynastyRows);
  const trendById = keyByPlayerId(trendRows);
  const draftResultsById = keyDraftResultsByPlayerId(Array.isArray(draftResultRows) ? draftResultRows : []);
  const transitionProfileRows = Array.isArray(transitionProfile?.rows) ? transitionProfile.rows : [];
  const transitionProfileById = keyByPlayerId(transitionProfileRows);
  // Distinguish "no governed artifact by design" (pre-2026 classes) from an
  // artifact that was expected but failed to load. On load failure we fail
  // closed rather than silently substituting the ungoverned draft-results
  // supplement for governed official facts.
  const transitionProfileStatus = transitionProfilePath == null
    ? 'not_expected'
    : (transitionProfile && Array.isArray(transitionProfile.rows) ? 'loaded' : 'load_failed');
  // Frozen pre-draft baseline provenance, disclosed on the card so the Alpha
  // reads as a dated snapshot rather than a live rating.
  const alphaModel = alphaExport.model ?? null;
  const alphaGeneratedAt = alphaExport.generated_at ?? null;

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
      draftResultRow: draftResultsById.get(playerId) ?? null,
      transitionProfileRow: transitionProfileById.get(playerId) ?? null,
      transitionProfileStatus,
      alphaModel,
      alphaGeneratedAt,
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
