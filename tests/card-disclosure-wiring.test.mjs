import test from 'node:test';
import assert from 'node:assert/strict';

import { mapRookieToCard } from '../lib/rookies/mapRookieToCard.js';
import { renderPprProjection } from '../components/rookies/renderPprProjection.js';
import { normalizeRookieIdentity } from '../lib/rookies/normalizeRookieIdentity.js';

const baseAlphaPlayer = { player_id: 'wr-data-gap-test', position: 'WR' };

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
