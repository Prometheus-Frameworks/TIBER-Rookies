function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function renderRookieBoardRow(row, { isQueued = false } = {}) {
  const rank = row.classRank == null ? 'N/A' : `#${row.classRank}`;
  const grade = row.rookieGrade == null ? 'N/A' : row.rookieGrade.toFixed(1);
  const slug = encodeURIComponent(String(row.slug ?? ''));

  return `
    <article class="board-row ${isQueued ? 'board-row-queued' : ''}">
      <div class="board-cell board-rank" data-label="Rank">${esc(rank)}</div>
      <div class="board-cell board-player" data-label="Player">
        <div class="board-player-name">${esc(row.name)}</div>
        <div class="meta">${esc(row.profileSummary)}</div>
      </div>
      <div class="board-cell" data-label="Position">${esc(row.position)}</div>
      <div class="board-cell" data-label="School">${esc(row.school)}</div>
      <div class="board-cell board-grade" data-label="Rookie Grade">${esc(grade)}</div>
      <div class="board-cell" data-label="Tier"><span class="board-tier-pill">${esc(row.tier.label)}</span></div>
      <div class="board-cell board-actions" data-label="Actions">
        <a class="nav-link" href="/cards/rookies/player.html?slug=${slug}">Detail</a>
        <a class="nav-link" href="/cards/rookies/compare/index.html?left=${slug}">Compare</a>
        <button type="button" class="queue-toggle ${isQueued ? 'is-queued' : ''}" data-queue-toggle="${esc(row.slug)}">${isQueued ? 'Queued ✓' : 'Add to queue'}</button>
      </div>
    </article>
  `;
}
