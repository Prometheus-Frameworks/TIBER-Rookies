import { selectRookieEvidenceMetrics } from '/lib/rookies/selectRookieEvidenceMetrics.js';
import { getCollegeLogoUrl, getNflTeamLogoUrl } from '/lib/rookies/teamLogos.js';
import { athleticMetricLabel } from '/lib/rookies/athleticLabel.js';
import { renderPprProjection } from './renderPprProjection.js';

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
    return `<div class="core-score"><div class="pill-label">${esc(score.label)}</div><div class="core-score-value">N/A</div><div class="score-track is-empty"></div></div>`;
  }
  const isSignedDelta = score.label === 'Model Edge' || score.label === 'Delta';
  const formatted = isSignedDelta
    ? (score.value >= 0 ? `+${score.value.toFixed(1)}` : score.value.toFixed(1))
    : score.value.toFixed(1);
  const edgeClass = isSignedDelta ? (score.value >= 3 ? ' delta-bull' : score.value <= -3 ? ' delta-bear' : ' delta-neutral') : '';
  const normalizedWidth = isSignedDelta
    ? Math.max(0, Math.min(100, Math.abs(score.value) * 10))
    : Math.max(0, Math.min(100, score.value));
  const trackFillClass = isSignedDelta
    ? (score.value >= 0 ? 'score-fill-edge-pos' : 'score-fill-edge-neg')
    : 'score-fill-standard';
  return `
    <div class="core-score">
      <div class="pill-label">${esc(score.label)}</div>
      <div class="core-score-value${edgeClass}">${esc(formatted)}</div>
      <div class="score-track">
        <div class="score-fill ${trackFillClass}" style="width:${normalizedWidth}%"></div>
      </div>
    </div>
  `;
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
  const athLabel = athleticMetricLabel(athleticSource);
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
    <div class="radar-section">
      <div class="section-title">Model Input Radar</div>
      <svg class="radar-chart" viewBox="0 0 200 200" role="img" aria-label="Radar chart for athletic, production, and draft capital scores">
        ${rings}
        ${axesLines}
        <polygon points="${dataPoints}" fill="rgba(59, 130, 246, 0.25)" stroke="#3b82f6" stroke-width="2" />
        ${labels}
      </svg>
    </div>
  `;
}

function renderBreakoutAgeBadge(card) {
  if (card.breakoutAge == null) return '';
  if (card.youngBreakoutFlag) {
    return `<span class="breakout-badge breakout-young">⚡ Age ${esc(card.breakoutAge)} breakout</span>`;
  }
  return `<span class="breakout-badge breakout-late">Age ${esc(card.breakoutAge)} breakout</span>`;
}

const EVIDENCE_TIER_LABELS = {
  strong_supported_edge: 'Strong Supported Edge',
  moderate_edge: 'Moderate Edge',
  consensus_aligned: 'Consensus Aligned',
  watchlist_outlier: 'Watchlist Outlier',
  insufficient_evidence: 'Insufficient Evidence',
};

function renderEvidenceTierBadge(card) {
  const tier = card.evidenceTier;
  if (!tier) return '';
  const label = EVIDENCE_TIER_LABELS[tier] ?? String(tier).replace(/_/g, ' ');
  const reason = card.evidenceTierReason ?? 'Evidence tier classification';
  return `<span class="evidence-tier-badge" title="${esc(reason)}">${esc(label)}</span>`;
}

function isoDate(value) {
  return value ? String(value).slice(0, 10) : null;
}

function renderBaselineProvenance(card) {
  const baseline = card.preDraftBaseline ?? null;
  const bits = [
    'Frozen snapshot',
    baseline?.modelVersion ? esc(baseline.modelVersion) : null,
    baseline?.generatedAt ? `generated ${esc(isoDate(baseline.generatedAt))}` : null,
  ].filter(Boolean);
  return bits.join(' · ');
}

function classRankLine(card) {
  const classRank = card.summary.classRank == null ? 'N/A' : card.summary.classRank;
  const posRank = card.summary.posRank;
  const posBit = posRank != null ? ` · ${esc(card.identity.position)} #${esc(posRank)}` : '';
  return `Class #${esc(classRank)}${posBit}`;
}

