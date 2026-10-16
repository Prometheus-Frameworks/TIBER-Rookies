// Display/derived CSV state only; never synthesize a raw transition observation.
export function deriveDevyActiveStatus(row) {
  if (row.transition_status === 'active_devy') return 'active_devy';
  if (row.transition_status === 'graduated_to_rookie') {
    return typeof row.rookie_card_slug === 'string' && row.rookie_card_slug.trim()
      ? 'graduated_to_rookie' : 'rookie_card_pending';
  }
  return 'unknown';
}

export function normalizeTransitionMap(payload) {
  const envelopes = ['transitions', 'rows', 'prospects'].filter((key) => Array.isArray(payload?.[key]));
  if (envelopes.length !== 1) throw new Error('Transition envelope unavailable or ambiguous.');
  const map = new Map();
  for (const row of payload[envelopes[0]]) {
    if (!row || typeof row.player_id !== 'string' || !row.player_id.trim()) {
      throw new Error('Malformed transition identity.');
    }
    // Duplicate identities cannot silently select a winner, even if rows agree.
    map.set(row.player_id, map.has(row.player_id) ? null : row);
  }
  return map;
}

export function enrichDevyRows(seedRows, transitionMap) {
  return seedRows.map((row) => {
    const transition = transitionMap.get(row.player_id) ?? {};
    const enriched = {
      ...row,
      identity_source_type: row.identity_provenance?.source_type ?? 'unknown',
      identity_source_urls: row.identity_provenance?.source_urls ?? [],
      transition_status: transition.transition_status ?? '',
      rookie_card_slug: transition.rookie_card_slug ?? '',
    };
    return { ...enriched, devy_active_status: deriveDevyActiveStatus(enriched) };
  });
}

// Browser-side validation of the seed-watchlist branch of
// scripts/devy_signal_registry.py::validate_devy_registry (v0.1.0).
// This checks existing observations; it never repairs rows or derives new facts.
const SEED_ENUMS = {
  position: ['QB', 'RB', 'WR', 'TE'],
  development_horizon: ['NEAR_TERM', 'MEDIUM_TERM', 'LONG_HORIZON', 'PREP_OR_FUTURE'],
  lifecycle_stage: ['PREP', 'TRUE_FRESHMAN', 'ROTATIONAL', 'EMERGING', 'BREAKOUT_WINDOW', 'NFL_TRACK', 'DECLARE_RISK', 'SENIOR_HOLD', 'STALLED'],
  signal_strength_band: ['LOW', 'MODERATE', 'STRONG', 'ELITE'],
  confidence_band: ['LOW', 'MEDIUM', 'HIGH'],
  actionability_band: ['WATCHLIST', 'MONITOR', 'TARGET', 'PRIORITY'],
  volatility_band: ['LOW', 'MEDIUM', 'HIGH', 'EXTREME'],
};
const SEED_TAGS = ['LONG_HORIZON', 'LONG_HORIZON_WATCHLIST', 'HIGH_RECRUITING_CAPITAL',
  'MULTI_SPORT_PROFILE', 'INJURY_REHAB_WATCH', 'INSULATED_PROGRAM', 'SIZE_PROFILE',
  'EARLY_DECLARE_CANDIDATE', 'PATHWAY_BLOCKED', 'PATHWAY_CLEARING', 'TRANSFER_RISK',
  'ASCENDING', 'STALLED_SIGNAL', 'RAW_TRAITS', 'PRODUCTION_PENDING', 'ROLE_UNCERTAIN'];
const SEED_TIMELINE_FIELDS = ['projected_draft_class', 'earliest_possible_draft_class', 'class_year', 'years_to_projected_draft'];
const SEED_PROVENANCE = {
  identity_provenance: {
    types: ['official_roster', 'recruiting_profile'],
    fields: ['player_name', 'school', 'position'],
  },
  timeline_provenance: {
    types: ['manual_eligibility_context', 'recruiting_profile'],
    fields: SEED_TIMELINE_FIELDS,
  },
  signal_provenance: {
    types: ['manual_curated_seed_signal', 'recruiting_profile', 'production_data', 'team_context_artifact'],
    fields: ['development_tags', 'signal_strength_band', 'confidence_band', 'actionability_band', 'volatility_band'],
  },
};
const SEED_REQUIRED_FIELDS = ['player_id', 'player_name', 'school', ...SEED_TIMELINE_FIELDS,
  ...Object.keys(SEED_ENUMS), 'development_tags', 'summary', 'why_it_matters', 'source_notes'];

