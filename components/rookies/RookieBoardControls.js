function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function option(value, label, selectedValue) {
  const selected = value === selectedValue ? ' selected' : '';
  return `<option value="${esc(value)}"${selected}>${esc(label)}</option>`;
}

const DRAFT_CLASS_OPTIONS = [2026, 2025, 2024, 2023, 2022];

export function renderRookieBoardControls({ positions, state }) {
  return `
    <form class="gallery-controls board-controls" id="rookie-board-controls">
      <label class="control-field">
        <span class="control-label">Sort board</span>
        <select data-board-control="sort">
          ${option('grade', 'Rookie Grade (desc)', state.sort)}
          ${option('rank', 'Class Rank (asc)', state.sort)}
          ${option('position', 'Position → Grade', state.sort)}
          ${option('edge', 'Model Edge ↑', state.sort)}
        </select>
      </label>

      <label class="control-field">
        <span class="control-label">Draft class</span>
        <select data-board-control="draftClass">
          ${option('ALL', 'All classes', state.draftClass)}
          ${DRAFT_CLASS_OPTIONS.map((yr) => option(String(yr), String(yr), state.draftClass)).join('')}
        </select>
      </label>

      <label class="control-field">
        <span class="control-label">Position</span>
        <select data-board-control="position">
          ${option('ALL', 'All positions', state.position)}
          ${positions.map((position) => option(position, position, state.position)).join('')}
        </select>
      </label>

      <label class="control-field">
        <span class="control-label">Board view</span>
        <select data-board-control="view">
          ${option('tiered', 'Grouped by tier', state.view)}
          ${option('flat', 'Flat ranking', state.view)}
        </select>
      </label>
    </form>
  `;
}
