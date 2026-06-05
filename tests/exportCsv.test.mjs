import test from 'node:test';
import assert from 'node:assert/strict';

import { buildBoardCsv, buildCompareCsv } from '../lib/rookies/exportCsv.js';

function parseCsv(csv) {
  return csv.split('\n');
}

test('buildBoardCsv emits the header row then one row per rookie', () => {
  const csv = buildBoardCsv([
    { name: 'Alpha', position: 'WR', rookieGrade: 80 },
    { name: 'Beta', position: 'RB', rookieGrade: 70 },
  ]);
  const lines = parseCsv(csv);
  assert.equal(lines.length, 3);
  assert.match(lines[0], /^board_rank,class_rank,name,position/);
});

test('buildBoardCsv numbers board_rank by output order (1-based)', () => {
  const csv = buildBoardCsv([{ name: 'A' }, { name: 'B' }, { name: 'C' }]);
  const ranks = parseCsv(csv).slice(1).map((line) => line.split(',')[0]);
  assert.deepEqual(ranks, ['1', '2', '3']);
});

test('buildBoardCsv formats numeric scores to one decimal and blanks nulls', () => {
  const csv = buildBoardCsv([{ name: 'A', rookieGrade: 75, athleticScore: null, productionScore: 0 }]);
  const row = parseCsv(csv)[1].split(',');
  // header index: rookie_grade=7, athletic_score=8, production_score=9
  assert.equal(row[7], '75.0');
  assert.equal(row[8], '');
  assert.equal(row[9], '0.0'); // 0 is not nullish — must still format
});

test('buildBoardCsv quotes and escapes cells containing commas and quotes', () => {
  const csv = buildBoardCsv([{ name: 'Smith, Jr.', school: 'O"Hara' }]);
  const row = parseCsv(csv)[1];
  assert.match(row, /"Smith, Jr\."/);
  assert.match(row, /"O""Hara"/); // embedded quote is doubled
});

test('buildBoardCsv quotes cells containing newlines so rows stay intact', () => {
  const csv = buildBoardCsv([{ name: 'Line1\nLine2' }]);
  // The newline inside the quoted cell must not create an extra logical column
  // break in the header/first-row structure.
  assert.match(csv, /"Line1\nLine2"/);
});

test('buildCompareCsv produces a header keyed by both rookie names and a grade-delta edge', () => {
  const left = { identity: { name: 'Left WR', position: 'WR', school: 'A', classYear: 2026 }, summary: { rookieGrade: 80 }, metrics: [] };
  const right = { identity: { name: 'Right WR', position: 'WR', school: 'B', classYear: 2026 }, summary: { rookieGrade: 72 }, metrics: [] };

  const csv = buildCompareCsv(left, right);
  const lines = parseCsv(csv);
  assert.equal(lines[0], 'metric,Left WR,Right WR,edge');
  const gradeRow = lines.find((line) => line.startsWith('Rookie Grade,'));
  assert.ok(gradeRow, 'expected a Rookie Grade row');
  assert.match(gradeRow, /delta 8\.0/); // 80 - 72
});
