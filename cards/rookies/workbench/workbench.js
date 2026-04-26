import { downloadCsv } from '/lib/rookies/exportCsv.js';

const PRIMARY_CONTEXT_PATH = '../../../exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_team_context_v0.json';
const POST_DRAFT_FALLBACK_PATH = '../../../exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_v0.json';
const MISSING_BASELINE_PATH = '../../../exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_missing_baselines_v0.json';
const OUTCOME_SUMMARY_PATH = '../../../exports/promoted/nfl-fantasy-outcomes/context_flag_outcome_summary_v1.json';
const JOURNAL_SIGNAL_PATH = '../../../data/operator-journal/processed/2026_operator_signal_candidates.json';

const CALIBRATION_COHORTS = [
  'skill_pick_1_10_since_2020',
  'skill_pick_11_20_since_2020',
  'skill_pick_21_32_since_2020',
  'skill_pick_33_45_since_2020',
  'skill_pick_46_64_since_2020',
  'skill_pick_65_102_since_2020',
  'rb_pick_1_32_since_2020',
  'rb_pick_33_64_since_2020',
  'rb_pick_65_102_since_2020',
  'te_pick_1_32_since_2020',
  'te_pick_33_64_since_2020',
];

const state = {
  rows: [],
  selectedId: null,
  hasExplicitPlayerSelection: false,
  sortKey: 'post_draft_alpha',
  sortDirection: 'desc',
  filters: {
    search: '',
    position: 'ALL',
    round: 'ALL',
    teamContextFound: 'ALL',
    sourceProfile: 'ALL',
    deltaDirection: 'ALL',
  },
  missingBaselines: null,
  outcomeSummary: null,
  journalSignals: { available: false, rows: [] },
  journalFilters: {
    search: '',
    modelEdge: false,
    missingDataAudit: false,
    roleOpportunity: false,
    needsHumanReview: false,
  },
};

const dom = {
  artifactStatus: document.getElementById('artifact-status'),
  summaryTiles: document.getElementById('summary-tiles'),
  tbody: document.getElementById('players-tbody'),
  detail: document.getElementById('player-detail'),
  missingPanel: document.getElementById('missing-baseline-panel'),
  calibrationPanel: document.getElementById('calibration-panel'),
  journalPanel: document.getElementById('journal-signals-panel'),
  journalTableBody: document.getElementById('journal-signals-tbody'),
  journalSearch: document.getElementById('journal-search-input'),
  journalModelEdge: document.getElementById('journal-filter-model-edge'),
  journalMissingData: document.getElementById('journal-filter-missing-data'),
  journalRoleOpportunity: document.getElementById('journal-filter-role-opportunity'),
  journalNeedsReview: document.getElementById('journal-filter-needs-review'),
  journalSelectedHint: document.getElementById('journal-selected-player-hint'),
  search: document.getElementById('search-input'),
  position: document.getElementById('position-filter'),
  round: document.getElementById('round-filter'),
  teamContext: document.getElementById('context-filter'),
  sourceProfile: document.getElementById('source-filter'),
  delta: document.getElementById('delta-filter'),
  exportPlayersCsv: document.getElementById('export-players-csv'),
  exportJournalCsv: document.getElementById('export-journal-csv'),
  exportMissingBaselineCsv: document.getElementById('export-missing-baseline-csv'),
  exportOutcomeCohortsCsv: document.getElementById('export-outcome-cohorts-csv'),
  headers: [...document.querySelectorAll('th[data-sort]')],
};

function toArray(value) {
  return Array.isArray(value) ? value : [];
}

function asNumber(value) {
  return Number.isFinite(Number(value)) ? Number(value) : null;
}

function coerceRows(payload) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.rows)) return payload.rows;
  return [];
}

function normalizeRow(row, index) {
  return {
    id: row.player_id || `${row.player_name || 'unknown'}-${index}`,
    player_name: row.player_name || 'Unknown',
    position: row.position || '—',
    team: row.team || row.nfl_team || '—',
    draft_round: asNumber(row.draft_round),
    draft_pick: asNumber(row.draft_pick || row.pick),
    pre_draft_alpha: asNumber(row.pre_draft_alpha),
    post_draft_alpha: asNumber(row.post_draft_alpha),
    post_draft_delta: asNumber(row.post_draft_delta),
    talent_signal: row.talent_confirmation_signal || row.talent_signal || '—',
    opportunity_signal: row.opportunity_insulation_signal || row.opportunity_signal || '—',
    runway: row.short_term_fantasy_runway || row.runway || '—',
    team_context_found: typeof row.team_context_found === 'boolean' ? row.team_context_found : null,
    source_profile: row.source_profile || '—',
    source_status: row.source_status || '—',
    team_context_source_status: row.team_context_source_status || '—',
    delta_reason_codes: toArray(row.delta_reason_codes),
    translator_tags: toArray(row.translator_tags),
    team_context_tags: toArray(row.team_context_tags),
    positive_team_context_tags: toArray(row.positive_team_context_tags),
    risk_team_context_tags: toArray(row.risk_team_context_tags),
    combined_context_tags: toArray(row.combined_context_tags),
    combined_risk_tags: toArray(row.combined_risk_tags),
    combined_context_tags_with_role: toArray(row.combined_context_tags_with_role),
    combined_risk_tags_with_role: toArray(row.combined_risk_tags_with_role),
    remaining_risks: toArray(row.remaining_risks),
    team_context_notes: row.team_context_notes || '—',
    role_team_profile_found:
      typeof row.role_team_profile_found === 'boolean'
        ? row.role_team_profile_found
        : typeof row.role_profile_found === 'boolean'
          ? row.role_profile_found
          : null,
    role_baseline_found: typeof row.role_baseline_found === 'boolean' ? row.role_baseline_found : null,
    full_role_opportunity_found:
      typeof row.full_role_opportunity_found === 'boolean'
        ? row.full_role_opportunity_found
        : typeof row.role_opportunity_found === 'boolean'
          ? row.role_opportunity_found
          : null,
  };
}

