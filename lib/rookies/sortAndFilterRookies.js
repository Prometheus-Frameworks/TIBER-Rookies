const POSITION_ORDER = ['QB', 'RB', 'WR', 'TE'];

function comparePosition(a, b) {
  const left = POSITION_ORDER.indexOf(a.identity.position);
  const right = POSITION_ORDER.indexOf(b.identity.position);
  const leftIdx = left === -1 ? Number.MAX_SAFE_INTEGER : left;
  const rightIdx = right === -1 ? Number.MAX_SAFE_INTEGER : right;
  if (leftIdx !== rightIdx) return leftIdx - rightIdx;
  return a.identity.name.localeCompare(b.identity.name);
}

function compareGradeDesc(a, b) {
  const av = a.summary.rookieGrade ?? Number.NEGATIVE_INFINITY;
  const bv = b.summary.rookieGrade ?? Number.NEGATIVE_INFINITY;
  if (bv !== av) return bv - av;
  return (a.summary.classRank ?? Number.MAX_SAFE_INTEGER) - (b.summary.classRank ?? Number.MAX_SAFE_INTEGER);
}

export function sortAndFilterRookies(cards, { sort = 'grade', position = 'ALL', tag = 'ALL' } = {}) {
  const filtered = cards.filter((card) => {
    const matchesPosition = position === 'ALL' || card.identity.position === position;
    const matchesTag = tag === 'ALL' || (card.tags ?? []).includes(tag);
    return matchesPosition && matchesTag;
  });

  if (sort === 'position') {
    return [...filtered].sort(comparePosition);
  }
  return [...filtered].sort(compareGradeDesc);
}

export function collectGalleryFilters(cards) {
  const positions = [...new Set(cards.map((card) => card.identity.position).filter(Boolean))]
    .sort((a, b) => POSITION_ORDER.indexOf(a) - POSITION_ORDER.indexOf(b));

  const tags = [...new Set(cards.flatMap((card) => card.tags ?? []))].sort();

  return { positions, tags };
}
