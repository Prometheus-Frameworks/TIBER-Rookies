/**
 * @typedef {{label:string,value:number|null}} RookieScore
 * @typedef {{label:string,value:number|null,display:string,percent:number|null,family:string,direction:'higher'|'lower',source:string}} RookieMetric
 * @typedef {{season:number,team:string,games:number|null,statLine:Record<string, number|string>}} RookieSeasonRow
 * @typedef {{playerId:string,slug:string,identity:{name:string,position:string|null,positionLabel:string,roleLabel:string,school:string|null,schoolDisplay:string,classYear:number,height:string|null,weight:string|null},summary:{rookieGrade:number|null,classRank:number|null,archetype:string|null,projection:string|null,profileSummary:string,identityNote:string,boardSummary:string},comps:{high:string|null,low:string|null},scores:RookieScore[],metrics:RookieMetric[],seasons:RookieSeasonRow[],tags:string[],translationFlags:string[],contextSignals:{evidenceTags:string[],contextFlags:string[],evidenceSummary:string|null,raw:Record<string, unknown>|null},evidence:{availableCount:number,totalCount:number,readinessLabel:string,metricFamiliesAvailable:string[],missingModelInputs:string[]}} RookieCardData
 */

import { deriveRookieProfileSummary } from './deriveRookieProfileSummary.js';
import { normalizeRookieIdentity } from './normalizeRookieIdentity.js';
import { athleticMetricLabel } from './athleticLabel.js';

// Rounding tolerance for reconciling the Alpha snapshot embedded in a PPR
// projection row against the current promoted Alpha. The PPR export carries a
// 1-decimal Alpha copy, so anything within half a tenth is the same snapshot.
const PPR_ALPHA_MATCH_TOLERANCE = 0.05;

// Parse and validate a governed official outcome. Returns null (→ the caller
// fails closed as unavailable) when the outcome is absent OR violates the
// documented invariants, so malformed/inconsistent governed data is never shown
// as authoritative.
function readOfficialOutcome(transitionProfileRow) {
  const outcome = transitionProfileRow?.official_postdraft_outcome ?? null;
  if (!outcome || typeof outcome !== 'object') return null;
  const value = outcome.value ?? null;
  if (!value || typeof value !== 'object') return null;
  const provenance = outcome.provenance ?? null;

  const status = value.status;
  const isUdfa = value.is_udfa === true;
  const team = typeof value.nfl_team === 'string' && value.nfl_team.trim() ? value.nfl_team : null;
  const round = value.draft_round;
  const pick = value.overall_pick;
  const nonEmpty = (s) => typeof s === 'string' && s.trim().length > 0;

  // Promoted-artifact provenance invariants: an externally verified, official
  // draft result with a named, linked source and a confidence band. Proxy or
  // unverified provenance must not cross this fail-closed boundary.
  // (last_verified_at is not universal in the promoted artifact, so not required.)
  if (value.source_status !== 'external_verified') return null;
  // Strict membership: the field must be present as explicit null or
  // 'source_verified'. An omitted (undefined) status fails closed rather than
  // being treated as an allowed explicit null.
  const upstream = value.upstream_provenance_status;
  if (!(upstream === null || upstream === 'source_verified')) return null;
  if (!provenance || typeof provenance !== 'object') return null;
  if (provenance.source_type !== 'official_draft_result') return null;
  if (!nonEmpty(provenance.source_name) || !nonEmpty(provenance.source_url) || !nonEmpty(provenance.confidence_band)) return null;

  // Team identity is required for any recognized outcome.
  if (!team) return null;

  // Status-specific consistency: is_udfa must be an explicit boolean agreeing
  // with the status; drafted needs integer round/pick; udfa_signed needs none.
  if (status === 'drafted') {
    if (value.is_udfa !== false) return null;
    if (!Number.isInteger(round) || round < 1) return null;
    if (!Number.isInteger(pick) || pick < 1) return null;
  } else if (status === 'udfa_signed') {
    if (value.is_udfa !== true) return null;
    if (round != null || pick != null) return null;
  } else {
    return null; // unrecognized status
  }

  return {
    status,
    nflTeam: team,
    draftRound: round ?? null,
    overallPick: pick ?? null,
    isUdfa,
    sourceStatus: value.source_status,
    provenance: {
      sourceName: provenance.source_name ?? null,
      sourceUrl: provenance.source_url ?? null,
      confidence: Number.isFinite(provenance.confidence) ? provenance.confidence : null,
      confidenceBand: provenance.confidence_band ?? null,
      lastVerifiedAt: provenance.last_verified_at ?? null,
    },
  };
}

