function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function groupByClass(cards) {
  const groups = new Map();
  for (const card of cards) {
    const yr = card.identity.classYear ?? 'Unknown';
    if (!groups.has(yr)) groups.set(yr, []);
    groups.get(yr).push(card);
  }
  // Sort each group by grade descending
  for (const group of groups.values()) {
    group.sort((a, b) => (b.summary.rookieGrade ?? -Infinity) - (a.summary.rookieGrade ?? -Infinity));
  }
  // Return class years newest-first
  return [...groups.entries()].sort((a, b) => Number(b[0]) - Number(a[0]));
}

function buildOptions(cards, selectedSlug) {
  const groups = groupByClass(cards);
  return groups.map(([yr, groupCards]) => {
    const opts = groupCards.map((card) => {
      const selected = card.slug === selectedSlug ? ' selected' : '';
      const grade = card.summary.rookieGrade != null ? ` ${card.summary.rookieGrade.toFixed(1)}` : '';
      return `<option value="${esc(card.slug)}"${selected}>${esc(card.identity.name)} (${esc(card.identity.position)}${grade})</option>`;
    }).join('');
    return `<optgroup label="${esc(String(yr))}">${opts}</optgroup>`;
  }).join('');
}

export function renderRookieCompareSelector({ cards, leftSlug, rightSlug }) {
  return `
    <form id="compare-selector" class="compare-selector compare-selector-redesign">
      <label class="control-field compare-control-panel compare-control-panel-left">
        <span class="control-label">Player A</span>
        <select name="left" data-compare-control="left">
          ${buildOptions(cards, leftSlug)}
        </select>
      </label>
      <button type="button" id="swap-compare-sides" class="compare-button compare-button-swap" aria-label="Swap compare sides">⇄</button>
      <label class="control-field compare-control-panel compare-control-panel-right">
        <span class="control-label">Player B</span>
        <select name="right" data-compare-control="right">
          ${buildOptions(cards, rightSlug)}
        </select>
      </label>
    </form>
  `;
}
