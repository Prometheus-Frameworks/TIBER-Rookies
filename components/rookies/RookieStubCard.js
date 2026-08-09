import {
  getRookieStubReasonCopy,
  ROOKIE_STUB_STATUS_COPY,
} from '../../lib/rookies/rookieStubs.js';

function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function safeHttpUrl(value) {
  try {
    const url = new URL(String(value));
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null;
  } catch {
    return null;
  }
}

function renderProvenance(stub) {
  const provenance = stub.provenance;
  const sourceUrl = safeHttpUrl(provenance.source_url);
  const source = sourceUrl
    ? `<a href="${esc(sourceUrl)}" target="_blank" rel="noopener noreferrer">${esc(provenance.source_name)}</a>`
    : esc(provenance.source_name);

  return `
    <section class="card-panel stub-provenance-panel">
      <div class="section-title">Draft-fact provenance</div>
      <div class="stub-provenance-source">${source}</div>
      <div class="meta">Source status: ${esc(provenance.source_status)} · Upstream: ${esc(provenance.upstream_provenance_status)}</div>
      <div class="meta">Ingested from ${esc(provenance.ingested_from)} on ${esc(provenance.ingested_at)}</div>
    </section>
  `;
}

export function buildRookieStubCardHtml(stub) {
  return `
    <article class="rookie-card rookie-card-layout rookie-stub-card">
      <section class="hero-panel stub-hero-panel">
        <div class="section-title">TIBER Rookie Coverage Stub</div>
        <h1 class="player-name">
          <span class="avatar-pos pos-${esc(stub.position)}">${esc(stub.position)}</span>
          ${esc(stub.name)}
        </h1>
        <div class="unscored-state unscored-state-large">${ROOKIE_STUB_STATUS_COPY}</div>
        <p class="profile-summary">This page contains source-backed draft facts only. No Rookie Alpha score, tier, projection, model edge, or scouting evaluation is attached.</p>
      </section>

      <section class="card-actions-row">
        <div class="card-actions-copy">
          <div class="section-title">Coverage state</div>
          <div class="meta">Reason: ${esc(getRookieStubReasonCopy(stub.reason))}</div>
        </div>
        <div class="card-actions-links">
          <a class="nav-link nav-link-action" href="/cards/rookies/board/">← Back to board</a>
        </div>
      </section>

      <div class="stub-detail-grid">
        <section class="card-panel">
          <div class="section-title">Draft facts</div>
          <div class="identity-strip stub-fact-strip">
            <div class="pill"><div class="pill-label">NFL team</div><div class="pill-value">${esc(stub.team)}</div></div>
            <div class="pill"><div class="pill-label">Round</div><div class="pill-value">${esc(stub.round)}</div></div>
            <div class="pill"><div class="pill-label">Overall pick</div><div class="pill-value">${esc(stub.overallPick)}</div></div>
          </div>
        </section>
        ${renderProvenance(stub)}
      </div>
    </article>
  `;
}

export function renderRookieStubCard(container, stub) {
  container.innerHTML = buildRookieStubCardHtml(stub);
}
