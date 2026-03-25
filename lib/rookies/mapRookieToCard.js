/**
 * @typedef {{label:string,value:number|null}} RookieScore
 * @typedef {{label:string,value:number|null,display:string,percent:number|null}} RookieMetric
 * @typedef {{season:number,team:string,games:number|null,statLine:Record<string, number|string>}} RookieSeasonRow
 * @typedef {{playerId:string,slug:string,identity:{name:string,position:string,school:string|null,classYear:number,height:string|null,weight:string|null},summary:{rookieGrade:number|null,classRank:number|null,archetype:string|null,projection:string|null},comps:{high:string|null,low:string|null},scores:RookieScore[],metrics:RookieMetric[],seasons:RookieSeasonRow[],tags:string[]}} RookieCardData
 */

const ARCHETYPE_BY_POSITION = {
  RB: 'Backfield anchor profile',
  WR: 'Field-stretch receiver profile',
  QB: 'Pocket-first projection',
  TE: 'Move tight end profile',
};

const PROJECTION_BY_POSITION = {
  RB: 'Rookie committee with lead-upside path',
  WR: 'Rotational outside receiver trajectory',
  QB: 'Developmental starter trajectory',
  TE: 'Passing-down role translation path',
};

function scoreBandTag(label, value) {
  if (value == null) return null;
  if (value >= 80) return `Elite ${label}`;
  if (value >= 70) return `Strong ${label}`;
  return `Developmental ${label}`;
}

/** @returns {RookieCardData} */
export function mapRookieToCard({ alphaPlayer, combineRow, productionRow, draftRow, rank }) {
  const weight = combineRow?.weight_lb ? `${combineRow.weight_lb} lb` : null;
  const height = combineRow?.height_in ? `${Math.floor(combineRow.height_in / 12)}'${combineRow.height_in % 12}"` : null;
  const ras = alphaPlayer?.scores?.ras_0_100 ?? null;
  const production = productionRow?.production_score_0_100 ?? alphaPlayer?.scores?.production_0_100 ?? null;
  const draftCapital = draftRow?.draft_capital_proxy_0_100 ?? alphaPlayer?.scores?.draft_capital_proxy_0_100 ?? null;
  const rookieGrade = alphaPlayer?.scores?.rookie_alpha_0_100 ?? null;

  const metrics = [
    { label: 'RAS', value: ras, display: ras != null ? ras.toFixed(1) : 'N/A', percent: ras },
    { label: 'Production Score', value: production, display: production != null ? production.toFixed(1) : 'N/A', percent: production },
    { label: 'Draft Capital Proxy', value: draftCapital, display: draftCapital != null ? draftCapital.toFixed(1) : 'N/A', percent: draftCapital },
    // 5.0s is the reference upper bound for a quick 40-yard normalization in this prototype.
    { label: '40 Yard Dash (s)', value: combineRow?.forty ?? null, display: combineRow?.forty != null ? combineRow.forty.toFixed(2) : 'N/A', percent: combineRow?.forty ? Math.max(0, Math.min(100, (5 - combineRow.forty) * 100)) : null },
    { label: 'Vertical (in)', value: combineRow?.vertical ?? null, display: combineRow?.vertical != null ? `${combineRow.vertical}` : 'N/A', percent: combineRow?.vertical ? Math.max(0, Math.min(100, (combineRow.vertical / 45) * 100)) : null },
    { label: 'Broad Jump (in)', value: combineRow?.broad ?? null, display: combineRow?.broad != null ? `${combineRow.broad}` : 'N/A', percent: combineRow?.broad ? Math.max(0, Math.min(100, (combineRow.broad / 140) * 100)) : null },
  ];

  const tags = [
    scoreBandTag('Athlete', ras),
    scoreBandTag('Production', production),
    draftCapital != null ? (draftCapital >= 75 ? 'Draft capital-friendly profile' : 'Later-capital profile') : null,
  ].filter(Boolean);

  return {
    playerId: alphaPlayer.player_id,
    slug: String(alphaPlayer.player_id).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''),
    identity: {
      name: alphaPlayer.player_name,
      position: alphaPlayer.position,
      school: null,
      classYear: 2026,
      height,
      weight,
    },
    summary: {
      rookieGrade,
      classRank: rank,
      archetype: ARCHETYPE_BY_POSITION[alphaPlayer.position] ?? null,
      projection: PROJECTION_BY_POSITION[alphaPlayer.position] ?? null,
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
  };
}
