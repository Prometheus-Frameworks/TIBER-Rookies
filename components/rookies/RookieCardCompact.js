import { selectRookieEvidenceMetrics } from '/lib/rookies/selectRookieEvidenceMetrics.js';

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function compactMetric(metric) {
  return `<div class="compact-metric"><div class="compact-metric-label">${esc(metric.evidenceLabel ?? metric.label)}</div><div class="compact-metric-value">${esc(metric.display)}</div></div>`;
}

function notePreview(note) {
  if (!note) return '';
  return note.length > 60 ? `${note.slice(0, 60)}…` : note;
}

export function renderRookieCardCompact(card, { isQueued = false, queueAnnotation = null } = {}) {
  const score = card.summary.rookieGrade == null ? 'N/A' : card.summary.rookieGrade.toFixed(1);
  const slug = encodeURIComponent(String(card.slug ?? ''));
  const snippets = selectRookieEvidenceMetrics(card, 'compact');
  const topTags = (card.tags ?? []).slice(0, 3);
  const queueTag = queueAnnotation?.queueTag ?? '';
  const queueNote = queueAnnotation?.queueNote ?? '';

  return `
    <article class="compact-card ${isQueued ? 'compact-card-queued' : ''}">
      <a class="compact-card-link" href="/cards/rookies/player.html?slug=${slug}">
        <div class="compact-header-row">
          <div>
            <p class="compact-name">${esc(card.identity.name)}</p>
            <div class="compact-meta">${esc(card.identity.positionLabel ?? card.identity.position)} • ${esc(card.identity.schoolDisplay ?? card.identity.school ?? 'School unavailable in current artifacts')} • Class ${esc(card.identity.classYear)}</div>
          </div>
          <div class="compact-rank">${card.summary.classRank != null ? '#' + esc(card.summary.classRank) : 'N/A'}</div>
        </div>
        <div class="section-title">Rookie Grade</div>
        <div class="compact-score">${esc(score)}</div>
        ${isQueued && queueTag ? `<div class="meta queue-inline-indicator">Queue tag: <span class="queue-tag-pill">${esc(queueTag)}</span></div>` : ''}
        ${isQueued && queueNote ? `<div class="meta">“${esc(notePreview(queueNote))}”</div>` : ''}
        ${snippets.length ? `<div class="compact-snippets">${snippets.map(compactMetric).join('')}</div>` : ''}
        <div class="compact-archetype">${esc(card.summary.profileSummary ?? card.summary.archetype ?? card.summary.projection ?? 'Role profile unavailable')}</div>
        ${topTags.length ? `<div class="compact-tags">${topTags.map((tag) => `<span class="tag">${esc(tag)}</span>`).join('')}</div>` : ''}
      </a>
      <div class="compact-actions-row">
        <button type="button" class="queue-toggle ${isQueued ? 'is-queued' : ''}" data-queue-toggle="${esc(card.slug)}">${isQueued ? 'Queued ✓' : 'Add to queue'}</button>
        <a class="compact-compare-link" href="/cards/rookies/compare/index.html?left=${slug}">Compare from this player</a>
      </div>
    </article>
  `;
}
