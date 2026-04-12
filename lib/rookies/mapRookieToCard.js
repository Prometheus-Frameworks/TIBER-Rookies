/**
 * @typedef {{label:string,value:number|null}} RookieScore
 * @typedef {{label:string,value:number|null,display:string,percent:number|null,family:string,direction:'higher'|'lower',source:string}} RookieMetric
 * @typedef {{season:number,team:string,games:number|null,statLine:Record<string, number|string>}} RookieSeasonRow
 * @typedef {{playerId:string,slug:string,identity:{name:string,position:string|null,positionLabel:string,roleLabel:string,school:string|null,schoolDisplay:string,classYear:number,height:string|null,weight:string|null},summary:{rookieGrade:number|null,classRank:number|null,archetype:string|null,projection:string|null,profileSummary:string,identityNote:string,boardSummary:string},comps:{high:string|null,low:string|null},scores:RookieScore[],metrics:RookieMetric[],seasons:RookieSeasonRow[],tags:string[],translationFlags:string[],contextSignals:{evidenceTags:string[],contextFlags:string[],evidenceSummary:string|null,raw:Record<string, unknown>|null},evidence:{availableCount:number,totalCount:number,readinessLabel:string,metricFamiliesAvailable:string[],missingModelInputs:string[]}} RookieCardData
 */

import { deriveRookieProfileSummary } from './deriveRookieProfileSummary.js';
import { normalizeRookieIdentity } from './normalizeRookieIdentity.js';

const METRIC_METADATA = {
  RAS: { family: 'athletic', direction: 'higher', source: 'combine+alpha' },
  'Production Score': { family: 'production', direction: 'higher', source: 'production+alpha' },
  'Draft Capital Proxy': { family: 'capital', direction: 'higher', source: 'draft+alpha' },
  '40 Yard Dash (s)': { family: 'athletic', direction: 'lower', source: 'combine' },
  'Vertical (in)': { family: 'athletic', direction: 'higher', source: 'combine' },
  'Broad Jump (in)': { family: 'athletic', direction: 'higher', source: 'combine' },
};

function scoreBandTag(label, value) {
  if (value == null) return null;
  if (value >= 80) return `Elite ${label}`;
  if (value >= 70) return `Strong ${label}`;
  return `Developmental ${label}`;
}

function withMetricMetadata(metric) {
  // Unlisted metrics default to direction:'higher'; add an entry to METRIC_METADATA for any lower-is-better metric.
  const metadata = METRIC_METADATA[metric.label] ?? {
    family: 'context',
    direction: 'higher',
    source: 'mapped',
  };
  return {
    ...metric,
    family: metadata.family,
    direction: metadata.direction,
    source: metadata.source,
  };
}


function buildSeasonRows(statsRow) {
  if (!statsRow || !statsRow.stats || Object.keys(statsRow.stats).length === 0) return [];
  return [{
    season: statsRow.season,
    team: statsRow.school,
    games: null,
    statLine: statsRow.stats,
  }];
}

