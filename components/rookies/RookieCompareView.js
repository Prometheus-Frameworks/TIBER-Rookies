import { compareRookies } from '/lib/rookies/compareRookies.js';
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

function pointForValue(cx, cy, radius, angle, value) {
  const safe = value == null ? 0 : Math.max(0, Math.min(100, Number(value) || 0));
  const r = (safe / 100) * radius;
  return `${(cx + r * Math.cos(angle)).toFixed(1)},${(cy + r * Math.sin(angle)).toFixed(1)}`;
}

function renderRadarChart(athleticScore, production, draftCapital, athleticSource) {
  const cx = 100, cy = 100, radius = 72;
  const athLabel = athleticSource === 'SPORQ' ? 'ATH (SPORQ)' : athleticSource === 'COMBINE_FALLBACK' ? 'ATH (partial)' : 'RAS';
  const axes = [
    { label: athLabel, angle: -Math.PI / 2, value: athleticScore },
    { label: 'Prod', angle: Math.PI / 6, value: production },
    { label: 'Capital', angle: (5 * Math.PI) / 6, value: draftCapital },
  ];

  const rings = [0.25, 0.5, 0.75].map((scale) => {
    const pts = axes.map((ax) => pointForValue(cx, cy, radius, ax.angle, scale * 100)).join(' ');
    const isAvg = scale === 0.5;
    return `<polygon points="${pts}" fill="none" stroke="#6f8098" stroke-width="${isAvg ? 1.6 : 0.8}" ${isAvg ? 'stroke-dasharray="4 3"' : ''} />`;
  }).join('');

  const dataPoints = axes.map((ax) => pointForValue(cx, cy, radius, ax.angle, ax.value)).join(' ');
  const axesLines = axes.map((ax) => {
    const end = pointForValue(cx, cy, radius, ax.angle, 100).split(',');
    return `<line x1="${cx}" y1="${cy}" x2="${end[0]}" y2="${end[1]}" stroke="#516179" stroke-width="1" />`;
  }).join('');
  const labels = axes.map((ax) => {
    const outer = pointForValue(cx, cy, radius + 16, ax.angle, 100).split(',');
    const rendered = ax.value == null ? '—' : Number(ax.value).toFixed(1);
    return `<text x="${outer[0]}" y="${outer[1]}" fill="#b5c7dd" font-size="9" text-anchor="middle">${esc(ax.label)} ${esc(rendered)}</text>`;
  }).join('');

  return `<svg class="radar-chart" viewBox="0 0 200 200" role="img" aria-label="Radar chart">${rings}${axesLines}<polygon points="${dataPoints}" fill="rgba(59,130,246,0.25)" stroke="#3b82f6" stroke-width="2" />${labels}</svg>`;
}

function renderPprInline(ppr) {
  if (!ppr) return '';
  const bandClass = {
    Elite: 'ppr-band-elite',
    Starter: 'ppr-band-starter',
    Contributor: 'ppr-band-contributor',
    Lottery: 'ppr-band-lottery',
  }[ppr.band] ?? 'ppr-band-lottery';
  return `<div class="compare-ppr-inline">
    <span class="ppr-stat-label">Yr1 PPR</span>
    <span class="compare-ppr-range">${esc(ppr.floor)}–${esc(ppr.ceiling)}</span>
    <span class="meta">med</span>
    <strong class="compare-ppr-median">${esc(ppr.median)}</strong>
    <span class="ppr-band ${bandClass}">${esc(ppr.band)}</span>
  </div>`;
}

