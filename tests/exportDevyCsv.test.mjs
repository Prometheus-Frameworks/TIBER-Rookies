import test from 'node:test';
import assert from 'node:assert/strict';

import { buildDevyCsv } from '../lib/devy/exportDevyCsv.js';

const HEADER = [
  'player_id', 'player_name', 'school', 'position', 'projected_draft_class',
  'earliest_possible_draft_class', 'class_year', 'development_horizon',
  'lifecycle_stage', 'actionability_band', 'signal_strength_band',
  'confidence_band', 'volatility_band', 'development_tags', 'summary',
  'why_it_matters', 'identity_source_type', 'identity_source_urls',
  'transition_status', 'rookie_card_slug', 'devy_active_status',
].join(',');

function rows(csv) {
  return csv.split('\n');
}

test('buildDevyCsv emits the fixed devy header', () => {
  const csv = buildDevyCsv([]);
  assert.equal(rows(csv)[0], HEADER);
});

test('buildDevyCsv joins array fields with a pipe', () => {
  const csv = buildDevyCsv([
    {
      player_name: 'Devy One',
      development_tags: ['breakout', 'young'],
      identity_source_urls: ['https://a.test', 'https://b.test'],
    },
  ]);
  const row = rows(csv)[1];
  assert.match(row, /breakout\|young/);
  // The URL cell contains commas? No — but pipe-join keeps it one cell.
  assert.match(row, /https:\/\/a\.test\|https:\/\/b\.test/);
});

test('buildDevyCsv derives devy_active_status from transition_status', () => {
  const csv = buildDevyCsv([
    { player_name: 'Graduated w/ slug', transition_status: 'graduated_to_rookie', rookie_card_slug: 'abc' },
    { player_name: 'Graduated no slug', transition_status: 'graduated_to_rookie' },
    { player_name: 'Other status', transition_status: 'transferred' },
    { player_name: 'No status' },
  ]);
  const dataRows = rows(csv).slice(1);
  const statusOf = (line) => line.split(',').pop();
  assert.equal(statusOf(dataRows[0]), 'graduated_to_rookie');
  assert.equal(statusOf(dataRows[1]), 'rookie_card_pending');
  assert.equal(statusOf(dataRows[2]), 'transferred');
  assert.equal(statusOf(dataRows[3]), 'active_devy');
});

test('buildDevyCsv prefers an explicit devy_active_status over derivation', () => {
  const csv = buildDevyCsv([
    { player_name: 'X', transition_status: 'graduated_to_rookie', devy_active_status: 'manual_override' },
  ]);
  assert.equal(rows(csv)[1].split(',').pop(), 'manual_override');
});

test('buildDevyCsv escapes commas in free-text fields', () => {
  const csv = buildDevyCsv([{ player_name: 'Last, First', summary: 'Fast, twitchy' }]);
  assert.match(rows(csv)[1], /"Last, First"/);
  assert.match(rows(csv)[1], /"Fast, twitchy"/);
});
