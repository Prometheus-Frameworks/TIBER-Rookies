function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

const PPR_BAND_CLASS = {
  Elite: 'ppr-band-elite',
  Starter: 'ppr-band-starter',
  Contributor: 'ppr-band-contributor',
  Lottery: 'ppr-band-lottery',
};

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

function renderConsensusDeltaCell(row) {
  const delta = row.consensusDelta;
  if (delta == null) {
    return '<div class="board-cell board-delta" data-label="Model Edge"><span class="delta-na">—</span></div>';
  }
  const abs = Math.abs(delta).toFixed(1);
  if (delta >= 3) {
    return `<div class="board-cell board-delta" data-label="Model Edge"><span class="delta-bull">+${abs} ↑</span></div>`;
  }
  if (delta <= -3) {
    return `<div class="board-cell board-delta" data-label="Model Edge"><span class="delta-bear">−${abs} ↓</span></div>`;
  }
  return `<div class="board-cell board-delta" data-label="Model Edge"><span class="delta-neutral">${delta >= 0 ? '+' : ''}${delta.toFixed(1)}</span></div>`;
}

function renderBreakoutBadge(row) {
  if (row.breakoutAge == null) return '';
  if (row.youngBreakoutFlag) {
    return `<span class="breakout-badge breakout-young">⚡ Age ${esc(row.breakoutAge)}</span>`;
  }
  return `<span class="breakout-badge breakout-late">Age ${esc(row.breakoutAge)}</span>`;
}

export function renderRookieBoardRow(row, { isQueued = false, queueAnnotation = null } = {}) {
  const rank = row.classRank == null ? 'N/A' : `#${row.classRank}`;
  const grade = row.rookieGrade == null ? 'N/A' : row.rookieGrade.toFixed(1);
  const slug = encodeURIComponent(String(row.slug ?? ''));
  const compareLeftHref = `/cards/rookies/compare/index.html?left=${slug}`;
  const compareRightHref = `/cards/rookies/compare/index.html?right=${slug}`;
  const queueTag = queueAnnotation?.queueTag ?? '';
  const translationPills = (row.translationFlags ?? []).slice(0, 3);

  return `
    <article class="board-row ${isQueued ? 'board-row-queued' : ''}">
      <div class="board-cell board-rank" data-label="Rank">${esc(rank)}</div>
      <div class="board-cell board-player" data-label="Player">
        <div class="board-player-name">${esc(row.name)} ${renderBreakoutBadge(row)}</div>
        <div class="meta">${esc(row.profileSummary)}</div>
        ${translationPills.length ? `<div class="meta">${translationPills.map((flag) => `<span class="tag">${esc(String(flag).replace(/_/g, ' '))}</span>`).join('')}</div>` : ''}
        ${isQueued && queueTag ? `<div class="meta queue-inline-indicator">Queue tag: <span class="queue-tag-pill">${esc(queueTag)}</span></div>` : ''}
      </div>
      <div class="board-cell" data-label="Position">${esc(row.position)}</div>
      <div class="board-cell" data-label="School">${esc(row.school)}</div>
      <div class="board-cell board-grade" data-label="Rookie Grade">${esc(grade)}</div>
      <div class="board-cell" data-label="Tier"><span class="board-tier-pill">${esc(row.tier.label)}</span></div>
      ${renderPprCell(row)}
      ${renderConsensusDeltaCell(row)}
      <div class="board-cell board-actions" data-label="Actions">
        <a class="nav-link" href="/cards/rookies/player.html?slug=${slug}">Detail</a>
        <a class="nav-link" href="${compareLeftHref}">Set Left</a>
        <a class="nav-link" href="${compareRightHref}">Set Right</a>
        <button type="button" class="queue-toggle ${isQueued ? 'is-queued' : ''}" data-queue-toggle="${esc(row.slug)}">${isQueued ? 'Queued ✓' : 'Add to queue'}</button>
      </div>
    </article>
  `;
}
