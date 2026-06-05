import test from 'node:test';
import assert from 'node:assert/strict';

// Imported via its browser-absolute path on purpose: this asserts the
// test-time resolve hook (tests/helpers/absolute-import-hooks.mjs) makes the
// '/lib/...' specifiers — including the one compareRookies itself imports —
// load correctly under Node.
import { compareRookies } from '/lib/rookies/compareRookies.js';

function card({ name, position, grade, metrics = [], classRank = null, athleticScore = null }) {
  return {
    slug: name.toLowerCase().replace(/\s+/g, '-'),
    identity: { name, position },
    summary: { rookieGrade: grade, classRank },
    metrics,
    athleticScore,
  };
}

test('overallDelta is the left-minus-right rookie grade', () => {
  const out = compareRookies(
    card({ name: 'Left', position: 'WR', grade: 80 }),
    card({ name: 'Right', position: 'WR', grade: 72 }),
  );
  assert.equal(out.overallDelta, 8);
  assert.equal(out.sharedPosition, true);
});

test('a grade gap beyond the lean threshold yields a clear lean to the higher grade', () => {
  const out = compareRookies(
    card({ name: 'Higher', position: 'WR', grade: 85 }),
    card({ name: 'Lower', position: 'WR', grade: 70 }),
  );
  assert.equal(out.verdict.code, 'lean-left');
  assert.match(out.verdict.headline, /Lean Higher/);
  assert.match(out.verdict.detail, /Clear/);
});

test('grades within the close threshold with no evidence edge read as a close profile', () => {
  const out = compareRookies(
    card({ name: 'A', position: 'WR', grade: 80 }),
    card({ name: 'B', position: 'WR', grade: 79 }),
  );
  assert.equal(out.verdict.code, 'close');
});

test('a missing rookie grade produces an insufficient verdict', () => {
  const out = compareRookies(
    card({ name: 'A', position: 'WR', grade: null }),
    card({ name: 'B', position: 'WR', grade: 80 }),
  );
  assert.equal(out.overallDelta, null);
  assert.equal(out.verdict.code, 'insufficient');
});

test('cross-position compares are flagged and noted', () => {
  const out = compareRookies(
    card({ name: 'A', position: 'WR', grade: 80 }),
    card({ name: 'B', position: 'RB', grade: 80 }),
  );
  assert.equal(out.sharedPosition, false);
  assert.ok(out.notes.some((n) => /Cross-position/.test(n)));
});

test('shared, non-duplicate evidence metrics produce edge rows with a direction-aware winner', () => {
  // 40-yard dash is "lower is better": the faster (smaller) time should win.
  const fast = card({
    name: 'Fast', position: 'WR', grade: 80,
    metrics: [{ label: '40 Yard Dash (s)', value: 4.4, display: '4.40', family: 'speed' }],
  });
  const slow = card({
    name: 'Slow', position: 'WR', grade: 80,
    metrics: [{ label: '40 Yard Dash (s)', value: 4.5, display: '4.50', family: 'speed' }],
  });
  const out = compareRookies(fast, slow);
  const row = out.evidenceComparisons.find((r) => r.label === '40 Yard Dash (s)');
  assert.ok(row, 'expected a 40-yard-dash evidence row');
  assert.equal(row.direction, 'lower');
  assert.equal(row.winner, 'left'); // faster time wins despite the smaller number
});
