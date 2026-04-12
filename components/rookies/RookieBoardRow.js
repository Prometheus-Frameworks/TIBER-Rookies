import { getCollegeLogoUrl, getNflTeamLogoUrl } from '/lib/rookies/teamLogos.js';

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderTeamLogos(school, nflTeam, { size = 'sm' } = {}) {
  const cls = size === 'sm' ? 'team-logo team-logo-sm' : 'team-logo';
  const collegeUrl = getCollegeLogoUrl(school);
  const nflUrl = getNflTeamLogoUrl(nflTeam);
  if (!collegeUrl && !nflUrl) return '';
  const imgs = [
    collegeUrl ? `<img class="${cls}" src="${esc(collegeUrl)}" alt="${esc(school ?? '')}" loading="lazy" onerror="this.style.display='none'">` : '',
    nflUrl     ? `<img class="${cls}" src="${esc(nflUrl)}" alt="${esc(nflTeam ?? '')}" loading="lazy" onerror="this.style.display='none'">` : '',
  ].join('');
  return `<span class="team-logos">${imgs}</span>`;
}

const PPR_BAND_CLASS = {
  Elite: 'ppr-band-elite',
  Starter: 'ppr-band-starter',
  Contributor: 'ppr-band-contributor',
  Lottery: 'ppr-band-lottery',
};

/**
 * Renders a compact 3-bar SVG showing RAS / Production / Draft Capital (0–100).
 * Bars are colour-coded: RAS = steel blue, Production = teal, Draft = coral.
 */
function renderMiniScoreChart(row) {
  const bars = [
    { value: row.rasScore,          color: '#6B9FD4', label: 'R' },
    { value: row.productionScore,   color: '#4ECDC4', label: 'P' },
    { value: row.draftCapitalScore, color: '#E8853D', label: 'D' },
  ];

  const W = 54, H = 22, barW = 14, gap = 4;
  const svgBars = bars.map((bar, i) => {
    const x = i * (barW + gap);
    const pct = bar.value != null ? Math.max(0, Math.min(100, bar.value)) : 0;
    const barH = Math.max(2, Math.round((pct / 100) * H));
    const y = H - barH;
    const opacity = bar.value != null ? '1' : '0.25';
    return `<rect x="${x}" y="${y}" width="${barW}" height="${barH}" rx="2" fill="${bar.color}" opacity="${opacity}"/>`;
  }).join('');

  return `<svg class="mini-score-chart" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" aria-hidden="true">${svgBars}</svg>`;
}

function renderPprCell(row) {
  const proj = row.pprProjection;
  if (!proj) return '<div class="board-cell" data-label="PPR Range"><span class="ppr-na">—</span></div>';
  const bandClass = PPR_BAND_CLASS[proj.band] ?? 'ppr-band-lottery';
  return `
    <div class="board-cell board-ppr" data-label="PPR Range">
      <div class="ppr-range">${esc(proj.floor)}–${esc(proj.ceiling)}</div>
      <div class="ppr-band ${bandClass}">${esc(proj.band)}</div>
    </div>`;
}

function deltaSpan(delta, label) {
  if (delta == null) return `<span class="delta-row"><span class="delta-label">${label}</span><span class="delta-na">—</span></span>`;
  const abs = Math.abs(delta).toFixed(1);
  if (delta >= 10)  return `<span class="delta-row"><span class="delta-label">${label}</span><span class="delta-extreme-bull">+${abs} ↑↑</span></span>`;
  if (delta <= -10) return `<span class="delta-row"><span class="delta-label">${label}</span><span class="delta-extreme-bear">−${abs} ↓↓</span></span>`;
  if (delta >= 3)   return `<span class="delta-row"><span class="delta-label">${label}</span><span class="delta-bull">+${abs} ↑</span></span>`;
  if (delta <= -3)  return `<span class="delta-row"><span class="delta-label">${label}</span><span class="delta-bear">−${abs} ↓</span></span>`;
  return `<span class="delta-row"><span class="delta-label">${label}</span><span class="delta-neutral">${delta >= 0 ? '+' : ''}${delta.toFixed(1)}</span></span>`;
}

function deltaSpanInline(delta) {
  if (delta == null) return `<span class="delta-na">—</span>`;
  const abs = Math.abs(delta).toFixed(1);
  if (delta >= 10)  return `<span class="delta-extreme-bull">+${abs} ↑↑</span>`;
  if (delta <= -10) return `<span class="delta-extreme-bear">−${abs} ↓↓</span>`;
  if (delta >= 3)   return `<span class="delta-bull">+${abs} ↑</span>`;
  if (delta <= -3)  return `<span class="delta-bear">−${abs} ↓</span>`;
  return `<span class="delta-neutral">${delta >= 0 ? '+' : ''}${delta.toFixed(1)}</span>`;
}

