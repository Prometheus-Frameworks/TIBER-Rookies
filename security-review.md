# TIBER-Rookies Defensive Security Review

**Date:** 2026-07-15  
**Scope:** Full codebase — static Node.js server, frontend HTML/JS, Python data pipeline, CI/CD

---

## Finding 1 — Stored XSS via Queue Import Note (Medium)

**Severity:** Medium  
**Confidence:** CONFIRMED  
**Files:**
- `cards/rookies/player.html` lines 82–90 (`renderActions`)
- `lib/rookies/rookieQueueStore.js` lines 19–24 (`sanitizeQueueNote`)

**Why it is risky:**

`renderActions` in `player.html` injects `annotation.queueNote` into `actionsRoot.innerHTML` without HTML encoding:

```js
// player.html:82-90
actionsRoot.innerHTML = `
  <div class="detail-actions-panel">
    <div class="detail-actions-copy">
      <div class="meta">Shortlist status for ${card.identity.name}: ...
      ${queued && annotationBits.length
        ? `<div ...>${annotationBits.join(' • ')}</div>`   // ← queueNote injected here
        : ''}
```

`annotationBits` includes `annotation.queueNote` verbatim (lines 78–79). This note is loaded from `localStorage` via `getQueuedRookieAnnotation()`. The storage path is writable via the Queue Import feature. `sanitizeQueueNote` only trims whitespace and caps length — it does not HTML-encode:

```js
// rookieQueueStore.js:19-24
function sanitizeQueueNote(note) {
  if (typeof note !== 'string') return '';
  return note.replace(/\s+/g, ' ').trim().slice(0, NOTE_MAX_LENGTH);
}
```

A payload like `<img src=x onerror=alert(1)>` (29 characters) survives sanitization and executes in the browser when the player detail page renders.

**Attack path:**
1. Attacker crafts a queue export JSON with `queueNote: "<img src=x onerror=alert(1)>"`
2. Victim imports the file via the Board's "Import queue JSON" button
3. The note is stored in `localStorage` unencoded
4. Victim navigates to any queued player's detail page — payload executes

Note: `RookieQueuePanel.js` line 87 correctly uses `esc(notePreview(playerNote))` for the same field in the board view. `player.html` is the inconsistent outlier.

**Safest minimal fix:**

Use the `esc()` function already defined at line 102 of `player.html`:

```js
// In renderActions — escape all interpolated values
actionsRoot.innerHTML = `
  <div class="detail-actions-panel">
    <div class="detail-actions-copy">
      <div class="meta">Shortlist status for ${esc(card.identity.name)}: <strong>...</strong></div>
      ${queued && annotationBits.length
        ? `<div class="meta detail-actions-note">${esc(annotationBits.join(' • '))}</div>`
        : ''}
    </div>
    ...
  </div>
`;
```

**Human reviewer follow-up:** Verify that `queueTag` (already allowlist-validated) and `card.identity.name` (from static JSON) have no other unescaped render paths.

---

## Finding 2 — Unescaped Data Fields in Devy Watchlist Table (Low–Medium)

**Severity:** Low–Medium  
**Confidence:** CONFIRMED  
**File:** `cards/devy/index.html` lines 99–128

All data fields from the devy watchlist JSON are injected directly into `innerHTML` and `insertAdjacentHTML` without any HTML encoding:

```js
// cards/devy/index.html:99-110
rowsEl.innerHTML = visibleRows.map((row) => `
  <td><strong>${row.player_name ?? ''}</strong>...</td>
  <td>${row.school ?? ''}</td>
  <td>${row.position ?? ''}</td>
  ...
`).join('');

// lines 127-128
actionability.forEach((value) =>
  actionabilityFilterEl.insertAdjacentHTML('beforeend', `<option value="${value}">${value}</option>`)
);
```

The data comes from `/data/devy/devy_seed_watchlist_2026.json`, an operator-controlled file. Any commit-time or pipeline-generated content with HTML characters (e.g., a player name containing `<`, or a `lifecycle_stage` tag with special characters) would execute. Every other page in the codebase uses `esc()` consistently — the devy page is an outlier.

**Safest minimal fix:** Add a local `esc()` function (or import one) and apply it to all string fields before interpolation. Match the pattern used in `RookieCard.js` and `RookieQueuePanel.js`.

---

## Finding 3 — `error.message` Injected Unescaped into `innerHTML` in Catch Blocks (Low)

**Severity:** Low  
**Confidence:** PLAUSIBLE  
**Files:**
- `cards/rookies/index.html` line 141
- `cards/rookies/board/index.html` line 487
- `cards/rookies/player.html` line 215
- `cards/rookies/compare/index.html` line 137

All four catch blocks follow this pattern:

```js
someRoot.innerHTML = `<div class="meta">Failed to load X: ${error.message}</div>`;
```

Today, error messages come from failed `fetch()` calls to local static files or JSON parse failures, so `error.message` is controlled by the JS engine. If a future code path surfaces attacker-controlled text as an error message (e.g., a server error body embedded in the exception), this becomes reflected XSS. The devy page correctly uses `statusEl.textContent =` for the same pattern — all other pages should follow suit.

**Safest minimal fix:** Replace with `textContent` assignment, or apply `esc()`:

```js
someRoot.innerHTML = `<div class="meta">Failed to load X: ${esc(error.message)}</div>`;
// or safer:
someRoot.textContent = `Failed to load X: ${error.message}`;
```

---

## Finding 4 — No HTTP Security Headers on Static Server (Low–Medium)

**Severity:** Low–Medium (compounding factor for all XSS findings above)  
**Confidence:** CONFIRMED  
**File:** `runtime-server.js`

The server sends no security-relevant headers. Missing headers:

| Header | Risk Without It |
|---|---|
| `Content-Security-Policy` | All pages use inline `<script type="module">` — any XSS executes fully |
| `X-Content-Type-Options: nosniff` | Browser may MIME-sniff served files |
| `X-Frame-Options: SAMEORIGIN` | Pages can be framed for clickjacking |
| `Referrer-Policy` | Full URL leaked to external resources (ESPN CDN) |

**Safest minimal fix:** Add headers in the request handler (applies to all responses):

```js
// In writeFileHeaders and sendJson/sendText helpers, add:
'X-Content-Type-Options': 'nosniff',
'X-Frame-Options': 'SAMEORIGIN',
'Referrer-Policy': 'strict-origin-when-cross-origin',
'Content-Security-Policy':
  "default-src 'self'; img-src 'self' https://a.espncdn.com; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
