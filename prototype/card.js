// Rookie card renderer — pure JS, reads window.ROOKIES.
(function () {
  const STATE = {
    slug: localStorage.getItem('tiber-proto-slug') || window.ROOKIES[0].slug,
    metricFilter: 'all',
    queue: JSON.parse(localStorage.getItem('tiber-proto-queue') || '[]'),
  };

  function esc(s) {
    return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  const EVIDENCE_LABELS = {
    strong_supported_edge: 'Strong Supported Edge',
    moderate_edge: 'Moderate Edge',
    consensus_aligned: 'Consensus Aligned',
    watchlist_outlier: 'Watchlist Outlier',
    insufficient_evidence: 'Insufficient Evidence',
  };
  const EVIDENCE_TIER_CLASS = {
    strong_supported_edge: '',
    moderate_edge: 'tier-teal',
    consensus_aligned: 'tier-gray',
    watchlist_outlier: 'tier-purple',
  };

  function getCard() {
    return window.ROOKIES.find(r => r.slug === STATE.slug) || window.ROOKIES[0];
  }

  // ─── Player switcher ─────────────────────────────────────────────────────
  function renderSwitcher() {
    const root = document.getElementById('player-switcher');
    const sorted = [...window.ROOKIES].sort((a,b) => a.summary.classRank - b.summary.classRank);
    root.innerHTML = sorted.map(r => `
      <div class="player-chip ${r.slug === STATE.slug ? 'active' : ''}" data-slug="${r.slug}">
        <span class="chip-rank">#${r.summary.classRank}</span>
        <span class="chip-name">${esc(r.identity.name)}</span>
        <span class="chip-pos pos-badge pos-badge-${r.identity.position}">${r.identity.position}</span>
      </div>
    `).join('');
    root.querySelectorAll('.player-chip').forEach(el => {
      el.addEventListener('click', () => {
        STATE.slug = el.dataset.slug;
        localStorage.setItem('tiber-proto-slug', STATE.slug);
        renderAll();
      });
    });
  }

  // ─── Radar ───────────────────────────────────────────────────────────────
  function renderRadar(card) {
    const cx = 130, cy = 130, r = 88;
    const athLabel = card.athleticSource === 'SPORQ' ? 'ATH (SPORQ)' : 'ATH (combine)';
    const axes = [
      { label: athLabel, angle: -Math.PI/2, value: card.scores[1].value },
      { label: 'Production', angle: Math.PI/6, value: card.scores[2].value },
      { label: 'Draft Capital', angle: (5*Math.PI)/6, value: card.scores[3].value },
    ];
    const point = (angle, v) => {
      const sv = Math.max(0, Math.min(100, Number(v)||0));
      const sr = (sv/100)*r;
      return `${(cx + sr*Math.cos(angle)).toFixed(1)},${(cy + sr*Math.sin(angle)).toFixed(1)}`;
    };
    const rings = [0.25, 0.5, 0.75, 1.0].map(s => {
      const pts = axes.map(a => point(a.angle, s*100)).join(' ');
      const dash = s === 0.5 ? 'stroke-dasharray="3 3"' : '';
      const sw = s === 1.0 ? 1.2 : 0.8;
      return `<polygon points="${pts}" fill="none" stroke="#3a2e20" stroke-width="${sw}" ${dash}/>`;
    }).join('');
    const lines = axes.map(a => {
      const p = point(a.angle, 100).split(',');
      return `<line x1="${cx}" y1="${cy}" x2="${p[0]}" y2="${p[1]}" stroke="#2E2318" stroke-width="1"/>`;
    }).join('');
    const dataPts = axes.map(a => point(a.angle, a.value)).join(' ');
    const labels = axes.map(a => {
      const p = point(a.angle, 122).split(',');
      const valP = point(a.angle, 108).split(',');
      return `
        <text x="${p[0]}" y="${p[1]}" class="radar-label" text-anchor="middle" dominant-baseline="middle">${esc(a.label)}</text>
        <text x="${valP[0]}" y="${parseFloat(valP[1])+12}" class="radar-value" text-anchor="middle">${Math.round(a.value)}</text>
      `;
    }).join('');
    return `
      <svg class="radar-svg" viewBox="0 0 260 260" role="img" aria-label="Model input radar">
        ${rings}${lines}
        <polygon points="${dataPts}" fill="rgba(232,133,61,0.22)" stroke="#E8853D" stroke-width="2"/>
        ${axes.map(a => { const p = point(a.angle, a.value).split(','); return `<circle cx="${p[0]}" cy="${p[1]}" r="3.5" fill="#E8853D"/>`; }).join('')}
        ${labels}
      </svg>
    `;
  }

  // ─── Hero ────────────────────────────────────────────────────────────────
  function renderHero(card) {
    const evLabel = EVIDENCE_LABELS[card.evidenceTier] || '';
    const evClass = `evidence-tier-${card.evidenceTier}`;
    const tierClass = EVIDENCE_TIER_CLASS[card.evidenceTier] || '';
    return `
      <div class="hero-panel">
        <div class="hero-top">
          <div class="hero-left">
            <div class="hero-eyebrow"><span class="dot"></span>TIBER Rookie Card · Pre-draft v0 · ${esc(card.identity.school)}</div>
            <h1 class="player-name">
              <span class="avatar-pos pos-${card.identity.position}">${esc(card.identity.position)}</span>${esc(card.identity.name)}
            </h1>
            <div class="player-meta-row">
              <span class="meta-item"><span class="meta-label">Age</span> ${esc(card.identity.age)}</span>
              <span class="meta-sep">·</span>
              <span class="meta-item"><span class="meta-label">Class</span> ${esc(card.identity.classYear)}</span>
              <span class="meta-sep">·</span>
              <span class="meta-item"><span class="meta-label">Ht</span> ${esc(card.identity.height)}</span>
              <span class="meta-sep">·</span>
              <span class="meta-item"><span class="meta-label">Wt</span> ${esc(card.identity.weight)}</span>
            </div>
            <p class="profile-summary">${esc(card.summary.profileSummary)}</p>
          </div>
          <div class="hero-right">
            <div class="grade-label">Rookie Grade</div>
            <div class="grade-value">${card.summary.rookieGrade.toFixed(1)}</div>
            <div class="grade-sub">
              <span>Class <strong>#${card.summary.classRank}</strong></span>
              <span>${esc(card.identity.position)} <strong>#${card.summary.posRank}</strong></span>
            </div>
            <span class="tier-badge-small ${tierClass}">${esc(evLabel)}</span>
          </div>
        </div>
        <div class="hero-identity-strip">
          <div class="strip-cell"><div class="strip-label">Archetype</div><div class="strip-value">${esc(card.summary.archetype)}</div></div>
          <div class="strip-cell"><div class="strip-label">Projection</div><div class="strip-value">${esc(card.summary.projection)}</div></div>
          <div class="strip-cell"><div class="strip-label">High comp</div><div class="strip-value">${esc(card.comps.high)}</div></div>
          <div class="strip-cell"><div class="strip-label">Breakout</div><div class="strip-value">Age ${esc(card.breakoutAge)} · ${esc(card.breakoutLabel)}</div></div>
        </div>
      </div>
    `;
  }

  // ─── Scores ──────────────────────────────────────────────────────────────
  function renderScores(card) {
    const fillClasses = ['', 'fill-blue', 'fill-teal', '', ''];
    const cells = card.scores.map((s, i) => {
      const isHero = i === 0;
      const isEdge = s.label === 'Model Edge';
      let deltaClass = '';
      let formatted = s.value.toFixed(1);
      if (isEdge) {
        formatted = (s.value >= 0 ? '+' : '') + s.value.toFixed(1);
        deltaClass = s.value >= 3 ? 'delta-bull' : s.value <= -3 ? 'delta-bear' : 'delta-neutral';
      }
      const width = isEdge ? Math.min(100, Math.abs(s.value) * 10) : Math.min(100, Math.max(0, s.value));
      return `
        <div class="score-cell">
          <div class="score-cell-label">${esc(s.label)}</div>
          <div class="score-cell-value ${isHero ? 'is-hero' : ''} ${deltaClass}">${esc(formatted)}</div>
          <div class="score-cell-bar"><div class="score-cell-fill ${fillClasses[i] || ''}" style="width:${width}%"></div></div>
        </div>
      `;
    }).join('');
    return `
      <div class="card-panel">
        <div class="section-title"><span class="title-accent"></span>Model Scores<span class="title-meta">0-100 scale</span></div>
        <div class="score-grid">${cells}</div>
      </div>
    `;
  }

  // ─── PPR projection ──────────────────────────────────────────────────────
  function renderPPR(card) {
    const ppr = card.pprProjection;
    // range viz positions assume 0-350 range
    const MAX = 350;
    const leftPct = (ppr.floor / MAX) * 100;
    const widthPct = ((ppr.ceiling - ppr.floor) / MAX) * 100;
    const medianPct = (ppr.median / MAX) * 100;
    return `
      <div class="card-panel ppr-panel">
        <div class="section-title"><span class="title-accent"></span>Year-1 PPR Projection<span class="title-meta">Floor / Median / Ceiling</span></div>
        <div class="ppr-row">
          <div class="ppr-stat"><div class="ppr-stat-label">Floor</div><div class="ppr-stat-value">${ppr.floor}</div></div>
          <div class="ppr-stat is-median"><div class="ppr-stat-label">Median</div><div class="ppr-stat-value">${ppr.median}</div></div>
          <div class="ppr-stat"><div class="ppr-stat-label">Ceiling</div><div class="ppr-stat-value">${ppr.ceiling}</div></div>
          <span class="ppr-band ppr-band-${ppr.band}">${esc(ppr.band)}</span>
        </div>
        <div class="ppr-range-viz">
          <div class="ppr-range-fill" style="left:${leftPct}%; width:${widthPct}%"></div>
          <div class="ppr-range-median" style="left:${medianPct}%"></div>
          <div class="ppr-range-axis"><span>0</span><span>100</span><span>200</span><span>300</span></div>
        </div>
      </div>
    `;
  }

  // ─── Metrics ─────────────────────────────────────────────────────────────
  function metricFamilies(card) {
    const set = new Set(card.metrics.map(m => m.family));
    return ['all', ...Array.from(set)];
  }

  function renderMetrics(card) {
    const families = metricFamilies(card);
    const filterBtns = families.map(f => `
      <button class="metric-filter-btn ${STATE.metricFilter === f ? 'active' : ''}" data-family="${esc(f)}">${esc(f === 'all' ? 'All' : f)}</button>
    `).join('');
    const visible = card.metrics.filter(m => STATE.metricFilter === 'all' || m.family === STATE.metricFilter);

    const ageAdj = card.ageAdjustedProduction;
    const boar = card.breakoutAgeRating;

    const rows = [];
    // Age-adjusted + BOAR as special rows above the filtered ones
    if (STATE.metricFilter === 'all' || STATE.metricFilter === 'production') {
      rows.push(`
        <div class="metric-row">
          <div class="metric-header">
            <span class="metric-label">Age-Adjusted Production</span>
            <span class="metric-value">${ageAdj.toFixed(1)}</span>
          </div>
          <div class="metric-track"><div class="metric-fill family-production" style="width:${Math.max(0,Math.min(100,ageAdj))}%"></div></div>
        </div>
      `);
      rows.push(`
        <div class="metric-row">
          <div class="metric-header">
            <span class="metric-label">Breakout Age Rating (BOAR)</span>
            <span class="metric-value">${boar}</span>
          </div>
          <div class="metric-track"><div class="metric-fill family-production" style="width:${Math.max(0,Math.min(100,boar))}%"></div></div>
        </div>
      `);
    }
    for (const m of visible) {
      rows.push(`
        <div class="metric-row">
          <div class="metric-header">
            <span class="metric-label">${esc(m.label)}</span>
            <span class="metric-value">${esc(m.display)} <span class="metric-percentile">p${m.percent}</span></span>
          </div>
          <div class="metric-track"><div class="metric-fill family-${esc(m.family)}" style="width:${m.percent}%"></div></div>
        </div>
      `);
    }

    return `
      <div class="card-panel">
        <div class="section-title"><span class="title-accent"></span>Position-Aware Evidence<span class="title-meta">${esc(card.identity.positionLabel)}</span></div>
        <div class="metric-filter-row">${filterBtns}</div>
        <div class="metrics-grid">${rows.join('')}</div>
      </div>
    `;
  }

  // ─── Radar panel ─────────────────────────────────────────────────────────
  function renderRadarPanel(card) {
    return `
      <div class="card-panel">
        <div class="section-title"><span class="title-accent"></span>Model Input Radar<span class="title-meta">Athletic · Production · Draft Capital</span></div>
        <div class="radar-wrap">${renderRadar(card)}</div>
      </div>
    `;
  }

  // ─── Comps ───────────────────────────────────────────────────────────────
  function renderComps(card) {
    return `
      <div class="card-panel">
        <div class="section-title"><span class="title-accent"></span>Projection Comps</div>
        <div class="comp-grid">
          <div class="comp-card">
            <div class="comp-card-label comp-high">High-end</div>
            <div class="comp-card-name">${esc(card.comps.high)}</div>
          </div>
          <div class="comp-card">
            <div class="comp-card-label comp-low">Low-end</div>
            <div class="comp-card-name">${esc(card.comps.low)}</div>
          </div>
        </div>
      </div>
    `;
  }

  // ─── Translation / evidence ──────────────────────────────────────────────
  function renderTranslation(card) {
    const flags = (card.translationFlags || []).map(f =>
      `<span class="flag-pill">${esc(f.replace(/_/g, ' '))}</span>`
    ).join('');
    const ctxFlags = (card.contextFlags || []).map(f =>
      `<span class="tag tag-neutral">${esc(f.replace(/_/g, ' '))}</span>`
    ).join('');
    return `
      <div class="card-panel">
        <div class="section-title"><span class="title-accent"></span>Why This Profile Translates<span class="title-meta">Deterministic</span></div>
        <p class="profile-summary" style="margin: 0 0 12px; font-size: 13px;">${esc(card.evidenceSummary)}</p>
        <div class="tag-row" style="margin-bottom: 10px;">${flags}</div>
        ${ctxFlags ? `<div class="tag-row">${ctxFlags}</div>` : ''}
      </div>
    `;
  }

  // ─── Stats table ─────────────────────────────────────────────────────────
  const STAT_LABELS = {
    completions:'Comp', attempts:'Att', completion_pct:'Comp%',
    passing_yards:'Pass Yds', passing_tds:'Pass TD', interceptions:'INT', yards_per_attempt:'Y/A',
    rush_attempts:'Att', rush_yards:'Rush Yds', rush_tds:'Rush TD', yards_per_carry:'YPC',
    receptions:'Rec', receiving_yards:'Rec Yds', receiving_tds:'Rec TD',
    yards_per_reception:'YPR', targets:'Tgt',
  };

  function renderStats(card) {
    const rows = card.seasons.map(s => {
      const kvs = Object.entries(s.statLine).map(([k,v]) => {
        const label = STAT_LABELS[k] || k;
        const val = k === 'completion_pct' ? `${v}%` : v;
        return `<span class="stat-kv"><span class="stat-k">${esc(label)}</span><span class="stat-v">${esc(val)}</span></span>`;
      }).join('');
      return `<tr><td class="stat-season">${esc(s.season)}</td><td>${esc(s.team)}</td><td class="stat-line">${kvs}</td></tr>`;
    }).join('');
    return `
      <div class="card-panel stats-panel">
        <div class="section-title"><span class="title-accent"></span>College Production<span class="title-meta">${card.seasons.length}-season history</span></div>
        <table class="stats-table">
          <thead><tr><th>Season</th><th>School</th><th>Line</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  }

  // ─── Actions ─────────────────────────────────────────────────────────────
  function renderActions(card) {
    const queued = STATE.queue.includes(card.slug);
    return `
      <div class="actions-bar">
        <button class="btn btn-primary" id="act-compare"><span class="btn-icon">⇄</span>Compare</button>
        <button class="btn ${queued ? 'btn-queued' : ''}" id="act-queue">
          <span class="btn-icon">${queued ? '✓' : '+'}</span>${queued ? 'Queued' : 'Add to queue'}
        </button>
        <button class="btn" id="act-export"><span class="btn-icon">↓</span>Export</button>
        <button class="btn" id="act-notes"><span class="btn-icon">✎</span>Draft note</button>
      </div>
    `;
  }

  // ─── Tags / summary at bottom ────────────────────────────────────────────
  function renderTags(card) {
    const tags = card.tags.map(t => `<span class="tag tag-teal">${esc(t)}</span>`).join('');
    return `<div class="card-panel panel-deep"><div class="section-title"><span class="title-accent"></span>Scouting Tags</div><div class="tag-row">${tags}</div></div>`;
  }

  // ─── Breadcrumb / main render ────────────────────────────────────────────
  function renderCrumb(card) {
    document.getElementById('crumb-pos').textContent = card.identity.position;
    document.getElementById('crumb-name').textContent = card.identity.name;
    document.title = `TIBER · ${card.identity.name}`;
  }

  function renderAll() {
    const card = getCard();
    renderCrumb(card);
    renderSwitcher();
    const root = document.getElementById('card-root');
    root.innerHTML = `
      <div class="rookie-card">
        <div class="card-col">
          ${renderHero(card)}
          ${renderActions(card)}
          ${renderScores(card)}
          ${renderMetrics(card)}
          ${renderStats(card)}
        </div>
        <div class="card-col">
          ${renderRadarPanel(card)}
          ${renderPPR(card)}
          ${renderComps(card)}
          ${renderTranslation(card)}
          ${renderTags(card)}
        </div>
      </div>
    `;

    // Wire interactions
    root.querySelectorAll('.metric-filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        STATE.metricFilter = btn.dataset.family;
        renderAll();
      });
    });
    const qBtn = document.getElementById('act-queue');
    if (qBtn) qBtn.addEventListener('click', () => {
      const c = getCard();
      if (STATE.queue.includes(c.slug)) {
        STATE.queue = STATE.queue.filter(s => s !== c.slug);
      } else {
        STATE.queue.push(c.slug);
      }
      localStorage.setItem('tiber-proto-queue', JSON.stringify(STATE.queue));
      renderAll();
    });
    ['act-compare','act-export','act-notes'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('click', () => {
        el.style.borderColor = 'var(--accent)';
        setTimeout(() => { el.style.borderColor = ''; }, 300);
      });
    });
  }

  window.TIBER_RENDER = renderAll;
  document.addEventListener('DOMContentLoaded', renderAll);
})();
