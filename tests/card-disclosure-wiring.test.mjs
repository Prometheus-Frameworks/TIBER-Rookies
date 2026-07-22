import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

import { mapRookieToCard } from '../lib/rookies/mapRookieToCard.js';
import { renderPprProjection } from '../components/rookies/renderPprProjection.js';
import { normalizeRookieIdentity } from '../lib/rookies/normalizeRookieIdentity.js';

const baseAlphaPlayer = { player_id: 'wr-data-gap-test', position: 'WR' };

const readJson = (relPath) => JSON.parse(fs.readFileSync(new URL(relPath, import.meta.url), 'utf8'));
const keyById = (rows) => new Map((rows ?? []).map((r) => [String(r.player_id ?? '').toLowerCase(), r]));

test('mapRookieToCard preserves PPR data_gap_flag / data_gap_note metadata', () => {
  const card = mapRookieToCard({
    alphaPlayer: baseAlphaPlayer,
    pprRow: {
      ppr_floor: 40,
      ppr_median: 70,
      ppr_ceiling: 110,
      projection_band: 'Contributor',
      projection_method: 'alpha_band_v1',
      data_gap_flag: true,
      data_gap_note: 'Missing combine athletic inputs.',
    },
  });

  assert.equal(card.pprProjection.dataGapFlag, true);
  assert.equal(card.pprProjection.dataGapNote, 'Missing combine athletic inputs.');
  assert.equal(card.pprProjection.projectionMethod, 'alpha_band_v1');
});

test('mapRookieToCard defaults data_gap_flag to false when absent', () => {
  const card = mapRookieToCard({
    alphaPlayer: baseAlphaPlayer,
    pprRow: {
      ppr_floor: 40,
      ppr_median: 70,
      ppr_ceiling: 110,
      projection_band: 'Contributor',
    },
  });

  assert.equal(card.pprProjection.dataGapFlag, false);
  assert.equal(card.pprProjection.dataGapNote, null);
});

test('renderPprProjection shows the data-gap warning with the provided note', () => {
  const html = renderPprProjection(
    {
      floor: 40,
      median: 70,
      ceiling: 110,
      band: 'Contributor',
      dataGapFlag: true,
      dataGapNote: 'Missing combine athletic inputs.',
    },
    { evidenceTier: 'moderate_edge' },
  );

  assert.match(html, /ppr-data-gap-warning/);
  assert.match(html, /Missing combine athletic inputs\./);
});

test('renderPprProjection omits the warning when there is no data gap', () => {
  const html = renderPprProjection(
    { floor: 40, median: 70, ceiling: 110, band: 'Contributor', dataGapFlag: false },
    { evidenceTier: 'moderate_edge' },
  );

  assert.doesNotMatch(html, /ppr-data-gap-warning/);
});

test('renderPprProjection adds the grade-band caveat for insufficient-evidence cards', () => {
  const html = renderPprProjection(
    { floor: 40, median: 70, ceiling: 110, band: 'Contributor' },
    { evidenceTier: 'insufficient_evidence' },
  );

  assert.match(html, /ppr-evidence-caveat/);
  assert.match(html, /Projection is grade-band based; limited evidence context applies\./);
});

test('WR role label is a neutral receiver profile, not perimeter-specific', () => {
  const identity = normalizeRookieIdentity({ alphaPlayer: { position: 'WR' } });
  assert.equal(identity.roleLabel, 'Receiver profile');
});

// ── Phase 1A: card temporal-integrity contract ──────────────────────────────

// Golden trace: Omar Cooper Jr. built from the real promoted 2026 artifacts.
function buildOmarCard() {
  const predraft = readJson('../exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json');
  const ppr = keyById(readJson('../data/processed/2026_ppr_projections.json'));
  const draft = keyById(readJson('../data/processed/2026_draft_results.json'));
  const transition = keyById(readJson('../exports/promoted/rookie-transition-profile/2026_rookie_transition_profile_v0.json').rows);
  const omar = predraft.players.find((p) => p.player_id === 'wr-omar-cooper-jr');
  assert.ok(omar, 'Omar must exist in the promoted pre-draft export');
  return mapRookieToCard({
    alphaPlayer: omar,
    pprRow: ppr.get('wr-omar-cooper-jr'),
    draftResultRow: draft.get('wr-omar-cooper-jr') ?? null,
    transitionProfileRow: transition.get('wr-omar-cooper-jr') ?? null,
    alphaModel: predraft.model,
    alphaGeneratedAt: predraft.generated_at,
    rank: omar.rookie_alpha_rank,
  });
}

test('golden Omar: NFL identity + draft facts come from the governed transition profile', () => {
  const card = buildOmarCard();
  assert.equal(card.identity.nflTeam, 'NYJ');
  assert.equal(card.officialOutcome.status, 'drafted');
  assert.equal(card.officialOutcome.nflTeam, 'NYJ');
  assert.equal(card.officialOutcome.draftRound, 1);
  assert.equal(card.officialOutcome.overallPick, 30);
  assert.equal(card.draft.provenanceSource, 'transition_profile');
  assert.ok(card.officialOutcome.provenance.sourceUrl, 'official outcome must carry a source URL');
});

