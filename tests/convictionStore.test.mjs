import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getConvictionRating,
  getVoteCount,
  recordMatchupResult,
  resetConvictionBoard,
  seedMatchup,
} from '../lib/rookies/convictionStore.js';

// convictionStore reads/writes window.localStorage at call time, so a simple
// in-memory mock installed on globalThis is enough to exercise the Elo math.
function installLocalStorage() {
  const store = new Map();
  globalThis.window = {
    localStorage: {
      getItem: (key) => (store.has(key) ? store.get(key) : null),
      setItem: (key, value) => store.set(key, String(value)),
      removeItem: (key) => store.delete(key),
    },
  };
  return store;
}

test('getConvictionRating returns the initial 1000 rating for unseen slugs', () => {
  installLocalStorage();
  assert.equal(getConvictionRating('nobody'), 1000);
  assert.equal(getVoteCount(), 0);
});

test('recordMatchupResult applies symmetric K=32 Elo around equal ratings', () => {
  installLocalStorage();
  recordMatchupResult('winner', 'loser');

  // Equal start (1000/1000): expected score 0.5 each, so +/-16.
  assert.equal(getConvictionRating('winner'), 1016);
  assert.equal(getConvictionRating('loser'), 984);
  assert.equal(getVoteCount(), 1);
});

test('recordMatchupResult coerces non-string slugs consistently', () => {
  installLocalStorage();
  recordMatchupResult(1, 2);
  assert.equal(getConvictionRating(1), 1016);
  assert.equal(getConvictionRating('1'), 1016);
  assert.equal(getConvictionRating(2), 984);
});

test('an upset (low beats high) moves ratings more than an expected result', () => {
  installLocalStorage();
  // Make "high" clearly favored first.
  for (let i = 0; i < 5; i++) recordMatchupResult('high', 'low');
  const highBefore = getConvictionRating('high');
  const lowBefore = getConvictionRating('low');
  assert.ok(highBefore > lowBefore);

  // Now the underdog wins — the swing should exceed the 16-pt even-match swing.
  recordMatchupResult('low', 'high');
  const lowGain = getConvictionRating('low') - lowBefore;
  assert.ok(lowGain > 16, `expected upset gain > 16, got ${lowGain}`);
});

test('resetConvictionBoard clears ratings and history', () => {
  installLocalStorage();
  recordMatchupResult('a', 'b');
  assert.equal(getVoteCount(), 1);

  resetConvictionBoard();
  assert.equal(getVoteCount(), 0);
  assert.equal(getConvictionRating('a'), 1000);
});

test('seedMatchup returns null when fewer than two cards share the position', () => {
  installLocalStorage();
  const cards = [{ slug: 'only-wr', identity: { position: 'WR' } }];
  assert.equal(seedMatchup(cards, 'WR'), null);
});

test('seedMatchup returns a same-position pair when enough candidates exist', () => {
  installLocalStorage();
  const cards = [
    { slug: 'wr-1', identity: { position: 'WR' } },
    { slug: 'wr-2', identity: { position: 'WR' } },
    { slug: 'rb-1', identity: { position: 'RB' } },
  ];
  const pair = seedMatchup(cards, 'WR');
  assert.ok(Array.isArray(pair));
  assert.equal(pair.length, 2);
  const slugs = pair.map((c) => c.slug).sort();
  assert.deepEqual(slugs, ['wr-1', 'wr-2']);
});

test('functions degrade to defaults when storage is unavailable', () => {
  delete globalThis.window;
  assert.equal(getConvictionRating('x'), 1000);
  assert.equal(getVoteCount(), 0);
  // Should not throw without storage.
  recordMatchupResult('x', 'y');
  resetConvictionBoard();
});