function normalizeJournalCandidate(candidate, index) {
  return {
    id: candidate.candidate_id || `journal-candidate-${index}`,
    candidate_id: candidate.candidate_id || `journal-candidate-${index}`,
    player_name: candidate.player_name || null,
    team: candidate.team || null,
    position: candidate.position || null,
    entity_type: candidate.entity_type || 'unknown',
    claim_summary: candidate.claim_summary || '—',
    positive_signal_tags: toArray(candidate.positive_signal_tags),
    risk_tags: toArray(candidate.risk_tags),
    context_tags: toArray(candidate.context_tags),
    model_impact: candidate.model_impact || '',
    confidence: candidate.confidence || '—',
    review_status: candidate.review_status || 'unknown',
    needs_verification: Boolean(candidate.needs_verification),
    source_entry_id: candidate.source_entry_id || null,
    source_type: candidate.source_type || null,
  };
}

function formatMetric(value, digits = 1) {
  return Number.isFinite(value) ? value.toFixed(digits) : '—';
}

function formatPick(round, pick) {
  if (!Number.isFinite(round) && !Number.isFinite(pick)) return '—';
  if (Number.isFinite(round) && Number.isFinite(pick)) return `R${round} / ${pick}`;
  return Number.isFinite(pick) ? `${pick}` : `R${round}`;
}

function formatContextFound(value) {
  if (value === true) return 'Yes';
  if (value === false) return 'No';
  return 'Unknown';
}

function asBooleanSort(value) {
  if (value === true) return 1;
  if (value === false) return 0;
  return -1;
}

function buildInspectionLookups() {
  const missingById = new Set();
  const missingByName = new Set();
  const missingRows = state.missingBaselines?.available ? state.missingBaselines.rows : [];
  missingRows.forEach((row) => {
    if (row.player_id) missingById.add(String(row.player_id).toLowerCase());
    if (row.player_name) missingByName.add(String(row.player_name).toLowerCase());
  });

  const journalCountByName = new Map();
  state.journalSignals.rows.forEach((candidate) => {
    const name = String(candidate.player_name || '').toLowerCase().trim();
    if (!name) return;
    journalCountByName.set(name, (journalCountByName.get(name) || 0) + 1);
  });

  return { missingById, missingByName, journalCountByName };
}

