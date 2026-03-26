import { renderRookieBoardRow } from '/components/rookies/RookieBoardRow.js';
import { groupRookiesByTier } from '/lib/rookies/groupRookiesByTier.js';

export function renderRookieBoard(rows, { view = 'tiered', queueSlugs = new Set(), queueAnnotations = new Map() } = {}) {
  const header = `
    <div class="board-header">
      <div>#</div>
      <div>Player</div>
      <div>Pos</div>
      <div>School</div>
      <div>Grade</div>
      <div>Tier</div>
      <div>Actions</div>
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
              <div class="tier-header">${group.label} · ${group.range} · ${group.rows.length} players</div>
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
