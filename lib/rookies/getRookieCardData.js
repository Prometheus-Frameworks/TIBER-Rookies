import { mapRookieToCard } from './mapRookieToCard.js';
import { getRookieStubLoadState, filterRookieCardsByStubCoverage } from './rookieStubs.js';
import { keyByPlayerId as keyDraftResultsByPlayerId } from './draftResults.js';
import {
  getRookieSeasons,
  rookieAlphaExportPath,
  rookieDisplaySupplementPaths,
  rookieTransitionProfilePath,
  isValidTransitionProfileEnvelope,
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
  const sources = [];
  const loadSource = async (path, valid) => {
    if (!path) return null;
    try {
      const payload = await loadJson(path);
      if (!valid(payload)) throw new Error('Malformed source envelope or rows.');
      sources.push({ path, status: 'loaded' });
      return payload;
    } catch (error) {
      sources.push({ path, status: 'load_failed', error: String(error.message ?? error) });
      return null;
    }
  };
  const validRows = (rows) => Array.isArray(rows) && rows.every((row) =>
    row && typeof row === 'object' && !Array.isArray(row)
    && typeof row.player_id === 'string' && row.player_id.trim());
  const alphaExport = await loadSource(rookieAlphaExportPath(season), (payload) =>
    validRows(payload?.players) && payload.players.every((row) =>
      // Match the existing stub identity convention before constructing cards.
      // Slug normalization must never let a different raw ID evade precedence.
      row.player_id === row.player_id.trim().toLowerCase()
      && (row.context?.class_year == null || String(row.context.class_year) === String(season))));
  if (!alphaExport) return { season, status: 'load_failed', cards: [], sources };

  const supplementPaths = rookieDisplaySupplementPaths(season);
  const transitionProfilePath = rookieTransitionProfilePath(season);
  const loadOrSkip = async (path) => (await loadSource(path, validRows)) ?? [];
  const [statsRows, pprRows, dynastyRows, trendRows, draftResultRows, transitionProfile] = await Promise.all([
    loadOrSkip(supplementPaths.playerStats),
    loadOrSkip(supplementPaths.pprProjections),
    loadOrSkip(supplementPaths.dynastyAdp),
    loadOrSkip(supplementPaths.yoyTrends),
    loadOrSkip(supplementPaths.draftResults),
    loadSource(transitionProfilePath, (payload) => isValidTransitionProfileEnvelope(payload, season) && validRows(payload.rows)),
  ]);

  const statsById = keyByPlayerId(statsRows);
  const pprById = keyByPlayerId(pprRows);
  const dynastyById = keyByPlayerId(dynastyRows);
  const trendById = keyByPlayerId(trendRows);
  const draftResultsById = keyDraftResultsByPlayerId(Array.isArray(draftResultRows) ? draftResultRows : []);
  // Distinguish "no governed artifact by design" (pre-2026 classes) from an
  // artifact that was expected but failed to load or is malformed. Validate the
  // envelope (schema family, season, rows) before treating it as loaded; on
  // failure we fail closed rather than silently substituting the ungoverned
  // draft-results supplement for governed official facts.
  const transitionProfileValid = transitionProfilePath != null
    && isValidTransitionProfileEnvelope(transitionProfile, season);
  const transitionProfileStatus = transitionProfilePath == null
    ? 'not_expected'
    : (transitionProfileValid ? 'loaded' : 'load_failed');
  const transitionProfileRows = transitionProfileValid ? transitionProfile.rows : [];
  const transitionProfileById = keyByPlayerId(transitionProfileRows);
  const transitionProfileVersion = transitionProfileValid ? transitionProfile.schema_version : null;
  // Frozen pre-draft baseline provenance, disclosed on the card so the Alpha
  // reads as a dated snapshot rather than a live rating.
  const alphaModel = alphaExport.model ?? null;
  const alphaGeneratedAt = alphaExport.generated_at ?? null;

  const cards = alphaExport.players.map((alphaPlayer, idx) => {
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
      transitionProfileVersion,
      alphaModel,
      alphaGeneratedAt,
      rank: alphaPlayer.rookie_alpha_rank ?? idx + 1,
    });
  });
  return { season, cards, sources, status: sources.some((source) => source.status === 'load_failed')
    ? 'partial' : (cards.length ? 'loaded' : 'empty') };
}

async function loadAllRookieCards() {
  const seasons = await Promise.all(getRookieSeasons().map(async (season) => {
    try { return await loadSeasonCards(season); }
    catch (error) {
      return { season, status: 'load_failed', cards: [], sources: [
        { path: rookieAlphaExportPath(season), status: 'load_failed', error: String(error.message ?? error) },
      ] };
    }
  }));
  return { cards: seasons.flatMap((result) => result.cards), seasons };
}

export async function getRookieCardLoadState() {
  if (!rookieCardsPromise) rookieCardsPromise = loadAllRookieCards();
  return rookieCardsPromise;
}

// Preserve the array API used by Gallery, Compare and Swipe.
export async function getAllRookieCards() {
  const [alpha, stubResult] = await Promise.all([getRookieCardLoadState(), getRookieStubLoadState()]);
  return filterRookieCardsByStubCoverage(alpha.cards, stubResult);
}

export async function getRookieCardBySlug(slug) {
  const cards = await getAllRookieCards();
  return cards.find((card) => card.slug === slug) ?? null;
}
