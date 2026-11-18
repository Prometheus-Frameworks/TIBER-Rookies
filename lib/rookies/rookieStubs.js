import { deriveRookieTier } from './deriveRookieTier.js';

export const ROOKIE_STUB_PATH = '/data/processed/2026_rookie_stubs_v0.json';
export const ROOKIE_STUB_ALPHA_STATUS = 'not_scored';
export const ROOKIE_STUB_REASON_BELOW_DAY2 = 'below_day2_scoring_floor';
export const ROOKIE_STUB_REASON_COVERAGE_GAP = 'not_in_postdraft_alpha_coverage';
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
let rookieStubStatePromise = null;

// Existing #289 inputs, pinned to their recorded integrity metadata at #294's
// base. This verifies that same coverage contract; it does not admit players or
// recompute scores. Never learn replacement pins from a runtime response.
// Draft digest: exports/promoted/rookie-transition-profile/2026_manifest.json
// Role digest: exports/promoted_integrity_registry_v0.json
const STUB_COVERAGE_INPUTS = [
  ['/data/processed/2026_draft_results.json',
    'ae6b037845f5b6bcd87e17185d1086a3de1cf6a915571f3da1d5d716965f01bd'],
  ['/exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_role_context_v0.json',
    '205c8d64232f072308f55bd9b163783d86ffa4bcb22131233708877c6e9a907d'],
];

async function loadCoverageInput([path, expectedDigest]) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Failed to load coverage input ${path}: ${response.status}`);
  const bytes = await response.arrayBuffer();
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  const actual = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
  if (actual !== expectedDigest) throw new Error(`Coverage input integrity mismatch: ${path}`);
  return JSON.parse(new TextDecoder().decode(bytes));
}

async function loadVerifiedStubState() {
  try {
    const [rows, [draftRows, roleContext]] = await Promise.all([
      get2026RookieStubs(), Promise.all(STUB_COVERAGE_INPUTS.map(loadCoverageInput)),
    ]);
    // The hash-verified inputs have the existing producer's validated identity
    // universe. Match by canonical ID, never by display name or a row count.
    const scoredIds = new Set(roleContext.rows.map((row) => row.player_id));
    const expected = new Map(draftRows
      .filter((row) => row.draft_result_status === 'drafted' && !scoredIds.has(row.player_id))
      .map((row) => [row.player_id, row]));
    const supported = rows.filter((stub) => {
      const source = expected.get(stub.playerId);
      return source && stub.name === source.player_name && stub.position === source.position
        && stub.team === source.nfl_team && stub.round === source.draft_round
        && stub.overallPick === source.overall_pick
        && PROVENANCE_FIELDS.every((field) => stub.provenance[field] === source[field]);
    });
    if (supported.length !== rows.length || supported.length !== expected.size) {
      // Positive, verified unscored rows survive; absence from a partial response
      // is never negative membership evidence for the shared score/action gate.
      return { status: 'load_failed', rows: supported, error: 'Incomplete or mismatched 2026 stub coverage.' };
    }
    return { status: 'loaded', rows: supported };
  } catch (error) {
    return { status: 'load_failed', rows: [], error: String(error.message ?? error) };
  }
}

function nonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function toSlug(playerId) {
  return String(playerId ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function expectedRookieStubReason(round) {
  return round <= 3
    ? ROOKIE_STUB_REASON_COVERAGE_GAP
    : ROOKIE_STUB_REASON_BELOW_DAY2;
}

export function getRookieStubReasonCopy(reason) {
  if (reason === ROOKIE_STUB_REASON_COVERAGE_GAP) {
    return 'Not included in post-draft Rookie Alpha coverage.';
  }
  if (reason === ROOKIE_STUB_REASON_BELOW_DAY2) {
    return 'Below Day-2 scoring floor.';
  }
  return 'Unscored draft-fact record.';
}

export function normalizeRookieStub(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  if (!nonEmptyString(raw.player_id) || raw.player_id !== raw.player_id.trim().toLowerCase()) return null;
  if (!nonEmptyString(raw.name) || !nonEmptyString(raw.position) || !nonEmptyString(raw.team)) return null;
  if (!Number.isInteger(raw.round) || raw.round < 1 || raw.round > 7) return null;
  if (!Number.isInteger(raw.overall_pick) || raw.overall_pick < 1) return null;
  if (raw.alpha_status !== ROOKIE_STUB_ALPHA_STATUS) return null;
  if (raw.reason !== expectedRookieStubReason(raw.round)) return null;
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

export async function getRookieStubLoadState() {
  if (!rookieStubStatePromise) rookieStubStatePromise = loadVerifiedStubState();
  return rookieStubStatePromise;
}

export function filterRookieCardsByStubCoverage(cards, stubResult) {
  const stubIds = new Set(stubResult.rows.map((stub) => stub.playerId));
  // Unknown 2026 membership cannot authorize a score or an action. Healthy
  // stub membership takes precedence over overlapping pre-draft Alpha cards.
  return cards.filter((card) => String(card.identity.classYear) !== '2026'
    || (stubResult.status === 'loaded' && !stubIds.has(card.playerId)));
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
  // Post-draft stub membership intentionally overrides stale 2026 pre-draft cards.
  const nonStubRows = rows.filter(
    (row) => String(row.draftClass) !== '2026' || !stubIds.has(row.playerId),
  );
  return [...nonStubRows, ...stubRows];
}

export function findRookieStubBySlug(stubs, slug) {
  return stubs.find((stub) => stub.slug === slug) ?? null;
}
