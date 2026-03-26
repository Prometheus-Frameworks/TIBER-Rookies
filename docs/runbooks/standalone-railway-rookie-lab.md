# Runbook: Standalone Railway Deploy for TIBER-Rookies

## Purpose

Operate TIBER-Rookies as a lean standalone static rookie lab while preserving producer → artifact → consumer boundaries.

## Service contract

- Runtime: `node runtime-server.js`
- Start command: `npm start`
- Port binding: `PORT` env var (default `3000`)
- Health endpoint: `GET /health`
- Root route: `GET /` redirects to `/cards/rookies/board/index.html`

## Artifact expectations

Static surfaces require these committed artifact files to be present:

- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json`
- `data/raw/2026_combine_results.json`
- `data/processed/2026_college_production.json`
- `data/processed/2026_draft_capital_proxy.json`

If these files are missing, surfaces render load errors (by design) rather than introducing runtime model recompute.

## Local start

1. Use Node.js 20+. No `npm install` is needed; there are no runtime dependencies.
2. From repo root, run:

```bash
npm start
```

3. Verify:

- `curl -s http://localhost:3000/health`
- open `http://localhost:3000/cards/rookies/board/index.html`

## Railway start

Railway uses:

- `package.json` script `start`
- `railway.json` deploy config (`startCommand`, `healthcheckPath`)

Deploy steps:

1. Link repo to Railway project.
2. Deploy default branch (or PR environment).
3. Confirm health check succeeds on `/health`.
4. Confirm rookie board route loads.

## Manual verification checklist

- [ ] `GET /health` returns deterministic JSON with `status: "ok"`.
- [ ] `GET /` redirects to rookie board route.
- [ ] Gallery route loads: `/cards/rookies/index.html`.
- [ ] Board route loads: `/cards/rookies/board/index.html`.
- [ ] Detail route loads a known player slug:
      `/cards/rookies/player.html?slug=wr-malik-ford`.
- [ ] Compare route loads:
      `/cards/rookies/compare/index.html?left=wr-malik-ford&right=te-owen-hale`.
- [ ] Shortlist queue still supports add/remove/reorder.
- [ ] Queue import/export works.
- [ ] Local note/tag annotations persist in browser local storage.

## Known limitations

- No auth, database, live sync, or websockets.
- No server-side drafting logic.
- No producer recompute during requests.
- Runtime is intentionally a thin static host for existing prototype surfaces.
