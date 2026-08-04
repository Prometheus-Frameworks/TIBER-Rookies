import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

import { athleticMetricLabel, hasObservedAthleticEvidence } from '../lib/rookies/athleticLabel.js';
import { compareRookies } from '../lib/rookies/compareRookies.js';
import { selectRookieEvidenceMetrics } from '../lib/rookies/selectRookieEvidenceMetrics.js';
import {
  CARD_RADAR_VIEWBOX,
  neutralAthleticPriorDisclosure,
  observedEvidenceReadiness,
  projectionTrackPercentages,
  sharedPprScaleMax,
} from '../lib/rookies/phase1bPresentation.js';

function projection(floor, median, ceiling, stale = false) {
  return { floor, median, ceiling, band: 'Starter', stale };
}

function compareCard({
  name,
  position,
  grade,
  athleticSource = 'NEUTRAL_DEFAULT',
  athleticScore = 50,
  productionScore = 60,
  draftCapitalScore = 55,
  metrics = [],
}) {
  return {
    identity: { name, position },
    summary: { rookieGrade: grade, classRank: null },
    preDraftGrade: grade,
    athleticSource,
    athleticScore,
    productionScore,
    draftCapitalScore,
    consensusDelta: null,
    metrics,
  };
}

test('neutral default is disclosed as ATH prior and never as observed RAS', () => {
  assert.equal(athleticMetricLabel('NEUTRAL_DEFAULT'), 'ATH prior');
  assert.equal(hasObservedAthleticEvidence('NEUTRAL_DEFAULT'), false);
  assert.equal(hasObservedAthleticEvidence('RAS'), true);
  assert.match(
    neutralAthleticPriorDisclosure({ athleticSource: 'NEUTRAL_DEFAULT', athleticScore: 50 }),
    /contributes to the frozen Rookie Alpha; no observed athletic testing is available/,
  );
});

test('neutral prior is excluded from observed evidence selection', () => {
  const metrics = [
    { label: 'ATH prior', value: 50, display: '50.0', family: 'athletic' },
    { label: 'Production Score', value: 67, display: '67.0', family: 'production' },
    { label: 'Draft Capital Proxy', value: 55, display: '55.0', family: 'capital' },
  ];
  const selected = selectRookieEvidenceMetrics({ identity: { position: 'WR' }, metrics }, 'full');
  assert.deepEqual(selected.map((metric) => metric.label), ['Production Score', 'Draft Capital Proxy']);
});

test('grade-only compare verdict does not claim supporting evidence rows', () => {
  const left = compareCard({
    name: 'Left Receiver',
    position: 'WR',
    grade: 67.7,
    metrics: [
      { label: 'ATH prior', value: 50, display: '50.0', family: 'athletic' },
      { label: 'Production Score', value: 70, display: '70.0', family: 'production' },
      { label: 'Draft Capital Proxy', value: 60, display: '60.0', family: 'capital' },
    ],
  });
  const right = compareCard({
    name: 'Right Tight End',
    position: 'TE',
    grade: 65.3,
    athleticSource: 'RAS',
    athleticScore: 82,
    metrics: [
      { label: 'RAS', value: 82, display: '82.0', family: 'athletic' },
      { label: 'Production Score', value: 62, display: '62.0', family: 'production' },
      { label: 'Draft Capital Proxy', value: 58, display: '58.0', family: 'capital' },
    ],
  });

  const result = compareRookies(left, right);
  assert.equal(result.evidenceComparisons.length, 0);
  assert.match(result.verdict.detail, /Rookie Grade delta only/);
  assert.doesNotMatch(result.verdict.detail, /shared observed evidence rows/);

  const athleticRow = result.scoreComparisons.find((row) => row.label === 'Athleticism Score');
  assert.equal(athleticRow.leftValue, null);
  assert.equal(athleticRow.winner, 'tie');
});