function renderPlayerPanel(card, sideLabel) {
  const grade = card?.summary?.rookieGrade == null ? 'N/A' : card.summary.rookieGrade.toFixed(1);
  const rank = card?.summary?.classRank == null ? 'N/A' : `#${card.summary.classRank}`;
  const posRank = card?.summary?.posRank != null ? ` · ${esc(card.identity.position)} #${card.summary.posRank}` : '';
  const identityBits = [
    card.identity.positionLabel ?? card.identity.position,
    card.identity.schoolDisplay ?? card.identity.school,
    `Class ${card.identity.classYear}`,
    card.identity.height,
    card.identity.weight,
  ].filter(Boolean).join(' • ');

  const hasPostDraft = card.postDraftAdjustedGrade != null;
  const translationFlags = Array.isArray(card?.translationFlags) ? card.translationFlags : [];
  const contextFlags = Array.isArray(card?.contextSignals?.contextFlags) ? card.contextSignals.contextFlags : [];
  const evidenceSummary = card?.contextSignals?.evidenceSummary ?? null;

  return `
    <article class="compare-player compare-detail-panel">
      <div class="section-title">${esc(sideLabel)}</div>
      <h2 class="compare-name">
        <span class="avatar-pos pos-${esc(card.identity.position)}">${esc(card.identity.position)}</span>
        ${renderTeamLogos(card.identity.school, card.identity.nflTeam)}${esc(card.identity.name)}
      </h2>
      <div class="meta">${esc(identityBits)}</div>

      <div class="compare-detail-grade">
        <div class="compare-grade">${esc(grade)}</div>
        <div class="meta">Class ${esc(rank)}${posRank}</div>
        ${hasPostDraft ? `<div class="meta">Post-Draft: ${esc(card.postDraftAdjustedGrade.toFixed(1))} · Δ ${esc((card.postDraftDelta >= 0 ? '+' : '') + card.postDraftDelta.toFixed(1))}</div>` : ''}
        ${renderEvidenceTierBadge(card)}
      </div>

      <p class="meta compare-profile-summary">${esc(card.summary.profileSummary ?? card.summary.identityNote ?? '')}</p>

      <div class="compare-pills">
        ${card.summary.archetype ? `<span class="tag">${esc(card.summary.archetype)}</span>` : ''}
        ${card.summary.projection ? `<span class="tag">${esc(card.summary.projection)}</span>` : ''}
        ${card.youngBreakoutFlag
          ? `<span class="breakout-badge breakout-young">⚡ Age ${esc(card.breakoutAge)} breakout</span>`
          : (card.breakoutAge != null ? `<span class="breakout-badge breakout-late">Age ${esc(card.breakoutAge)} breakout</span>` : '')}
      </div>

      ${renderPprInline(card.pprProjection)}

      <div class="radar-section">
        <div class="section-title">Model Input Radar</div>
        ${renderRadarChart(card.athleticScore, card.productionScore, card.draftCapitalScore, card.athleticSource)}
      </div>

      ${evidenceSummary ? `<div class="meta compare-evidence-summary">${esc(evidenceSummary)}</div>` : ''}

      ${translationFlags.length ? `<div class="tags compare-translation-tags">${translationFlags.map((f) => `<span class="tag">${esc(String(f).replace(/_/g, ' '))}</span>`).join('')}</div>` : ''}
      ${contextFlags.length ? `<div class="tags" style="margin-top:4px">${contextFlags.map((f) => `<span class="tag tag-context">${esc(String(f).replace(/_/g, ' '))}</span>`).join('')}</div>` : ''}
    </article>`;
}

function renderScoreRows(scoreComparisons) {
  if (!scoreComparisons.length) return '<div class="meta">No shared scores available.</div>';
  return `<div class="compare-score-rows">${
    scoreComparisons.map((row) => {
      const leftWidth = row.leftValue == null ? 0 : Math.max(0, Math.min(100, row.leftValue));
      const rightWidth = row.rightValue == null ? 0 : Math.max(0, Math.min(100, row.rightValue));
      const leftWins = row.winner === 'left';
      const rightWins = row.winner === 'right';

      const barLeft = row.leftValue == null
        ? '<span class="meta">N/A</span>'
        : `<div class="compare-score-bar-row${leftWins ? ' is-winner' : ''}">
            <div class="compare-score-track">
              <div class="${leftWins ? 'compare-fill-winner' : 'compare-fill-dim'}" style="width:${leftWidth}%"></div>
            </div>
            <span class="compare-bar-value">${row.leftValue.toFixed(1)}</span>
          </div>`;

      const barRight = row.rightValue == null
        ? '<span class="meta">N/A</span>'
        : `<div class="compare-score-bar-row${rightWins ? ' is-winner' : ''}">
            <div class="compare-score-track">
              <div class="${rightWins ? 'compare-fill-winner' : 'compare-fill-dim'}" style="width:${rightWidth}%"></div>
            </div>
            <span class="compare-bar-value">${row.rightValue.toFixed(1)}</span>
          </div>`;

      return `<div class="compare-score-row">
        <div class="compare-score-label">${esc(row.label)}</div>
        <div class="compare-score-sides">
          <div class="compare-score-side"><span class="compare-side-tag">L</span>${barLeft}</div>
          <div class="compare-score-side"><span class="compare-side-tag">R</span>${barRight}</div>
        </div>
      </div>`;
    }).join('')
  }</div>`;
}

