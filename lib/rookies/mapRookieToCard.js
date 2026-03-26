/**
 * @typedef {{label:string,value:number|null}} RookieScore
 * @typedef {{label:string,value:number|null,display:string,percent:number|null,family:string,direction:'higher'|'lower',source:string}} RookieMetric
 * @typedef {{season:number,team:string,games:number|null,statLine:Record<string, number|string>}} RookieSeasonRow
 * @typedef {{playerId:string,slug:string,identity:{name:string,position:string|null,positionLabel:string,roleLabel:string,school:string|null,schoolDisplay:string,classYear:number,height:string|null,weight:string|null},summary:{rookieGrade:number|null,classRank:number|null,archetype:string|null,projection:string|null,profileSummary:string,identityNote:string,boardSummary:string},comps:{high:string|null,low:string|null},scores:RookieScore[],metrics:RookieMetric[],seasons:RookieSeasonRow[],tags:string[],evidence:{availableCount:number,totalCount:number,readinessLabel:string,metricFamiliesAvailable:string[],missingModelInputs:string[]}} RookieCardData
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

/** @returns {RookieCardData} */
export function mapRookieToCard({ alphaPlayer, combineRow, productionRow, draftRow, rank }) {
  const identity = normalizeRookieIdentity({ alphaPlayer, combineRow, productionRow, draftRow });
  const weight = combineRow?.weight_lb ? `${combineRow.weight_lb} lb` : null;
  const height = combineRow?.height_in ? `${Math.floor(combineRow.height_in / 12)}'${combineRow.height_in % 12}"` : null;
  const ras = alphaPlayer?.scores?.ras_0_100 ?? null;
  const production = productionRow?.production_score_0_100 ?? alphaPlayer?.scores?.production_0_100 ?? null;
  const draftCapital = draftRow?.draft_capital_proxy_0_100 ?? alphaPlayer?.scores?.draft_capital_proxy_0_100 ?? null;
  const rookieGrade = alphaPlayer?.scores?.rookie_alpha_0_100 ?? null;
  const missingModelInputs = Array.isArray(alphaPlayer?.model_inputs_missing) ? alphaPlayer.model_inputs_missing : [];

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
  ].filter(Boolean);

  return {
    playerId: alphaPlayer.player_id,
    slug: String(alphaPlayer.player_id).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''),
    identity: {
      ...identity,
      height,
      weight,
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
    ],
    metrics,
    seasons: [],
    tags,
    evidence: {
      availableCount: availableMetrics.length,
      totalCount: metrics.length,
      readinessLabel: `${availableMetrics.length}/${metrics.length} metrics available`,
      metricFamiliesAvailable: [...new Set(availableMetrics.map((metric) => metric.family))],
      missingModelInputs,
    },
  };
}
