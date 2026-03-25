function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function summarizePositions(queue) {
  const counts = queue.reduce((acc, player) => {
    acc[player.position] = (acc[player.position] ?? 0) + 1;
    return acc;
  }, {});

  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([position, count]) => `${position}: ${count}`)
    .join(' • ');
}

function findHighestRanked(queue) {
  const ranked = queue
    .filter((player) => Number.isFinite(player.classRank))
    .sort((a, b) => a.classRank - b.classRank);

  return ranked[0] ?? null;
}

export function renderRookieQueuePanel(queue, compareState = {}) {
  const highestRanked = findHighestRanked(queue);
  const canCompare = compareState.left && compareState.right && compareState.left !== compareState.right;

  return `
    <section class="queue-panel">
      <div class="queue-summary">
        <div><span class="section-title">Queue size</span><div class="board-summary-value">${queue.length}</div></div>
        <div><span class="section-title">Position mix</span><div class="meta">${esc(summarizePositions(queue) || 'No players queued yet')}</div></div>
        <div><span class="section-title">Highest ranked</span><div class="meta">${highestRanked ? `#${esc(highestRanked.classRank)} ${esc(highestRanked.name)}` : 'Rank data unavailable'}</div></div>
        <div><span class="section-title">Storage</span><div class="meta">Saved locally in this browser (no account sync).</div></div>
      </div>

      <div class="queue-toolbar">
        <a class="nav-link ${canCompare ? '' : 'is-disabled'}" href="${canCompare ? `/cards/rookies/compare/index.html?left=${encodeURIComponent(compareState.left)}&right=${encodeURIComponent(compareState.right)}` : '#'}">Compare selected pair →</a>
        <button type="button" class="queue-clear" data-queue-clear ${queue.length ? '' : 'disabled'}>Clear queue</button>
      </div>

      <div class="queue-list">
        ${queue.length
          ? queue
              .map((player, index) => {
                const grade = player.rookieGrade == null ? 'N/A' : player.rookieGrade.toFixed(1);
                return `
                  <article class="queue-item">
                    <div class="queue-item-main">
                      <div class="queue-rank">${player.classRank != null ? `#${esc(player.classRank)}` : 'N/A'}</div>
                      <div>
                        <div class="board-player-name">${esc(player.name)}</div>
                        <div class="meta">${esc(player.position)} • ${esc(player.school)}</div>
                        <div class="meta">Grade ${esc(grade)} • ${esc(player.tierLabel)}</div>
                        <div class="meta">${esc(player.identityNote)}</div>
                      </div>
                    </div>
                    <div class="queue-item-actions">
                      <a class="nav-link" href="/cards/rookies/player.html?slug=${encodeURIComponent(player.slug)}">Detail</a>
                      <button type="button" class="queue-action" data-queue-mark="left" data-slug="${esc(player.slug)}">Set Left${compareState.left === player.slug ? ' ✓' : ''}</button>
                      <button type="button" class="queue-action" data-queue-mark="right" data-slug="${esc(player.slug)}">Set Right${compareState.right === player.slug ? ' ✓' : ''}</button>
                      <button type="button" class="queue-action" data-queue-move="up" data-slug="${esc(player.slug)}" ${index === 0 ? 'disabled' : ''}>Move up</button>
                      <button type="button" class="queue-action" data-queue-move="down" data-slug="${esc(player.slug)}" ${index === queue.length - 1 ? 'disabled' : ''}>Move down</button>
                      <button type="button" class="queue-action queue-remove" data-queue-remove data-slug="${esc(player.slug)}">Remove</button>
                    </div>
                  </article>
                `;
              })
              .join('')
          : '<article class="rookie-card"><div class="meta">Queue is empty. Add players from the board to build your draft shortlist.</div></article>'}
      </div>
    </section>
  `;
}
