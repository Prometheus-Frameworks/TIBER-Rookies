import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildRookieBoardRows,
  sortRookieBoard,
  filterRookieBoard,
} from '../lib/rookies/buildRookieBoardRows.js';

function card(overrides = {}) {
  return {
    slug: 'slug',
    identity: { name: 'Rookie', position: 'WR', schoolDisplay: 'School', classYear: 2026 },
    summary: { rookieGrade: 75, classRank: 1, profileSummary: 'Sharp route runner' },
    tags: [],
    ...overrides,
  };
}

test('buildRookieBoardRows maps identity, grade, tier and profile summary', () => {
  const [row] = buildRookieBoardRows([card()]);
  assert.equal(row.name, 'Rookie');
  assert.equal(row.position, 'WR');
  assert.equal(row.rookieGrade, 75);
  assert.equal(row.classRank, 1);
  assert.equal(row.tier.key, 'tier_1'); // grade 75 -> top cluster
  assert.equal(row.profileSummary, 'Sharp route runner');
});

test('buildRookieBoardRows derives tier from the post-draft adjusted grade when present', () => {
  const [row] = buildRookieBoardRows([
    card({ summary: { rookieGrade: 75, classRank: 1 }, postDraftAdjustedGrade: 64 }),
  ]);
  assert.equal(row.tier.key, 'tier_4'); // 64 falls below every positive cutoff
});

test('buildRookieBoardRows falls back through profile fields and finally a default note', () => {
  const [row] = buildRookieBoardRows([
    card({ summary: { rookieGrade: 75, classRank: 1, archetype: 'Slot technician' }, tags: [] }),
  ]);
  assert.equal(row.profileSummary, 'Slot technician');

  const [bare] = buildRookieBoardRows([
    card({ summary: { rookieGrade: 75, classRank: 1 }, tags: [] }),
  ]);
  assert.equal(bare.profileSummary, 'Profile context limited by current artifacts');
});

const sample = [
  { name: 'A', position: 'WR', rookieGrade: 70, classRank: 3, draftClass: 2026, consensusDelta: 1 },
  { name: 'B', position: 'RB', rookieGrade: 90, classRank: 1, draftClass: 2026, consensusDelta: 5 },
  { name: 'C', position: 'WR', rookieGrade: 80, classRank: 2, draftClass: 2025, consensusDelta: -2 },
];

test('sortRookieBoard defaults to descending board grade', () => {
  const names = sortRookieBoard(sample).map((r) => r.name);
  assert.deepEqual(names, ['B', 'C', 'A']);
});

test('sortRookieBoard by rank orders ascending class rank', () => {
  const names = sortRookieBoard(sample, 'rank').map((r) => r.name);
  assert.deepEqual(names, ['B', 'C', 'A']);
});

test('sortRookieBoard by position groups by position then grade', () => {
  const names = sortRookieBoard(sample, 'position').map((r) => r.name);
  // RB before WR; within WR, higher grade (C=80) before A=70.
  assert.deepEqual(names, ['B', 'C', 'A']);
});

test('sortRookieBoard by edge orders by descending consensus delta', () => {
  const names = sortRookieBoard(sample, 'edge').map((r) => r.name);
  assert.deepEqual(names, ['B', 'A', 'C']);
});

test('sortRookieBoard does not mutate the input array', () => {
  const input = [...sample];
  sortRookieBoard(input, 'edge');
  assert.deepEqual(input.map((r) => r.name), ['A', 'B', 'C']);
});

test('filterRookieBoard filters by position, draft class and name (case-insensitive)', () => {
  assert.deepEqual(filterRookieBoard(sample, { position: 'WR' }).map((r) => r.name), ['A', 'C']);
  assert.deepEqual(filterRookieBoard(sample, { draftClass: 2025 }).map((r) => r.name), ['C']);
  assert.deepEqual(filterRookieBoard(sample, { nameFilter: 'b' }).map((r) => r.name), ['B']);
  assert.deepEqual(filterRookieBoard(sample, {}).map((r) => r.name), ['A', 'B', 'C']);
});
