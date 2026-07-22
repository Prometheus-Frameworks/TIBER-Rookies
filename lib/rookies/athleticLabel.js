// Single source of truth for athletic-source display labels across every rookie
// surface (card, board, compare). Keeping the mapping here prevents the surfaces
// from drifting — e.g. one treating RAS_PARTIAL as a full RAS while another
// labels it a partial composite.

/** @returns {'sporq'|'partial'|'ras'} */
export function athleticSourceCategory(source) {
  if (source === 'SPORQ') return 'sporq';
  if (source === 'COMBINE_FALLBACK' || source === 'RAS_PARTIAL') return 'partial';
  return 'ras';
}

/** Full metric label (card + compare radar). */
export function athleticMetricLabel(source) {
  const category = athleticSourceCategory(source);
  return category === 'sporq' ? 'ATH (SPORQ)' : category === 'partial' ? 'ATH (partial)' : 'RAS';
}

/** Compact chip label (board). */
export function athleticChipLabel(source) {
  const category = athleticSourceCategory(source);
  return category === 'sporq' ? 'SPORQ' : category === 'partial' ? 'ATH*' : 'RAS';
}

/** Chip tooltip (board). */
export function athleticChipTitle(source) {
  const category = athleticSourceCategory(source);
  return category === 'sporq'
    ? 'Athletic score (SPORQ composite)'
    : category === 'partial'
      ? 'Athletic score (partial composite)'
      : 'Relative Athletic Score';
}
