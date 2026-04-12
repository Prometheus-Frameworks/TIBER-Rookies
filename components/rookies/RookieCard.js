import { selectRookieEvidenceMetrics } from '/lib/rookies/selectRookieEvidenceMetrics.js';
import { getCollegeLogoUrl, getNflTeamLogoUrl } from '/lib/rookies/teamLogos.js';

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderTeamLogos(school, nflTeam) {
  const collegeUrl = getCollegeLogoUrl(school);
  const nflUrl = getNflTeamLogoUrl(nflTeam);
  if (!collegeUrl && !nflUrl) return '';
  const imgs = [
    collegeUrl ? `<img class="team-logo" src="${esc(collegeUrl)}" alt="${esc(school ?? '')}" loading="lazy" onerror="this.style.display='none'">` : '',
    nflUrl     ? `<img class="team-logo" src="${esc(nflUrl)}" alt="${esc(nflTeam ?? '')}" loading="lazy" onerror="this.style.display='none'">` : '',
  ].join('');
  return `<span class="team-logos">${imgs}</span>`;
}

function pill(label, value) {
  if (value == null || value === '') return '';
  return `<div class="pill"><div class="pill-label">${esc(label)}</div><div class="pill-value">${esc(value)}</div></div>`;
}

function scoreCell(score) {
  if (score.value == null) {
    return `<div class="core-score"><div class="pill-label">${esc(score.label)}</div><div class="core-score-value">N/A</div></div>`;
  }
  const isEdge = score.label === 'Model Edge';
  const formatted = isEdge
    ? (score.value >= 0 ? `+${score.value.toFixed(1)}` : score.value.toFixed(1))
    : score.value.toFixed(1);
  const edgeClass = isEdge ? (score.value >= 3 ? ' delta-bull' : score.value <= -3 ? ' delta-bear' : ' delta-neutral') : '';
  return `<div class="core-score"><div class="pill-label">${esc(score.label)}</div><div class="core-score-value${edgeClass}">${esc(formatted)}</div></div>`;
}

function metricRow(metric) {
  if (metric.value == null) return '';
  const width = metric.percent == null ? 0 : Math.max(0, Math.min(100, metric.percent));
  return `<div class="metric-row"><div class="metric-header"><span>${esc(metric.evidenceLabel ?? metric.label)}</span><strong>${esc(metric.display)}</strong></div><div class="metric-track"><div class="metric-fill" style="width:${width}%"></div></div></div>`;
}

function pointForValue(centerX, centerY, radius, angle, value) {
  const safeValue = value == null ? 0 : Math.max(0, Math.min(100, Number(value) || 0));
  const scaledRadius = (safeValue / 100) * radius;
  const x = centerX + (scaledRadius * Math.cos(angle));
  const y = centerY + (scaledRadius * Math.sin(angle));
  return `${x.toFixed(1)},${y.toFixed(1)}`;
}

function renderRadarChart(athleticScore, production, draftCapital, athleticSource) {
  const centerX = 100;
  const centerY = 100;
  const radius = 80;
  const athLabel = athleticSource === 'SPORQ' ? 'ATH (SPORQ)' : athleticSource === 'COMBINE_FALLBACK' ? 'ATH (partial)' : 'ATH';
  const axes = [
    { label: athLabel, angle: -Math.PI / 2, value: athleticScore },
    { label: 'Production', angle: Math.PI / 6, value: production },
    { label: 'Draft Capital', angle: (5 * Math.PI) / 6, value: draftCapital },
  ];

  const ringScales = [0.25, 0.5, 0.75];
  const rings = ringScales.map((scale) => {
    const points = axes.map((axis) => pointForValue(centerX, centerY, radius, axis.angle, scale * 100)).join(' ');
    const isAverageRing = scale === 0.5;
    return `<polygon points="${points}" fill="none" stroke="#6f8098" stroke-width="${isAverageRing ? 1.6 : 1}" ${isAverageRing ? 'stroke-dasharray="4 3"' : ''} />`;
  }).join('');

  const dataPoints = axes.map((axis) => pointForValue(centerX, centerY, radius, axis.angle, axis.value)).join(' ');
  const axesLines = axes.map((axis) => {
    const endpoint = pointForValue(centerX, centerY, radius, axis.angle, 100);
    return `<line x1="${centerX}" y1="${centerY}" x2="${endpoint.split(',')[0]}" y2="${endpoint.split(',')[1]}" stroke="#516179" stroke-width="1" />`;
  }).join('');

  const labels = axes.map((axis) => {
    const outer = pointForValue(centerX, centerY, radius + 16, axis.angle, 100).split(',');
    const rendered = axis.value == null ? '0.0' : Number(axis.value).toFixed(1);
    return `<text x="${outer[0]}" y="${outer[1]}" fill="#b5c7dd" font-size="11" text-anchor="middle">${esc(axis.label)} ${esc(rendered)}</text>`;
  }).join('');

  return `
    <section class="metrics radar-section">
      <div class="section-title">Model Input Radar</div>
      <svg class="radar-chart" viewBox="0 0 200 200" role="img" aria-label="Radar chart for athletic, production, and draft capital scores">
        ${rings}
        ${axesLines}
        <polygon points="${dataPoints}" fill="rgba(59, 130, 246, 0.25)" stroke="#3b82f6" stroke-width="2" />
        ${labels}
      </svg>
    </section>
  `;
}