const METRIC_METADATA = {
  RAS: { family: 'athletic', direction: 'higher', source: 'combine+alpha' },
  'ATH (SPORQ)': { family: 'athletic', direction: 'higher', source: 'sporq+alpha' },
  'ATH (partial)': { family: 'athletic', direction: 'higher', source: 'combine_fallback+alpha' },
  'Production Score': { family: 'production', direction: 'higher', source: 'production+alpha' },
  'Draft Capital Proxy': { family: 'capital', direction: 'higher', source: 'draft+alpha' },
  '40 Yard Dash (s)': { family: 'athletic', direction: 'lower', source: 'combine' },
  '3-Cone (s)': { family: 'athletic', direction: 'lower', source: 'combine' },
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
export function mapRookieToCard({ alphaPlayer, statsRow, pprRow, dynastyRow, trendRow, draftResultRow, transitionProfileRow, transitionProfileStatus, transitionProfileVersion, alphaModel, alphaGeneratedAt, rank }) {
  const identity = normalizeRookieIdentity({ alphaPlayer });
  const weight = null;
  const height = null;
  const ras = alphaPlayer?.scores?.ras_0_100 ?? null;
  const athleticScore = alphaPlayer?.scores?.athletic_score_0_100 ?? ras;
  const athleticSource = alphaPlayer?.scores?.athletic_source ?? (ras != null ? 'RAS' : null);
  const athleticConfidence = alphaPlayer?.scores?.athletic_confidence ?? 0;
  const athleticExplainer = alphaPlayer?.scores?.athletic_explainer ?? null;
  const production = alphaPlayer?.scores?.production_0_100 ?? null;
  // draft_capital_proxy_0_100 is an overall market-investment proxy (overall board / NFL pick),
  // not a positional consensus rank. Keep this distinct from consensus_delta_positional.
  const draftCapital = alphaPlayer?.scores?.draft_capital_proxy_0_100 ?? null;
  const rookieGrade = alphaPlayer?.scores?.rookie_alpha_0_100 ?? null;
  const ageAdjustedProduction = alphaPlayer?.scores?.age_adjusted_production_0_100 ?? null;
  // Use position-aware positional consensus delta; fall back to null when unavailable.
  // The old consensus_delta field (alpha - draft_capital_proxy) has been renamed to
  // market_investment_delta_legacy in the export and must not be used for display.
  const consensusDelta = alphaPlayer?.scores?.consensus_delta_positional ?? null;
  const evidenceTier = alphaPlayer?.scores?.evidence_tier ?? null;
  const evidenceTierReason = alphaPlayer?.scores?.evidence_tier_reason ?? null;
  const isCappedDisagreement = alphaPlayer?.scores?.is_capped_disagreement ?? null;
  const breakoutAge = alphaPlayer?.context?.breakout_age ?? null;
  const youngBreakoutFlag = alphaPlayer?.context?.young_breakout_flag ?? false;
  const breakoutAgeRating = alphaPlayer?.context?.breakout_age_rating_0_100 ?? null;
  const breakoutStrength = alphaPlayer?.context?.breakout_strength ?? null;
  const breakoutConfidence = alphaPlayer?.context?.breakout_confidence ?? null;
  const breakoutLabel = alphaPlayer?.context?.breakout_label ?? null;
  const missingModelInputs = Array.isArray(alphaPlayer?.model_inputs_missing) ? alphaPlayer.model_inputs_missing : [];
  const evidenceTags = Array.isArray(alphaPlayer?.evidence?.evidence_tags) ? alphaPlayer.evidence.evidence_tags : [];
  const contextFlags = Array.isArray(alphaPlayer?.evidence?.context_flags) ? alphaPlayer.evidence.context_flags : [];
  const translationFlags = Array.isArray(alphaPlayer?.evidence?.translation_flags) ? alphaPlayer.evidence.translation_flags : [];
  const evidenceSummary = typeof alphaPlayer?.evidence?.evidence_summary === 'string'
    ? alphaPlayer.evidence.evidence_summary
    : null;
  // Fail-closed reconciliation: the PPR export embeds a copy of the Alpha it was
  // built from. If that snapshot no longer matches the current promoted Alpha,
  // the projection is stale and its numbers are withheld rather than shown as
  // current. Matching projections render normally.
  const pprAlphaEmbedded = Number.isFinite(pprRow?.rookie_alpha_0_100) ? pprRow.rookie_alpha_0_100 : null;
  const pprAlphaMatches = pprRow != null
    && pprAlphaEmbedded != null
    && rookieGrade != null
    && Math.abs(pprAlphaEmbedded - rookieGrade) <= PPR_ALPHA_MATCH_TOLERANCE;
  const pprProjection = !pprRow
    ? null
    : pprAlphaMatches
      ? {
          floor: pprRow.ppr_floor,
          median: pprRow.ppr_median,
          ceiling: pprRow.ppr_ceiling,
          band: pprRow.projection_band,
          projectionMethod: pprRow.projection_method ?? null,
          dataGapFlag: pprRow.data_gap_flag === true,
          dataGapNote: pprRow.data_gap_note ?? null,
          stale: false,
        }
      : {
          stale: true,
          embeddedAlpha: pprAlphaEmbedded,
          currentAlpha: rookieGrade,
          floor: null,
          median: null,
          ceiling: null,
          band: null,
          projectionMethod: pprRow.projection_method ?? null,
          dataGapFlag: pprRow.data_gap_flag === true,
          dataGapNote: pprRow.data_gap_note ?? null,
        };

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

  const athLabel = athleticMetricLabel(athleticSource);
  const metrics = [
    { label: athLabel, value: athleticScore, display: athleticScore != null ? athleticScore.toFixed(1) : 'N/A', percent: athleticScore },
    { label: 'Production Score', value: production, display: production != null ? production.toFixed(1) : 'N/A', percent: production },
    { label: 'Draft Capital Proxy', value: draftCapital, display: draftCapital != null ? draftCapital.toFixed(1) : 'N/A', percent: draftCapital },
    // 5.0s is the reference upper bound for a quick 40-yard normalization in this prototype.
    { label: '40 Yard Dash (s)', value: null, display: 'N/A', percent: null },
    { label: '3-Cone (s)', value: null, display: 'N/A', percent: null },
    { label: 'Vertical (in)', value: null, display: 'N/A', percent: null },
    { label: 'Broad Jump (in)', value: null, display: 'N/A', percent: null },
  ].map(withMetricMetadata);

  const profileContext = deriveRookieProfileSummary({
    identity,
    rookieGrade,
    athleticScore,
    production,
    draftCapital,
    missingInputs: missingModelInputs,
  });

  const availableMetrics = metrics.filter((metric) => metric.value != null);
  const tags = [
    scoreBandTag('Athlete', athleticScore),
    scoreBandTag('Production', production),
    draftCapital != null ? (draftCapital >= 75 ? 'Draft capital-friendly profile' : 'Later-capital profile') : null,
    profileContext.archetype,
    ...evidenceTags.slice(0, 2).map(toTitleLabel),
  ].filter(Boolean);

  const nflContextTeam = alphaPlayer?.context?.nfl_team ?? null;

  // Official NFL identity/draft facts. The ungoverned draft-results supplement
  // may fill display facts ONLY for classes that have no governed profile by
  // design (transitionProfileStatus === 'not_expected', i.e. pre-2026). Every
  // other status — including unknown/missing/unrecognized — fails closed.
  //
  //   not_expected → fall back to the draft-results supplement (no governed layer).
  //   loaded       → use the player's governed outcome; a missing or malformed
  //                  outcome fails closed as unavailable (no supplement fallback).
  //   load_failed  → unavailable (governed source did not load).
  //   anything else→ unavailable (unknown status; no fallback).
  //
  // No score is derived here — the pre-draft Alpha stays frozen and no
  // post-draft grade is computed.
  const allowSupplementFallback = transitionProfileStatus === 'not_expected';
  const unavailable = (reason) => ({
    status: 'unavailable',
    reason,
    nflTeam: null,
    draftRound: null,
    overallPick: null,
    isUdfa: false,
    sourceStatus: null,
    provenance: null,
  });

  let officialOutcome;
  if (transitionProfileStatus === 'not_expected') {
    officialOutcome = null; // no governed layer; supplement may fill display facts
  } else if (transitionProfileStatus === 'loaded') {
    const parsed = readOfficialOutcome(transitionProfileRow);
    officialOutcome = parsed
      ? { ...parsed, schemaVersion: transitionProfileVersion ?? null }
      : unavailable('governed_outcome_missing');
  } else if (transitionProfileStatus === 'load_failed') {
    officialOutcome = unavailable('governed_source_load_failed');
  } else {
    // Unknown, missing, or unrecognized status — fail closed, no fallback.
    officialOutcome = unavailable('governed_status_unknown');
  }
  const officialGoverned = officialOutcome != null && officialOutcome.status !== 'unavailable';

  const officialTeam = officialGoverned
    ? officialOutcome.nflTeam
    : (allowSupplementFallback ? (draftResultRow?.nfl_team ?? nflContextTeam) : null);
  const officialRound = officialGoverned
    ? officialOutcome.draftRound
    : (allowSupplementFallback && Number.isFinite(draftResultRow?.draft_round) ? draftResultRow.draft_round : null);
  const officialPick = officialGoverned
    ? officialOutcome.overallPick
    : (allowSupplementFallback && Number.isFinite(draftResultRow?.overall_pick) ? draftResultRow.overall_pick : null);
  const officialIsUdfa = officialGoverned
    ? officialOutcome.isUdfa
    : (allowSupplementFallback ? (draftResultRow?.is_udfa === true) : false);
  const hasDraftOutcome = Boolean(
    officialGoverned
    || (allowSupplementFallback && draftResultRow && (
      draftResultRow.is_udfa === true
      || Number.isFinite(draftResultRow.draft_round)
      || Number.isFinite(draftResultRow.overall_pick)
      || typeof draftResultRow.nfl_team === 'string'
    ))
  );

  // Frozen, dated pre-draft baseline. The Alpha is disclosed as a snapshot with
  // its model version and generation date, not as a live player rating. No
  // post-draft numeric grade is published on the card.
  const preDraftBaseline = {
    grade: rookieGrade,
    modelVersion: alphaModel?.model_version ?? null,
    stage: alphaModel?.stage ?? 'pre-draft',
    generatedAt: alphaGeneratedAt ?? null,
  };
  const postDraftStatus = 'not_yet_published';

  return {
    playerId: alphaPlayer.player_id,
    slug: String(alphaPlayer.player_id).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''),
    identity: {
      ...identity,
      height,
      weight,
      nflTeam: officialTeam,
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
      { label: 'Pre-Draft Grade', value: rookieGrade },
      { label: 'ATH', value: athleticScore },
      { label: 'Production', value: production },
      { label: 'Draft Capital', value: draftCapital },
      { label: 'Model Edge', value: consensusDelta },
    ],
    metrics,
    seasons: buildSeasonRows(statsRow),
    tags,
    translationFlags,
    athleticScore,
    productionScore: production,
    draftCapitalScore: draftCapital,
    athleticSource,
    athleticConfidence,
    athleticExplainer,
    breakoutAge,
    youngBreakoutFlag,
    breakoutAgeRating,
    breakoutStrength,
    breakoutConfidence,
    breakoutLabel,
    ageAdjustedProduction,
    consensusDelta,
    evidenceTier,
    evidenceTierReason,
    isCappedDisagreement,
    dynastyDelta,
    dynastyAdp,
    volumeTrend,
    efficiencyTrend,
    volumeMetric,
    volume2024,
    volume2025,
    pprProjection,
    draft: {
      nflTeam: officialTeam,
      draftRound: officialRound,
      overallPick: officialPick,
      draftDay: draftResultRow?.draft_day ?? null,
      draftCapitalTier: draftResultRow?.draft_capital_tier ?? null,
      isUdfa: officialIsUdfa,
      hasDraftOutcome,
      provenanceSource: officialGoverned
        ? 'transition_profile'
        : (allowSupplementFallback && draftResultRow ? 'draft_results_supplement' : null),
    },
    // Governed official NFL outcome with per-field provenance (transition
    // profile). Null for classes without a transition profile artifact.
    officialOutcome,
    preDraftBaseline,
    preDraftGrade: rookieGrade,
    preDraftRank: rank,
    // No competing post-draft grade is computed in browser code; the card
    // discloses status only.
    postDraftGrade: null,
    postDraftStatus,
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