function enrichInspectionStatus(row, lookups) {
  const tags = [
    ...row.delta_reason_codes,
    ...row.translator_tags,
    ...row.team_context_tags,
    ...row.positive_team_context_tags,
    ...row.risk_team_context_tags,
    ...row.combined_context_tags,
    ...row.combined_risk_tags,
    ...row.remaining_risks,
  ]
    .join(' ')
    .toLowerCase();
  const sourceStatus = `${row.source_status || ''} ${row.team_context_source_status || ''}`.toLowerCase();
  const hasExplicitMissingBaselineTag = tags.includes('baseline_not_found') || tags.includes('predraft_baseline_not_found');
  const canUseMissingBaselineArtifact = Boolean(state.missingBaselines?.available);

  const missingBaselineFromArtifact =
    canUseMissingBaselineArtifact &&
    (lookups.missingById.has(String(row.id || '').toLowerCase()) ||
      lookups.missingByName.has(String(row.player_name || '').toLowerCase()));
  const missingBaselineFlag = hasExplicitMissingBaselineTag ? true : missingBaselineFromArtifact ? true : canUseMissingBaselineArtifact ? false : null;
  const teamContextFound = row.team_context_found;
  const roleTeamProfileFound = row.role_team_profile_found;
  const roleBaselineFound = row.role_baseline_found ?? (missingBaselineFlag ? false : null);
  const fullRoleOpportunityFound = row.full_role_opportunity_found;
  const journalSignalCount = lookups.journalCountByName.get(String(row.player_name || '').toLowerCase()) || 0;
  const dataAuditWarningFlag =
    missingBaselineFlag ||
    sourceStatus.includes('fallback') ||
    sourceStatus.includes('missing') ||
    sourceStatus.includes('audit') ||
    tags.includes('missing_data') ||
    tags.includes('profile_data_completeness');

  const badges = [];
  if (teamContextFound === false) badges.push('Team context missing');
  if (roleTeamProfileFound === false) badges.push('Role profile missing');
  if (roleBaselineFound === false) badges.push('Role baseline missing');
  if (roleBaselineFound === true && (roleTeamProfileFound !== true || fullRoleOpportunityFound !== true)) badges.push('Baseline only');
  if (journalSignalCount > 0) badges.push('Journal note present');
  if (dataAuditWarningFlag) badges.push('Missing data audit');
  const isContextComplete =
    teamContextFound === true &&
    roleTeamProfileFound === true &&
    roleBaselineFound === true &&
    fullRoleOpportunityFound === true &&
    dataAuditWarningFlag !== true;
  if (isContextComplete) badges.unshift('Context complete');

  return {
    ...row,
    team_context_found: teamContextFound,
    role_team_profile_found: roleTeamProfileFound,
    role_baseline_found: roleBaselineFound,
    full_role_opportunity_found: fullRoleOpportunityFound,
    journal_signal_count: journalSignalCount,
    missing_baseline_flag: missingBaselineFlag,
    data_audit_warning_flag: dataAuditWarningFlag,
    context_status_badges: badges,
    context_complete: isContextComplete,
  };
}

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function renderSummary(filteredRows) {
  const rows = state.rows;
  const averageDelta = rows.length ? rows.reduce((acc, row) => acc + (row.post_draft_delta || 0), 0) / rows.length : null;
  const teamstateContextFound = rows.filter((row) => row.role_team_profile_found === true).length;
  const teamstateContextMissing = rows.filter((row) => row.role_team_profile_found === false).length;
  const roleOpportunityComplete = rows.filter((row) => row.full_role_opportunity_found === true).length;
  const baselineOnly = rows.filter((row) => row.role_baseline_found === true && row.full_role_opportunity_found !== true).length;
  const journalNotesPresent = rows.filter((row) => (row.journal_signal_count || 0) > 0).length;
  const auditWarnings = rows.filter((row) => row.data_audit_warning_flag).length;

  const biggestRiser = [...rows]
    .filter((row) => Number.isFinite(row.post_draft_delta))
    .sort((a, b) => b.post_draft_delta - a.post_draft_delta)[0];
  const biggestFaller = [...rows]
    .filter((row) => Number.isFinite(row.post_draft_delta))
    .sort((a, b) => a.post_draft_delta - b.post_draft_delta)[0];

  const tiles = [
    ['Players loaded', `${rows.length}`],
    ['Teamstate context found', `${teamstateContextFound}`],
    ['Teamstate context missing', `${teamstateContextMissing}`],
    ['Role opportunity complete', `${roleOpportunityComplete}`],
    ['Baseline only', `${baselineOnly}`],
    ['Journal notes present', `${journalNotesPresent}`],
    ['Data/audit warnings', `${auditWarnings}`],
    ['Avg post_draft_delta', formatMetric(averageDelta, 2)],
    ['Biggest riser', biggestRiser ? `${biggestRiser.player_name} (${formatMetric(biggestRiser.post_draft_delta, 1)})` : '—'],
    ['Biggest faller', biggestFaller ? `${biggestFaller.player_name} (${formatMetric(biggestFaller.post_draft_delta, 1)})` : '—'],
    ['Missing baselines', state.missingBaselines?.available ? `${state.missingBaselines.rows.length}` : 'Unavailable'],
    ['Rows after filters', `${filteredRows.length}`],
  ];

  dom.summaryTiles.innerHTML = tiles
    .map(
      ([label, value]) =>
        `<article class="summary-tile"><div class="summary-label">${escapeHtml(label)}</div><div class="summary-value">${escapeHtml(value)}</div></article>`,
    )
    .join('');
}

function toCsvValue(value) {
  const text = String(value ?? '');
  if (text.includes(',') || text.includes('"') || text.includes('\n') || text.includes('\r')) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function buildCsv(headers, rows) {
  return [headers.map(toCsvValue).join(','), ...rows.map((row) => headers.map((key) => toCsvValue(row[key])).join(','))].join('\n');
}

function getDisplayedPlayerRows() {
  return sortRows(state.rows.filter(matchesFilters));
}

function sortRows(rows) {
  const multiplier = state.sortDirection === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const left = a[state.sortKey];
    const right = b[state.sortKey];

    if (
      state.sortKey === 'team_context_found' ||
      state.sortKey === 'role_team_profile_found' ||
      state.sortKey === 'role_baseline_found' ||
      state.sortKey === 'full_role_opportunity_found' ||
      state.sortKey === 'missing_baseline_flag' ||
      state.sortKey === 'data_audit_warning_flag'
    ) {
      return (asBooleanSort(left) - asBooleanSort(right)) * multiplier;
    }

    if (typeof left === 'string' || typeof right === 'string') {
      return String(left || '').localeCompare(String(right || '')) * multiplier;
    }

    const leftValue = Number.isFinite(left) ? left : -99999;
    const rightValue = Number.isFinite(right) ? right : -99999;
    return (leftValue - rightValue) * multiplier;
  });
}

function matchesFilters(row) {
  const searchHaystack = [
    row.player_name,
    row.team,
    row.position,
    ...row.delta_reason_codes,
    ...row.translator_tags,
    ...row.team_context_tags,
    ...row.positive_team_context_tags,
    ...row.risk_team_context_tags,
    ...row.combined_context_tags,
    ...row.combined_risk_tags,
    ...row.remaining_risks,
  ]
    .join(' ')
    .toLowerCase();

  if (state.filters.search && !searchHaystack.includes(state.filters.search.toLowerCase())) {
    return false;
  }

  if (state.filters.position !== 'ALL' && row.position !== state.filters.position) {
    return false;
  }

  if (state.filters.round !== 'ALL' && String(row.draft_round || 'UDFA') !== state.filters.round) {
    return false;
  }

  if (state.filters.teamContextFound === 'true' && row.team_context_found !== true) {
    return false;
  }

  if (state.filters.teamContextFound === 'false' && row.team_context_found !== false) {
    return false;
  }

  if (state.filters.teamContextFound === 'unknown' && row.team_context_found !== null) {
    return false;
  }

  if (state.filters.sourceProfile !== 'ALL' && row.source_profile !== state.filters.sourceProfile) {
    return false;
  }

  if (state.filters.deltaDirection === 'positive' && !(row.post_draft_delta > 0)) {
    return false;
  }

  if (state.filters.deltaDirection === 'negative' && !(row.post_draft_delta < 0)) {
    return false;
  }

  return true;
}

