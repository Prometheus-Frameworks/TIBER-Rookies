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
      nflTeam: card.identity.nflTeam ?? null,
      draftClass: card.identity.classYear ?? null,
      rookieGrade,
      classRank: card.summary.classRank,
      tier,
      profileSummary: summarizeProfile(card),
      tags: card.tags ?? [],
      translationFlags: card.translationFlags ?? [],
      pprProjection: card.pprProjection ?? null,
      consensusDelta: card.consensusDelta ?? null,
      dynastyDelta: card.dynastyDelta ?? null,
      volumeTrend: card.volumeTrend ?? null,
      efficiencyTrend: card.efficiencyTrend ?? null,
      breakoutAge: card.breakoutAge ?? null,
      youngBreakoutFlag: card.youngBreakoutFlag ?? false,
      rasScore: card.scores[1]?.value ?? null,
      productionScore: card.scores[2]?.value ?? null,
      draftCapitalScore: card.scores[3]?.value ?? null,
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

  if (sort === 'edge') {
    return copy.sort((a, b) => {
      const av = a.consensusDelta ?? Number.NEGATIVE_INFINITY;
      const bv = b.consensusDelta ?? Number.NEGATIVE_INFINITY;
      if (bv !== av) return bv - av;
      const ag = a.rookieGrade ?? Number.NEGATIVE_INFINITY;
      const bg = b.rookieGrade ?? Number.NEGATIVE_INFINITY;
      return bg - ag;
    });
  }

  return copy.sort((a, b) => {
    const bv = b.rookieGrade ?? Number.NEGATIVE_INFINITY;
    const av = a.rookieGrade ?? Number.NEGATIVE_INFINITY;
    if (bv !== av) return bv - av;
    return (a.classRank ?? Number.MAX_SAFE_INTEGER) - (b.classRank ?? Number.MAX_SAFE_INTEGER);
  });
}

export function filterRookieBoard(rows, { position = 'ALL', draftClass = 'ALL' } = {}) {
  return rows.filter(
    (row) =>
      (position === 'ALL' || row.position === position) &&
      (draftClass === 'ALL' || String(row.draftClass) === String(draftClass)),
  );
}
