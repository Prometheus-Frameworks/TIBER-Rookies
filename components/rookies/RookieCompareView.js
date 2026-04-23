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

// ── Shared overlaid radar chart ───────────────────────────────────────────────

function pointForValue(cx, cy, radius, angle, value) {
  const safe = value == null ? 0 : Math.max(0, Math.min(100, Number(value) || 0));
  const r = (safe / 100) * radius;
  return `${(cx + r * Math.cos(angle)).toFixed(1)},${(cy + r * Math.sin(angle)).toFixed(1)}`;
}

function renderSharedRadar(leftCard, rightCard) {
  const cx = 110, cy = 110, radius = 88;
  const axes = [
    { angle: -Math.PI / 2,       leftVal: leftCard.athleticScore,   rightVal: rightCard.athleticScore,   label: 'ATH' },
    { angle: Math.PI / 6,        leftVal: leftCard.productionScore,  rightVal: rightCard.productionScore,  label: 'Prod' },
    { angle: (5 * Math.PI) / 6,  leftVal: leftCard.draftCapitalScore, rightVal: rightCard.draftCapitalScore, label: 'Capital' },
  ];

  const rings = [0.25, 0.5, 0.75].map((s) => {
    const pts = axes.map((ax) => pointForValue(cx, cy, radius, ax.angle, s * 100)).join(' ');
    const isAvg = s === 0.5;
    return `<polygon points="${pts}" fill="none" stroke="#6f8098" stroke-width="${isAvg ? 1.6 : 0.8}" ${isAvg ? 'stroke-dasharray="4 3"' : ''} />`;
  }).join('');

  const axisLines = axes.map((ax) => {
    const end = pointForValue(cx, cy, radius, ax.angle, 100).split(',');
    return `<line x1="${cx}" y1="${cy}" x2="${end[0]}" y2="${end[1]}" stroke="#516179" stroke-width="1" />`;
  }).join('');

  const axisLabels = axes.map((ax) => {
    const outer = pointForValue(cx, cy, radius + 18, ax.angle, 100).split(',');
    return `<text x="${outer[0]}" y="${outer[1]}" fill="#b5c7dd" font-size="9" text-anchor="middle">${esc(ax.label)}</text>`;
  }).join('');

  const leftPoints  = axes.map((ax) => pointForValue(cx, cy, radius, ax.angle, ax.leftVal)).join(' ');
  const rightPoints = axes.map((ax) => pointForValue(cx, cy, radius, ax.angle, ax.rightVal)).join(' ');

  const leftName  = leftCard.identity.name;
  const rightName = rightCard.identity.name;
  const athLabel  = leftCard.athleticSource === 'SPORQ' ? 'ATH (SPORQ)' : leftCard.athleticSource === 'COMBINE_FALLBACK' ? 'ATH (partial)' : 'RAS';

  function val(v) { return v == null ? '—' : Number(v).toFixed(1); }

  return `
    <div class="compare-radar-row">
      <div class="compare-radar-side compare-radar-side-left">
        <div class="compare-radar-metric">
          <span class="compare-radar-val compare-radar-val-left">${val(leftCard.athleticScore)}</span>
          <span class="compare-radar-label">${esc(athLabel)}</span>
        </div>
        <div class="compare-radar-metric">
          <span class="compare-radar-val compare-radar-val-left">${val(leftCard.productionScore)}</span>
          <span class="compare-radar-label">Production</span>
        </div>
        <div class="compare-radar-metric">
          <span class="compare-radar-val compare-radar-val-left">${val(leftCard.draftCapitalScore)}</span>
          <span class="compare-radar-label">Draft Capital</span>
        </div>
      </div>
      <div class="compare-radar-center">
        <svg class="compare-radar-svg" viewBox="0 0 220 220" role="img" aria-label="Overlaid radar chart">
          ${rings}${axisLines}
          <polygon points="${rightPoints}" fill="rgba(232,133,61,0.15)" stroke="#E8853D" stroke-width="2" />
          <polygon points="${leftPoints}"  fill="rgba(59,130,246,0.2)"  stroke="#3b82f6" stroke-width="2" />
          ${axisLabels}
        </svg>
        <div class="compare-radar-legend">
          <span class="compare-radar-legend-item"><span class="compare-radar-dot compare-radar-dot-left"></span>${esc(leftName)}</span>
          <span class="compare-radar-legend-item"><span class="compare-radar-dot compare-radar-dot-right"></span>${esc(rightName)}</span>
        </div>
      </div>
      <div class="compare-radar-side compare-radar-side-right">
        <div class="compare-radar-metric">
          <span class="compare-radar-label">${esc(athLabel)}</span>
          <span class="compare-radar-val compare-radar-val-right">${val(rightCard.athleticScore)}</span>
        </div>
        <div class="compare-radar-metric">
          <span class="compare-radar-label">Production</span>
          <span class="compare-radar-val compare-radar-val-right">${val(rightCard.productionScore)}</span>
        </div>
        <div class="compare-radar-metric">
          <span class="compare-radar-label">Draft Capital</span>
          <span class="compare-radar-val compare-radar-val-right">${val(rightCard.draftCapitalScore)}</span>
        </div>
      </div>
    </div>`;
}

