import { ROOKIE_STUB_STATUS_COPY } from '../../lib/rookies/rookieStubs.js';

function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderPositionBadge(position) {
  const normalized = String(position ?? '').toUpperCase();
  const className = ['QB', 'RB', 'WR', 'TE'].includes(normalized) ? `pos-badge-${normalized}` : '';
  return `<span class="pos-badge ${className}">${esc(normalized)}</span>`;
}

function renderDraftFacts(row) {
  return `${esc(row.draftFacts.team)} · Round ${esc(row.draftFacts.round)} · Pick ${esc(row.draftFacts.overallPick)}`;
}

function renderMobileStub(row) {
  const slug = encodeURIComponent(String(row.slug ?? ''));
  return `
    <div class="board-mobile-card board-mobile-card-unscored">
      <div class="bmc-header">
        <span class="unscored-state">${ROOKIE_STUB_STATUS_COPY}</span>
      </div>
      <div class="bmc-name">
        <a class="board-player-name board-player-link" href="/cards/rookies/player.html?slug=${slug}">${esc(row.name)}</a>
      </div>
      <div class="bmc-meta">${renderPositionBadge(row.position)} · ${renderDraftFacts(row)}</div>
      <div class="bmc-thesis">No Rookie Alpha score or model-derived projection is attached to this source-backed draft record.</div>
      <div class="bmc-actions-utility">
        <a class="nav-link" href="/cards/rookies/player.html?slug=${slug}">Draft facts</a>
      </div>
    </div>
  `;
}

export function renderRookieStubBoardRow(row) {
  const slug = encodeURIComponent(String(row.slug ?? ''));
  return `
    <article class="board-row board-row-unscored">
      ${renderMobileStub(row)}
      <div class="board-cell board-rank board-num" data-label="Rank">—</div>
      <div class="board-cell board-player" data-label="Player">
        <div class="board-player-top">
          <a class="board-player-name board-player-link" href="/cards/rookies/player.html?slug=${slug}">${esc(row.name)}</a>
        </div>
        <div class="meta board-summary-line">${renderDraftFacts(row)}</div>
      </div>
      <div class="board-cell" data-label="Position">${renderPositionBadge(row.position)}</div>
      <div class="board-cell" data-label="School">${esc(row.school)}</div>
      <div class="board-cell board-grade" data-label="Pre/Post Grade">
        <span class="unscored-state">${ROOKIE_STUB_STATUS_COPY}</span>
      </div>
      <div class="board-cell" data-label="Tier"><span class="board-tier-pill board-tier-unscored">Not scored</span></div>
      <div class="board-cell" data-label="PPR Range"><span class="ppr-na">—</span></div>
      <div class="board-cell" data-label="Model Edge"><span class="delta-na">—</span></div>
      <div class="board-cell board-actions" data-label="Actions">
        <a class="nav-link" href="/cards/rookies/player.html?slug=${slug}">Draft facts</a>
      </div>
    </article>
  `;
}
