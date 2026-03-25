function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function option(card, selectedSlug) {
  const selected = card.slug === selectedSlug ? ' selected' : '';
  return `<option value="${esc(card.slug)}"${selected}>${esc(card.identity.name)} (${esc(card.identity.position)})</option>`;
}

export function renderRookieCompareSelector({ cards, leftSlug, rightSlug }) {
  return `
    <form id="compare-selector" class="compare-selector">
      <label class="control-field">
        <span class="control-label">Left rookie</span>
        <select name="left" data-compare-control="left">
          ${cards.map((card) => option(card, leftSlug)).join('')}
        </select>
      </label>
      <label class="control-field">
        <span class="control-label">Right rookie</span>
        <select name="right" data-compare-control="right">
          ${cards.map((card) => option(card, rightSlug)).join('')}
        </select>
      </label>
      <button type="button" id="swap-compare-sides" class="compare-button">Swap</button>
    </form>
  `;
}
