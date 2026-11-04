const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');

function buildUrl(port, route) {
  return `http://127.0.0.1:${port}${route}`;
}

test('standalone runtime smoke routes', async (t) => {
  // Failure fixtures must never rewrite or remove canonical promoted files.
  // Serve the unchanged runtime from a disposable copy instead.
  const fixtureRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'rookies-runtime-smoke-'));
  t.after(() => fs.rm(fixtureRoot, { recursive: true, force: true }));
  for (const entry of ['runtime-server.js', 'cards', 'components', 'lib', 'data', 'exports']) {
    await fs.cp(path.join(__dirname, '..', entry), path.join(fixtureRoot, entry), { recursive: true });
  }
  const { startServer } = require(path.join(fixtureRoot, 'runtime-server.js'));
  const roleContextPath = path.join(
    fixtureRoot,
    'exports',
    'promoted',
    'rookie-alpha',
    '2026_rookie_alpha_postdraft_role_context_v0.json',
  );
  const teamContextPath = path.join(
    fixtureRoot,
    'exports',
    'promoted',
    'rookie-alpha',
    '2026_rookie_alpha_postdraft_team_context_v0.json',
  );
  const fallbackPath = path.join(
    fixtureRoot,
    'exports',
    'promoted',
    'rookie-alpha',
    '2026_rookie_alpha_postdraft_v0.json',
  );

  const fallbackRaw = await fs.readFile(fallbackPath, 'utf8');
  const fallbackPayload = JSON.parse(fallbackRaw);
  const syntheticRoleContextPayload = {
    rows: [
      {
        player_name: '__SMOKE_ROLE_CONTEXT__',
        post_draft_alpha: 0,
        team_context_found: true,
        role_team_profile_found: true,
        role_baseline_found: true,
        role_opportunity_found: true,
      },
    ],
  };
  const syntheticTeamContextPayload = {
    rows: [
      {
        player_name: '__SMOKE_TEAM_CONTEXT__',
        post_draft_alpha: 0,
        team_context_found: true,
      },
    ],
  };

  await fs.writeFile(roleContextPath, `${JSON.stringify(syntheticRoleContextPayload)}\n`, 'utf8');
  await fs.writeFile(teamContextPath, `${JSON.stringify(syntheticTeamContextPayload)}\n`, 'utf8');
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
    '/cards/devy/index.html',
    '/cards/devy',
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

  const boardPage = await fetch(buildUrl(port, '/cards/rookies/board/index.html'));
  const boardHtml = await boardPage.text();
  assert.match(boardHtml, /getRookieShellState/);
  assert.match(boardHtml, /mergeRookieBoardRowsWithStubs/);

  const playerPage = await fetch(buildUrl(port, '/cards/rookies/player.html?slug=wr-cyrus-allen'));
  const playerHtml = await playerPage.text();
  assert.match(playerHtml, /selectRookiePlayer/);
  assert.match(playerHtml, /renderRookieStubCard/);

  for (const route of ['/lib/rookies/rookieShellState.js', '/lib/devy/transitionState.js']) {
    const response = await fetch(buildUrl(port, route));
    assert.equal(response.status, 200);
    assert.match(response.headers.get('content-type') || '', /javascript/);
  }

  const rookieStubs = await fetch(
    buildUrl(port, '/data/processed/2026_rookie_stubs_v0.json'),
  );
  assert.equal(rookieStubs.status, 200);
  assert.match(rookieStubs.headers.get('content-type') || '', /application\/json/);
  const stubPayload = await rookieStubs.json();
  assert.equal(stubPayload.length, 49);
  assert.equal(stubPayload[0].alpha_status, 'not_scored');
  assert.equal(stubPayload[0].reason, 'not_in_postdraft_alpha_coverage');
  assert.equal(
    stubPayload.filter((stub) => stub.round >= 4)
      .every((stub) => stub.reason === 'below_day2_scoring_floor'),
    true,
  );

  const css = await fetch(buildUrl(port, '/components/rookies/rookieCardStyles.css'));
  assert.equal(css.status, 200);
  assert.match(css.headers.get('content-type') || '', /text\/css/);


  const workbenchJs = await fetch(buildUrl(port, '/cards/rookies/workbench/workbench.js'));
  assert.equal(workbenchJs.status, 200);
  assert.match(workbenchJs.headers.get('content-type') || '', /text\/javascript/);

  const workbenchCss = await fetch(buildUrl(port, '/cards/rookies/workbench/workbench.css'));
  assert.equal(workbenchCss.status, 200);
  assert.match(workbenchCss.headers.get('content-type') || '', /text\/css/);

  const primaryRoleContext = await fetch(
    buildUrl(port, '/exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_role_context_v0.json'),
  );
  assert.equal(primaryRoleContext.status, 200);
  assert.match(primaryRoleContext.headers.get('content-type') || '', /application\/json/);
  const primaryRolePayload = await primaryRoleContext.json();
  assert.deepEqual(primaryRolePayload, syntheticRoleContextPayload);

  const primaryTeamContext = await fetch(
    buildUrl(port, '/exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_team_context_v0.json'),
  );
  assert.equal(primaryTeamContext.status, 200);
  assert.match(primaryTeamContext.headers.get('content-type') || '', /application\/json/);
  const primaryPayload = await primaryTeamContext.json();
  assert.deepEqual(primaryPayload, syntheticTeamContextPayload);

  await fs.rm(roleContextPath, { force: true });

  const roleContextFallbackToTeam = await fetch(
    buildUrl(port, '/exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_role_context_v0.json'),
  );
  assert.equal(roleContextFallbackToTeam.status, 200);
  assert.match(roleContextFallbackToTeam.headers.get('content-type') || '', /application\/json/);
  const roleToTeamPayload = await roleContextFallbackToTeam.json();
  assert.deepEqual(roleToTeamPayload, syntheticTeamContextPayload);

  await fs.rm(teamContextPath, { force: true });

  const roleContextFallbackToPostDraft = await fetch(
    buildUrl(port, '/exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_role_context_v0.json'),
  );
  assert.equal(roleContextFallbackToPostDraft.status, 200);
  assert.match(roleContextFallbackToPostDraft.headers.get('content-type') || '', /application\/json/);
  const roleToPostDraftPayload = await roleContextFallbackToPostDraft.json();
  assert.deepEqual(roleToPostDraftPayload, fallbackPayload);

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
