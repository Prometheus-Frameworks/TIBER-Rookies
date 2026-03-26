import { compareRookies } from '/lib/rookies/compareRookies.js';
import { selectRookieEvidenceMetrics } from '/lib/rookies/selectRookieEvidenceMetrics.js';

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function gradeCell(label, card, side) {
  const grade = card?.summary?.rookieGrade == null ? 'N/A' : card.summary.rookieGrade.toFixed(1);
  const rank = card?.summary?.classRank == null ? 'N/A' : `#${card.summary.classRank}`;
  return `
    <article class="compare-player compare-${side}">
      <div class="section-title">${esc(label)}</div>
      <h2 class="compare-name">${esc(card.identity.name)}</h2>
      <div class="meta">${esc(card.identity.positionLabel ?? card.identity.position)} • Class ${esc(card.identity.classYear)}${card.identity.schoolDisplay ? ` • ${esc(card.identity.schoolDisplay)}` : ''}</div>
      <div class="meta">${esc(card.summary.profileSummary ?? card.summary.identityNote ?? 'Identity summary unavailable')}</div>
      <div class="compare-grade">${esc(grade)}</div>
      <div class="meta">Class rank ${esc(rank)}</div>
      <div class="compare-pills">
        ${card.summary.archetype ? `<span class="tag">${esc(card.summary.archetype)}</span>` : ''}
        ${card.summary.projection ? `<span class="tag">${esc(card.summary.projection)}</span>` : ''}
      </div>
    </article>
  `;
}

function scoreRow(row) {
  const left = row.leftValue == null ? 'N/A' : row.leftValue.toFixed(1);
  const right = row.rightValue == null ? 'N/A' : row.rightValue.toFixed(1);
  const edge = row.winner === 'tie' ? 'Even' : row.winner === 'left' ? 'Left edge' : 'Right edge';
  return `<tr><td>${esc(row.label)}</td><td>${esc(left)}</td><td>${esc(right)}</td><td>${esc(edge)}</td></tr>`;
}

function evidenceRow(row) {
  const edge = row.winner === 'tie' ? 'Even' : row.winner === 'left' ? 'Left leads' : 'Right leads';
  return `<tr><td>${esc(row.label)}</td><td>${esc(row.leftDisplay)}</td><td>${esc(row.rightDisplay)}</td><td>${esc(edge)}</td></tr>`;
}

function seasonSnapshot(card) {
  if (!card?.seasons?.length) {
    return '<div class="meta">Season rows unavailable in current promoted artifacts.</div>';
  }

  const top = card.seasons.slice(0, 2);
  return `<table class="stats-table"><thead><tr><th>Season</th><th>Team</th><th>Games</th></tr></thead><tbody>${top.map((row) => `<tr><td>${esc(row.season)}</td><td>${esc(row.team)}</td><td>${esc(row.games ?? 'N/A')}</td></tr>`).join('')}</tbody></table>`;
}

export function renderRookieCompareView(container, leftCard, rightCard) {
  const compared = compareRookies(leftCard, rightCard);
  const leftHighlights = selectRookieEvidenceMetrics(leftCard, 'compact').slice(0, 3);
  const rightHighlights = selectRookieEvidenceMetrics(rightCard, 'compact').slice(0, 3);

  container.innerHTML = `
    <section class="compare-layout">
      <div class="verdict-strip verdict-${esc(compared.verdict.code)}">
        <div>
          <div class="section-title">Transparent verdict</div>
          <strong>${esc(compared.verdict.headline)}</strong>
          <p class="meta">${esc(compared.verdict.detail)}</p>
        </div>
        <div class="delta-chip">Grade Δ ${compared.overallDelta == null ? 'N/A' : esc(compared.overallDelta.toFixed(1))}</div>
      </div>

      <div class="compare-grid">
        ${gradeCell('Left', leftCard, 'left')}
        ${gradeCell('Right', rightCard, 'right')}
      </div>

      <section class="metrics">
        <div class="section-title">Score comparison</div>
        <table class="stats-table compare-table">
          <thead><tr><th>Score</th><th>Left</th><th>Right</th><th>Edge</th></tr></thead>
          <tbody>${compared.scoreComparisons.map(scoreRow).join('')}</tbody>
        </table>
      </section>

      <section class="metrics">
        <div class="section-title">Key evidence edges</div>
        ${compared.evidenceComparisons.length
          ? `<table class="stats-table compare-table"><thead><tr><th>Metric</th><th>Left</th><th>Right</th><th>Edge</th></tr></thead><tbody>${compared.evidenceComparisons.map(evidenceRow).join('')}</tbody></table>`
          : '<div class="meta">Insufficient shared evidence rows for a meaningful metric edge table.</div>'}
      </section>

      <section class="compare-grid compare-snapshot-grid">
        <article class="rookie-card compare-snapshot">
          <div class="section-title">Left profile snapshot</div>
          <div class="meta">${leftHighlights.map((metric) => `${esc(metric.evidenceLabel ?? metric.label)}: ${esc(metric.display)}`).join(' • ') || 'No evidence snippets available.'}</div>
          ${seasonSnapshot(leftCard)}
        </article>
        <article class="rookie-card compare-snapshot">
          <div class="section-title">Right profile snapshot</div>
          <div class="meta">${rightHighlights.map((metric) => `${esc(metric.evidenceLabel ?? metric.label)}: ${esc(metric.display)}`).join(' • ') || 'No evidence snippets available.'}</div>
          ${seasonSnapshot(rightCard)}
        </article>
      </section>

      <section class="metrics">
        <div class="section-title">Compare notes</div>
        <ul class="compare-notes">${compared.notes.map((note) => `<li>${esc(note)}</li>`).join('')}</ul>
      </section>
    </section>
  `;
}