// ── Top-edge highlight cards ──────────────────────────────────────────────────

function renderTopEdges(evidenceComparisons, scoreComparisons) {
  const candidates = [...evidenceComparisons, ...scoreComparisons]
    .filter((r) => r.winner !== 'tie' && Math.abs(r.delta ?? 0) >= 1.5)
    .sort((a, b) => Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0))
    .slice(0, 3);

  if (!candidates.length) return '';

  const cards = candidates.map((row) => {
    const isLeft  = row.winner === 'left';
    const strength = Math.abs(row.delta ?? 0) >= 4 ? 'STRONG' : 'EDGE';
    const leftDisplay  = row.leftDisplay  ?? (row.leftValue  != null ? row.leftValue.toFixed(1)  : 'N/A');
    const rightDisplay = row.rightDisplay ?? (row.rightValue != null ? row.rightValue.toFixed(1) : 'N/A');
    return `
      <div class="compare-top-edge-card compare-top-edge-${esc(row.winner)}">
        <div class="compare-top-edge-label">${esc(row.label)}</div>
        <div class="compare-top-edge-values">
          <span class="${isLeft ? 'compare-top-edge-winner' : 'compare-top-edge-other'}">${esc(String(leftDisplay))}</span>
          <span class="compare-top-edge-vs">vs</span>
          <span class="${!isLeft ? 'compare-top-edge-winner' : 'compare-top-edge-other'}">${esc(String(rightDisplay))}</span>
        </div>
        <div class="compare-top-edge-badge">${strength} → ${isLeft ? 'Left' : 'Right'}</div>
      </div>`;
  }).join('');

  return `<div class="compare-top-edges">${cards}</div>`;
}

// ── 3-column comparison table ─────────────────────────────────────────────────

function render3ColRow(leftHtml, labelHtml, rightHtml, winner, delta) {
  const absD = Math.abs(delta ?? 0);
  const edgeCls = winner === 'left' ? ' edge-left' : winner === 'right' ? ' edge-right' : '';
  const strongCls = absD >= 4 ? ' is-strong-edge' : absD >= 1.5 ? ' is-lean-edge' : '';
  const edgeTag = winner && winner !== 'tie'
    ? `<span class="compare-3col-edge-tag compare-3col-edge-${esc(winner)}">${winner === 'left' ? '◀' : '▶'} ${absD >= 4 ? 'STRONG' : 'EDGE'}</span>`
    : '';
  return `
    <div class="compare-3col-row${edgeCls}${strongCls}">
      <div class="compare-3col-left">${leftHtml}</div>
      <div class="compare-3col-center">${labelHtml}${edgeTag}</div>
      <div class="compare-3col-right">${rightHtml}</div>
    </div>`;
}

function formatScoreVal(v) {
  if (v == null) return '<span class="compare-3col-na">—</span>';
  const formatted = Number.isInteger(v) ? String(v) : v.toFixed(1);
  return `<strong>${esc(formatted)}</strong>`;
}

function renderScoreSection(scoreComparisons) {
  if (!scoreComparisons.length) return '';
  const rows = scoreComparisons.map((r) =>
    render3ColRow(formatScoreVal(r.leftValue), esc(r.label), formatScoreVal(r.rightValue), r.winner, r.delta)
  ).join('');
  return `<div class="compare-domain-header">Model Scores</div>${rows}`;
}

const DOMAIN_ORDER  = ['production', 'athletic', 'capital', 'context'];
const DOMAIN_LABELS = { production: 'Production', athletic: 'Athletic', capital: 'Draft Capital', context: 'Context' };

