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

## Manual smoke test URLs (exact)

Replace `<DEPLOYED_URL>` with the Railway environment URL.

- `<DEPLOYED_URL>/health`
- `<DEPLOYED_URL>/`
- `<DEPLOYED_URL>/cards/rookies/index.html`
- `<DEPLOYED_URL>/cards/rookies/board/index.html`
- `<DEPLOYED_URL>/cards/rookies/player.html?slug=wr-malik-ford`
- `<DEPLOYED_URL>/cards/rookies/compare/index.html?left=wr-malik-ford&right=te-owen-hale`

### Deep-link verification examples

Run these from a shell to validate route behavior in deployment-style access:

```bash
curl -i "<DEPLOYED_URL>/"
curl -i "<DEPLOYED_URL>/cards/rookies/player?slug=wr-malik-ford"
curl -i "<DEPLOYED_URL>/cards/rookies/compare?left=wr-malik-ford&right=te-owen-hale"
curl -i "<DEPLOYED_URL>/components/rookies/rookieCardStyles.css"
```

Expected outcomes:

- `/` returns `302` with `Location: /cards/rookies/board/index.html`.
- `/cards/rookies/player` and `/cards/rookies/compare` resolve to their HTML surfaces (no local-file-only assumptions).
- CSS route returns `200` with `Content-Type: text/css`.

## “Healthy enough to use before draft day” definition

The standalone lab is healthy enough to use before April 23, 2026 when all of the following are true:

1. `GET /health` returns `200` and JSON includes `status: "ok"`.
2. Root redirect works (`/` → board).
3. Gallery, board, detail, and compare routes above render without browser console fetch errors.
4. Detail and compare query-parameter deep links select the expected players.
5. Queue add/remove/reorder/import/export still works in-browser.
6. Runtime smoke test passes locally via `npm run test:runtime-smoke`.

## Lightweight automated verification

Use the included smoke test before deploys or when hardening route behavior:

```bash
npm run test:runtime-smoke
```

This test starts the standalone server, checks core routes (including query-param deep links), and verifies content-type/path traversal guardrails.


## Draft-week handoff companion

For end-to-end 2026 production + validation + downstream handoff rehearsal, use `docs/runbooks/draft-week-handoff-2026.md` (or run `npm run ops:rehearse-2026`).

## Remaining limitations

- No auth, database, live sync, or websockets.
- No server-side drafting logic.
- No producer recompute during requests.
- Queue state is local-browser storage only (not shared).
- Runtime is intentionally a thin static host for existing prototype surfaces.