function renderConsensusDeltaCell(row) {
  return `
    <div class="board-cell board-delta" data-label="Model Edge">
      ${deltaSpan(row.consensusDelta, 'NFL')}
      ${deltaSpan(row.dynastyDelta, 'DYN')}
    </div>`;
}

function renderVolumeTrend(row) {
  const t = row.volumeTrend;
  if (!t || t === 'neutral') return '';
  if (t === 'up')   return '<span class="vol-trend vol-up" title="Volume up vs 2024">↑</span>';
  if (t === 'down') return '<span class="vol-trend vol-down" title="Volume down vs 2024">↓</span>';
  return '';
}

function renderBreakoutBadge(row) {
  if (row.breakoutAge == null) return '';
  if (row.youngBreakoutFlag) {
    return `<span class="breakout-badge breakout-young">⚡ Age ${esc(row.breakoutAge)}</span>`;
  }
  return `<span class="breakout-badge breakout-late">Age ${esc(row.breakoutAge)}</span>`;
}

function renderEdgeOutlierBadge(row) {
  const d = row.consensusDelta;
  if (d == null) return '';
  if (d >= 10) {
    const abs = Math.abs(d).toFixed(1);
    return `<span class="edge-outlier-badge edge-outlier-badge-bull" title="Model edge: +${abs} above NFL consensus">▲ EDGE +${abs}</span>`;
  }
  if (d <= -10) {
    const abs = Math.abs(d).toFixed(1);
    return `<span class="edge-outlier-badge edge-outlier-badge-bear" title="Model edge: −${abs} below NFL consensus">▽ −${abs}</span>`;
  }
  return '';
}

const TIER_CSS = {
  tier_1: 'tier-elite',
  tier_2: 'tier-strong',
  tier_3: 'tier-mid',
  tier_4: 'tier-dart',
};

function renderPosBadge(position) {
  const pos = String(position ?? '').toUpperCase();
  const cls = ['QB','RB','WR','TE'].includes(pos) ? `pos-badge-${pos}` : '';
  return `<span class="pos-badge ${cls}">${esc(pos)}</span>`;
}

function renderMobileCard(row, { isQueued = false, queueAnnotation = null } = {}) {
  const rank = row.classRank == null ? 'N/A' : `#${row.classRank}`;
  const grade = row.rookieGrade == null ? 'N/A' : row.rookieGrade.toFixed(1);
  const slug = encodeURIComponent(String(row.slug ?? ''));
  const compareLeftHref = `/cards/rookies/compare/index.html?left=${slug}`;
  const compareRightHref = `/cards/rookies/compare/index.html?right=${slug}`;
  const queueTag = queueAnnotation?.queueTag ?? '';

  const identityParts = [
    row.position,
    row.school,
    row.draftClass ? String(row.draftClass) : null,
  ].filter(Boolean);

  const pprBand = row.pprProjection?.band ?? null;
  const pprRange = row.pprProjection
    ? `${esc(row.pprProjection.floor)}–${esc(row.pprProjection.ceiling)}`
    : null;

  return `
    <div class="board-mobile-card">
      <div class="bmc-header">
        <span class="bmc-rank board-num">${esc(rank)}</span>
        <span class="bmc-grade">Grade <strong class="bmc-grade-value">${esc(grade)}</strong></span>
      </div>
      <div class="bmc-name">
        ${renderTeamLogos(row.school, row.nflTeam)}
        <span class="board-player-name">${esc(row.name)}</span>
        ${renderBreakoutBadge(row)}
        ${renderEdgeOutlierBadge(row)}
      </div>
      <div class="bmc-meta">${esc(identityParts.join(' • '))}</div>
      <div class="bmc-thesis">${esc(row.profileSummary)}</div>
      <div class="bmc-pills">
        <span class="board-tier-pill">${esc(row.tier?.label ?? '')}</span>
        ${pprBand ? `<span class="ppr-band ${PPR_BAND_CLASS[pprBand] ?? 'ppr-band-lottery'}">${esc(pprBand)}</span>` : ''}
      </div>
      <div class="bmc-signals">
        ${row.draftCapitalScore != null ? `<span class="bmc-signal-chip bmc-signal-capital" title="Draft Capital">CAP ${Math.round(row.draftCapitalScore)}</span>` : ''}
        ${row.rasScore         != null ? `<span class="bmc-signal-chip bmc-signal-ras"     title="Relative Athletic Score">RAS ${Math.round(row.rasScore)}</span>` : ''}
        ${row.productionScore  != null ? `<span class="bmc-signal-chip bmc-signal-prod"    title="Production Score">PRD ${Math.round(row.productionScore)}</span>` : ''}
      </div>
      <div class="bmc-stats">
        <div class="bmc-stat-row">
          <span class="bmc-stat-label">NFL Edge</span>
          <span>${deltaSpanInline(row.consensusDelta)}</span>
        </div>
        <div class="bmc-stat-row">
          <span class="bmc-stat-label">Dyn Edge</span>
          <span>${deltaSpanInline(row.dynastyDelta)}</span>
        </div>
        ${pprRange ? `<div class="bmc-stat-row"><span class="bmc-stat-label">Range</span><span class="bmc-ppr-range">${pprRange} PPR</span></div>` : ''}
      </div>
      ${isQueued && queueTag ? `<div class="meta queue-inline-indicator" style="margin-bottom:6px">Queue tag: <span class="queue-tag-pill">${esc(queueTag)}</span></div>` : ''}
      <div class="bmc-actions-utility">
        <a class="nav-link" href="/cards/rookies/player.html?slug=${slug}">Detail</a>
        <a class="nav-link" href="${compareLeftHref}">Compare L</a>
        <a class="nav-link" href="${compareRightHref}">Compare R</a>
      </div>
      <button type="button" class="queue-toggle bmc-queue-btn ${isQueued ? 'is-queued' : ''}" data-queue-toggle="${esc(row.slug)}">${isQueued ? 'Queued ✓' : 'Add to queue'}</button>
    </div>
  `;
}

