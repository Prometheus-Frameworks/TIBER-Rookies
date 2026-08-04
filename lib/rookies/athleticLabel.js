// Single source of truth for athletic-source display labels across every rookie
// surface (card, board, compare). Keeping the mapping here prevents the surfaces
// from drifting — e.g. one treating RAS_PARTIAL as a full RAS while another
// labels it a partial composite.

/** @returns {'sporq'|'partial'|'neutral'|'ras'} */
export function athleticSourceCategory(source) {
  if (source === 'SPORQ') return 'sporq';
  if (source === 'COMBINE_FALLBACK' || source === 'RAS_PARTIAL') return 'partial';
  if (source === 'NEUTRAL_DEFAULT') return 'neutral';
  return 'ras';
}

/** Full metric label (card + compare radar). */
export function athleticMetricLabel(source) {
  const category = athleticSourceCategory(source);
  if (category === 'sporq') return 'ATH (SPORQ)';
  if (category === 'partial') return 'ATH (partial)';
  if (category === 'neutral') return 'ATH prior';
  return 'RAS';
}

/** Compact chip label (board). */
export function athleticChipLabel(source) {
  const category = athleticSourceCategory(source);
  if (category === 'sporq') return 'SPORQ';
  if (category === 'partial') return 'ATH*';
  if (category === 'neutral') return 'ATH prior';
  return 'RAS';
}

/** Chip tooltip (board). */
export function athleticChipTitle(source) {
  const category = athleticSourceCategory(source);
  if (category === 'sporq') return 'Athletic score (SPORQ composite)';
  if (category === 'partial') return 'Athletic score (partial composite)';
  if (category === 'neutral') return 'Neutral athletic model prior; no observed testing available';
  return 'Relative Athletic Score';
}

/** Whether the source represents observed athletic evidence. */
export function hasObservedAthleticEvidence(source) {
  return source != null && athleticSourceCategory(source) !== 'neutral';
}
