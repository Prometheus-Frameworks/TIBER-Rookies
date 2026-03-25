function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function selectField({ id, label, value, options }) {
  return `
    <label class="control-field" for="${esc(id)}">
      <span class="control-label">${esc(label)}</span>
      <select id="${esc(id)}" data-control="${esc(id)}">
        ${options.map((option) => `<option value="${esc(option.value)}" ${option.value === value ? 'selected' : ''}>${esc(option.label)}</option>`).join('')}
      </select>
    </label>
  `;
}

export function renderRookieGalleryControls({ positions, tags, state }) {
  return `
    <section class="gallery-controls">
      ${selectField({
        id: 'sort',
        label: 'Sort',
        value: state.sort,
        options: [
          { value: 'grade', label: 'Rookie Grade (desc)' },
          { value: 'position', label: 'Position (QB/RB/WR/TE)' },
        ],
      })}
      ${selectField({
        id: 'position',
        label: 'Position',
        value: state.position,
        options: [{ value: 'ALL', label: 'All positions' }, ...positions.map((position) => ({ value: position, label: position }))],
      })}
      ${selectField({
        id: 'tag',
        label: 'Profile tag',
        value: state.tag,
        options: [{ value: 'ALL', label: 'All profiles' }, ...tags.map((tag) => ({ value: tag, label: tag }))],
      })}
    </section>
  `;
}
