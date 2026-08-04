function finiteProjectionRange(projection) {
  if (!projection || projection.stale === true) return null;
  const floor = Number(projection.floor);
  const median = Number(projection.median);
  const ceiling = Number(projection.ceiling);
  if (![floor, median, ceiling].every(Number.isFinite) || ceiling < floor) return null;
  return { floor, median, ceiling };
}

export function sharedPprScaleMax(...projections) {
  const ranges = projections.map(finiteProjectionRange).filter(Boolean);
  if (!ranges.length) return null;
  const maximum = Math.max(...ranges.flatMap((range) => [range.floor, range.median, range.ceiling]));
  return Math.max(25, Math.ceil(maximum / 25) * 25);
}

export function projectionTrackPercentages(projection, scaleMaximum) {
  const range = finiteProjectionRange(projection);
  const scale = Number(scaleMaximum);
  if (!range || !Number.isFinite(scale) || scale <= 0) return null;
  const rangeLeft = Math.max(0, Math.min(100, (range.floor / scale) * 100));
  const rangeWidth = Math.max(0, Math.min(100 - rangeLeft, ((range.ceiling - range.floor) / scale) * 100));
  const medianLeft = Math.max(0, Math.min(100, (range.median / scale) * 100));
  return { rangeLeft, rangeWidth, medianLeft };
}

export function observedEvidenceReadiness(card) {
  const metrics = Array.isArray(card?.metrics) ? card.metrics : [];
  const eligibleMetricSlots = metrics.filter((metric) => metric?.label !== 'ATH prior');
  const availableMetricSlots = eligibleMetricSlots.filter(
    (metric) => metric?.value != null && metric?.display != null,
  );
  const productionContextSlots = [card?.ageAdjustedProduction, card?.breakoutAgeRating];
  const availableProductionContext = productionContextSlots.filter(
    (value) => value != null && Number.isFinite(Number(value)),
  ).length;
  const availableCount = availableMetricSlots.length + availableProductionContext;
  const totalCount = eligibleMetricSlots.length + productionContextSlots.length;
  const neutralPriorNote = card?.athleticSource === 'NEUTRAL_DEFAULT'
    ? ' ATH prior is disclosed separately and does not count as observed testing.'
    : '';

  return {
    availableCount,
    totalCount,
    label: `Observed evidence represented: ${availableCount}/${totalCount} rows.${neutralPriorNote}`,
  };
}

export function neutralAthleticPriorDisclosure(card) {
  if (card?.athleticSource !== 'NEUTRAL_DEFAULT') return null;
  const numeric = Number(card?.athleticScore);
  const value = Number.isFinite(numeric) ? ` (${numeric.toFixed(1)})` : '';
  return `ATH prior${value} is a neutral model default that contributes to the frozen Rookie Alpha; no observed athletic testing is available.`;
}

export const CARD_RADAR_VIEWBOX = '-55 -44 310 268';
