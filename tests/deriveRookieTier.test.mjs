import test from 'node:test';
import assert from 'node:assert/strict';

import { deriveRookieTier, getRookieTierRules } from '../lib/rookies/deriveRookieTier.js';

test('deriveRookieTier buckets grades at the documented cutoffs', () => {
  assert.equal(deriveRookieTier(75).key, 'tier_1');
  assert.equal(deriveRookieTier(74.9).key, 'tier_2');
  assert.equal(deriveRookieTier(70).key, 'tier_2');
  assert.equal(deriveRookieTier(69.9).key, 'tier_3');
  assert.equal(deriveRookieTier(65).key, 'tier_3');
  assert.equal(deriveRookieTier(64.9).key, 'tier_4');
  assert.equal(deriveRookieTier(0).key, 'tier_4');
});

test('deriveRookieTier returns the unscored bucket for null grades', () => {
  const tier = deriveRookieTier(null);
  assert.equal(tier.key, 'unscored');
  assert.equal(tier.bucketOrder, 99);
});

test('deriveRookieTier exposes a zero-based bucketOrder matching rule position', () => {
  assert.equal(deriveRookieTier(75).bucketOrder, 0);
  assert.equal(deriveRookieTier(70).bucketOrder, 1);
  assert.equal(deriveRookieTier(0).bucketOrder, 3);
});

test('getRookieTierRules returns a defensive copy', () => {
  const rules = getRookieTierRules();
  rules[0].label = 'mutated';
  assert.notEqual(getRookieTierRules()[0].label, 'mutated');
});
