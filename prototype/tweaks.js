// Tweaks — host-integrated tweak panel for prototype iteration.
(function () {
  const TWEAK_DEFAULS = /*EDITMODE-BEGIN*/{
    "accent": "orange",
    "density": "default",
    "framing": "contained",
    "view": "with_percentile"
  }/*EDITMODE-END*/;

  const state = { ...TWEAK_DEFAULS };
  applyAll();

  const panel = document.getElementById('tweaks-panel');
  const body = document.getElementById('tweaks-body');
  const closeBtn = document.getElementById('tweaks-close');

  const groups = [
    { key: 'accent', label: 'Accent color', options: ['orange', 'teal', 'purple'] },
    { key: 'density', label: 'Density', options: ['default', 'compact'] },
    { key: 'framing', label: 'Framing', options: ['contained', 'flush'] },
    { key: 'view', label: 'Metric view', options: ['with_percentile', 'normalized'] },
  ];

  function renderTweaks() {
    body.innerHTML = groups.map(g => `
      <div>
        <div class="tweak-group-label">${g.label}</div>
        <div class="tweak-buttons">
          ${g.options.map(opt => `
            <button class="tweak-btn ${state[g.key] === opt ? 'active' : ''}" data-key="${g.key}" data-val="${opt}">${opt}</button>
          `).join('')}
        </div>
      </div>
    `).join('');
    body.querySelectorAll('.tweak-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        state[btn.dataset.key] = btn.dataset.val;
        applyAll();
        renderTweaks();
        window.parent.postMessage({ type: '__edit_mode_set_keys', edits: { [btn.dataset.key]: btn.dataset.val } }, '*');
      });
    });
  }

  function applyAll() {
    document.body.dataset.accent = state.accent;
    document.body.dataset.density = state.density;
    document.body.dataset.framing = state.framing;
    document.body.dataset.view = state.view;
  }

  // Host integration
  window.addEventListener('message', (e) => {
    const msg = e.data || {};
    if (msg.type === '__activate_edit_mode') {
      panel.hidden = false;
      renderTweaks();
    } else if (msg.type === '__deactivate_edit_mode') {
      panel.hidden = true;
    }
  });
  try { window.parent.postMessage({ type: '__edit_mode_available' }, '*'); } catch (e) {}

  closeBtn.addEventListener('click', () => { panel.hidden = true; });
})();
