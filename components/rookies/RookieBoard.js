import { renderRookieBoardRow } from '/components/rookies/RookieBoardRow.js';
import { groupRookiesByTier } from '/lib/rookies/groupRookiesByTier.js';

export function renderRookieBoard(rows, { view = 'tiered', queueSlugs = new Set(), queueAnnotations = new Map() } = {}) {
  if (!rows.length) {
    return '<article class="rookie-card"><div class="meta">No rookies matched this board filter.</div></article>';
  }

  const header = `
    <div class="board-row board-header">
      <div class="board-cell">#</div>
      <div class="board-cell">Player</div>
      <div class="board-cell">Pos</div>
      <div class="board-cell">School</div>
      <div class="board-cell">Grade</div>
      <div class="board-cell">Tier</div>
      <div class="board-cell">Actions</div>
    </div>
  `;

  if (view === 'flat') {
    return `<section class="rookie-board-surface">${header}${rows
      .map((row) => renderRookieBoardRow(row, { isQueued: queueSlugs.has(row.slug), queueAnnotation: queueAnnotations.get(row.slug) ?? null }))
      .join('')}</section>`;
  }

  const groups = groupRookiesByTier(rows);
  return `
    <section class="rookie-board-surface">
      ${groups
        .map(
          (group) => `
            <div class="tier-group">
              <div class="tier-header">${group.label} · ${group.rows.length} players</div>
              ${header}
              ${group.rows
                .map((row) => renderRookieBoardRow(row, { isQueued: queueSlugs.has(row.slug), queueAnnotation: queueAnnotations.get(row.slug) ?? null }))
                .join('')}
            </div>
          `,
        )
        .join('')}
    </section>
  `;
}
