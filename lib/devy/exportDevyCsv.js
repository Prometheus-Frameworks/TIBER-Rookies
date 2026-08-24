function escCsvCell(value) {
  let str = String(value ?? '');
  // Neutralize spreadsheet formula injection before CSV quoting. Genuine finite
  // numbers are exempt: a number cannot carry a formula, so negative values
  // stay numeric cells. Numeric-looking strings are still guarded.
  if (!Number.isFinite(value) && /^[=+\-@]/.test(str)) str = `'${str}`;
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function toCsvString(headers, rows) {
  return [
    headers.map(escCsvCell).join(','),
    ...rows.map((row) => headers.map((header) => escCsvCell(row[header])).join(',')),
  ].join('\n');
}

export function downloadCsv(csvString, filename) {
  const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

const DEVY_HEADERS = [
  'player_id',
  'player_name',
  'school',
  'position',
  'projected_draft_class',
  'earliest_possible_draft_class',
  'class_year',
  'development_horizon',
  'lifecycle_stage',
  'actionability_band',
  'signal_strength_band',
  'confidence_band',
  'volatility_band',
  'development_tags',
  'summary',
  'why_it_matters',
  'identity_source_type',
  'identity_source_urls',
  'transition_status',
  'rookie_card_slug',
  'devy_active_status',
];

function deriveDevyActiveStatus(row) {
  if (row.transition_status === 'graduated_to_rookie') {
    if (row.rookie_card_slug) return 'graduated_to_rookie';
    return 'rookie_card_pending';
  }

  if (row.transition_status) {
    return row.transition_status;
  }

  return 'active_devy';
}

export function buildDevyCsv(rows) {
  const normalizedRows = rows.map((row) => ({
    player_id: row.player_id ?? '',
    player_name: row.player_name ?? '',
    school: row.school ?? '',
    position: row.position ?? '',
    projected_draft_class: row.projected_draft_class ?? '',
    earliest_possible_draft_class: row.earliest_possible_draft_class ?? '',
    class_year: row.class_year ?? '',
    development_horizon: row.development_horizon ?? '',
    lifecycle_stage: row.lifecycle_stage ?? '',
    actionability_band: row.actionability_band ?? '',
    signal_strength_band: row.signal_strength_band ?? '',
    confidence_band: row.confidence_band ?? '',
    volatility_band: row.volatility_band ?? '',
    development_tags: Array.isArray(row.development_tags) ? row.development_tags.join('|') : '',
    summary: row.summary ?? '',
    why_it_matters: row.why_it_matters ?? '',
    identity_source_type: row.identity_source_type ?? '',
    identity_source_urls: Array.isArray(row.identity_source_urls) ? row.identity_source_urls.join('|') : '',
    transition_status: row.transition_status ?? '',
    rookie_card_slug: row.rookie_card_slug ?? '',
    devy_active_status: row.devy_active_status ?? deriveDevyActiveStatus(row),
  }));

  return toCsvString(DEVY_HEADERS, normalizedRows);
}
