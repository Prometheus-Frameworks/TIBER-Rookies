function pill(label, value) {
  if (!value) return '';
  return `<div class="pill"><div class="pill-label">${label}</div><div class="pill-value">${value}</div></div>`;
}

function scoreCell(score) {
  const rendered = score.value == null ? 'N/A' : score.value.toFixed(1);
  return `<div class="core-score"><div class="pill-label">${score.label}</div><div class="core-score-value">${rendered}</div></div>`;
}

function metricRow(metric) {
  if (metric.value == null) return '';
  const width = metric.percent == null ? 0 : Math.max(0, Math.min(100, metric.percent));
  return `<div class="metric-row"><div class="metric-header"><span>${metric.label}</span><strong>${metric.display}</strong></div><div class="metric-track"><div class="metric-fill" style="width:${width}%"></div></div></div>`;
}

export function renderRookieCard(container, card) {
  const heroScore = card.summary.rookieGrade == null ? 'N/A' : card.summary.rookieGrade.toFixed(1);
  const identityBits = [
    card.identity.position,
    card.identity.school,
    `Class ${card.identity.classYear}`,
    card.identity.height,
    card.identity.weight,
  ].filter(Boolean).join(' • ');

  const seasonsTable = card.seasons.length
    ? `<table class="stats-table"><thead><tr><th>Season</th><th>Team</th><th>Games</th><th>Stat Line</th></tr></thead><tbody>${card.seasons.map((row) => `<tr><td>${row.season}</td><td>${row.team}</td><td>${row.games ?? 'N/A'}</td><td>${Object.entries(row.statLine).map(([k, v]) => `${k}: ${v}`).join(' | ')}</td></tr>`).join('')}</tbody></table>`
    : '<div class="meta">Season stat rows are not available in the current promoted artifacts.</div>';

  container.innerHTML = `
    <article class="rookie-card">
      <div class="header-grid">
        <div>
          <div class="section-title">TIBER Rookie Card Prototype</div>
          <h1 class="player-name">${card.identity.name}</h1>
          <div class="meta">${identityBits || 'Profile context not available'}</div>
        </div>
        <div class="hero-score">
          <div class="section-title">Rookie Grade</div>
          <div class="score">${heroScore}</div>
          <div class="meta">Class rank #${card.summary.classRank ?? 'N/A'}</div>
        </div>
      </div>

      <section class="identity-strip">
        ${pill('Archetype', card.summary.archetype)}
        ${pill('Projection', card.summary.projection)}
        ${pill('High-end comp', card.comps.high)}
        ${pill('Low-end comp', card.comps.low)}
      </section>

      <section class="core-row">
        ${card.scores.map(scoreCell).join('')}
      </section>

      <section class="metrics">
        <div class="section-title">Metric Evidence</div>
        ${card.metrics.map(metricRow).join('') || '<div class="meta">No evidence metrics available.</div>'}
      </section>

      <section class="metrics">
        <div class="section-title">Season Stats</div>
        ${seasonsTable}
      </section>

      <section class="tags">
        ${card.tags.map((tag) => `<span class="tag">${tag}</span>`).join('')}
      </section>
    </article>
  `;
}