function renderBreakoutAgeBadge(card) {
  if (card.breakoutAge == null) return '';
  if (card.youngBreakoutFlag) {
    return `<span class="breakout-badge breakout-young">⚡ Age ${esc(card.breakoutAge)} breakout</span>`;
  }
  return `<span class="breakout-badge breakout-late">Age ${esc(card.breakoutAge)} breakout</span>`;
}

function boarTierClass(boar) {
  if (boar >= 75) return 'boar-elite';
  if (boar >= 60) return 'boar-early';
  if (boar >= 45) return 'boar-avg';
  return 'boar-late';
}

function renderBoarSection(card) {
  const boar = card.breakoutAgeRating;
  const boa = card.breakoutAge;
  if (boar == null && boa == null) return '';

  const boarChip = boar != null
    ? `<span class="boar-chip ${boarTierClass(boar)}"><span class="boar-label">BOAR</span> <span class="boar-value">${Math.round(boar)}</span></span>`
    : '';
  const boaChip = boa != null
    ? `<span class="boa-chip"><span class="boa-label">BOA</span> <span class="boa-value">${esc(boa)}</span></span>`
    : '';
  const labelText = card.breakoutLabel ?? null;
  const labelSpan = labelText
    ? `<span class="boar-signal-label">${esc(labelText)}</span>`
    : '';

  return `
    <div class="boar-section">
      <div class="boar-chips">${boaChip}${boarChip}</div>
      ${labelSpan}
    </div>`;
}

function renderPprProjection(ppr) {
  if (!ppr) return '';
  const bandClass = { Elite: 'ppr-band-elite', Starter: 'ppr-band-starter', Contributor: 'ppr-band-contributor', Lottery: 'ppr-band-lottery' }[ppr.band] ?? 'ppr-band-lottery';
  return `
    <div class="ppr-card-section">
      <div class="section-title">Year 1 PPR Projection</div>
      <div class="ppr-card-row">
        <div class="ppr-card-stat"><div class="ppr-stat-label">Floor</div><div class="ppr-stat-value">${esc(ppr.floor)}</div></div>
        <div class="ppr-card-stat ppr-median"><div class="ppr-stat-label">Median</div><div class="ppr-stat-value ppr-median-value">${esc(ppr.median)}</div></div>
        <div class="ppr-card-stat"><div class="ppr-stat-label">Ceiling</div><div class="ppr-stat-value">${esc(ppr.ceiling)}</div></div>
        <div class="ppr-card-band"><span class="ppr-band ${bandClass}">${esc(ppr.band)}</span></div>
      </div>
    </div>`;
}

function renderAgeAdjMetric(ageAdjustedProduction) {
  if (ageAdjustedProduction == null) return '';
  const width = Math.max(0, Math.min(100, ageAdjustedProduction));
  return `<div class="metric-row"><div class="metric-header"><span>Age-Adjusted Production</span><strong>${esc(ageAdjustedProduction.toFixed(1))}</strong></div><div class="metric-track"><div class="metric-fill metric-fill-age-adj" style="width:${width}%"></div></div></div>`;
}

const STAT_LABELS = {
  // Passing
  completions:      'Comp',
  attempts:         'Att',
  completion_pct:   'Comp%',
  passing_yards:    'Pass Yds',
  passing_tds:      'Pass TD',
  interceptions:    'INT',
  yards_per_attempt:'Y/A',
  // Rushing
  rush_attempts:    'Att',
  rush_yards:       'Rush Yds',
  rush_tds:         'Rush TD',
  yards_per_carry:  'YPC',
  // Receiving
  receptions:       'Rec',
  receiving_yards:  'Rec Yds',
  receiving_tds:    'Rec TD',
  yards_per_reception: 'YPR',
  targets:          'Tgt',
  // Skip non-numeric meta fields silently
  note:             null,
};

