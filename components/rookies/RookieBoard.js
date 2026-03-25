import { renderRookieBoardRow } from '/components/rookies/RookieBoardRow.js';
import { groupRookiesByTier } from '/lib/rookies/groupRookiesByTier.js';

export function renderRookieBoard(rows, { view = 'tiered' } = {}) {
  if (!rows.length) {
    return '<article class="rookie-card"><div class="meta">No rookies matched this board filter.</div></article>';
  }

  const header = `
    <div class="board-row board-header">
      <div class="board-cell">Rank</div>
      <div class="board-cell">Player</div>
      <div class="board-cell">Pos</div>
      <div class="board-cell">School</div>
      <div class="board-cell">Rookie Grade</div>
      <div class="board-cell">Tier</div>
      <div class="board-cell">Actions</div>
    </div>
  `;

  if (view === 'flat') {
    return `<section class="rookie-board-surface">${header}${rows.map(renderRookieBoardRow).join('')}</section>`;
  }

  const groups = groupRookiesByTier(rows);
  return `
    <section class="rookie-board-surface">${header}
      ${groups
        .map(
          (group) => `
            <div class="board-tier-break">
              <div class="board-tier-title">${group.label}</div>
              <div class="meta">${group.rows.length} rookies</div>
            </div>
            ${group.rows.map(renderRookieBoardRow).join('')}
          `
        )
        .join('')}
    </section>
  `;
}
