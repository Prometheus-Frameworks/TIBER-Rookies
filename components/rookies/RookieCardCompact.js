export function renderRookieCardCompact(card) {
  const score = card.summary.rookieGrade == null ? 'N/A' : card.summary.rookieGrade.toFixed(1);
  return `
    <a class="compact-card" href="/cards/rookies/player.html?slug=${card.slug}">
      <p class="compact-name">${card.identity.name}</p>
      <div class="compact-meta">${card.identity.position} • Class ${card.identity.classYear}</div>
      <div class="section-title">Rookie Grade</div>
      <div class="compact-score">${score}</div>
    </a>
  `;
}