function renderOfficialOutcome(card) {
  const outcome = card.officialOutcome ?? null;
  if (!outcome) return '';
  if (outcome.status === 'unavailable') {
    const reasonCopy = outcome.reason === 'governed_source_load_failed'
      ? 'governed source did not load'
      : 'governed outcome not available';
    return `
    <section class="metrics card-panel official-outcome-panel">
      <div class="section-title">Official NFL Outcome</div>
      <div class="ppr-stale-warning" role="alert">⚠️ Official NFL outcome unavailable (${esc(reasonCopy)}).</div>
    </section>`;
  }
  const factBits = [
    outcome.nflTeam ? `Team: ${esc(outcome.nflTeam)}` : '',
    outcome.draftRound != null ? `Round ${esc(outcome.draftRound)}` : '',
    outcome.overallPick != null ? `Pick ${esc(outcome.overallPick)}` : '',
    outcome.isUdfa ? 'UDFA' : '',
  ].filter(Boolean).join(' · ');
  const prov = outcome.provenance;
  const provLine = prov
    ? `<div class="meta official-outcome-provenance">Source: ${prov.sourceUrl
        ? `<a href="${esc(prov.sourceUrl)}" target="_blank" rel="noopener noreferrer">${esc(prov.sourceName ?? 'source')}</a>`
        : esc(prov.sourceName ?? 'source unavailable')}${prov.lastVerifiedAt ? ` · verified ${esc(isoDate(prov.lastVerifiedAt))}` : ''}${prov.confidenceBand ? ` · confidence ${esc(prov.confidenceBand)}` : ''}</div>`
    : '';
  return `
    <section class="metrics card-panel official-outcome-panel">
      <div class="section-title">Official NFL Outcome</div>
      <div class="meta">Governed transition profile · rookie_transition_profile_v0.2.0.</div>
      <div class="official-outcome-facts">${factBits || 'Outcome not yet recorded'}</div>
      ${provLine}
    </section>`;
}

function boarTierClass(boar) {
  if (boar >= 75) return 'boar-elite';
  if (boar >= 60) return 'boar-early';
  if (boar >= 45) return 'boar-avg';
  return 'boar-late';
}

function breakoutPillValue(card) {
  if (card.breakoutAge == null) return null;
  const label = card.breakoutLabel ?? null;
  return label ? `Age ${card.breakoutAge} · ${label}` : `Age ${card.breakoutAge}`;
}

function renderBoarMetricRow(card) {
  const boar = card.breakoutAgeRating;
  if (boar == null) return '';
  const width = Math.max(0, Math.min(100, boar));
  const tierClass = boarTierClass(boar);
  return `<div class="metric-row"><div class="metric-header"><span>Breakout Age Rating (BOAR)</span><strong class="${tierClass}">${Math.round(boar)}</strong></div><div class="metric-track"><div class="metric-fill metric-fill-boar ${tierClass}" style="width:${width}%"></div></div></div>`;
}

function renderAgeAdjMetric(ageAdjustedProduction) {
  if (ageAdjustedProduction == null) return '';
  const width = Math.max(0, Math.min(100, ageAdjustedProduction));
  return `<div class="metric-row"><div class="metric-header"><span>Age-Adjusted Production</span><strong>${esc(ageAdjustedProduction.toFixed(1))}</strong></div><div class="metric-track"><div class="metric-fill metric-fill-age-adj" style="width:${width}%"></div></div></div>`;
}

function normalizeMetricFamily(family) {
  if (!family) return 'uncategorized';
  return String(family).trim().toLowerCase();
}

