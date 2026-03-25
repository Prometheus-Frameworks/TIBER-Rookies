import { selectRookieEvidenceMetrics } from '/lib/rookies/selectRookieEvidenceMetrics.js';

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function compactMetric(metric) {
  return `<div class="compact-metric"><div class="compact-metric-label">${esc(metric.label)}</div><div class="compact-metric-value">${esc(metric.display)}</div></div>`;
}

export function renderRookieCardCompact(card) {
  const score = card.summary.rookieGrade == null ? 'N/A' : card.summary.rookieGrade.toFixed(1);
  const slug = encodeURIComponent(String(card.slug ?? ''));
  const snippets = selectRookieEvidenceMetrics(card, 'compact');
  const topTags = (card.tags ?? []).slice(0, 3);

  return `
    <a class="compact-card" href="/cards/rookies/player.html?slug=${slug}">
      <div class="compact-header-row">
        <div>
          <p class="compact-name">${esc(card.identity.name)}</p>
          <div class="compact-meta">${esc(card.identity.position)} • ${esc(card.identity.school ?? 'School N/A')} • Class ${esc(card.identity.classYear)}</div>
        </div>
        <div class="compact-rank">${card.summary.classRank != null ? '#' + esc(card.summary.classRank) : 'N/A'}</div>
      </div>
      <div class="section-title">Rookie Grade</div>
      <div class="compact-score">${esc(score)}</div>
      ${snippets.length ? `<div class="compact-snippets">${snippets.map(compactMetric).join('')}</div>` : ''}
      <div class="compact-archetype">${esc(card.summary.archetype ?? card.summary.projection ?? 'Role profile unavailable')}</div>
      ${topTags.length ? `<div class="compact-tags">${topTags.map((tag) => `<span class="tag">${esc(tag)}</span>`).join('')}</div>` : ''}
    </a>
  `;
}