function toTitleLabel(tag) {
  return String(tag ?? '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

/** @returns {RookieCardData} */
export function mapRookieToCard({ alphaPlayer, combineRow, productionRow, draftRow, statsRow, pprRow, dynastyRow, trendRow, rank }) {
  const identity = normalizeRookieIdentity({ alphaPlayer, combineRow, productionRow, draftRow });
  const weight = combineRow?.weight_lb ? `${combineRow.weight_lb} lb` : null;
  const height = combineRow?.height_in ? `${Math.floor(combineRow.height_in / 12)}'${combineRow.height_in % 12}"` : null;
  const ras = alphaPlayer?.scores?.ras_0_100 ?? null;
  const production = productionRow?.production_score_0_100 ?? alphaPlayer?.scores?.production_0_100 ?? null;
  const draftCapital = draftRow?.draft_capital_proxy_0_100 ?? alphaPlayer?.scores?.draft_capital_proxy_0_100 ?? null;
  const rookieGrade = alphaPlayer?.scores?.rookie_alpha_0_100 ?? null;
  const ageAdjustedProduction = alphaPlayer?.scores?.age_adjusted_production_0_100 ?? null;
  const consensusDelta = alphaPlayer?.scores?.consensus_delta ?? null;
  const breakoutAge = alphaPlayer?.context?.breakout_age ?? null;
  const youngBreakoutFlag = alphaPlayer?.context?.young_breakout_flag ?? false;
  const missingModelInputs = Array.isArray(alphaPlayer?.model_inputs_missing) ? alphaPlayer.model_inputs_missing : [];
  const evidenceTags = Array.isArray(alphaPlayer?.evidence?.evidence_tags) ? alphaPlayer.evidence.evidence_tags : [];
  const contextFlags = Array.isArray(alphaPlayer?.evidence?.context_flags) ? alphaPlayer.evidence.context_flags : [];
  const translationFlags = Array.isArray(alphaPlayer?.evidence?.translation_flags) ? alphaPlayer.evidence.translation_flags : [];
  const evidenceSummary = typeof alphaPlayer?.evidence?.evidence_summary === 'string'
    ? alphaPlayer.evidence.evidence_summary
    : null;
  const pprProjection = pprRow
    ? { floor: pprRow.ppr_floor, median: pprRow.ppr_median, ceiling: pprRow.ppr_ceiling, band: pprRow.projection_band }
    : null;

  const dynastyAdp = dynastyRow?.dynasty_adp_0_100 ?? null;
  const dynastyDelta = (rookieGrade != null && dynastyAdp != null)
    ? Math.round((rookieGrade - dynastyAdp) * 10) / 10
    : null;

  // volume_trend: 'up' | 'down' | 'neutral' — null when no prior-year data
  const rawVolumeTrend = trendRow?.volume_trend ?? null;
  const volumeTrend = (rawVolumeTrend === 'neutral' && !trendRow?.volume_2024)
    ? null   // no 2024 data → don't show a trend arrow
    : rawVolumeTrend;
  const efficiencyTrend = trendRow?.efficiency_trend ?? null;
  const volumeMetric = trendRow?.volume_metric ?? null;
  const volume2024 = trendRow?.volume_2024 ?? null;
  const volume2025 = trendRow?.volume_2025 ?? null;

  const metrics = [
    { label: 'RAS', value: ras, display: ras != null ? ras.toFixed(1) : 'N/A', percent: ras },
    { label: 'Production Score', value: production, display: production != null ? production.toFixed(1) : 'N/A', percent: production },
    { label: 'Draft Capital Proxy', value: draftCapital, display: draftCapital != null ? draftCapital.toFixed(1) : 'N/A', percent: draftCapital },
    // 5.0s is the reference upper bound for a quick 40-yard normalization in this prototype.
    { label: '40 Yard Dash (s)', value: combineRow?.forty ?? null, display: combineRow?.forty != null ? combineRow.forty.toFixed(2) : 'N/A', percent: combineRow?.forty ? Math.max(0, Math.min(100, (5 - combineRow.forty) * 100)) : null },
    { label: 'Vertical (in)', value: combineRow?.vertical ?? null, display: combineRow?.vertical != null ? `${combineRow.vertical}` : 'N/A', percent: combineRow?.vertical ? Math.max(0, Math.min(100, (combineRow.vertical / 45) * 100)) : null },
    { label: 'Broad Jump (in)', value: combineRow?.broad ?? null, display: combineRow?.broad != null ? `${combineRow.broad}` : 'N/A', percent: combineRow?.broad ? Math.max(0, Math.min(100, (combineRow.broad / 140) * 100)) : null },
  ].map(withMetricMetadata);

  const profileContext = deriveRookieProfileSummary({
    identity,
    rookieGrade,
    ras,
    production,
    draftCapital,
    missingInputs: missingModelInputs,
  });

  const availableMetrics = metrics.filter((metric) => metric.value != null);
  const tags = [
    scoreBandTag('Athlete', ras),
    scoreBandTag('Production', production),
    draftCapital != null ? (draftCapital >= 75 ? 'Draft capital-friendly profile' : 'Later-capital profile') : null,
    profileContext.archetype,
    ...evidenceTags.slice(0, 2).map(toTitleLabel),
  ].filter(Boolean);

  const nflTeam = alphaPlayer?.context?.nfl_team ?? null;

  return {
    playerId: alphaPlayer.player_id,
    slug: String(alphaPlayer.player_id).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''),
    identity: {
      ...identity,
      height,
      weight,
      nflTeam,
    },
    summary: {
      rookieGrade,
      classRank: rank,
      archetype: profileContext.archetype,
      projection: profileContext.projection,
      profileSummary: profileContext.profileSummary,
      identityNote: profileContext.identityNote,
      boardSummary: profileContext.boardSummary,
    },
    comps: { high: null, low: null },
    scores: [
      { label: 'Rookie Alpha', value: rookieGrade },
      { label: 'RAS', value: ras },
      { label: 'Production', value: production },
      { label: 'Draft Capital', value: draftCapital },
      { label: 'Model Edge', value: consensusDelta },
    ],
    metrics,
    seasons: buildSeasonRows(statsRow),
    tags,
    translationFlags,
    breakoutAge,
    youngBreakoutFlag,
    ageAdjustedProduction,
    consensusDelta,
    dynastyDelta,
    dynastyAdp,
    volumeTrend,
    efficiencyTrend,
    volumeMetric,
    volume2024,
    volume2025,
    pprProjection,
    contextSignals: {
      evidenceTags,
      contextFlags,
      evidenceSummary,
      raw: alphaPlayer?.context ?? null,
    },
    evidence: {
      availableCount: availableMetrics.length,
      totalCount: metrics.length,
      readinessLabel: `${availableMetrics.length}/${metrics.length} metrics available`,
      metricFamiliesAvailable: [...new Set(availableMetrics.map((metric) => metric.family))],
      missingModelInputs,
    },
  };
}
