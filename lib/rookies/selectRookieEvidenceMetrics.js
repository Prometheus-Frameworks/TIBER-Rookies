const ATH_LABELS = ['RAS', 'ATH (SPORQ)', 'ATH (partial)'];

const METRIC_PRIORITY = {
  // WR: production dominates; 40-yard + 3-cone matter for short WRs, vertical for both archetypes
  WR: ['Production Score', 'RAS', '40 Yard Dash (s)', '3-Cone (s)', 'Vertical (in)', 'Broad Jump (in)', 'Draft Capital Proxy'],
  // TE: speed score > 3-cone > broad jump per SPORQ research; burst events overrated
  TE: ['Production Score', 'RAS', '40 Yard Dash (s)', '3-Cone (s)', 'Broad Jump (in)', 'Vertical (in)', 'Draft Capital Proxy'],
  // RB: speed score most predictive; 3-cone uniquely underrated (McCaffrey, Bell, Rice)
  RB: ['Production Score', 'Draft Capital Proxy', '40 Yard Dash (s)', '3-Cone (s)', 'Broad Jump (in)', 'Vertical (in)', 'RAS'],
  QB: ['Draft Capital Proxy', 'Production Score', 'RAS', '40 Yard Dash (s)', '3-Cone (s)', 'Vertical (in)', 'Broad Jump (in)'],
};

const FALLBACK_PRIORITY = ['Production Score', 'Draft Capital Proxy', 'RAS', '40 Yard Dash (s)', '3-Cone (s)', 'Vertical (in)', 'Broad Jump (in)'];

function byPriority(position) {
  return METRIC_PRIORITY[position] ?? FALLBACK_PRIORITY;
}

/** Find an ATH metric by any of the possible ATH labels */
function findAthMetric(byLabel) {
  for (const label of ATH_LABELS) {
    const m = byLabel.get(label);
    if (m) return m;
  }
  return undefined;
}

function formatEvidenceLabel(metric) {
  if (!metric?.family) return metric.label;
  return `${metric.label} (${metric.family})`;
}

/**
 * Deterministically choose display-ready evidence metrics based on player position.
 * Returns only metrics with non-null values.
 */
export function selectRookieEvidenceMetrics(card, variant = 'full') {
  const cap = variant === 'compact' ? 4 : 6;
  const available = (card?.metrics ?? []).filter(
    (metric) => metric?.value != null && metric?.display != null
  );
  if (!available.length) return [];

  const byLabel = new Map(available.map((metric) => [metric.label, metric]));
  const ordered = byPriority(card?.identity?.position)
    .map((label) => label === 'RAS' ? (byLabel.get(label) ?? findAthMetric(byLabel)) : byLabel.get(label))
    .filter(Boolean)
    .map((metric) => ({
      ...metric,
      evidenceLabel: formatEvidenceLabel(metric),
    }));

  return ordered.slice(0, cap);
}