export function renderRookieBoardRow(row, { isQueued = false, queueAnnotation = null } = {}) {
  const rank = row.classRank == null ? 'N/A' : `#${row.classRank}`;
  const grade = row.rookieGrade == null ? 'N/A' : row.rookieGrade.toFixed(1);
  const slug = encodeURIComponent(String(row.slug ?? ''));
  const compareLeftHref = `/cards/rookies/compare/index.html?left=${slug}`;
  const compareRightHref = `/cards/rookies/compare/index.html?right=${slug}`;
  const queueTag = queueAnnotation?.queueTag ?? '';
  const tierCss = TIER_CSS[row.tier?.key] ?? 'tier-dart';

  return `
    <article class="board-row ${tierCss} ${isQueued ? 'board-row-queued' : ''}">
      ${renderMobileCard(row, { isQueued, queueAnnotation })}
      <div class="board-cell board-rank board-num" data-label="Rank">${esc(rank)}</div>
      <div class="board-cell board-player" data-label="Player">
        <div class="board-player-top">
          ${renderTeamLogos(row.school, row.nflTeam)}
          <span class="board-player-name">${esc(row.name)}</span>
          ${renderBreakoutBadge(row)}
          ${renderEdgeOutlierBadge(row)}
          ${renderMiniScoreChart(row)}
        </div>
        <div class="meta board-summary-line">${esc(row.profileSummary)}</div>
        ${isQueued && queueTag ? `<div class="meta queue-inline-indicator">Queue tag: <span class="queue-tag-pill">${esc(queueTag)}</span></div>` : ''}
      </div>
      <div class="board-cell" data-label="Position">${renderPosBadge(row.position)}</div>
      <div class="board-cell" data-label="School">${esc(row.school)}</div>
      <div class="board-cell board-grade board-num" data-label="Rookie Grade">${esc(grade)}${renderVolumeTrend(row)}</div>
      <div class="board-cell" data-label="Tier"><span class="board-tier-pill">${esc(row.tier.label)}</span></div>
      ${renderPprCell(row)}
      ${renderConsensusDeltaCell(row)}
      <div class="board-cell board-actions" data-label="Actions">
        <a class="nav-link" href="/cards/rookies/player.html?slug=${slug}">Detail</a>
        <a class="nav-link" href="${compareLeftHref}">Compare L</a>
        <a class="nav-link" href="${compareRightHref}">Compare R</a>
        <button type="button" class="queue-toggle ${isQueued ? 'is-queued' : ''}" data-queue-toggle="${esc(row.slug)}">${isQueued ? 'Queued ✓' : 'Add to queue'}</button>
      </div>
    </article>
  `;
}