function renderEvidenceSections(evidenceComparisons) {
  if (!evidenceComparisons.length) return '';

  const byDomain = new Map();
  for (const row of evidenceComparisons) {
    const d = row.family ?? 'context';
    if (!byDomain.has(d)) byDomain.set(d, []);
    byDomain.get(d).push(row);
  }

  return [...byDomain.entries()]
    .sort(([a], [b]) => {
      const ai = DOMAIN_ORDER.indexOf(a), bi = DOMAIN_ORDER.indexOf(b);
      return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi);
    })
    .map(([domain, rows]) => {
      const header = DOMAIN_LABELS[domain] ?? domain.charAt(0).toUpperCase() + domain.slice(1);
      const rowsHtml = rows.map((r) =>
        render3ColRow(`<span>${esc(r.leftDisplay)}</span>`, esc(r.label), `<span>${esc(r.rightDisplay)}</span>`, r.winner, r.delta)
      ).join('');
      return `<div class="compare-domain-header">${esc(header)}</div>${rowsHtml}`;
    }).join('');
}

// ── Player header panels ──────────────────────────────────────────────────────

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
  return `${label ?? key.replace(/_/g, ' ')}: ${key === 'completion_pct' ? `${value}%` : value}`;
}

function seasonSnapshot(card) {
  if (!card?.seasons?.length) return '<div class="meta">College stats not yet available.</div>';
  return `<table class="stats-table"><thead><tr><th>Season</th><th>School</th><th>Stats</th></tr></thead><tbody>${
    card.seasons.slice(0, 2).map((row) => {
      const bits = Object.entries(row.statLine).map(([k, v]) => formatStatEntry(k, v)).filter(Boolean).join(' · ');
      return `<tr><td>${esc(row.season)}</td><td>${esc(row.team)}</td><td>${esc(bits)}</td></tr>`;
    }).join('')
  }</tbody></table>`;
}

function renderPlayerHeader(card, sideLabel) {
  const grade = card?.summary?.rookieGrade == null ? 'N/A' : card.summary.rookieGrade.toFixed(1);
  const rank  = card?.summary?.classRank == null ? 'N/A' : `#${card.summary.classRank}`;
  const posRank = card?.summary?.posRank != null ? ` · ${esc(card.identity.position)} #${card.summary.posRank}` : '';
  const identityBits = [
    card.identity.positionLabel ?? card.identity.position,
    card.identity.schoolDisplay ?? card.identity.school,
    `Class ${card.identity.classYear}`,
  ].filter(Boolean).join(' · ');

  const hasPostDraft  = card.postDraftAdjustedGrade != null;
  const translation   = Array.isArray(card?.translationFlags) ? card.translationFlags : [];
  const contextFlags  = Array.isArray(card?.contextSignals?.contextFlags) ? card.contextSignals.contextFlags : [];
  const evidenceSummary = card?.contextSignals?.evidenceSummary ?? null;
  const ppr = card.pprProjection;
  const pprNote = ppr ? `Yr1 PPR ${esc(ppr.floor)}–${esc(ppr.ceiling)} med ${esc(ppr.median)}` : '';

  return `
    <article class="compare-player compare-player-panel">
      <div class="compare-player-panel-top">
        <div class="compare-player-panel-identity">
          <div class="section-title">${esc(sideLabel)}</div>
          <h2 class="compare-name">
            <span class="avatar-pos pos-${esc(card.identity.position)}">${esc(card.identity.position)}</span>
            ${renderTeamLogos(card.identity.school, card.identity.nflTeam)}${esc(card.identity.name)}
          </h2>
          <div class="meta">${esc(identityBits)}</div>
        </div>
        <div class="compare-player-panel-grade">
          <div class="compare-grade">${esc(grade)}</div>
          <div class="meta">Class ${esc(rank)}${posRank}</div>
          ${hasPostDraft ? `<div class="meta">Post ${esc(card.postDraftAdjustedGrade.toFixed(1))} Δ ${esc((card.postDraftDelta >= 0 ? '+' : '') + card.postDraftDelta.toFixed(1))}</div>` : ''}
          ${renderEvidenceTierBadge(card)}
        </div>
      </div>

      <p class="meta compare-profile-summary">${esc(card.summary.profileSummary ?? card.summary.identityNote ?? '')}</p>

      <div class="compare-pills">
        ${card.summary.archetype ? `<span class="tag">${esc(card.summary.archetype)}</span>` : ''}
        ${card.summary.projection ? `<span class="tag">${esc(card.summary.projection)}</span>` : ''}
        ${card.youngBreakoutFlag
          ? `<span class="breakout-badge breakout-young">⚡ Age ${esc(card.breakoutAge)} breakout</span>`
          : card.breakoutAge != null ? `<span class="breakout-badge breakout-late">Age ${esc(card.breakoutAge)} breakout</span>` : ''}
      </div>

      ${pprNote ? `<div class="meta compare-ppr-note" style="margin-top:6px">${pprNote}</div>` : ''}

      <details class="compare-expandable">
        <summary class="compare-expand-trigger">Full context ↓</summary>
        <div class="compare-expand-content">
          ${evidenceSummary ? `<p class="meta">${esc(evidenceSummary)}</p>` : ''}
          ${translation.length ? `<div class="tags" style="margin-top:8px">${translation.map((f) => `<span class="tag">${esc(String(f).replace(/_/g, ' '))}</span>`).join('')}</div>` : ''}
          ${contextFlags.length ? `<div class="tags" style="margin-top:6px">${contextFlags.map((f) => `<span class="tag tag-context">${esc(String(f).replace(/_/g, ' '))}</span>`).join('')}</div>` : ''}
          <div style="margin-top:12px">${seasonSnapshot(card)}</div>
        </div>
      </details>
    </article>`;
}

