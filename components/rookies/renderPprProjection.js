function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

const DATA_GAP_FALLBACK_NOTE = 'Projection has limited supporting data; treat floor/median/ceiling as low-confidence.';
const INSUFFICIENT_EVIDENCE_CAVEAT = 'Projection is grade-band based; limited evidence context applies.';

export function renderPprProjection(ppr, card) {
  if (!ppr) return '';
  const bandClass = { Elite: 'ppr-band-elite', Starter: 'ppr-band-starter', Contributor: 'ppr-band-contributor', Lottery: 'ppr-band-lottery' }[ppr.band] ?? 'ppr-band-lottery';
  const floor = Number(ppr.floor);
  const median = Number(ppr.median);
  const ceiling = Number(ppr.ceiling);
  const hasRange = Number.isFinite(floor) && Number.isFinite(median) && Number.isFinite(ceiling) && ceiling >= floor;
  const maxForScale = hasRange
    ? Math.max(1, Math.ceil(Math.max(floor, median, ceiling) / 25) * 25)
    : 1;
  const rangeLeft = hasRange ? Math.max(0, Math.min(100, (floor / maxForScale) * 100)) : 0;
  const rangeWidth = hasRange ? Math.max(0, Math.min(100 - rangeLeft, ((ceiling - floor) / maxForScale) * 100)) : 0;
  const medianLeft = hasRange ? Math.max(0, Math.min(100, (median / maxForScale) * 100)) : 0;
  const dataGapWarning = ppr.dataGapFlag === true
    ? `<div class="ppr-data-gap-warning" role="alert">⚠️ ${esc(ppr.dataGapNote || DATA_GAP_FALLBACK_NOTE)}</div>`
    : '';
  const evidenceCaveat = card?.evidenceTier === 'insufficient_evidence'
    ? `<div class="ppr-evidence-caveat">${esc(INSUFFICIENT_EVIDENCE_CAVEAT)}</div>`
    : '';
  return `
    <div class="ppr-card-section">
      <div class="section-title">Year 1 PPR Projection</div>
      ${dataGapWarning}
      <div class="ppr-card-row">
        <div class="ppr-card-stat"><div class="ppr-stat-label">Floor</div><div class="ppr-stat-value">${esc(ppr.floor)}</div></div>
        <div class="ppr-card-stat ppr-median"><div class="ppr-stat-label">Median</div><div class="ppr-stat-value ppr-median-value">${esc(ppr.median)}</div></div>
        <div class="ppr-card-stat"><div class="ppr-stat-label">Ceiling</div><div class="ppr-stat-value">${esc(ppr.ceiling)}</div></div>
        <div class="ppr-card-band"><span class="ppr-band ${bandClass}">${esc(ppr.band)}</span></div>
      </div>
      <div class="ppr-range-viz">
        <div class="ppr-range-track">
          ${hasRange ? `<div class="ppr-range-fill" style="left:${rangeLeft}%; width:${rangeWidth}%"></div>
          <div class="ppr-range-median-marker" style="left:${medianLeft}%" aria-label="Median projection marker"></div>` : ''}
        </div>
      </div>
      ${evidenceCaveat}
    </div>`;
}
