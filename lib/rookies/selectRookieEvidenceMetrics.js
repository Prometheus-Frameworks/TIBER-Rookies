const METRIC_PRIORITY = {
  WR: ['Production Score', 'RAS', '40 Yard Dash (s)', 'Vertical (in)', 'Broad Jump (in)', 'Draft Capital Proxy'],
  TE: ['Production Score', 'RAS', 'Vertical (in)', 'Broad Jump (in)', '40 Yard Dash (s)', 'Draft Capital Proxy'],
  RB: ['Production Score', 'Draft Capital Proxy', '40 Yard Dash (s)', 'Broad Jump (in)', 'Vertical (in)', 'RAS'],
  QB: ['Draft Capital Proxy', 'Production Score', 'RAS', '40 Yard Dash (s)', 'Vertical (in)', 'Broad Jump (in)'],
};

const FALLBACK_PRIORITY = ['Production Score', 'Draft Capital Proxy', 'RAS', '40 Yard Dash (s)', 'Vertical (in)', 'Broad Jump (in)'];

function byPriority(position) {
  return METRIC_PRIORITY[position] ?? FALLBACK_PRIORITY;
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
    .map((label) => byLabel.get(label))
    .filter(Boolean)
    .map((metric) => ({
      ...metric,
      evidenceLabel: formatEvidenceLabel(metric),
      readiness: card?.evidence?.readinessLabel ?? null,
    }));

  return ordered.slice(0, cap);
}
