function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function renderRookieCardCompact(card) {
  const score = card.summary.rookieGrade == null ? 'N/A' : card.summary.rookieGrade.toFixed(1);
  const slug = encodeURIComponent(String(card.slug ?? ''));

  return `
    <a class="compact-card" href="/cards/rookies/player.html?slug=${slug}">
      <p class="compact-name">${esc(card.identity.name)}</p>
      <div class="compact-meta">${esc(card.identity.position)} • Class ${esc(card.identity.classYear)}</div>
      <div class="section-title">Rookie Grade</div>
      <div class="compact-score">${esc(score)}</div>
    </a>
  `;
}