function renderTable(rows) {
  if (!rows.length) {
    dom.tbody.innerHTML = '<tr><td colspan="19" class="meta">No players matched current filters.</td></tr>';
    return;
  }

  dom.tbody.innerHTML = rows
    .map((row) => {
      const deltaClass = row.post_draft_delta > 0 ? 'delta-positive' : row.post_draft_delta < 0 ? 'delta-negative' : '';
      const selectedClass = state.selectedId === row.id ? 'selected' : '';
      return `
        <tr data-player-id="${escapeHtml(row.id)}" class="${selectedClass}">
          <td>${escapeHtml(row.player_name)}</td>
          <td>${escapeHtml(row.position)}</td>
          <td>${escapeHtml(row.team)}</td>
          <td>${escapeHtml(formatPick(row.draft_round, row.draft_pick))}</td>
          <td>${escapeHtml(formatMetric(row.pre_draft_alpha))}</td>
          <td>${escapeHtml(formatMetric(row.post_draft_alpha))}</td>
          <td class="${deltaClass}">${escapeHtml(formatMetric(row.post_draft_delta))}</td>
          <td>${escapeHtml(row.talent_signal)}</td>
          <td>${escapeHtml(row.opportunity_signal)}</td>
          <td>${escapeHtml(row.runway)}</td>
          <td>${escapeHtml(formatContextFound(row.team_context_found))}</td>
          <td>${escapeHtml(formatContextFound(row.role_team_profile_found))}</td>
          <td>${escapeHtml(formatContextFound(row.role_baseline_found))}</td>
          <td>${escapeHtml(formatContextFound(row.full_role_opportunity_found))}</td>
          <td>${escapeHtml(String(row.journal_signal_count || 0))}</td>
          <td>${escapeHtml(formatContextFound(row.missing_baseline_flag))}</td>
          <td>${escapeHtml(formatContextFound(row.data_audit_warning_flag))}</td>
          <td>${renderStatusBadges(row.context_status_badges)}</td>
          <td>${escapeHtml(row.source_profile)}</td>
        </tr>
      `;
    })
    .join('');

  dom.tbody.querySelectorAll('tr[data-player-id]').forEach((rowEl) => {
    rowEl.addEventListener('click', () => {
      if (state.selectedId === rowEl.dataset.playerId && state.hasExplicitPlayerSelection) {
        state.selectedId = null;
        state.hasExplicitPlayerSelection = false;
      } else {
        state.selectedId = rowEl.dataset.playerId;
        state.hasExplicitPlayerSelection = true;
      }
      render();
    });
  });
}

function renderStatusBadges(labels) {
  if (!labels?.length) return '<span class="meta">—</span>';
  return `<div class="tag-list compact-badge-list">${labels.map((label) => `<span class="status-badge">${escapeHtml(label)}</span>`).join('')}</div>`;
}

function renderTagList(tags, risk = false) {
  if (!tags.length) return '<span class="meta">None</span>';
  return `<div class="tag-list">${tags
    .map((tag) => `<span class="tag-pill${risk ? ' risk' : ''}">${escapeHtml(tag)}</span>`)
    .join('')}</div>`;
}