// ── PPR side-by-side ──────────────────────────────────────────────────────────

function renderPprSideBySide(leftCard, rightCard) {
  const leftPpr  = leftCard.pprProjection;
  const rightPpr = rightCard.pprProjection;
  if (!leftPpr && !rightPpr) return '';

  function pprPanel(card, ppr) {
    if (!ppr) return `<div class="compare-ppr-panel"><div class="meta">${esc(card.identity.name)}: No projection</div></div>`;
    const bandClass = { Elite: 'ppr-band-elite', Starter: 'ppr-band-starter', Contributor: 'ppr-band-contributor', Lottery: 'ppr-band-lottery' }[ppr.band] ?? 'ppr-band-lottery';
    const floor = Number(ppr.floor), median = Number(ppr.median), ceiling = Number(ppr.ceiling);
    const maxScale = Math.max(1, Math.ceil(Math.max(floor, median, ceiling) / 25) * 25);
    const rangeLeft  = Math.max(0, Math.min(100, (floor / maxScale) * 100));
    const rangeWidth = Math.max(0, Math.min(100 - rangeLeft, ((ceiling - floor) / maxScale) * 100));
    const medianLeft = Math.max(0, Math.min(100, (median / maxScale) * 100));
    return `
      <div class="compare-ppr-panel">
        <div class="section-title">${esc(card.identity.name)}</div>
        <div class="compare-ppr-values">
          <span class="ppr-stat-label">Flr</span><strong>${esc(ppr.floor)}</strong>
          <span class="ppr-stat-label">Med</span><strong style="color:var(--accent)">${esc(ppr.median)}</strong>
          <span class="ppr-stat-label">Ceil</span><strong>${esc(ppr.ceiling)}</strong>
          <span class="ppr-band ${bandClass}">${esc(ppr.band)}</span>
        </div>
        <div class="ppr-range-viz" style="margin-top:8px">
          <div class="ppr-range-track">
            <div class="ppr-range-fill" style="left:${rangeLeft}%;width:${rangeWidth}%"></div>
            <div class="ppr-range-median-marker" style="left:${medianLeft}%"></div>
          </div>
        </div>
      </div>`;
  }

  return `
    <section class="metrics">
      <div class="section-title">Year 1 PPR projection</div>
      <div class="compare-ppr-grid">
        ${pprPanel(leftCard, leftPpr)}
        ${pprPanel(rightCard, rightPpr)}
      </div>
    </section>`;
}

// ── Main export ───────────────────────────────────────────────────────────────

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
        ${renderPlayerHeader(leftCard, 'Left')}
        ${renderPlayerHeader(rightCard, 'Right')}
      </div>

      ${renderTopEdges(compared.evidenceComparisons, compared.scoreComparisons)}

      <div class="compare-3col-table">
        <div class="compare-3col-name-row">
          <div class="compare-3col-left compare-3col-name">${esc(leftCard.identity.name)}</div>
          <div class="compare-3col-center"></div>
          <div class="compare-3col-right compare-3col-name">${esc(rightCard.identity.name)}</div>
        </div>

        ${renderScoreSection(compared.scoreComparisons)}
        ${renderSharedRadar(leftCard, rightCard)}
        ${renderEvidenceSections(compared.evidenceComparisons)}
      </div>

      ${renderPprSideBySide(leftCard, rightCard)}

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
        <ul class="compare-notes">${compared.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul>
        <div style="margin-top:12px">
          <button type="button" class="btn" data-compare-csv-export>↓ Export comparison CSV</button>
        </div>
      </section>

    </section>
  `;
}
