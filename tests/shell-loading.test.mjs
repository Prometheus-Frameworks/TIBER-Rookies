import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { deriveDevyActiveStatus, normalizeTransitionMap, enrichDevyRows, readDevySeedRows } from '../lib/devy/transitionState.js';
import { buildDevyCsv } from '../lib/devy/exportDevyCsv.js';
import { buildRookieShellState, selectRookiePlayer, rookieLoadMessage } from '../lib/rookies/rookieShellState.js';
import { normalizeRookieStubs, mergeRookieBoardRowsWithStubs } from '../lib/rookies/rookieStubs.js';
import { filterRookieBoard, sortRookieBoard, buildRookieBoardRows } from '../lib/rookies/buildRookieBoardRows.js';
import { renderRookieStubCard } from '../components/rookies/RookieStubCard.js';

const repo = new URL('../', import.meta.url);
const json = (path) => JSON.parse(fs.readFileSync(new URL(path.replace(/^\//, ''), repo), 'utf8'));
const seed = [{ player_id: 'test-player', player_name: 'Test Player' }];
let loadId = 0;
async function loadWith(overrides = {}) {
  const oldFetch = globalThis.fetch;
  globalThis.fetch = async (path) => {
    if (Object.hasOwn(overrides, path)) {
      const value = overrides[path];
      if (value === 'reject') throw new Error('Synthetic request rejection');
      if (value === '404' || value === '503') return { ok: false, status: Number(value) };
      if (value === 'invalid-json') return { ok: true, json: async () => { throw new SyntaxError('Synthetic malformed JSON'); } };
      return { ok: true, json: async () => value };
    }
    try { return { ok: true, json: async () => json(path) }; }
    catch { return { ok: false, status: 404 }; }
  };
  try {
    const module = await import(`../lib/rookies/getRookieCardData.js?load=${++loadId}`);
    const result = await module.getRookieCardLoadState();
    assert.deepEqual(await module.getAllRookieCards(), result.cards, 'shared array API stays compatible');
    return result;
  } finally { globalThis.fetch = oldFetch; }
}
const alphaPath = '/exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json';
const stubRows = normalizeRookieStubs(json('data/processed/2026_rookie_stubs_v0.json'));
const goodStubs = { status: 'loaded', rows: stubRows };
const failedStubs = { status: 'load_failed', rows: [] };

for (const raw of [undefined, '', null, 'unsupported', ['active_devy'], {}, 'ACTIVE_DEVY']) {
  test(`Devy ${JSON.stringify(raw)} stays unknown in UI-derived state and CSV`, () => {
    const row = { transition_status: raw, devy_active_status: 'active_devy' };
    assert.equal(deriveDevyActiveStatus(row), 'unknown');
    assert.match(buildDevyCsv([row]).split('\n')[1], /,unknown$/);
  });
}
for (const [status, slug, expected] of [['active_devy', '', 'active_devy'], ['graduated_to_rookie', '', 'rookie_card_pending'], ['graduated_to_rookie', 'test-player', 'graduated_to_rookie']]) {
  test(`explicit transition ${expected} has UI/CSV parity and unchanged raw fields`, () => {
    const raw = { player_id: 'test-player', transition_status: status, rookie_card_slug: slug };
    const [row] = enrichDevyRows(seed, normalizeTransitionMap({ transitions: [raw] }));
    assert.equal(row.devy_active_status, expected);
    assert.equal(row.transition_status, status);
    assert.match(buildDevyCsv([row]).split('\n')[1], new RegExp(`,${status},${slug},${expected}$`));
    assert.deepEqual(raw, { player_id: 'test-player', transition_status: status, rookie_card_slug: slug });
  });
}
test('missing, unmatched and duplicate transition identities cannot imply activity', () => {
  for (const rows of [[], [{ player_id: 'TEST-PLAYER', transition_status: 'active_devy' }], [1, 2, 3].map(() => ({ player_id: 'test-player', transition_status: 'active_devy' }))]) {
    const [row] = enrichDevyRows(seed, normalizeTransitionMap({ rows }));
    assert.equal(row.devy_active_status, 'unknown');
    assert.equal(row.transition_status, '');
  }
});
test('malformed and ambiguous transition envelopes reject; empty envelope is valid', () => {
  for (const value of [null, {}, { transitions: {} }, { rows: [], transitions: [] }, { rows: [null] }]) assert.throws(() => normalizeTransitionMap(value));
  assert.equal(normalizeTransitionMap({ transitions: [] }).size, 0);
});
test('empty seed is distinct from malformed seed', () => {
  assert.deepEqual(readDevySeedRows({ prospects: [] }), []);
  for (const value of [null, {}, { prospects: {} }, { prospects: [null] }]) assert.throws(() => readDevySeedRows(value));
});

for (const failure of ['404', '503', 'reject', 'invalid-json', {}, { players: [null] }, { players: [{ player_id: 'test-player', context: { class_year: 2025 } }] }]) {
  test(`Alpha failure ${JSON.stringify(failure)} preserves healthy historical cards and healthy stubs`, async () => {
    const alpha = await loadWith({ [alphaPath]: failure });
    assert.equal(alpha.seasons.find((r) => r.season === 2026).status, 'load_failed');
    assert(alpha.cards.some((card) => card.identity.classYear === 2025));
    const shell = buildRookieShellState(alpha, goodStubs);
    const selected = selectRookiePlayer(shell, stubRows[0].slug);
    assert.equal(selected.status, 'unscored');
    assert.equal(selectRookiePlayer(shell, 'synthetic-non-player-294').status, 'unavailable');
    assert.match(rookieLoadMessage(shell), /Alpha unavailable for 2026/);
  });
}
test('legitimate empty Alpha retains successful population status', async () => {
  const alpha = await loadWith({ [alphaPath]: { players: [] } });
  const season = alpha.seasons.find((r) => r.season === 2026);
  assert.notEqual(season.status, 'load_failed');
  assert.equal(season.cards.length, 0);
  assert.equal(season.sources.find((source) => source.path === alphaPath).status, 'loaded');
});
for (const failure of ['404', '503', 'reject', 'invalid-json', {}, [null]]) {
  test(`supplement failure ${JSON.stringify(failure)} stays partial without blanking the class`, async () => {
    const alpha = await loadWith({ '/data/processed/2026_player_stats.json': failure });
    const season = alpha.seasons.find((r) => r.season === 2026);
    assert.equal(season.status, 'partial');
    assert(season.cards.length > 0);
    assert(season.sources.some((source) => source.path.endsWith('player_stats.json') && source.status === 'load_failed'));
  });
}
test('failed stub coverage withholds overlapping 2026 scores on Board and Player while retaining history', async () => {
  const alpha = await loadWith();
  const overlap = alpha.cards.find((card) => card.identity.classYear === 2026 && stubRows.some((stub) => stub.playerId === card.playerId));
  assert(overlap, 'real existing overlap is exercised');
  const shell = buildRookieShellState(alpha, failedStubs);
  assert(shell.cards.length > 0);
  assert(shell.cards.every((card) => card.identity.classYear !== 2026));
  assert.equal(selectRookiePlayer(shell, overlap.slug).status, 'unavailable');
  const rows = mergeRookieBoardRowsWithStubs(buildRookieBoardRows(shell.cards), shell.stubs);
  assert(!rows.some((row) => row.playerId === overlap.playerId && row.draftClass === 2026));
  const historical = shell.cards.find((card) => card.identity.classYear === 2025);
  assert.equal(selectRookiePlayer(shell, historical.slug).status, 'scored');
  assert.match(rookieLoadMessage(shell, '2026'), /scores, ranks and actions are withheld/);
  assert.doesNotMatch(rookieLoadMessage(shell, '2025'), /stub/);
});
test('healthy stub precedence retains null ranks and no scored player actions', async () => {
  const shell = buildRookieShellState(await loadWith(), goodStubs);
  const stub = stubRows.find((row) => row.slug.includes('cyrus')) ?? stubRows[0];
  assert.equal(selectRookiePlayer(shell, stub.slug).status, 'unscored');
  const rows = mergeRookieBoardRowsWithStubs(buildRookieBoardRows(shell.cards), shell.stubs);
  const row = rows.find((row) => row.playerId === stub.playerId && row.draftClass === 2026);
  assert.equal(row.rookieGrade, null);
  assert.equal(row.classRank, null);
  const root = { innerHTML: '' };
  renderRookieStubCard(root, stub);
  assert.doesNotMatch(root.innerHTML, /data-compare|detail-queue-toggle|radar-svg/);
});
test('healthy empty, unknown player, and incomplete population remain distinct', () => {
  const empty = { cards: [], seasons: [{ season: 2026, status: 'empty' }] };
  const shell = buildRookieShellState(empty, { status: 'loaded', rows: [] });
  assert.equal(selectRookiePlayer(shell, null).status, 'empty');
  assert.equal(selectRookiePlayer(shell, 'synthetic-non-player-294').status, 'not_found');
  assert.equal(selectRookiePlayer(buildRookieShellState(empty, failedStubs), 'synthetic-non-player-294').status, 'unavailable');
});
test('official outcome gate remains closed on malformed governed profile, with cards retained', async () => {
  const alpha = await loadWith({ '/exports/promoted/rookie-transition-profile/2026_rookie_transition_profile_v0.json': {} });
  assert.equal(alpha.seasons.find((row) => row.season === 2026).status, 'partial');
  assert(alpha.cards.some((card) => card.identity.classYear === 2026));
});

// Execute the actual entry script against a minimal DOM adapter. These are
// wiring regressions only, not browser/visual verification.
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
function entryScript(path) {
  return fs.readFileSync(new URL(path, repo), 'utf8').match(/<script type="module">([\s\S]*?)<\/script>/)[1]
    .replace(/^\s*import[\s\S]*?from\s+['"][^'"]+['"];\s*$/gm, '');
}
function domAdapter() {
  const nodes = new Map();
  return { nodes, document: { title: '', getElementById(id) {
    if (!nodes.has(id)) nodes.set(id, { innerHTML: '', textContent: '', value: '', disabled: true,
      events: {}, addEventListener(event, fn) { this.events[event] = fn; },
      insertAdjacentHTML() {}, querySelectorAll() { return []; }, querySelector() { return null; } });
    return nodes.get(id);
  } } };
}
for (const failure of ['404', '503', 'reject', 'invalid-json', {}]) {
  test(`Devy entry rejects failed/malformed seed ${JSON.stringify(failure)}`, async () => {
    const { document, nodes } = domAdapter();
    const fetcher = async () => {
      if (failure === 'reject') throw new Error('Synthetic rejection');
      return { ok: !['404', '503'].includes(failure), status: Number(failure), json: async () => {
        if (failure === 'invalid-json') throw new SyntaxError('Synthetic JSON failure');
        return failure;
      } };
    };
    await new AsyncFunction('document', 'fetch', 'readDevySeedRows', 'normalizeTransitionMap', 'enrichDevyRows', 'buildDevyCsv', 'downloadCsv', entryScript('cards/devy/index.html'))(
      document, fetcher, readDevySeedRows, normalizeTransitionMap, enrichDevyRows, buildDevyCsv, () => {});
    assert.match(nodes.get('status').textContent, /Failed to load Devy data/);
    assert.equal(nodes.get('exportVisibleButton').disabled, true);
  });
}
for (const transitionFailure of ['404', 'reject', 'invalid-json', {}]) {
  test(`Devy entry retains seed rows on transition failure ${JSON.stringify(transitionFailure)} and survives rerender`, async () => {
    const { document, nodes } = domAdapter();
    const fetcher = async (path) => {
      if (path.includes('seed_watchlist')) return { ok: true, json: async () => ({ prospects: seed }) };
      if (transitionFailure === 'reject') throw new Error('Synthetic rejection');
      return { ok: transitionFailure !== '404', json: async () => {
        if (transitionFailure === 'invalid-json') throw new SyntaxError('Synthetic JSON failure');
        return transitionFailure;
      } };
    };
    await new AsyncFunction('document', 'fetch', 'readDevySeedRows', 'normalizeTransitionMap', 'enrichDevyRows', 'buildDevyCsv', 'downloadCsv', entryScript('cards/devy/index.html'))(
      document, fetcher, readDevySeedRows, normalizeTransitionMap, enrichDevyRows, buildDevyCsv, () => {});
    assert.match(nodes.get('rows').innerHTML, /Transition unknown \/ unavailable/);
    assert.equal(nodes.get('exportVisibleButton').disabled, false);
    nodes.get('search').value = 'synthetic-no-match';
    nodes.get('search').events.input();
    assert.match(nodes.get('rows').innerHTML, /current search\/filter/);
    nodes.get('search').value = '';
    nodes.get('search').events.input();
    assert.match(nodes.get('rows').innerHTML, /Test Player/);
    assert.doesNotMatch(nodes.get('rows').innerHTML, /active_devy/);
  });
}
async function runPlayer(shell, slug) {
  const { document, nodes } = domAdapter();
  const calls = [];
  const deps = { document, window: { location: { search: `?slug=${slug}` } },
    getRookieShellState: async () => shell, rookieLoadMessage, selectRookiePlayer,
    renderRookieStubCard: (root, stub) => { calls.push(['stub', stub.slug]); renderRookieStubCard(root, stub); },
    renderRookieCard: (root, card) => { calls.push(['card', card.slug]); root.innerHTML = 'Scored card'; },
    isRookieQueued: () => false, getQueuedRookieAnnotation: () => null,
    deriveRookieTier: () => ({ label: 'Test' }), findSimilarAthletes: async () => [], getSporqDistribution: async () => [],
  };
  await new AsyncFunction(...Object.keys(deps), entryScript('cards/rookies/player.html'))(...Object.values(deps));
  return { nodes, calls };
}
test('Player entry never renders scored actions when stub coverage fails, but still renders history', async () => {
  const alpha = await loadWith();
  const shell = buildRookieShellState(alpha, failedStubs);
  const overlap = alpha.cards.find((card) => card.identity.classYear === 2026 && stubRows.some((stub) => stub.playerId === card.playerId));
  const withheld = await runPlayer(shell, overlap.slug);
  assert.deepEqual(withheld.calls, []);
  assert.equal(withheld.nodes.get('detail-actions').innerHTML, '');
  assert.match(withheld.nodes.get('card-root').textContent, /coverage unavailable/);
  const historical = shell.cards.find((card) => card.identity.classYear === 2025);
  const rendered = await runPlayer(shell, historical.slug);
  assert.deepEqual(rendered.calls, [['card', historical.slug]]);
});
test('Player entry renders healthy stub with failed Alpha and distinguishes unknown player', async () => {
  const shell = buildRookieShellState(await loadWith({ [alphaPath]: 'reject' }), goodStubs);
  const rendered = await runPlayer(shell, stubRows[0].slug);
  assert.deepEqual(rendered.calls, [['stub', stubRows[0].slug]]);
  assert.equal(rendered.nodes.get('detail-actions').innerHTML, '');
  const missing = await runPlayer(shell, 'synthetic-non-player-294');
  assert.match(missing.nodes.get('card-root').textContent, /Missing sources may contain this player/);
});
async function runBoard(shell, query = '') {
  const { document, nodes } = domAdapter();
  const renderedRows = [];
  const deps = { document, window: { location: { search: query, href: `http://localhost/cards/rookies/board/${query}` }, history: { replaceState() {} } },
    getRookieShellState: async () => shell, rookieLoadMessage, buildRookieBoardRows, mergeRookieBoardRowsWithStubs,
    filterRookieBoard, sortRookieBoard, groupRookiesByTier: () => [], getRookieTierRules: () => [],
    getRookieQueueTagOptions: () => [], getRookieQueueNoteMaxLength: () => 100,
    loadRookieQueue: () => [], renderRookieBoardControls: () => '', renderRookieQueuePanel: () => '',
    renderRookieBoard: (rows) => { renderedRows.push(rows); return 'Board rows'; },
  };
  await new AsyncFunction(...Object.keys(deps), entryScript('cards/rookies/board/index.html'))(...Object.values(deps));
  return { nodes, renderedRows };
}
test('Board entry withholds 2026 rows on failed stub coverage across search rerenders', async () => {
  const shell = buildRookieShellState(await loadWith(), failedStubs);
  const { nodes, renderedRows } = await runBoard(shell);
  assert(renderedRows[0].length > 0);
  assert(renderedRows[0].every((row) => row.draftClass !== 2026));
  nodes.get('board-name-search').value = 'synthetic-non-player-294';
  nodes.get('board-name-search').events.input();
  assert.match(nodes.get('board-root').textContent, /not a confirmed empty population/);
  assert.match(nodes.get('load-status').textContent, /stub coverage unavailable/);
  const only2026 = await runBoard(shell, '?draftClass=2026');
  assert.deepEqual(only2026.renderedRows[0], []);
  assert.match(only2026.nodes.get('board-root').textContent, /Coverage is incomplete/);
});
test('Board entry distinguishes healthy empty and filtered empty and retains healthy stubs with failed Alpha', async () => {
  const shell = buildRookieShellState(await loadWith({ [alphaPath]: 'reject' }), goodStubs);
  const partial = await runBoard(shell, '?draftClass=2026');
  assert(partial.renderedRows[0].length > 0);
  assert(partial.renderedRows[0].every((row) => row.alphaStatus === 'not_scored' && row.rookieGrade === null));
  const empty = await runBoard({ cards: [], stubs: [], seasons: [{ season: 2026, status: 'empty' }], stubStatus: 'loaded' });
  assert.match(empty.nodes.get('board-root').textContent, /successfully loaded sources.*contain no players/);
  const healthy = await runBoard(buildRookieShellState(await loadWith(), goodStubs));
  healthy.nodes.get('board-name-search').value = 'synthetic-non-player-294';
  healthy.nodes.get('board-name-search').events.input();
  assert.match(healthy.nodes.get('board-root').textContent, /current search\/filter/);
});

for (const failure of ['404', '503', 'reject', 'invalid-json', {}, [null]]) {
  test(`actual shell loader isolates stub source ${JSON.stringify(failure)}`, async () => {
    const oldFetch = globalThis.fetch;
    globalThis.fetch = async (path) => {
      if (path.endsWith('2026_rookie_stubs_v0.json')) {
        if (failure === 'reject') throw new Error('Synthetic rejection');
        return { ok: !['404', '503'].includes(failure), status: Number(failure), json: async () => {
          if (failure === 'invalid-json') throw new SyntaxError('Synthetic JSON failure');
          return failure;
        } };
      }
      return { ok: true, json: async () => json(path) };
    };
    try {
      let source = fs.readFileSync(new URL('lib/rookies/rookieShellState.js', repo), 'utf8');
      source = source.replace(/from '(\.\/[^']+)'/g, (_, path) => `from '${new URL(`lib/rookies/${path}?case=${++loadId}`, repo).href}'`);
      const module = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
      const shell = await module.getRookieShellState();
      assert.equal(shell.stubStatus, 'load_failed');
      assert(shell.cards.length > 0);
      assert(shell.cards.every((card) => card.identity.classYear !== 2026));
      assert.match(module.rookieLoadMessage(shell), /stub coverage unavailable/);
    } finally { globalThis.fetch = oldFetch; }
  });
}