function renderDetail(row) {
  if (!row) {
    dom.detail.className = 'player-detail-card meta';
    dom.detail.innerHTML = 'Select a player row to inspect translator tags, context joins, and risk stack.';
    return;
  }

  const deltaClass = row.post_draft_delta > 0 ? 'delta-positive' : row.post_draft_delta < 0 ? 'delta-negative' : '';
  dom.detail.className = 'player-detail-card';
  dom.detail.innerHTML = `
    <div class="detail-grid">
      <div class="detail-row"><span class="detail-label">Player</span><span class="detail-value">${escapeHtml(row.player_name)}</span></div>
      <div class="detail-row"><span class="detail-label">Position</span><span class="detail-value">${escapeHtml(row.position)}</span></div>
      <div class="detail-row"><span class="detail-label">Team</span><span class="detail-value">${escapeHtml(row.team)}</span></div>
      <div class="detail-row"><span class="detail-label">Pick</span><span class="detail-value">${escapeHtml(formatPick(row.draft_round, row.draft_pick))}</span></div>
      <div class="detail-row"><span class="detail-label">Pre Draft Alpha</span><span class="detail-value">${escapeHtml(formatMetric(row.pre_draft_alpha))}</span></div>
      <div class="detail-row"><span class="detail-label">Post Draft Alpha</span><span class="detail-value">${escapeHtml(formatMetric(row.post_draft_alpha))}</span></div>
      <div class="detail-row"><span class="detail-label">Post Draft Delta</span><span class="detail-value ${deltaClass}">${escapeHtml(formatMetric(row.post_draft_delta))}</span></div>
      <div class="detail-row"><span class="detail-label">Source Status</span><span class="detail-value">${escapeHtml(row.source_status)}</span></div>
      <div class="detail-row"><span class="detail-label">Team Context Source Status</span><span class="detail-value">${escapeHtml(row.team_context_source_status)}</span></div>
      <div class="detail-row"><span class="detail-label">Team Context Notes</span><span class="detail-value">${escapeHtml(row.team_context_notes)}</span></div>
      <div class="detail-row"><span class="detail-label">Context Status</span><span class="detail-value">${renderStatusBadges(row.context_status_badges)}</span></div>
      <div class="detail-row"><span class="detail-label">Role Team Profile Found</span><span class="detail-value">${escapeHtml(formatContextFound(row.role_team_profile_found))}</span></div>
      <div class="detail-row"><span class="detail-label">Role Baseline Found</span><span class="detail-value">${escapeHtml(formatContextFound(row.role_baseline_found))}</span></div>
      <div class="detail-row"><span class="detail-label">Full Role Opportunity Found</span><span class="detail-value">${escapeHtml(formatContextFound(row.full_role_opportunity_found))}</span></div>
      <div class="detail-row"><span class="detail-label">Journal Signal Count</span><span class="detail-value">${escapeHtml(String(row.journal_signal_count || 0))}</span></div>
      <div class="detail-row"><span class="detail-label">Missing Baseline Flag</span><span class="detail-value">${escapeHtml(formatContextFound(row.missing_baseline_flag))}</span></div>
      <div class="detail-row"><span class="detail-label">Data/Audit Warning</span><span class="detail-value">${escapeHtml(formatContextFound(row.data_audit_warning_flag))}</span></div>
      <div class="detail-row"><span class="detail-label">Delta Reason Codes</span><span class="detail-value">${renderTagList(row.delta_reason_codes)}</span></div>
      <div class="detail-row"><span class="detail-label">Translator Tags</span><span class="detail-value">${renderTagList(row.translator_tags)}</span></div>
      <div class="detail-row"><span class="detail-label">Team Context Tags</span><span class="detail-value">${renderTagList(row.team_context_tags)}</span></div>
      <div class="detail-row"><span class="detail-label">Positive Team Context Tags</span><span class="detail-value">${renderTagList(row.positive_team_context_tags)}</span></div>
      <div class="detail-row"><span class="detail-label">Risk Team Context Tags</span><span class="detail-value">${renderTagList(row.risk_team_context_tags, true)}</span></div>
      <div class="detail-row"><span class="detail-label">Combined Context Tags</span><span class="detail-value">${renderTagList(row.combined_context_tags)}</span></div>
      <div class="detail-row"><span class="detail-label">Combined Risk Tags</span><span class="detail-value">${renderTagList(row.combined_risk_tags, true)}</span></div>
      <div class="detail-row"><span class="detail-label">Remaining Risks</span><span class="detail-value">${renderTagList(row.remaining_risks, true)}</span></div>
    </div>
  `;
}

function renderMissingBaselines() {
  if (!state.missingBaselines?.available) {
    dom.missingPanel.innerHTML = '<p class="meta">Missing baseline artifact unavailable.</p>';
    return;
  }

  const rows = state.missingBaselines.rows;
  if (!rows.length) {
    dom.missingPanel.innerHTML = '<p class="meta">No players are missing pre-draft baselines.</p>';
    return;
  }

  dom.missingPanel.innerHTML = `
    <p class="meta">${rows.length} players missing pre-draft baseline linkage.</p>
    <table class="compact-table">
      <thead><tr><th>Player</th><th>Team</th><th>Pos</th><th>Pick</th><th>Reason</th></tr></thead>
      <tbody>
        ${rows
          .map((row) => {
            const pick = formatPick(asNumber(row.draft_round), asNumber(row.draft_pick));
            return `<tr><td>${escapeHtml(row.player_name || 'Unknown')}</td><td>${escapeHtml(row.team || '—')}</td><td>${escapeHtml(row.position || '—')}</td><td>${escapeHtml(pick)}</td><td>${escapeHtml(row.reason || '—')}</td></tr>`;
          })
          .join('')}
      </tbody>
    </table>
  `;
}