function formatStatEntry(key, value) {
  const label = STAT_LABELS[key];
  if (label === null) return null; // explicitly suppressed
  const displayLabel = label ?? key.replace(/_/g, ' ');
  const displayValue = key === 'completion_pct' ? `${value}%` : value;
  return `${displayLabel}: ${displayValue}`;
}

export function renderRookieCard(container, card) {
  const heroScore = card.summary.rookieGrade == null ? 'N/A' : card.summary.rookieGrade.toFixed(1);
  const identityBits = [
    card.identity.positionLabel ?? card.identity.position,
    card.identity.schoolDisplay ?? card.identity.school,
    `Class ${card.identity.classYear}`,
    card.identity.height,
    card.identity.weight,
  ].filter(Boolean).join(' • ');
  const evidenceMetrics = selectRookieEvidenceMetrics(card, 'full');
  const translationFlags = Array.isArray(card.translationFlags) ? card.translationFlags : [];
  const contextFlags = Array.isArray(card.contextSignals?.contextFlags) ? card.contextSignals.contextFlags : [];
  const evidenceSummary = card.contextSignals?.evidenceSummary ?? null;

  const seasonsTable = card.seasons.length
    ? `<table class="stats-table">
        <thead><tr><th>Season</th><th>School</th><th>Stats</th></tr></thead>
        <tbody>${card.seasons.map((row) => {
          const statBits = Object.entries(row.statLine)
            .map(([k, v]) => formatStatEntry(k, v))
            .filter(Boolean)
            .join(' · ');
          return `<tr><td>${esc(row.season)}</td><td>${esc(row.team)}</td><td>${esc(statBits)}</td></tr>`;
        }).join('')}</tbody>
       </table>`
    : '<div class="meta">College stats not yet available for this player.</div>';

  container.innerHTML = `
    <article class="rookie-card">
      <div class="header-grid">
        <div>
          <div class="section-title">TIBER Rookie Card</div>
          <h1 class="player-name">
            ${renderTeamLogos(card.identity.school, card.identity.nflTeam)}${esc(card.identity.name)}
          </h1>
          <div class="meta">${esc(identityBits || 'Profile context not available')}</div>
          <div class="meta">${esc(card.summary.profileSummary ?? card.summary.identityNote ?? 'Identity summary unavailable')}</div>
          ${renderBoarSection(card)}
        </div>
        <div class="hero-score">
          <div class="section-title">Rookie Grade</div>
          <div class="score">${esc(heroScore)}</div>
          <div class="meta">Class rank #${esc(card.summary.classRank ?? 'N/A')}</div>
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

      ${renderRadarChart(card.scores[1]?.value, card.scores[2]?.value, card.scores[3]?.value, card.athleticSource)}

      ${renderPprProjection(card.pprProjection)}

      <section class="metrics">
        <div class="section-title">Position-aware Evidence</div>
        <div class="meta">${esc(card.evidence?.readinessLabel ?? 'Evidence readiness unavailable')}</div>
        ${renderAgeAdjMetric(card.ageAdjustedProduction)}
        ${evidenceMetrics.map(metricRow).join('') || '<div class="meta">No evidence metrics available.</div>'}
      </section>

      <section class="metrics">
        <div class="section-title">Why this profile translates (deterministic)</div>
        <div class="meta">${esc(evidenceSummary ?? 'Translation summary unavailable in current artifacts.')}</div>
        ${translationFlags.length
          ? `<div class="tags">${translationFlags.map((flag) => `<span class="tag">${esc(String(flag).replace(/_/g, ' '))}</span>`).join('')}</div>`
          : '<div class="meta">No translation evidence tags available.</div>'}
        ${contextFlags.length
          ? `<div class="meta">Context flags: ${esc(contextFlags.map((flag) => String(flag).replace(/_/g, ' ')).join(' • '))}</div>`
          : ''}
      </section>

      <section class="metrics">
        <div class="section-title">Season Stats</div>
        ${seasonsTable}
      </section>

      ${card.tags.length
        ? `<section class="tags">${card.tags.map((tag) => `<span class="tag">${esc(tag)}</span>`).join('')}</section>`
        : ''}
    </article>
  `;
}
