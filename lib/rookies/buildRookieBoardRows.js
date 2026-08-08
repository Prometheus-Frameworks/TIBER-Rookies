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
    // Tier from the frozen pre-draft Alpha; no client-invented post-draft grade.
    const tier = deriveRookieTier(rookieGrade);

    return {
      playerId: card.playerId,
      slug: card.slug,
      name: card.identity.name,
      position: card.identity.position ?? 'N/A',
      school: card.identity.schoolDisplay ?? card.identity.school ?? 'School unavailable in current artifacts',
      nflTeam: card.identity.nflTeam ?? null,
      draftClass: card.identity.classYear ?? null,
      rookieGrade,
      preDraftGrade: card.preDraftGrade ?? rookieGrade ?? null,
      preDraftRank: card.preDraftRank ?? card.summary.classRank ?? null,
      postDraftStatus: card.postDraftStatus ?? 'not_yet_published',
      classRank: card.summary.classRank,
      tier,
      profileSummary: summarizeProfile(card),
      tags: card.tags ?? [],
      translationFlags: card.translationFlags ?? [],
      pprProjection: card.pprProjection ?? null,
      consensusDelta: card.consensusDelta ?? null,
      evidenceTier: card.evidenceTier ?? null,
      evidenceTierReason: card.evidenceTierReason ?? null,
      isCappedDisagreement: card.isCappedDisagreement ?? null,
      dynastyDelta: card.dynastyDelta ?? null,
      volumeTrend: card.volumeTrend ?? null,
      efficiencyTrend: card.efficiencyTrend ?? null,
      breakoutAge: card.breakoutAge ?? null,
      youngBreakoutFlag: card.youngBreakoutFlag ?? false,
      breakoutAgeRating: card.breakoutAgeRating ?? null,
      breakoutLabel: card.breakoutLabel ?? null,
      athleticScore: card.athleticScore ?? null,
      athleticSource: card.athleticSource ?? null,
      productionScore: card.productionScore ?? null,
      draftCapitalScore: card.draftCapitalScore ?? null,
    };
  });
}

export function sortRookieBoard(rows, sort = 'grade') {
  const copy = [...rows];
  const boardGrade = (row) => row.rookieGrade ?? Number.NEGATIVE_INFINITY;

  if (sort === 'rank') {
    return copy.sort((a, b) => (a.classRank ?? Number.MAX_SAFE_INTEGER) - (b.classRank ?? Number.MAX_SAFE_INTEGER));
  }

  if (sort === 'position') {
    return copy.sort((a, b) => {
      if (a.position !== b.position) return a.position.localeCompare(b.position);
      const bv = boardGrade(b);
      const av = boardGrade(a);
      if (bv !== av) return bv - av;
      return (a.classRank ?? Number.MAX_SAFE_INTEGER) - (b.classRank ?? Number.MAX_SAFE_INTEGER);
    });
  }

  if (sort === 'edge') {
    return copy.sort((a, b) => {
      const av = a.consensusDelta ?? Number.NEGATIVE_INFINITY;
      const bv = b.consensusDelta ?? Number.NEGATIVE_INFINITY;
      if (bv !== av) return bv - av;
      const ag = boardGrade(a);
      const bg = boardGrade(b);
      return bg - ag;
    });
  }

  return copy.sort((a, b) => {
    const bv = boardGrade(b);
    const av = boardGrade(a);
    if (bv !== av) return bv - av;
    return (a.classRank ?? Number.MAX_SAFE_INTEGER) - (b.classRank ?? Number.MAX_SAFE_INTEGER);
  });
}

export function filterRookieBoard(rows, { position = 'ALL', draftClass = 'ALL', nameFilter = '' } = {}) {
  const nameLower = nameFilter.toLowerCase().trim();
  return rows.filter(
    (row) =>
      (position === 'ALL' || row.position === position) &&
      (draftClass === 'ALL' || String(row.draftClass) === String(draftClass)) &&
      (!nameLower || row.name.toLowerCase().includes(nameLower)),
  );
}