function metricFamilyLabel(family) {
  if (family === 'all') return 'All';
  return family
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(' ');
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
  const metricFamilies = ['all', ...Array.from(new Set(evidenceMetrics.map((metric) => normalizeMetricFamily(metric.family))))];
  const translationFlags = Array.isArray(card.translationFlags) ? card.translationFlags : [];
  const contextFlags = Array.isArray(card.contextSignals?.contextFlags) ? card.contextSignals.contextFlags : [];
  const evidenceSummary = card.contextSignals?.evidenceSummary ?? null;
  const athleticNotIncorporated = card.athleticSource === 'NEUTRAL_DEFAULT';
  const athleticPartial = card.athleticSource === 'RAS_PARTIAL' || card.athleticSource === 'COMBINE_FALLBACK';
  const quickPprMedian = card.pprProjection?.median ?? null;
  let selectedMetricFamily = 'all';

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

  function render() {
    const filteredEvidenceMetrics = evidenceMetrics.filter((metric) => {
      if (selectedMetricFamily === 'all') return true;
      return normalizeMetricFamily(metric.family) === selectedMetricFamily;
    });
    const includeProductionSpecials = selectedMetricFamily === 'all' || selectedMetricFamily === 'production';

    container.innerHTML = `
    <article class="rookie-card rookie-card-layout">
      <section class="hero-panel">
        <div class="hero-top">
          <div class="hero-left">
            <div class="section-title">TIBER Rookie Card</div>
            <h1 class="player-name">
              <span class="avatar-pos pos-${esc(card.identity.position)}">${esc(card.identity.position)}</span>
              ${renderTeamLogos(card.identity.school, card.identity.nflTeam)}${esc(card.identity.name)}
            </h1>
            <div class="meta">${esc(identityBits || 'Profile context not available')}</div>
            <p class="profile-summary">${esc(card.summary.profileSummary ?? card.summary.identityNote ?? 'Identity summary unavailable')}</p>
          </div>
          <div class="hero-score">
            <div class="section-title">Rookie Alpha · Frozen Pre-Draft Baseline</div>
            <div class="score">${esc(heroScore)}</div>
            <div class="meta">${renderBaselineProvenance(card)}</div>
            <div class="meta">Post-draft grade not yet published.</div>
            <div class="meta">${classRankLine(card)}</div>
            ${renderEvidenceTierBadge(card)}
          </div>
        </div>
        <div class="identity-strip">
          ${pill('Archetype', card.summary.archetype)}
          ${pill('Projection', card.summary.projection)}
          ${pill('Year 1 Median PPR', quickPprMedian)}
          ${pill('Breakout', breakoutPillValue(card))}
        </div>
      </section>

      <section class="card-actions-row">
        <div class="card-actions-copy">
          <div class="section-title">Next Steps</div>
          <div class="meta">Continue scouting this profile with board context or head-to-head comparison.</div>
        </div>
        <div class="card-actions-links">
          <a class="nav-link nav-link-action" href="/cards/rookies/board/">← Back to board</a>
          <a class="nav-link nav-link-action" href="/cards/rookies/compare/?left=${esc(card.slug)}">Compare this profile →</a>
        </div>
      </section>

      <div class="card-columns">
        <div class="card-col">
          ${renderOfficialOutcome(card)}

          <section class="metrics card-panel">
            <div class="section-title">Model Scores</div>
            <div class="meta">Deterministic model components from canonical artifacts.</div>
            <div class="core-row model-score-grid">
              ${card.scores.map(scoreCell).join('')}
            </div>
          </section>

          <section class="metrics card-panel">
            <div class="section-title">Position-aware Evidence</div>
            <div class="meta">${esc(card.evidence?.readinessLabel ?? 'Evidence readiness unavailable')}</div>
            <div class="metric-family-filters" aria-label="Filter evidence metrics by family">
              ${metricFamilies.map((family) => `
                <button type="button" class="metric-family-btn ${selectedMetricFamily === family ? 'is-active' : ''}" data-metric-family="${esc(family)}" aria-pressed="${selectedMetricFamily === family ? 'true' : 'false'}">${esc(metricFamilyLabel(family))}</button>
              `).join('')}
            </div>
            ${includeProductionSpecials ? renderAgeAdjMetric(card.ageAdjustedProduction) : ''}
            ${includeProductionSpecials ? renderBoarMetricRow(card) : ''}
            ${filteredEvidenceMetrics.map(metricRow).join('') || '<div class="meta">No evidence metrics available.</div>'}
          </section>

          <section class="metrics card-panel">
            <div class="section-title">Season Stats</div>
            ${seasonsTable}
          </section>
        </div>

        <div class="card-col">
          <section class="card-panel">
            ${renderRadarChart(card.athleticScore, card.productionScore, card.draftCapitalScore, card.athleticSource)}
          </section>

          ${renderPprProjection(card.pprProjection, card)}

          ${(card.comps?.high != null || card.comps?.low != null)
            ? `<section class="metrics card-panel">
            <div class="section-title">Projection Comps</div>
            <div class="comp-grid">
              <div class="comp-card"><div class="pill-label">High-end</div><div class="comp-name">${esc(card.comps.high ?? 'N/A')}</div></div>
              <div class="comp-card"><div class="pill-label">Low-end</div><div class="comp-name">${esc(card.comps.low ?? 'N/A')}</div></div>
            </div>
          </section>`
            : ''}

          <section class="metrics card-panel">
            <div class="section-title">Research Notes & Translation Signals</div>
            <div class="meta evidence-caveat">Research notes may include non-canonical context. Treat as scouting context, not model input truth.</div>
            <div class="meta">${esc(evidenceSummary ?? 'Translation summary unavailable in current artifacts.')}</div>
            ${athleticNotIncorporated
              ? '<div class="meta evidence-caveat">Athletic testing data was not incorporated into the model score.</div>'
              : ''}
            ${athleticPartial
              ? `<div class="meta evidence-caveat">Partial athletic-testing composite (subset of combine events; not a full RAS).${card.athleticExplainer ? ` ${esc(card.athleticExplainer)}` : ''}</div>`
              : ''}
            ${translationFlags.length
              ? `<div class="tags tags-translation">${translationFlags.map((flag) => `<span class="tag">${esc(String(flag).replace(/_/g, ' '))}</span>`).join('')}</div>`
              : '<div class="meta">No translation evidence tags available.</div>'}
            ${contextFlags.length
              ? `<div class="tags tags-context">${contextFlags.map((flag) => `<span class="tag tag-context">${esc(String(flag).replace(/_/g, ' '))}</span>`).join('')}</div>`
              : ''}
          </section>

          ${card.tags.length
            ? `<section class="metrics card-panel"><div class="section-title">Scouting Tags</div><div class="tags">${card.tags.map((tag) => `<span class="tag">${esc(tag)}</span>`).join('')}</div></section>`
            : ''}
        </div>
      </div>
    </article>
  `;

    container.querySelectorAll('[data-metric-family]').forEach((button) => {
      button.addEventListener('click', () => {
        const nextFamily = button.getAttribute('data-metric-family') ?? 'all';
        if (!metricFamilies.includes(nextFamily) || selectedMetricFamily === nextFamily) return;
        selectedMetricFamily = nextFamily;
        render();
      });
    });
  }

  render();
}
