const test = require('node:test');
const assert = require('node:assert/strict');
const { startServer } = require('../runtime-server.js');

function buildUrl(port, route) {
  return `http://127.0.0.1:${port}${route}`;
}

test('standalone runtime smoke routes', async (t) => {
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

  const blocked = await fetch(buildUrl(port, '/..%2Fpackage.json'));
  assert.equal(blocked.status, 400);
});
