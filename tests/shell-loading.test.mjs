import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { deriveDevyActiveStatus, normalizeTransitionMap, enrichDevyRows, readDevySeedRows } from '../lib/devy/transitionState.js';
import { buildDevyCsv } from '../lib/devy/exportDevyCsv.js';
import { buildRookieShellState, selectRookiePlayer, rookieLoadMessage } from '../lib/rookies/rookieShellState.js';
import { normalizeRookieStubs, mergeRookieBoardRowsWithStubs } from '../lib/rookies/rookieStubs.js';
import { filterRookieBoard, sortRookieBoard, buildRookieBoardRows } from '../lib/rookies/buildRookieBoardRows.js';
import { renderRookieStubCard } from '../components/rookies/RookieStubCard.js';
import { renderRookieQueuePanel, reconcileRookieQueue } from '../components/rookies/RookieQueuePanel.js';
import { loadRookieQueue, importRookieQueue } from '../lib/rookies/rookieQueueStore.js';
import { collectGalleryFilters, sortAndFilterRookies } from '../lib/rookies/sortAndFilterRookies.js';

const repo = new URL('../', import.meta.url);
const json = (path) => JSON.parse(fs.readFileSync(new URL(path.replace(/^\//, ''), repo), 'utf8'));
const fileText = (path) => fs.readFileSync(new URL(path.replace(/^\//, ''), repo), 'utf8');
const responseFromText = (text) => ({ ok: true,
  json: async () => JSON.parse(text),
  arrayBuffer: async () => new TextEncoder().encode(text).buffer,
});
const seed = [{ player_id: 'test-player', player_name: 'Test Player' }];
let loadId = 0;
async function loadWith(overrides = {}, inspect = (module) => module.getRookieCardLoadState()) {
  const oldFetch = globalThis.fetch;
  globalThis.fetch = async (path) => {
    if (Object.hasOwn(overrides, path)) {
      const value = overrides[path];
      if (value === 'reject') throw new Error('Synthetic request rejection');
      if (value === '404' || value === '503') return { ok: false, status: Number(value) };
      if (value === 'invalid-json') return responseFromText('{');
      return responseFromText(JSON.stringify(value));
    }
    try { return responseFromText(fileText(path)); }
    catch { return { ok: false, status: 404 }; }
  };
  try {
    // Isolate both loader caches for each request fixture without modifying files.
    let source = fs.readFileSync(new URL('lib/rookies/getRookieCardData.js', repo), 'utf8');
    let stubModuleUrl;
    source = source.replace(/from '(\.\/[^']+)'/g, (_, path) => {
      const url = new URL(`lib/rookies/${path}?case=${++loadId}`, repo).href;
      if (path === './rookieStubs.js') stubModuleUrl = url;
      return `from '${url}'`;
    });
    const module = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
    return await inspect(module, await import(stubModuleUrl));
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
async function runBoard(shell, query = '', overrides = {}, setup = () => {}) {
  const { document, nodes } = domAdapter();
  setup(document, nodes);
  const renderedRows = [];
  const deps = { document, window: { location: { search: query, href: `http://localhost/cards/rookies/board/${query}` }, history: { replaceState() {} } },
    getRookieShellState: async () => shell, rookieLoadMessage, buildRookieBoardRows, mergeRookieBoardRowsWithStubs,
    filterRookieBoard, sortRookieBoard, groupRookiesByTier: () => [], getRookieTierRules: () => [],
    getRookieQueueTagOptions: () => [], getRookieQueueNoteMaxLength: () => 100,
    loadRookieQueue: () => [], renderRookieBoardControls: () => '', renderRookieQueuePanel,
    renderRookieBoard: (rows) => { renderedRows.push(rows); return 'Board rows'; },
    ...overrides,
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
      return responseFromText(fileText(path));
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

const stubPath = '/data/processed/2026_rookie_stubs_v0.json';
const stubFailures = ['404', '503', 'reject', 'invalid-json', {}, [null],
  [json(stubPath)[0], json(stubPath)[0]]];
// Mendoza is the first real stub and overlaps the frozen pre-draft cards.
const rawStubs = json(stubPath);
const incompleteCases = [
  ['empty array', []],
  ['valid subset', rawStubs.slice(1, 4)],
  ['one omitted identity', rawStubs.slice(1)],
  ['same count wrong identity', [{ ...rawStubs[0], player_id: 'synthetic-non-player-294' }, ...rawStubs.slice(1)]],
];
const coverageFailureCases = [['rejection', 'reject'], ['malformed row', [null]], ...incompleteCases];

for (const [name, payload] of incompleteCases) {
  test(`incomplete coverage ${name} cannot authorize scores or player absence`, async () => {
    const { alpha, cards, overlap, stubState, shell } = await sharedLoad({ [stubPath]: payload });
    assert.equal(stubState.status, 'load_failed');
    assert.deepEqual(cards, alpha.cards.filter((card) => card.identity.classYear !== 2026));
    assert.equal(selectRookiePlayer(shell, overlap.slug).status, 'unavailable');
    assert.equal(selectRookiePlayer(shell, 'synthetic-non-player-294').status, 'unavailable');
    const player = await runPlayer(shell, overlap.slug);
    assert.deepEqual(player.calls, []);
    assert.equal(player.nodes.get('detail-actions').innerHTML, '');
    const board = await runBoard(shell);
    assert.match(board.nodes.get('load-status').textContent, /stub coverage unavailable/);
    assert(!shell.stubs.some((stub) => stub.playerId === 'synthetic-non-player-294'));
    for (const stub of shell.stubs) {
      assert.equal(selectRookiePlayer(shell, stub.slug).status, 'unscored');
      const row = mergeRookieBoardRowsWithStubs([], [stub])[0];
      assert.equal(row.rookieGrade, null);
      assert.equal(row.classRank, null);
    }
    assert.equal(shell.stubs.length, payload.filter((row) => rawStubs.some((s) => s.player_id === row.player_id)).length);
  });
}

test('every omitted canonical stub identity makes coverage incomplete', async () => {
  for (const omitted of rawStubs) {
    const { stubState, cards } = await sharedLoad({ [stubPath]: rawStubs.filter((row) => row !== omitted) });
    assert.equal(stubState.status, 'load_failed', omitted.player_id);
    assert(cards.every((card) => card.identity.classYear !== 2026), omitted.player_id);
  }
});

test('complete reordered stubs retain eligibility and healthy stubs survive failed pre-draft Alpha', async () => {
  const normal = await sharedLoad();
  const reordered = await sharedLoad({ [stubPath]: [...rawStubs].reverse() });
  assert.equal(normal.stubState.status, 'loaded');
  assert.equal(reordered.stubState.status, 'loaded');
  assert.deepEqual(reordered.cards, normal.cards);
  const failedAlpha = await sharedLoad({ [alphaPath]: 'reject' });
  assert.equal(failedAlpha.stubState.status, 'loaded');
  assert.equal(failedAlpha.shell.stubs.length, rawStubs.length);
  assert.equal(selectRookiePlayer(failedAlpha.shell, stubRows[0].slug).status, 'unscored');
});

const coveragePaths = ['/data/processed/2026_draft_results.json',
  '/exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_role_context_v0.json'];
for (const path of coveragePaths) {
  for (const failure of ['404', '503', 'reject', 'invalid-json', [], {}]) {
    test(`coverage reference ${path} rejects ${JSON.stringify(failure)}`, async () => {
      const { stubState, alpha, cards } = await sharedLoad({ [path]: failure });
      assert.equal(stubState.status, 'load_failed');
      assert.deepEqual(cards, alpha.cards.filter((card) => card.identity.classYear !== 2026));
    });
  }
  test(`structurally valid altered coverage reference cannot replace the pin: ${path}`, async () => {
    const payload = json(path);
    if (Array.isArray(payload)) payload.pop();
    else payload.rows.push({ ...payload.rows[0], player_id: rawStubs[0].player_id });
    const { stubState, cards } = await sharedLoad({ [path]: payload });
    assert.equal(stubState.status, 'load_failed');
    assert.match(stubState.error, /integrity mismatch/);
    assert(cards.every((card) => card.identity.classYear !== 2026));
  });
}

test('unavailable digest capability cannot authorize coverage', async () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'crypto');
  Object.defineProperty(globalThis, 'crypto', { configurable: true, value: undefined });
  try {
    const { stubState, cards } = await sharedLoad();
    assert.equal(stubState.status, 'load_failed');
    assert(cards.every((card) => card.identity.classYear !== 2026));
  } finally { Object.defineProperty(globalThis, 'crypto', descriptor); }
});

test('mismatched stub facts are withheld while verified unscored rows survive', async () => {
  const payload = rawStubs.map((row, i) => i === 0 ? { ...row, team: 'SYNTHETIC' } : row);
  const { stubState, shell } = await sharedLoad({ [stubPath]: payload });
  assert.equal(stubState.status, 'load_failed');
  assert.equal(shell.stubs.length, rawStubs.length - 1);
  assert(!shell.stubs.some((row) => row.playerId === rawStubs[0].player_id));
});


async function sharedLoad(overrides = {}) {
  return loadWith(overrides, async (module, stubModule) => {
    const alpha = await module.getRookieCardLoadState();
    const cards = await module.getAllRookieCards();
    const overlap = alpha.cards.find((card) => card.identity.classYear === 2026
      && stubRows.some((stub) => stub.playerId === card.playerId));
    if (overlap) assert.equal(await module.getRookieCardBySlug(overlap.slug), null,
      'slug API cannot bypass coverage or healthy stub precedence');
    const stubState = await stubModule.getRookieStubLoadState();
    return { alpha, cards, overlap, stubState, shell: buildRookieShellState(alpha, stubState) };
  });
}

for (const failure of stubFailures) {
  test(`shared score APIs fail closed on stub failure ${Array.isArray(failure) && failure.length > 1 ? "duplicate identity" : JSON.stringify(failure)}`, async () => {
    const { alpha, cards, overlap } = await sharedLoad({ [stubPath]: failure });
    assert(overlap, 'exercise an actual overlapping 2026 card');
    assert(Array.isArray(cards), 'retain the consumer array contract');
    assert(cards.every((card) => card.identity.classYear !== 2026));
    assert.deepEqual(cards, alpha.cards.filter((card) => card.identity.classYear !== 2026),
      'independent historical card objects remain unchanged');
  });
}
test('shared score APIs preserve supported healthy cards and healthy stub precedence', async () => {
  const { alpha, cards, overlap } = await sharedLoad();
  assert(overlap);
  const expected = buildRookieShellState(alpha, goodStubs).cards;
  assert.deepEqual(cards, expected);
  assert(cards.some((card) => card.identity.classYear === 2026));
  assert(!cards.some((card) => stubRows.some((stub) => stub.playerId === card.playerId)
    && card.identity.classYear === 2026));
});
test('shared API retains history while healthy stubs survive failed Alpha', async () => {
  const { alpha, cards } = await sharedLoad({ [alphaPath]: 'reject' });
  assert(cards.length > 0);
  assert(cards.every((card) => card.identity.classYear !== 2026));
  assert.equal(selectRookiePlayer(buildRookieShellState(alpha, goodStubs), stubRows[0].slug).status, 'unscored');
});

function eventNode() {
  return { events: {}, value: '', style: {}, dataset: {}, classList: { toggle() {} },
    addEventListener(event, fn) { this.events[event] = fn; } };
}

async function runSharedConsumer(surface, cards, shell, overlap) {
  const { document, nodes } = domAdapter();
  const rendered = [];
  const viewButton = Object.assign(eventNode(), { dataset: { view: 'board' } });
  document.querySelectorAll = (selector) => selector === '[data-view]' ? [viewButton] : [];
  for (const id of ['matchup-section', 'board-section']) document.getElementById(id).style = {};
  const left = eventNode();
  const right = eventNode();
  document.getElementById('compare-selector').querySelector = (selector) => selector.includes('left') ? left : right;
  const skip = eventNode();
  document.getElementById('matchup-root').querySelector = () => skip;
  const deps = { document,
    window: { location: { search: `?left=${overlap.slug}&right=${overlap.slug}`, href: 'http://localhost/' }, history: { replaceState() {} } },
    getAllRookieCards: async () => cards, getRookieShellState: async () => shell, rookieLoadMessage,
    collectGalleryFilters, sortAndFilterRookies, loadRookieQueue: () => [], isRookieQueued: () => false,
    renderRookieGalleryControls: () => '',
    renderRookieCardCompact: (card) => { rendered.push(card); return `<span>${card.slug}</span>`; },
    renderRookieCompareSelector: ({ cards: candidates, leftSlug, rightSlug }) => {
      rendered.push(...candidates); left.value = leftSlug; right.value = rightSlug;
      return candidates.map((card) => card.slug).join(' ');
    },
    renderRookieCompareView: (root, l, r) => { rendered.push(l, r); root.innerHTML = `${l.slug} ${r.slug}`; },
    seedMatchup: (pool, pos) => { rendered.push(...pool); return pool.filter((card) => card.identity.position === pos).slice(0, 2); },
    getVoteCount: () => 0, getConvictionRating: () => 1000,
  };
  const path = surface === 'gallery' ? 'cards/rookies/index.html' : `cards/rookies/${surface}/index.html`;
  await new AsyncFunction(...Object.keys(deps), entryScript(path))(...Object.values(deps));
  if (surface === 'gallery') {
    const search = nodes.get('gallery-name-search');
    search.value = overlap.identity.name;
    search.events.input();
    assert.doesNotMatch(nodes.get('gallery').innerHTML, new RegExp(overlap.slug));
    search.value = ''; search.events.input();
  } else if (surface === 'compare') {
    const before = rendered.length;
    left.value = overlap.slug;
    left.events.change();
    assert.equal(rendered.length, before, 'stale selector value cannot compare withheld player');
    left.value = cards[0].slug; right.value = cards[1].slug;
    nodes.get('swap-compare-sides').events.click();
  } else {
    skip.events.click();
    viewButton.events.click();
    assert(!nodes.get('board-root').innerHTML.includes(overlap.identity.name));
  }
  assert(rendered.length > 0, `${surface} must actually execute its supported rendering path`);
  assert(rendered.every((card) => card.identity.classYear !== 2026));
  assert.match(nodes.get('load-status').textContent, /stub coverage unavailable/);
}

for (const [caseName, failure] of coverageFailureCases) {
  for (const surface of ['gallery', 'compare', 'swipe']) {
    test(`${surface} entry and rerenders withhold affected cards on ${caseName}`, async () => {
      const { cards, overlap, shell } = await sharedLoad({ [stubPath]: failure });
      await runSharedConsumer(surface, cards, shell, overlap);
    });
  }
}

function savedEntry(card) {
  return { slug: card.slug, name: card.identity.name, position: card.identity.position, school: card.identity.school,
    rookieGrade: 9876.5, classRank: 9876, tierLabel: 'STALE_TIER', identityNote: 'STALE_PROFILE',
    queueNote: 'Keep my observation', queueTag: 'Compare later' };
}

test('queue presentation revalidates scores and comparison without changing saved entries', async () => {
  const alpha = await loadWith();
  const overlap = alpha.cards.find((card) => card.identity.classYear === 2026
    && stubRows.some((stub) => stub.playerId === card.playerId));
  const history = alpha.cards.find((card) => card.identity.classYear === 2025);
  const saved = [savedEntry(overlap), savedEntry(history)];
  const before = structuredClone(saved);
  for (const stubs of [failedStubs, goodStubs]) {
    const shell = buildRookieShellState(alpha, stubs);
    const rows = mergeRookieBoardRowsWithStubs(buildRookieBoardRows(shell.cards), shell.stubs);
    const display = reconcileRookieQueue(saved, rows);
    assert.equal(display[0].rookieGrade, null);
    assert.equal(display[0].classRank, null);
    assert.equal(display[0].scoreAvailable, false);
    assert.equal(display[1].rookieGrade, history.summary.rookieGrade);
    assert.equal(display[1].scoreAvailable, true);
    const html = renderRookieQueuePanel(saved, { left: overlap.slug, right: history.slug }, {}, { supportedRows: rows });
    assert.doesNotMatch(html, /9876|STALE_TIER|STALE_PROFILE|href="\/cards\/rookies\/compare/);
    assert(!html.includes(`data-queue-mark="left" data-slug="${overlap.slug}"`));
    assert(html.includes(`data-queue-mark="left" data-slug="${history.slug}"`));
    assert.match(html, /Keep my observation/);
    assert.match(html, stubs === failedStubs ? /Coverage unavailable/ : /Unscored — draft-fact only/);
  }
  assert.deepEqual(saved, before, 'rendering must not mutate or delete saved entries');
  assert.doesNotMatch(renderRookieQueuePanel(saved), /9876|data-queue-mark/, 'no supplied authority fails closed');
});

for (const [caseName, failure] of coverageFailureCases) {
  test(`Board saved queue and actual import stay gated through rerenders on ${caseName}`, async () => {
    const { overlap, shell } = await sharedLoad({ [stubPath]: failure });
    const history = shell.cards.find((card) => card.identity.classYear === 2025);
    const stored = [savedEntry(overlap), savedEntry(history)];
    const key = 'tiber-rookie-queue-v1';
    const storage = new Map([[key, JSON.stringify(stored)]]);
    const windowBefore = globalThis.window;
    const win = { location: { search: '', href: 'http://localhost/cards/rookies/board/' },
      history: { replaceState() {} }, confirm: () => true,
      localStorage: { getItem: (k) => storage.get(k), setItem: (k, v) => storage.set(k, v) } };
    globalThis.window = win;
    try {
      const importInput = eventNode();
      const importTrigger = eventNode();
      class FixtureReader {
        readAsText(file) { this.result = file.content; this.onload(); }
      }
      const setup = (document) => {
        document.getElementById('queue-root').querySelector = (selector) =>
          selector === '[data-queue-import-input]' ? importInput : selector === '[data-queue-import-trigger]' ? importTrigger : null;
      };
      const board = await runBoard(shell, '', { window: win, loadRookieQueue, importRookieQueue, FileReader: FixtureReader }, setup);
      const assertWithheld = () => {
        const html = board.nodes.get('queue-root').innerHTML;
        assert.match(html, /Coverage unavailable/);
        assert.doesNotMatch(html, /9876|STALE_TIER|STALE_PROFILE/);
        assert(!html.includes(`data-queue-mark="left" data-slug="${overlap.slug}"`));
        assert(html.includes(`data-queue-mark="left" data-slug="${history.slug}"`));
        assert.match(html, /Keep my observation/);
      };
      assertWithheld();
      assert.equal(storage.get(key), JSON.stringify(stored), 'initial render must leave storage byte-identical');
      board.nodes.get('board-name-search').value = overlap.identity.name;
      board.nodes.get('board-name-search').events.input();
      assertWithheld();
      await importInput.events.change({ target: { files: [{ name: 'synthetic-queue.json', content: JSON.stringify({ version: 2, queue: stored }) }] } });
      assert.match(board.nodes.get('queue-root').innerHTML, /Imported 2 queue items/);
      assertWithheld();
      const afterImport = storage.get(key);
      assert.equal(loadRookieQueue()[0].rookieGrade, 9876.5, 'imported snapshot stays stored; it is not eligibility');
      assert.equal(loadRookieQueue().length, 2);
      board.nodes.get('board-name-search').value = '';
      board.nodes.get('board-name-search').events.input();
      assertWithheld();
      assert.equal(storage.get(key), afterImport, 'rerenders must not migrate or sanitize storage');
    } finally { globalThis.window = windowBefore; }
  });
}