test('golden Omar: pre-draft Alpha is a frozen, dated baseline with model version', () => {
  const card = buildOmarCard();
  assert.equal(card.preDraftBaseline.grade, card.summary.rookieGrade);
  assert.match(card.preDraftBaseline.modelVersion, /^rookie-alpha-predraft-v/);
  assert.match(card.preDraftBaseline.generatedAt, /^\d{4}-\d{2}-\d{2}/);
});

test('golden Omar: no competing post-draft grade is computed', () => {
  const card = buildOmarCard();
  assert.equal(card.postDraftGrade, null);
  assert.equal(card.postDraftStatus, 'not_yet_published');
  const scoreLabels = card.scores.map((s) => s.label);
  assert.ok(!scoreLabels.includes('Post-Draft Adjusted Grade'));
  assert.ok(!scoreLabels.includes('Delta'));
  // The governed post-draft artifact value (65.2) must not leak onto the card.
  assert.ok(!card.scores.some((s) => s.value === 65.2));
});

test('golden Omar: partial athletic evidence is labeled as a partial composite', () => {
  const card = buildOmarCard();
  assert.equal(card.athleticSource, 'RAS_PARTIAL');
  assert.equal(card.metrics[0].label, 'ATH (partial)');
});

test('golden Omar: Alpha-derived PPR fails closed when the embedded snapshot is stale', () => {
  const card = buildOmarCard();
  assert.equal(card.pprProjection.stale, true);
  assert.equal(card.pprProjection.median, null);
  const html = renderPprProjection(card.pprProjection, card);
  assert.match(html, /ppr-stale-warning/);
  assert.doesNotMatch(html, /ppr-range-median-marker/);
});

test('PPR renders normally when the embedded Alpha matches the current promoted Alpha', () => {
  const card = mapRookieToCard({
    alphaPlayer: { player_id: 'wr-match', position: 'WR', scores: { rookie_alpha_0_100: 58.0712 } },
    pprRow: { player_id: 'wr-match', rookie_alpha_0_100: 58.1, ppr_floor: 70, ppr_median: 115, ppr_ceiling: 165, projection_band: 'Starter' },
  });
  assert.equal(card.pprProjection.stale, false);
  assert.equal(card.pprProjection.median, 115);
  assert.match(renderPprProjection(card.pprProjection, card), /ppr-range-median-marker/);
});

test('PPR fails closed when the projection row carries no embedded Alpha to verify', () => {
  const card = mapRookieToCard({
    alphaPlayer: { player_id: 'wr-noalpha', position: 'WR', scores: { rookie_alpha_0_100: 58.0712 } },
    pprRow: { player_id: 'wr-noalpha', ppr_floor: 70, ppr_median: 115, ppr_ceiling: 165, projection_band: 'Starter' },
  });
  assert.equal(card.pprProjection.stale, true);
  assert.equal(card.pprProjection.median, null);
});

test('missing data: no transition profile and no draft result → no official outcome, no invented grade', () => {
  const card = mapRookieToCard({
    alphaPlayer: { player_id: 'wr-undrafted-unknown', position: 'WR', scores: { rookie_alpha_0_100: 42.0 } },
    rank: 40,
  });
  assert.equal(card.officialOutcome, null);
  assert.equal(card.identity.nflTeam, null);
  assert.equal(card.draft.hasDraftOutcome, false);
  assert.equal(card.draft.provenanceSource, null);
  assert.equal(card.postDraftGrade, null);
  assert.equal(card.postDraftStatus, 'not_yet_published');
});

test('historical fallback: draft-results supplement supplies facts when no transition profile exists', () => {
  const card = mapRookieToCard({
    alphaPlayer: { player_id: 'wr-2024-vet', position: 'WR', scores: { rookie_alpha_0_100: 60.0 } },
    draftResultRow: { player_id: 'wr-2024-vet', nfl_team: 'KC', draft_round: 2, overall_pick: 50, is_udfa: false },
    rank: 10,
  });
  assert.equal(card.officialOutcome, null); // no governed provenance for pre-2026 classes
  assert.equal(card.identity.nflTeam, 'KC');
  assert.equal(card.draft.draftRound, 2);
  assert.equal(card.draft.overallPick, 50);
  assert.equal(card.draft.provenanceSource, 'draft_results_supplement');
});

test('COMBINE_FALLBACK athletic source is also labeled as a partial composite', () => {
  const card = mapRookieToCard({
    alphaPlayer: { player_id: 'wr-combine', position: 'WR', scores: { athletic_score_0_100: 55, athletic_source: 'COMBINE_FALLBACK' } },
  });
  assert.equal(card.metrics[0].label, 'ATH (partial)');
});
