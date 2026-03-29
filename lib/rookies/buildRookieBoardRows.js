import { deriveRookieTier } from './deriveRookieTier.js';

function summarizeProfile(card) {
  return card.summary.profileSummary
    ?? card.summary.boardSummary
    ?? card.summary.archetype
    ?? card.summary.projection
    ?? card.tags?.[0]
    ?? 'Profile context limited by current artifacts';
}

export function buildRookieBoardRows(cards) {
  return cards.map((card) => {
    const rookieGrade = card.summary.rookieGrade;
    const tier = deriveRookieTier(rookieGrade);

    return {
      slug: card.slug,
      name: card.identity.name,
      position: card.identity.position ?? 'N/A',
      school: card.identity.schoolDisplay ?? card.identity.school ?? 'School unavailable in current artifacts',
      rookieGrade,
      classRank: card.summary.classRank,
      tier,
      profileSummary: summarizeProfile(card),
      tags: card.tags ?? [],
      translationFlags: card.translationFlags ?? [],
    };
  });
}

export function sortRookieBoard(rows, sort = 'grade') {
  const copy = [...rows];

  if (sort === 'rank') {
    return copy.sort((a, b) => (a.classRank ?? Number.MAX_SAFE_INTEGER) - (b.classRank ?? Number.MAX_SAFE_INTEGER));
  }

  if (sort === 'position') {
    return copy.sort((a, b) => {
      if (a.position !== b.position) return a.position.localeCompare(b.position);
      const bv = b.rookieGrade ?? Number.NEGATIVE_INFINITY;
      const av = a.rookieGrade ?? Number.NEGATIVE_INFINITY;
      if (bv !== av) return bv - av;
      return (a.classRank ?? Number.MAX_SAFE_INTEGER) - (b.classRank ?? Number.MAX_SAFE_INTEGER);
    });
  }

  return copy.sort((a, b) => {
    const bv = b.rookieGrade ?? Number.NEGATIVE_INFINITY;
    const av = a.rookieGrade ?? Number.NEGATIVE_INFINITY;
    if (bv !== av) return bv - av;
    return (a.classRank ?? Number.MAX_SAFE_INTEGER) - (b.classRank ?? Number.MAX_SAFE_INTEGER);
  });
}

export function filterRookieBoard(rows, { position = 'ALL' } = {}) {
  return rows.filter((row) => position === 'ALL' || row.position === position);
}
