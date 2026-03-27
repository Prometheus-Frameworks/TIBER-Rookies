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
    '/cards/rookies/player.html?slug=wr-malik-ford',
    '/cards/rookies/compare/index.html?left=wr-malik-ford&right=te-owen-hale',
    '/cards/rookies',
    '/cards/rookies/board',
    '/cards/rookies/player?slug=wr-malik-ford',
    '/cards/rookies/compare?left=wr-malik-ford&right=te-owen-hale',
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

  const blocked = await fetch(buildUrl(port, '/..%2Fpackage.json'));
  assert.equal(blocked.status, 400);
});
