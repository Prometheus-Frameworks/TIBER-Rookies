import { getRookieCardLoadState } from './getRookieCardData.js';
import { get2026RookieStubs, findRookieStubBySlug } from './rookieStubs.js';

export async function getRookieShellState() {
  const [alpha, stubResult] = await Promise.all([
    getRookieCardLoadState(),
    get2026RookieStubs().then(
      (rows) => ({ status: 'loaded', rows }),
      (error) => ({ status: 'load_failed', rows: [], error: String(error.message ?? error) }),
    ),
  ]);
  return buildRookieShellState(alpha, stubResult);
}

export function buildRookieShellState(alpha, stubResult) {
  const stubs = stubResult.rows;
  const stubIds = new Set(stubs.map((stub) => stub.playerId));
  // No independently valid membership evidence means no affected 2026 score,
  // rank, compare or queue action. Never interpret a failed stub load as [].
  const cards = alpha.cards.filter((card) => String(card.identity.classYear) !== '2026'
    || (stubResult.status === 'loaded' && !stubIds.has(card.playerId)));
  return { cards, stubs, seasons: alpha.seasons, stubStatus: stubResult.status };
}

export function rookieLoadMessage(state, season = 'ALL') {
  const relevant = state.seasons.filter((result) => season === 'ALL' || String(result.season) === String(season));
  const failed = relevant.filter((result) => result.status === 'load_failed').map((result) => result.season);
  const partial = relevant.filter((result) => result.status === 'partial').map((result) => result.season);
  const messages = [];
  if (failed.length) messages.push(`Rookie Alpha unavailable for ${failed.join(', ')}; class coverage is incomplete.`);
  if (partial.length) messages.push(`Supplementary evidence unavailable for ${partial.join(', ')}; supported cards remain visible.`);
  if ((season === 'ALL' || String(season) === '2026') && state.stubStatus !== 'loaded') {
    messages.push('2026 stub coverage unavailable; affected scores, ranks and actions are withheld.');
  }
  return messages.join(' ');
}

export function selectRookiePlayer(state, slug) {
  const stub = slug ? findRookieStubBySlug(state.stubs, slug) : null;
  if (stub) return { status: 'unscored', stub };
  const card = slug ? state.cards.find((candidate) => candidate.slug === slug) : state.cards[0];
  if (card) return { status: 'scored', card };
  const incomplete = state.stubStatus !== 'loaded' || state.seasons.some((result) => result.status === 'load_failed');
  if (incomplete) return { status: 'unavailable', message: 'Player coverage unavailable. Missing sources may contain this player; no score or absence can be confirmed.' };
  if (!slug && state.stubs.length) return { status: 'unscored', stub: state.stubs[0] };
  return { status: slug ? 'not_found' : 'empty', message: slug
    ? 'No player matches this link in the successfully loaded rookie sources.'
    : 'The successfully loaded rookie sources contain no players.' };
}