function renderCalibration() {
  if (!state.outcomeSummary?.available) {
    dom.calibrationPanel.innerHTML = '<p class="meta">Outcome calibration artifact unavailable.</p>';
    return;
  }

  const byCohort = new Map(state.outcomeSummary.rows.map((row) => [row.cohort, row]));
  dom.calibrationPanel.innerHTML = `
    <table class="compact-table">
      <thead>
        <tr>
          <th>Cohort</th>
          <th>Player Count</th>
          <th>Year 1 Avg PPR</th>
          <th>Year 1 Median PPR</th>
          <th>Complete Year 1</th>
        </tr>
      </thead>
      <tbody>
        ${CALIBRATION_COHORTS.map((cohort) => {
          const row = byCohort.get(cohort);
          return `<tr>
            <td>${escapeHtml(cohort)}</td>
            <td>${escapeHtml(String(row?.player_count ?? '—'))}</td>
            <td>${escapeHtml(formatMetric(asNumber(row?.year_1_avg_ppr), 2))}</td>
            <td>${escapeHtml(formatMetric(asNumber(row?.year_1_median_ppr), 2))}</td>
            <td>${escapeHtml(String(row?.complete_year_1_count ?? '—'))}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
  `;
}

function isModelEdgeCandidate(candidate) {
  const haystack = [
    candidate.model_impact || '',
    candidate.claim_summary || '',
    ...candidate.positive_signal_tags,
    ...candidate.risk_tags,
    ...candidate.context_tags,
  ]
    .join(' ')
    .toLowerCase();

  return (
    haystack.includes('model_edge') ||
    haystack.includes('model-edge') ||
    haystack.includes('tiber_edge_plus') ||
    haystack.includes('tiber edge plus')
  );
}

function isMissingDataAuditCandidate(candidate) {
  const haystack = `${candidate.model_impact} ${candidate.claim_summary} ${candidate.risk_tags.join(' ')} ${candidate.context_tags.join(' ')}`.toLowerCase();
  return haystack.includes('missing_data') || haystack.includes('profile_data_completeness');
}

function isRoleOpportunityCandidate(candidate) {
  const haystack = `${candidate.model_impact} ${candidate.claim_summary} ${candidate.context_tags.join(' ')}`.toLowerCase();
  return haystack.includes('role_opportunity') || haystack.includes('role_path');
}

function isLandingSpotOverProfileCandidate(candidate) {
  return candidate.model_impact.toLowerCase().includes('landing_spot_opportunity_over_profile');
}

function getJournalRowsForDisplay(selectedPlayer) {
  if (!state.journalSignals.available) return [];

  let rows = state.journalSignals.rows;
  if (state.hasExplicitPlayerSelection && selectedPlayer?.player_name) {
    const selectedName = selectedPlayer.player_name.toLowerCase();
    rows = rows.filter((candidate) => candidate.player_name && candidate.player_name.toLowerCase() === selectedName);
  }

  return rows.filter((candidate) => {
    const haystack = [
      candidate.player_name || '',
      candidate.team || '',
      candidate.entity_type || '',
      candidate.claim_summary || '',
      ...candidate.positive_signal_tags,
      ...candidate.risk_tags,
      ...candidate.context_tags,
      candidate.model_impact || '',
      candidate.review_status || '',
    ]
      .join(' ')
      .toLowerCase();

    if (state.journalFilters.search && !haystack.includes(state.journalFilters.search.toLowerCase())) {
      return false;
    }

    if (state.journalFilters.modelEdge && !isModelEdgeCandidate(candidate)) {
      return false;
    }

    if (state.journalFilters.missingDataAudit && !isMissingDataAuditCandidate(candidate)) {
      return false;
    }

    if (state.journalFilters.roleOpportunity && !isRoleOpportunityCandidate(candidate)) {
      return false;
    }

    if (state.journalFilters.needsHumanReview && candidate.review_status !== 'needs_human_review') {
      return false;
    }

    return true;
  });
}

function getSelectedPlayerForJournalScope(sortedRows = getDisplayedPlayerRows()) {
  if (!state.hasExplicitPlayerSelection) return null;
  return state.rows.find((row) => row.id === state.selectedId) || sortedRows[0] || null;
}

function exportPlayersCsv() {
  const rows = getDisplayedPlayerRows();
  const headers = [
    'player_name',
    'position',
    'team',
    'draft_round',
    'draft_pick',
    'pre_draft_alpha',
    'post_draft_alpha',
    'post_draft_delta',
    'team_context_found',
    'role_team_profile_found',
    'role_baseline_found',
    'full_role_opportunity_found',
    'context_complete',
    'journal_signal_count',
    'missing_baseline_flag',
    'data_audit_warning_flag',
    'context_status_badges',
    'delta_reason_codes',
    'translator_tags',
    'team_context_tags',
    'risk_team_context_tags',
    'combined_context_tags_with_role',
    'combined_risk_tags_with_role',
    'source_profile',
    'source_status',
  ];
  const normalizedRows = rows.map((row) => ({
    ...row,
    context_status_badges: JSON.stringify(row.context_status_badges),
    delta_reason_codes: JSON.stringify(row.delta_reason_codes),
    translator_tags: JSON.stringify(row.translator_tags),
    team_context_tags: JSON.stringify(row.team_context_tags),
    risk_team_context_tags: JSON.stringify(row.risk_team_context_tags),
    combined_context_tags_with_role: JSON.stringify(row.combined_context_tags_with_role),
    combined_risk_tags_with_role: JSON.stringify(row.combined_risk_tags_with_role),
  }));
  const csv = buildCsv(headers, normalizedRows);
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  downloadCsv(csv, `tiber-workbench-players-${stamp}.csv`);
}

function exportJournalCsv() {
  const selectedPlayer = getSelectedPlayerForJournalScope();
  const rows = getJournalRowsForDisplay(selectedPlayer);
  const headers = [
    'candidate_id',
    'source_entry_id',
    'player_name',
    'team',
    'position',
    'entity_type',
    'claim_summary',
    'model_impact',
    'confidence',
    'needs_verification',
    'review_status',
    'source_type',
    'positive_signal_tags',
    'risk_tags',
    'context_tags',
  ];
  const normalizedRows = rows.map((row) => ({
    ...row,
    positive_signal_tags: JSON.stringify(row.positive_signal_tags),
    risk_tags: JSON.stringify(row.risk_tags),
    context_tags: JSON.stringify(row.context_tags),
  }));
  const csv = buildCsv(headers, normalizedRows);
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  downloadCsv(csv, `tiber-workbench-journal-${stamp}.csv`);
}

function exportMissingBaselineCsv() {
  if (!state.missingBaselines?.available) return;
  const headers = ['player_name', 'player_id', 'team', 'position', 'draft_round', 'draft_pick', 'reason', 'source_status'];
  const csv = buildCsv(headers, state.missingBaselines.rows);
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  downloadCsv(csv, `tiber-workbench-missing-baselines-${stamp}.csv`);
}

function exportOutcomeCohortsCsv() {
  if (!state.outcomeSummary?.available) return;
  const rows = state.outcomeSummary.rows;
  const extraHeaders = [...new Set(rows.flatMap((row) => Object.keys(row || {})))].filter((key) => !['cohort', 'player_count', 'year_1_avg_ppr', 'year_1_median_ppr', 'complete_year_1_count'].includes(key));
  const headers = ['cohort', 'player_count', 'year_1_avg_ppr', 'year_1_median_ppr', 'complete_year_1_count', ...extraHeaders];
  const csv = buildCsv(headers, rows);
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  downloadCsv(csv, `tiber-workbench-outcome-cohorts-${stamp}.csv`);
}

function renderJournalSignals(selectedPlayer) {
  if (!state.journalSignals.available) {
    dom.journalPanel.innerHTML = '<p class="meta">Operator journal signal artifact unavailable.</p>';
    dom.journalTableBody.innerHTML = '<tr><td colspan="10" class="meta">Operator journal signal artifact unavailable.</td></tr>';
    dom.journalSelectedHint.textContent = 'Select a player to scope journal signals.';
    return;
  }

  const allRows = state.journalSignals.rows;
  const displayRows = getJournalRowsForDisplay(selectedPlayer);
  const needsReviewCount = allRows.filter((candidate) => candidate.review_status === 'needs_human_review').length;
  const modelEdgeCount = allRows.filter(isModelEdgeCandidate).length;
  const missingDataCount = allRows.filter(isMissingDataAuditCandidate).length;
  const landingSpotCount = allRows.filter(isLandingSpotOverProfileCandidate).length;

  dom.journalPanel.innerHTML = `
    <div class="summary-grid journal-summary-grid">
      <article class="summary-tile"><div class="summary-label">Total candidates</div><div class="summary-value">${allRows.length}</div></article>
      <article class="summary-tile"><div class="summary-label">Candidates needing review</div><div class="summary-value">${needsReviewCount}</div></article>
      <article class="summary-tile"><div class="summary-label">Model-edge validation candidates</div><div class="summary-value">${modelEdgeCount}</div></article>
      <article class="summary-tile"><div class="summary-label">Missing-data audit candidates</div><div class="summary-value">${missingDataCount}</div></article>
      <article class="summary-tile"><div class="summary-label">Landing-spot-over-profile candidates</div><div class="summary-value">${landingSpotCount}</div></article>
    </div>
  `;

  if (!displayRows.length) {
    const selectedMessage = selectedPlayer?.player_name
      ? `No journal candidates found for ${escapeHtml(selectedPlayer.player_name)} with active filters.`
      : 'No journal candidates matched active filters.';
    dom.journalTableBody.innerHTML = `<tr><td colspan="10" class="meta">${selectedMessage}</td></tr>`;
  } else {
    dom.journalTableBody.innerHTML = displayRows
      .map((candidate) => {
        const identity = [candidate.player_name || '—', candidate.team || '—', candidate.position || '—'].join(' / ');
        return `<tr>
          <td>${escapeHtml(candidate.candidate_id)}</td>
          <td>${escapeHtml(identity)}</td>
          <td>${escapeHtml(candidate.entity_type)}</td>
          <td>${escapeHtml(candidate.claim_summary)}</td>
          <td>${escapeHtml(candidate.positive_signal_tags.join(', ') || '—')}</td>
          <td>${escapeHtml(candidate.risk_tags.join(', ') || '—')}</td>
          <td>${escapeHtml(candidate.context_tags.join(', ') || '—')}</td>
          <td>${escapeHtml(candidate.model_impact || '—')}</td>
          <td>${escapeHtml(candidate.confidence)}</td>
          <td>${escapeHtml(candidate.review_status)}</td>
        </tr>`;
      })
      .join('');
  }

  if (selectedPlayer?.player_name) {
    dom.journalSelectedHint.textContent = `Showing journal candidates matching selected player: ${selectedPlayer.player_name}.`;
  } else {
    dom.journalSelectedHint.textContent = 'Showing journal candidates for all players/entities.';
  }
}

function render() {
  const sorted = getDisplayedPlayerRows();
  renderSummary(sorted);
  renderTable(sorted);
  const selected = getSelectedPlayerForJournalScope(sorted) || sorted[0] || null;
  renderDetail(selected);
  renderMissingBaselines();
  renderCalibration();
  renderJournalSignals(state.hasExplicitPlayerSelection ? selected : null);
}

function renderFilterOptions() {
  const positions = ['ALL', ...new Set(state.rows.map((row) => row.position).filter(Boolean))].sort();
  const rounds = ['ALL', ...new Set(state.rows.map((row) => (Number.isFinite(row.draft_round) ? String(row.draft_round) : 'UDFA')))].sort((a, b) => {
    if (a === 'ALL') return -1;
    if (b === 'ALL') return 1;
    if (a === 'UDFA') return 1;
    if (b === 'UDFA') return -1;
    return Number(a) - Number(b);
  });
  const sources = ['ALL', ...new Set(state.rows.map((row) => row.source_profile).filter(Boolean))].sort();

  dom.position.innerHTML = positions.map((value) => `<option value="${escapeHtml(value)}">Pos: ${escapeHtml(value)}</option>`).join('');
  dom.round.innerHTML = rounds.map((value) => `<option value="${escapeHtml(value)}">Round: ${escapeHtml(value)}</option>`).join('');
  dom.sourceProfile.innerHTML = sources.map((value) => `<option value="${escapeHtml(value)}">Source: ${escapeHtml(value)}</option>`).join('');

  dom.teamContext.innerHTML = `
    <option value="ALL">Team context: ALL</option>
    <option value="true">Team context: true</option>
    <option value="false">Team context: false</option>
    <option value="unknown">Team context: unknown</option>
  `;

  dom.delta.innerHTML = `
    <option value="ALL">Delta: ALL</option>
    <option value="positive">Delta: positive</option>
    <option value="negative">Delta: negative</option>
  `;
}

function wireEvents() {
  dom.search.addEventListener('input', () => {
    state.filters.search = dom.search.value.trim();
    render();
  });

  dom.position.addEventListener('change', () => {
    state.filters.position = dom.position.value;
    render();
  });

  dom.round.addEventListener('change', () => {
    state.filters.round = dom.round.value;
    render();
  });

  dom.teamContext.addEventListener('change', () => {
    state.filters.teamContextFound = dom.teamContext.value;
    render();
  });

  dom.sourceProfile.addEventListener('change', () => {
    state.filters.sourceProfile = dom.sourceProfile.value;
    render();
  });

  dom.delta.addEventListener('change', () => {
    state.filters.deltaDirection = dom.delta.value;
    render();
  });

  dom.exportPlayersCsv.addEventListener('click', () => {
    exportPlayersCsv();
  });

  dom.exportJournalCsv.addEventListener('click', () => {
    exportJournalCsv();
  });
  dom.exportMissingBaselineCsv?.addEventListener('click', () => {
    exportMissingBaselineCsv();
  });
  dom.exportOutcomeCohortsCsv?.addEventListener('click', () => {
    exportOutcomeCohortsCsv();
  });

  dom.journalSearch.addEventListener('input', () => {
    state.journalFilters.search = dom.journalSearch.value.trim();
    render();
  });

  dom.journalModelEdge.addEventListener('change', () => {
    state.journalFilters.modelEdge = dom.journalModelEdge.checked;
    render();
  });

  dom.journalMissingData.addEventListener('change', () => {
    state.journalFilters.missingDataAudit = dom.journalMissingData.checked;
    render();
  });

  dom.journalRoleOpportunity.addEventListener('change', () => {
    state.journalFilters.roleOpportunity = dom.journalRoleOpportunity.checked;
    render();
  });

  dom.journalNeedsReview.addEventListener('change', () => {
    state.journalFilters.needsHumanReview = dom.journalNeedsReview.checked;
    render();
  });

  dom.headers.forEach((header) => {
    header.addEventListener('click', () => {
      const key = header.dataset.sort;
      if (!key) return;

      if (state.sortKey === key) {
        state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
      } else {
        state.sortKey = key;
        state.sortDirection = key === 'player_name' || key === 'position' || key === 'team' || key === 'source_profile' ? 'asc' : 'desc';
      }

      dom.headers.forEach((target) => {
        const same = target.dataset.sort === state.sortKey;
        target.classList.toggle('sorted', same);
        if (!same) {
          target.textContent = target.textContent.replace(/\s[↑↓]$/, '');
          return;
        }

        const clean = target.textContent.replace(/\s[↑↓]$/, '');
        target.textContent = `${clean} ${state.sortDirection === 'asc' ? '↑' : '↓'}`;
      });

      render();
    });
  });
}

async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} (${response.status})`);
  }

  return response.json();
}

