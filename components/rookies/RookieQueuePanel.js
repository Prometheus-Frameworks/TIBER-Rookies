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

function notePreview(note) {
  if (!note) return '';
  return note.length > 90 ? `${note.slice(0, 90)}…` : note;
}

export function reconcileRookieQueue(queue, supportedRows = []) {
  const rowsBySlug = new Map(supportedRows.map((row) => [row.slug, row]));
  return queue.map((entry) => {
    const row = rowsBySlug.get(entry.slug);
    const scoreAvailable = Boolean(row && row.alphaStatus !== 'not_scored' && Number.isFinite(row.rookieGrade));
    return {
      ...entry,
      scoreAvailable,
      rookieGrade: scoreAvailable ? row.rookieGrade : null,
      classRank: scoreAvailable ? row.classRank : null,
      tierLabel: scoreAvailable ? row.tier?.label : '',
      identityNote: scoreAvailable ? row.profileSummary : '',
      scoreStatus: row?.alphaStatus === 'not_scored'
        ? 'Unscored — draft-fact only. Scores, ranks and comparison unavailable.'
        : 'Coverage unavailable; scores, ranks and comparison withheld.',
    };
  });
}

export function renderRookieQueuePanel(savedQueue, compareState = {}, portabilityState = {}, options = {}) {
  // Presentation only: stored entries and user annotations are never rewritten.
  const queue = reconcileRookieQueue(savedQueue, options.supportedRows);
  const highestRanked = findHighestRanked(queue);
  const eligibleSlugs = new Set(queue.filter((player) => player.scoreAvailable).map((player) => player.slug));
  const canCompare = eligibleSlugs.has(compareState.left) && eligibleSlugs.has(compareState.right) && compareState.left !== compareState.right;
  const importMode = portabilityState.mode === 'merge' ? 'merge' : 'replace';
  const statusTone = portabilityState.tone === 'error' ? 'error' : 'info';
  const statusMessage = portabilityState.message ?? 'Export to a JSON file, then import on another browser/device.';
  const tagOptions = Array.isArray(options.tagOptions) ? options.tagOptions : [];
  const noteMaxLength = Number.isFinite(options.noteMaxLength) ? options.noteMaxLength : 160;

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
      <div class="queue-toolbar" style="margin-top: 10px; align-items: center; gap: 8px; flex-wrap: wrap;">
        <button type="button" class="queue-action" data-queue-export ${queue.length ? '' : 'disabled'}>Export queue JSON</button>
        <label class="meta" for="queue-import-mode">Import mode</label>
        <select id="queue-import-mode" data-queue-import-mode>
          <option value="replace" ${importMode === 'replace' ? 'selected' : ''}>Replace queue</option>
          <option value="merge" ${importMode === 'merge' ? 'selected' : ''}>Merge imported first</option>
        </select>
        <button type="button" class="queue-action" data-queue-import-trigger>Import queue JSON</button>
        <input type="file" data-queue-import-input accept="application/json,.json" style="display: none" />
      </div>
      <div class="meta" data-queue-import-status="${statusTone}" style="${statusTone === 'error' ? 'color: #ff8f8f;' : ''}">${esc(statusMessage)}</div>

      <div class="queue-list">
        ${queue.length
          ? queue
              .map((player, index) => {
                const grade = player.rookieGrade == null ? 'N/A' : player.rookieGrade.toFixed(1);
                const playerNote = player.queueNote ?? '';
                const playerTag = player.queueTag ?? '';
                const counterTone = playerNote.length >= noteMaxLength ? ' queue-note-counter-limit' : '';
                return `
                  <article class="queue-item">
                    <div class="queue-item-main">
                      <div class="queue-rank">${player.classRank != null ? `#${esc(player.classRank)}` : 'N/A'}</div>
                      <div>
                        <div class="board-player-name">${esc(player.name)}</div>
                        <div class="meta">${esc(player.position)} • ${esc(player.school)}</div>
                        ${player.scoreAvailable
                          ? `<div class="meta">Grade ${esc(grade)} • ${esc(player.tierLabel)}</div><div class="meta">${esc(player.identityNote)}</div>`
                          : `<div class="meta" role="status">${esc(player.scoreStatus)}</div>`}
                        ${playerTag ? `<div class="queue-annotation-tags"><span class="queue-tag-pill">${esc(playerTag)}</span></div>` : ''}
                        ${playerNote ? `<div class="queue-note-preview">“${esc(notePreview(playerNote))}”</div>` : ''}
                        <div class="queue-annotation-editor">
                          <label class="meta" for="queue-tag-${esc(player.slug)}">Draft tag</label>
                          <select id="queue-tag-${esc(player.slug)}" class="queue-annotation-select" data-queue-tag data-slug="${esc(player.slug)}">
                            <option value="">No tag</option>
                            ${tagOptions.map((tag) => `<option value="${esc(tag)}" ${playerTag === tag ? 'selected' : ''}>${esc(tag)}</option>`).join('')}
                          </select>
                          <label class="meta" for="queue-note-${esc(player.slug)}">Queue note</label>
                          <textarea
                            id="queue-note-${esc(player.slug)}"
                            class="queue-annotation-note"
                            data-queue-note
                            data-slug="${esc(player.slug)}"
                            maxlength="${noteMaxLength}"
                            placeholder="Short local note (why this player is queued)">${esc(playerNote)}</textarea>
                          <div class="meta queue-note-counter${counterTone}" data-queue-note-counter data-slug="${esc(player.slug)}">${playerNote.length}/${noteMaxLength}</div>
                          <div style="display:flex; gap: 6px; flex-wrap: wrap; margin-top: 4px;">
                            <button type="button" class="queue-action" data-queue-note-clear data-slug="${esc(player.slug)}" ${playerNote ? '' : 'disabled'}>Clear note</button>
                            <button type="button" class="queue-action" data-queue-tag-clear data-slug="${esc(player.slug)}" ${playerTag ? '' : 'disabled'}>Clear tag</button>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div class="queue-item-actions">
                      <a class="nav-link" href="/cards/rookies/player.html?slug=${encodeURIComponent(player.slug)}">Detail</a>
                      ${player.scoreAvailable ? `<button type="button" class="queue-action" data-queue-mark="left" data-slug="${esc(player.slug)}">Set Left${compareState.left === player.slug ? ' ✓' : ''}</button>
                      <button type="button" class="queue-action" data-queue-mark="right" data-slug="${esc(player.slug)}">Set Right${compareState.right === player.slug ? ' ✓' : ''}</button>` : ''}
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