```

Note: `unsafe-inline` is required because scripts are inline `<script type="module">` blocks. Moving scripts to external files would enable a stricter CSP.

---

## Finding 5 — `.git` Directory (and Full Repo) Served by Static Server (Low)

**Severity:** Low  
**Confidence:** CONFIRMED  
**File:** `runtime-server.js` line 7 (`ROOT_DIR = __dirname`)

The server has no path allowlist and serves every file under the repository root, including:
- `/.git/config` — may contain remote URLs; could include credentials if `store` helper is configured
- `/.git/ORIG_HEAD` — commit SHAs
- `/scripts/*.py` — all pipeline source code
- `/data/operator-journal/raw/2026_rookie_journal_entries.json` — internal operator notes
- `/.env.example` — reveals expected environment variable names

If a `.env` file were accidentally placed in the repo directory (not committed, just present on disk), it would be served publicly at `/.env`.

**Safest minimal fix:** Block dot-prefixed path segments before resolving the file path:

```js
// In resolveStaticPath, after decoding:
const segments = decodedPath.split('/').filter(Boolean);
if (segments.some((s) => s.startsWith('.'))) return null;
```

This blocks `.git`, `.github`, `.env*`, `.gitignore`, and any future dot-files.

---

## Finding 6 — CI Actions Pinned to Mutable Tags, Not SHA Digests (Low)

**Severity:** Low  
**Confidence:** CONFIRMED  
**File:** `.github/workflows/ci.yml`

All three third-party actions use floating tag references:

```yaml
uses: actions/checkout@v4          # mutable tag
uses: actions/setup-python@v5
uses: actions/setup-node@v4
```

If any upstream repository is compromised and a tag is re-pointed, malicious code runs in CI with access to runner secrets and repository write permissions.

Additionally, the workflow has no `permissions:` block, so `GITHUB_TOKEN` defaults to broad write access (contents, packages, deployments).

**Safest minimal fix:**

Pin to specific commit SHAs (verify against the upstream repos):

```yaml
uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683    # v4.2.2
uses: actions/setup-python@0b93645e9fea7318ecaed2b359559ac225c90a2  # v5.3.0
uses: actions/setup-node@39370e3970a6d050c480ffad4ff0ed4d3fdee5af   # v4.1.0
```

Add minimum permissions:

```yaml
permissions:
  contents: read
```

---

## Finding 7 — Missing `esc()` on Logo `src` Attribute in `RookieCardCompact.js` (Informational)

**Severity:** Informational (no current exploitability)  
**Confidence:** CONFIRMED  
**File:** `components/rookies/RookieCardCompact.js` lines 17–18

```js
// RookieCardCompact.js — src NOT escaped:
src="${collegeUrl}"
src="${nflUrl}"

// RookieCard.js — src IS escaped (correct):
src="${esc(collegeUrl)}"
src="${esc(nflUrl)}"
```

Not currently exploitable: both URLs come from a static lookup table in `teamLogos.js` that produces only hardcoded ESPN CDN HTTPS URLs. However, the inconsistency with `RookieCard.js` creates a maintenance trap — if the lookup ever becomes data-driven, this omission becomes a reflected XSS via an HTML attribute.

**Safest minimal fix:** Apply `esc()` for consistency:

```js
src="${esc(collegeUrl)}"
src="${esc(nflUrl)}"
```

---

## Summary

| # | Finding | Severity | Confidence | Primary File |
|---|---|---|---|---|
| 1 | Stored XSS via queue import note (player detail) | Medium | CONFIRMED | `cards/rookies/player.html:82` |
| 2 | Unescaped data fields in devy watchlist table | Low–Med | CONFIRMED | `cards/devy/index.html:99` |
| 3 | `error.message` unescaped in catch innerHTML | Low | PLAUSIBLE | 4 HTML pages |
| 4 | No HTTP security headers | Low–Med | CONFIRMED | `runtime-server.js` |
| 5 | `.git` dir and full repo served by static server | Low | CONFIRMED | `runtime-server.js` |
| 6 | CI actions on mutable tags; no `permissions` block | Low | CONFIRMED | `.github/workflows/ci.yml` |
| 7 | Missing `esc()` on logo `src` (informational) | Info | CONFIRMED | `components/rookies/RookieCardCompact.js:17` |

### No Issues Found In

- **Hardcoded secrets:** None found. `CFBD_API_KEY` is read from environment only, never committed.
- **Path traversal:** Double-checked (`..` segment filter + `absolutePath.startsWith(ROOT_DIR)`). Smoke test confirms it works.
- **SQL / command injection:** No database, no shell execution in production paths.
- **SSRF:** All outbound URLs are hardcoded constants; `KTC_API_URL` is `None` by default.
- **Dependency confusion:** Single npm dep with lockfile; Python uses stdlib only.
- **Queue import schema validation:** `parseImportedRookieQueue` validates version, type-checks, and normalizes all items — robust against malformed structures, though not against XSS payload passthrough (Finding 1).