test('side-by-side PPR projections share one scale and ignore stale projections', () => {
  const left = projection(70, 115, 165);
  const right = projection(55, 90, 135);
  const stale = projection(0, 0, 400, true);

  assert.equal(sharedPprScaleMax(left, right), 175);
  assert.equal(sharedPprScaleMax(left, stale), 175);
  assert.equal(sharedPprScaleMax(stale, null), null);

  const leftTrack = projectionTrackPercentages(left, 175);
  const rightTrack = projectionTrackPercentages(right, 175);
  assert.equal(leftTrack.medianLeft, (115 / 175) * 100);
  assert.equal(rightTrack.medianLeft, (90 / 175) * 100);
  assert.equal(projectionTrackPercentages(stale, 175), null);
});

test('readiness wording counts represented observed rows and excludes ATH prior', () => {
  const card = {
    athleticSource: 'NEUTRAL_DEFAULT',
    ageAdjustedProduction: 72,
    breakoutAgeRating: 64,
    metrics: [
      { label: 'ATH prior', value: 50, display: '50.0' },
      { label: 'Production Score', value: 68, display: '68.0' },
      { label: 'Draft Capital Proxy', value: 55, display: '55.0' },
      { label: '40 Yard Dash (s)', value: null, display: 'N/A' },
      { label: '3-Cone (s)', value: null, display: 'N/A' },
      { label: 'Vertical (in)', value: null, display: 'N/A' },
      { label: 'Broad Jump (in)', value: null, display: 'N/A' },
    ],
  };

  const readiness = observedEvidenceReadiness(card);
  assert.equal(readiness.availableCount, 4);
  assert.equal(readiness.totalCount, 8);
  assert.equal(
    readiness.label,
    'Observed evidence represented: 4/8 rows. ATH prior is disclosed separately and does not count as observed testing.',
  );
});

test('card radar geometry reserves additional top clearance for narrow mobile labels', () => {
  assert.equal(CARD_RADAR_VIEWBOX, '-55 -44 310 268');
  const [x, y, width, height] = CARD_RADAR_VIEWBOX.split(/\s+/).map(Number);
  assert.ok(x < 0);
  assert.ok(y <= -40, 'top of viewBox must reserve at least 40 units above the original chart');
  assert.ok(width > 200 && height >= 268);
});

test('player and compare routes wire the bounded Phase 1B presentation layer', () => {
  const playerHtml = fs.readFileSync(new URL('../cards/rookies/player.html', import.meta.url), 'utf8');
  const baseCard = fs.readFileSync(new URL('../components/rookies/RookieCard.js', import.meta.url), 'utf8');
  const phase1bCard = fs.readFileSync(new URL('../components/rookies/RookieCardPhase1B.js', import.meta.url), 'utf8');
  const compareView = fs.readFileSync(new URL('../components/rookies/RookieCompareView.js', import.meta.url), 'utf8');
  const compareRepairs = fs.readFileSync(new URL('../components/rookies/RookieCompareViewPhase1B.js', import.meta.url), 'utf8');
  const mobileCss = fs.readFileSync(new URL('../components/rookies/phase1bMobileIntegrity.css', import.meta.url), 'utf8');

  assert.match(playerHtml, /phase1bMobileIntegrity\.css/);
  assert.match(playerHtml, /RookieCardPhase1B\.js/);
  assert.match(baseCard, /afterRender\?\.\(container, card\)/);
  assert.match(phase1bCard, /afterRender:\s*applyRookieCardPhase1B/);
  assert.doesNotMatch(phase1bCard, /renderBaseRookieCard\(container, card\);/);
  assert.match(compareView, /applyRookieComparePhase1B/);
  assert.match(compareRepairs, /Shared track scale: 0–\$\{scaleMaximum\} PPR points/);
  assert.match(compareRepairs, /ATH prior is a neutral model input, not observed athletic testing/);
  assert.match(compareRepairs, /neutralPriorAxis/);
  assert.match(compareRepairs, /setAttribute\('viewBox', '-18 -24 256 262'\)/);
  assert.match(compareRepairs, /paddingTop = '18px'/);
  assert.match(mobileCss, /box-sizing:\s*border-box/);
  assert.match(mobileCss, /\.compare-3col-table\s*\{[\s\S]*overflow-x:\s*auto/);
  assert.match(mobileCss, /\.site-nav\s*\{[\s\S]*overflow-x:\s*auto/);
  assert.match(mobileCss, /\.hero-score\s*\{[\s\S]*width:\s*100%/);
});
