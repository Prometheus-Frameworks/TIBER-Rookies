const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { startServer } = require('../runtime-server.js');

function buildUrl(port, route) {
  return `http://127.0.0.1:${port}${route}`;
}

test('standalone runtime smoke routes', async (t) => {
  const teamContextPath = path.join(
    __dirname,
    '..',
    'exports',
    'promoted',
    'rookie-alpha',
    '2026_rookie_alpha_postdraft_team_context_v0.json',
  );
  const fallbackPath = path.join(
    __dirname,
    '..',
    'exports',
    'promoted',
    'rookie-alpha',
    '2026_rookie_alpha_postdraft_v0.json',
  );

  const fallbackRaw = await fs.readFile(fallbackPath, 'utf8');
  const fallbackPayload = JSON.parse(fallbackRaw);
  const syntheticTeamContextPayload = {
    rows: [
      {
        player_name: '__SMOKE_TEAM_CONTEXT__',
        post_draft_alpha: 0,
        team_context_found: true,
      },
    ],
  };

  await fs.writeFile(teamContextPath, `${JSON.stringify(syntheticTeamContextPayload)}\n`, 'utf8');
  t.after(async () => {
    await fs.rm(teamContextPath, { force: true });
  });

  const server = startServer(0);
  t.after(() => {
    server.close();
  });

  await new Promise((resolve) => server.once('listening', resolve));
  const address = server.address();
  const port = typeof address === 'object' && address ? address.port : 0;

  assert.ok(port > 0, 'expected ephemeral port from test server');

  const health = await fetch(buildUrl(port, '/health'));
  assert.equal(health.status, 200);
  assert.match(health.headers.get('content-type') || '', /application\/json/);
  const payload = await health.json();
  assert.equal(payload.status, 'ok');

  const root = await fetch(buildUrl(port, '/'), { redirect: 'manual' });
  assert.equal(root.status, 302);
  assert.equal(root.headers.get('location'), '/cards/rookies/board/index.html');

  const htmlRoutes = [
    '/cards/rookies/index.html',
    '/cards/rookies/board/index.html',
    '/cards/rookies/player.html?slug=wr-jordyn-tyson',
    '/cards/rookies/compare/index.html?left=wr-jordyn-tyson&right=te-kenyon-sadiq',
    '/cards/rookies',
    '/cards/rookies/board',
    '/cards/rookies/player?slug=wr-jordyn-tyson',
    '/cards/rookies/compare?left=wr-jordyn-tyson&right=te-kenyon-sadiq',
    '/cards/rookies/workbench/index.html',
    '/cards/rookies/workbench',
    '/cards/rookies/workbench/',
  ];

  for (const route of htmlRoutes) {
    const response = await fetch(buildUrl(port, route));
    assert.equal(response.status, 200, `expected 200 for ${route}`);
    assert.match(response.headers.get('content-type') || '', /text\/html/);
    const body = await response.text();
    assert.match(body, /<!doctype html>/i);
  }

  const css = await fetch(buildUrl(port, '/components/rookies/rookieCardStyles.css'));
  assert.equal(css.status, 200);
  assert.match(css.headers.get('content-type') || '', /text\/css/);


  const workbenchJs = await fetch(buildUrl(port, '/cards/rookies/workbench/workbench.js'));
  assert.equal(workbenchJs.status, 200);
  assert.match(workbenchJs.headers.get('content-type') || '', /text\/javascript/);

  const workbenchCss = await fetch(buildUrl(port, '/cards/rookies/workbench/workbench.css'));
  assert.equal(workbenchCss.status, 200);
  assert.match(workbenchCss.headers.get('content-type') || '', /text\/css/);

  const primaryTeamContext = await fetch(
    buildUrl(port, '/exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_team_context_v0.json'),
  );
  assert.equal(primaryTeamContext.status, 200);
  assert.match(primaryTeamContext.headers.get('content-type') || '', /application\/json/);
  const primaryPayload = await primaryTeamContext.json();
  assert.deepEqual(primaryPayload, syntheticTeamContextPayload);

  await fs.rm(teamContextPath, { force: true });

  const primaryTeamContextFallback = await fetch(
    buildUrl(port, '/exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_team_context_v0.json'),
  );
  assert.equal(primaryTeamContextFallback.status, 200);
  assert.match(primaryTeamContextFallback.headers.get('content-type') || '', /application\/json/);
  const fallbackServedPayload = await primaryTeamContextFallback.json();
  assert.deepEqual(fallbackServedPayload, fallbackPayload);

  const outcomeSummary = await fetch(
    buildUrl(port, '/exports/promoted/nfl-fantasy-outcomes/context_flag_outcome_summary_v1.json'),
  );
  if (outcomeSummary.status === 404) {
    assert.ok(true, 'outcome summary artifact is optional in some runtime bundles');
  } else {
    assert.equal(outcomeSummary.status, 200);
    assert.match(outcomeSummary.headers.get('content-type') || '', /application\/json/);
    const outcomePayload = await outcomeSummary.json();
    assert.ok(Array.isArray(outcomePayload) || Array.isArray(outcomePayload.rows));
  }

  const journalSignals = await fetch(
    buildUrl(port, '/data/operator-journal/processed/2026_operator_signal_candidates.json'),
  );
  if (journalSignals.status === 404) {
    assert.ok(true, 'operator journal signal artifact is optional in some runtime bundles');
  } else {
    assert.equal(journalSignals.status, 200);
    assert.match(journalSignals.headers.get('content-type') || '', /application\/json/);
    const journalPayload = await journalSignals.json();
    assert.ok(Array.isArray(journalPayload) || Array.isArray(journalPayload.rows));
  }

  const blocked = await fetch(buildUrl(port, '/..%2Fpackage.json'));
  assert.equal(blocked.status, 400);
});