async function initialize() {
  const messages = [];

  try {
    const primaryPayload = await loadJson(PRIMARY_CONTEXT_PATH);
    const rows = coerceRows(primaryPayload).map(normalizeRow);
    state.rows = rows;
    messages.push(`Loaded primary team-context artifact (${rows.length} rows).`);
  } catch (error) {
    messages.push(`Primary team-context artifact unavailable (${error.message}).`);

    try {
      const fallbackPayload = await loadJson(POST_DRAFT_FALLBACK_PATH);
      const rows = coerceRows(fallbackPayload).map(normalizeRow);
      state.rows = rows;
      messages.push(`Loaded fallback post-draft artifact (${rows.length} rows). Team-context fields may be sparse.`);
    } catch (fallbackError) {
      dom.artifactStatus.textContent = `Failed to load player artifact: ${fallbackError.message}`;
      dom.summaryTiles.innerHTML = '<p class="meta">Unable to load any post-draft artifact.</p>';
      dom.tbody.innerHTML = '<tr><td colspan="19" class="meta">No player data available.</td></tr>';
      return;
    }
  }

  try {
    const missingPayload = await loadJson(MISSING_BASELINE_PATH);
    state.missingBaselines = { available: true, rows: coerceRows(missingPayload) };
    messages.push(`Loaded missing baseline artifact (${state.missingBaselines.rows.length} rows).`);
  } catch (error) {
    state.missingBaselines = { available: false, rows: [] };
    messages.push('Missing baseline artifact unavailable.');
  }

  try {
    const outcomePayload = await loadJson(OUTCOME_SUMMARY_PATH);
    state.outcomeSummary = { available: true, rows: coerceRows(outcomePayload) };
    messages.push(`Loaded outcome summary artifact (${state.outcomeSummary.rows.length} cohorts).`);
  } catch (error) {
    state.outcomeSummary = { available: false, rows: [] };
    messages.push('Outcome calibration artifact unavailable.');
  }

  try {
    const journalPayload = await loadJson(JOURNAL_SIGNAL_PATH);
    const rows = (Array.isArray(journalPayload) ? journalPayload : coerceRows(journalPayload)).map(normalizeJournalCandidate);
    state.journalSignals = { available: true, rows };
    messages.push(`Loaded operator journal signal artifact (${rows.length} candidates).`);
  } catch (error) {
    state.journalSignals = { available: false, rows: [] };
    messages.push('Operator journal signal artifact unavailable.');
  }

  dom.artifactStatus.textContent = messages.join(' ');

  const lookups = buildInspectionLookups();
  state.rows = state.rows.map((row) => enrichInspectionStatus(row, lookups));

  renderFilterOptions();
  wireEvents();
  render();
}

initialize();
