const STORAGE_KEY = 'tiber-conviction-board-v1';
const INITIAL_RATING = 1000;
const K_FACTOR = 32;

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

function loadConvictionBoard() {
  if (!canUseStorage()) return { ratings: {}, history: [] };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ratings: {}, history: [] };
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return { ratings: {}, history: [] };
    return {
      ratings: parsed.ratings && typeof parsed.ratings === 'object' ? parsed.ratings : {},
      history: Array.isArray(parsed.history) ? parsed.history : [],
    };
  } catch {
    return { ratings: {}, history: [] };
  }
}

function persistConvictionBoard(board) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(board));
}

export function getConvictionRating(slug) {
  return loadConvictionBoard().ratings[String(slug)] ?? INITIAL_RATING;
}

export function getVoteCount() {
  return loadConvictionBoard().history.length;
}

export function recordMatchupResult(winnerSlug, loserSlug) {
  const board = loadConvictionBoard();
  const rA = board.ratings[String(winnerSlug)] ?? INITIAL_RATING;
  const rB = board.ratings[String(loserSlug)] ?? INITIAL_RATING;
  const eA = 1 / (1 + Math.pow(10, (rB - rA) / 400));
  const eB = 1 - eA;

  board.ratings[String(winnerSlug)] = Math.round(rA + K_FACTOR * (1 - eA));
  board.ratings[String(loserSlug)] = Math.round(rB + K_FACTOR * (0 - eB));
  board.history.push({ winner: String(winnerSlug), loser: String(loserSlug), ts: Date.now() });

  persistConvictionBoard(board);
}

// Seed a matchup: same position, prefer similarly-rated pairs not seen recently.
export function seedMatchup(cards, position) {
  const pool = cards.filter((c) => c.identity.position === position);
  if (pool.length < 2) return null;

  const board = loadConvictionBoard();
  const recentPairs = new Set(
    board.history.slice(-10).map((h) => [h.winner, h.loser].sort().join('|'))
  );

  // Sort by current ELO so adjacent entries are similarly-rated
  const sorted = [...pool].sort((a, b) => {
    const rA = board.ratings[a.slug] ?? INITIAL_RATING;
    const rB = board.ratings[b.slug] ?? INITIAL_RATING;
    return rB - rA;
  });

  // Find the nearest ELO pair not shown recently
  for (let i = 0; i < sorted.length - 1; i++) {
    for (let j = i + 1; j < Math.min(i + 4, sorted.length); j++) {
      const pairKey = [sorted[i].slug, sorted[j].slug].sort().join('|');
      if (!recentPairs.has(pairKey)) {
        const pair = [sorted[i], sorted[j]];
        return Math.random() < 0.5 ? pair : [pair[1], pair[0]];
      }
    }
  }

  // Fallback: random pair
  const shuffled = [...pool].sort(() => Math.random() - 0.5);
  return [shuffled[0], shuffled[1]];
}

export function resetConvictionBoard() {
  if (!canUseStorage()) return;
  window.localStorage.removeItem(STORAGE_KEY);
}
