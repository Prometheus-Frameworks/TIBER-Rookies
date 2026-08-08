import { deriveRookieTier } from './deriveRookieTier.js';

export const ROOKIE_STUB_PATH = '/data/processed/2026_rookie_stubs_v0.json';
export const ROOKIE_STUB_ALPHA_STATUS = 'not_scored';
export const ROOKIE_STUB_REASON = 'below_day2_scoring_floor';
export const ROOKIE_STUB_STATUS_COPY = 'unscored — draft-fact only';

const PROVENANCE_FIELDS = [
  'source_name',
  'source_url',
  'source_status',
  'upstream_provenance_status',
  'ingested_from',
  'ingested_at',
];

let rookieStubsPromise = null;

function nonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function toSlug(playerId) {
  return String(playerId ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function normalizeRookieStub(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  if (!nonEmptyString(raw.player_id) || raw.player_id !== raw.player_id.trim().toLowerCase()) return null;
  if (!nonEmptyString(raw.name) || !nonEmptyString(raw.position) || !nonEmptyString(raw.team)) return null;
  if (!Number.isInteger(raw.round) || raw.round < 1 || raw.round > 7) return null;
  if (!Number.isInteger(raw.overall_pick) || raw.overall_pick < 1) return null;
  if (raw.alpha_status !== ROOKIE_STUB_ALPHA_STATUS || raw.reason !== ROOKIE_STUB_REASON) return null;
  if (!raw.provenance || typeof raw.provenance !== 'object' || Array.isArray(raw.provenance)) return null;
  if (PROVENANCE_FIELDS.some((field) => !nonEmptyString(raw.provenance[field]))) return null;

  return {
    playerId: raw.player_id,
    slug: toSlug(raw.player_id),
    name: raw.name,
    position: raw.position,
    team: raw.team,
    round: raw.round,
    overallPick: raw.overall_pick,
    alphaStatus: raw.alpha_status,
    reason: raw.reason,
    provenance: Object.fromEntries(
      PROVENANCE_FIELDS.map((field) => [field, raw.provenance[field]]),
    ),
  };
}

export function normalizeRookieStubs(payload) {
  if (!Array.isArray(payload)) {
    throw new Error('Rookie stub artifact must be a top-level array.');
  }

  const normalized = payload.map(normalizeRookieStub);
  const invalidIndex = normalized.findIndex((stub) => stub == null);
  if (invalidIndex >= 0) {
    throw new Error(`Rookie stub artifact row ${invalidIndex} is malformed.`);
  }

  const seen = new Set();
  for (const stub of normalized) {
    if (seen.has(stub.playerId)) {
      throw new Error(`Rookie stub artifact contains duplicate player_id: ${stub.playerId}`);
    }
    seen.add(stub.playerId);
  }

  return normalized;
}

export async function get2026RookieStubs() {
  if (!rookieStubsPromise) {
    rookieStubsPromise = fetch(ROOKIE_STUB_PATH).then(async (response) => {
      if (!response.ok) {
        throw new Error(`Failed to load ${ROOKIE_STUB_PATH}: ${response.status}`);
      }
      return normalizeRookieStubs(await response.json());
    });
  }
  return rookieStubsPromise;
}

export function buildRookieStubBoardRow(stub) {
  return {
    playerId: stub.playerId,
    slug: stub.slug,
    name: stub.name,
    position: stub.position,
    school: 'Unavailable in stub',
    nflTeam: stub.team,
    draftClass: 2026,
    rookieGrade: null,
    preDraftGrade: null,
    preDraftRank: null,
    postDraftStatus: ROOKIE_STUB_ALPHA_STATUS,
    classRank: null,
    tier: deriveRookieTier(null),
    profileSummary: `${stub.team} · Round ${stub.round} · Pick ${stub.overallPick}`,
    tags: [],
    translationFlags: [],
    pprProjection: null,
    consensusDelta: null,
    evidenceTier: null,
    evidenceTierReason: null,
    isCappedDisagreement: null,
    dynastyDelta: null,
    volumeTrend: null,
    efficiencyTrend: null,
    breakoutAge: null,
    youngBreakoutFlag: false,
    breakoutAgeRating: null,
    breakoutLabel: null,
    athleticScore: null,
    athleticSource: null,
    productionScore: null,
    draftCapitalScore: null,
    alphaStatus: stub.alphaStatus,
    unscoredReason: stub.reason,
    draftFacts: {
      team: stub.team,
      round: stub.round,
      overallPick: stub.overallPick,
    },
    provenance: stub.provenance,
  };
}

export function mergeRookieBoardRowsWithStubs(rows, stubs) {
  const stubRows = stubs.map(buildRookieStubBoardRow);
  const stubIds = new Set(stubRows.map((row) => row.playerId));
  const nonStubRows = rows.filter(
    (row) => String(row.draftClass) !== '2026' || !stubIds.has(row.playerId),
  );
  return [...nonStubRows, ...stubRows];
}

export function findRookieStubBySlug(stubs, slug) {
  return stubs.find((stub) => stub.slug === slug) ?? null;
}