const STAT_LABELS = {
  completions: 'Comp', attempts: 'Att', completion_pct: 'Comp%',
  passing_yards: 'Pass Yds', passing_tds: 'Pass TD', interceptions: 'INT', yards_per_attempt: 'Y/A',
  rush_attempts: 'Att', rush_yards: 'Rush Yds', rush_tds: 'Rush TD', yards_per_carry: 'YPC',
  receptions: 'Rec', receiving_yards: 'Rec Yds', receiving_tds: 'Rec TD', yards_per_reception: 'YPR',
  targets: 'Tgt', note: null,
};

function formatStatEntry(key, value) {
  const label = STAT_LABELS[key];
  if (label === null) return null;
  const displayLabel = label ?? key.replace(/_/g, ' ');
  const displayValue = key === 'completion_pct' ? `${value}%` : value;
  return `${displayLabel}: ${displayValue}`;
}

function seasonSnapshot(card) {
  if (!card?.seasons?.length) {
    return '<div class="meta">College stats not yet available for this player.</div>';
  }
  const top = card.seasons.slice(0, 2);
  return `<table class="stats-table"><thead><tr><th>Season</th><th>School</th><th>Stats</th></tr></thead><tbody>${
    top.map((row) => {
      const statBits = Object.entries(row.statLine).map(([k, v]) => formatStatEntry(k, v)).filter(Boolean).join(' · ');
      return `<tr><td>${esc(row.season)}</td><td>${esc(row.team)}</td><td>${esc(statBits)}</td></tr>`;
    }).join('')
  }</tbody></table>`;
}

function evidenceRow(row) {
  const edgeClass = row.winner === 'left' ? 'compare-edge-left' : row.winner === 'right' ? 'compare-edge-right' : '';
  const edge = row.winner === 'tie' ? 'Even' : row.winner === 'left' ? 'Left leads' : 'Right leads';
  return `<tr><td>${esc(row.label)}</td><td>${esc(row.leftDisplay)}</td><td>${esc(row.rightDisplay)}</td><td class="${edgeClass}">${esc(edge)}</td></tr>`;
}

export function renderRookieCompareView(container, leftCard, rightCard) {
  const compared = compareRookies(leftCard, rightCard);

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
        ${renderPlayerPanel(leftCard, 'Left')}
        ${renderPlayerPanel(rightCard, 'Right')}
      </div>

      <section class="metrics">
        <div class="section-title">Score comparison</div>
        ${renderScoreRows(compared.scoreComparisons)}
      </section>

      <section class="metrics">
        <div class="section-title">Key evidence edges</div>
        ${compared.evidenceComparisons.length
          ? `<table class="stats-table compare-table"><thead><tr><th>Metric</th><th>Left</th><th>Right</th><th>Edge</th></tr></thead><tbody>${compared.evidenceComparisons.map(evidenceRow).join('')}</tbody></table>`
          : '<div class="meta">Insufficient shared evidence rows for a meaningful metric edge table.</div>'}
      </section>

      <section class="compare-grid compare-snapshot-grid">
        <article class="rookie-card compare-snapshot">
          <div class="section-title">Left · ${esc(leftCard.identity.name)} season stats</div>
          ${seasonSnapshot(leftCard)}
        </article>
        <article class="rookie-card compare-snapshot">
          <div class="section-title">Right · ${esc(rightCard.identity.name)} season stats</div>
          ${seasonSnapshot(rightCard)}
        </article>
      </section>

      <section class="metrics">
        <div class="section-title">Compare notes</div>
        <ul class="compare-notes">${compared.notes.map((note) => `<li>${esc(note)}</li>`).join('')}</ul>
        <div style="margin-top: 12px">
          <button type="button" class="btn" data-compare-csv-export>↓ Export comparison CSV</button>
        </div>
      </section>
    </section>
  `;
}