export function readDevySeedRows(payload) {
  const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
  const text = (value) => typeof value === 'string' && value.trim().length > 0;
  const list = (value, valid) => Array.isArray(value) && value.length > 0 && value.every(valid);
  const requireValid = (valid, field) => {
    if (!valid) throw new Error(`Malformed Devy seed watchlist: ${field}.`);
  };

  requireValid(object(payload), 'envelope');
  requireValid(payload.schema_version === 'devy-prospect-registry-v0.1.0', 'schema_version');
  // A fixture-only registry is not a seed-watchlist response.
  requireValid(payload.artifact_type === 'devy_seed_watchlist', 'artifact_type');
  requireValid(text(payload.disclaimer) && ['seed watchlist', 'not rankings', 'not rookie alpha inputs']
    .every((phrase) => payload.disclaimer.toLowerCase().includes(phrase)), 'disclaimer');
  requireValid(Number.isInteger(payload.as_of_year), 'as_of_year');
  const audit = payload.intake_audit;
  requireValid(object(audit), 'intake_audit');
  requireValid(['manual_curated_seed_watchlist', 'codex_curated_task', 'future_script_generated_candidate']
    .includes(audit.intake_method), 'intake_audit.intake_method');
  for (const field of ['introduced_by_issue', 'introduced_by_pr']) {
    requireValid(Number.isInteger(audit[field]) && audit[field] > 0, `intake_audit.${field}`);
  }
  requireValid(text(audit.validation_command), 'intake_audit.validation_command');
  requireValid(['non_promoted_discovery_only', 'blocked_from_downstream_use']
    .includes(audit.promotion_status), 'intake_audit.promotion_status');
  requireValid(['blocked_until_rookie_transition', 'blocked']
    .includes(audit.downstream_eligibility), 'intake_audit.downstream_eligibility');
  requireValid(list(audit.notes, text), 'intake_audit.notes');
  requireValid(Array.isArray(payload.prospects), 'prospects');

  const seen = new Set();
  for (const [index, row] of payload.prospects.entries()) {
    const prefix = `prospects[${index}]`;
    requireValid(object(row), prefix);
    requireValid(SEED_REQUIRED_FIELDS.every((field) => Object.hasOwn(row, field)), `${prefix}.required fields`);
    requireValid(text(row.player_id) && !seen.has(row.player_id), `${prefix}.player_id`);
    seen.add(row.player_id);
    for (const field of ['player_name', 'summary', 'why_it_matters']) {
      requireValid(text(row[field]), `${prefix}.${field}`);
    }
    requireValid(row.school === null || typeof row.school === 'string', `${prefix}.school`);
    for (const [field, values] of Object.entries(SEED_ENUMS)) {
      requireValid(values.includes(row[field]), `${prefix}.${field}`);
    }
    requireValid(list(row.development_tags, (tag) => SEED_TAGS.includes(tag)), `${prefix}.development_tags`);
    for (const field of [...SEED_TIMELINE_FIELDS, 'recruiting_stars', 'recruiting_rank_national', 'recruiting_rank_position']) {
      requireValid(!Object.hasOwn(row, field) || row[field] === null || Number.isInteger(row[field]), `${prefix}.${field}`);
    }
    const projected = row.projected_draft_class;
    const earliest = row.earliest_possible_draft_class;
    const years = row.years_to_projected_draft;
    requireValid(!Number.isInteger(projected) || !Number.isInteger(earliest) || earliest <= projected, `${prefix}.draft timeline`);
    requireValid(!Number.isInteger(projected) || years === projected - payload.as_of_year, `${prefix}.years_to_projected_draft`);
    if (Number.isInteger(years)) {
      const horizon = row.lifecycle_stage === 'PREP' || years >= 4 ? 'PREP_OR_FUTURE'
        : years >= 3 ? 'LONG_HORIZON' : years === 2 ? 'MEDIUM_TERM'
          : years === 0 || years === 1 ? 'NEAR_TERM' : null;
      requireValid(row.development_horizon === horizon, `${prefix}.development_horizon`);
      requireValid(years < 3 || !['TARGET', 'PRIORITY'].includes(row.actionability_band), `${prefix}.long-horizon actionability`);
    }
    requireValid(list(row.source_notes, text), `${prefix}.source_notes`);
    for (const [key, contract] of Object.entries(SEED_PROVENANCE)) {
      const provenance = row[key];
      requireValid(object(provenance), `${prefix}.${key}`);
      requireValid(contract.types.includes(provenance.source_type), `${prefix}.${key}.source_type`);
      if (provenance.supports_fields != null) {
        const fields = provenance.supports_fields;
        requireValid(list(fields, (field) => contract.fields.includes(field))
          && new Set(fields).size === contract.fields.length, `${prefix}.${key}.supports_fields`);
      }
      requireValid(list(provenance.source_notes, text), `${prefix}.${key}.source_notes`);
      if (provenance.source_urls != null) {
        requireValid(list(provenance.source_urls, (url) => typeof url === 'string' && /^https?:\/\//.test(url)), `${prefix}.${key}.source_urls`);
      }
      requireValid(Number.isInteger(provenance.last_verified_year)
        && provenance.last_verified_year <= payload.as_of_year, `${prefix}.${key}.last_verified_year`);
    }
  }
  return payload.prospects;
}
