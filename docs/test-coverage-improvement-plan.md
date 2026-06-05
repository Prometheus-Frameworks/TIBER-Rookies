# Test Coverage Improvement Plan

**Status:** living checkpoint document — update the checkboxes and the
"Resume here" section as work proceeds so any session or agent (Claude,
Codex, etc.) can pick up exactly where the last one stopped.

**Tracking issue:** see the "Test coverage improvements" issue on
`Prometheus-Frameworks/tiber-rookies`.

Last updated: 2026-06-05

---

## Why this exists

The repo is dual-language:

- **Python pipeline** (`scripts/`) — well covered. 376 tests pass via
  `python -m pytest -q`. ~17 of 34 scripts have dedicated tests.
- **JavaScript / Node** (`lib/`, `components/`, `cards/`,
  `runtime-server.js`) — near zero coverage. 30 source files, 2 test files.

This plan captures the prioritized work to close the JS gap and harden CI.
It doubles as a **checkpoint log** so progress is not lost across rate-limit
cutoffs or container reclaim.

## How to resume (read this first)

1. Run the current state checks (see "Verification commands" below) to see
   what already passes.
2. Find the first unchecked `[ ]` item in "Work items" — that is the next task.
3. Read its "Resume here" note for the exact next step and any gotchas.
4. After completing a step: check the box, update "Resume here", commit, push.

## Verification commands

```bash
# Python suite (should be 376+ passing)
python -m pytest -q

# All Node tests (item 1 complete). Requires Node >= 21 for the glob.
npm test
```

---

## Work items (the checkpoints)

### 1. Wire Node tests into CI + a working `npm test` — DONE (2026-06-05)
*Priority: HIGH — lowest effort, highest ROI. Tests exist but never run in CI.*

- [x] Added `npm test` → `node --test "tests/**/*.test.{cjs,mjs}"`. The bare
      `node --test tests/` failed because Node 22 treats the directory as a
      module entry point; the quoted glob is Node-expanded (shell-portable)
      and discovers all Node tests recursively (so item 2's new `lib` tests
      are picked up automatically). Requires Node >= 21 for glob support.
- [x] Added a separate `node` job to `.github/workflows/ci.yml` (Node 22 via
      `actions/setup-node@v4`, runs `npm test`). The existing `test`
      (Python) job is untouched so its status-check name is unchanged. No
      `npm ci` step needed — the Node tests import only builtins + local
      files, not `@replit/connectors-sdk`.
- [x] Confirmed all 4 Node tests pass (`# pass 4`) with no `node_modules`.

**Resume here:** Complete. Nothing further. The CI `node` job will appear on
the next push/PR.

### 2. Make `lib/*.js` unit-testable, then cover pure-logic modules
*Priority: HIGH — unblocks ~20 currently untestable modules.*

**Blocker:** 7 `lib`/`components` files import via browser-absolute paths
(`from '/lib/rookies/compareRookies.js'`) which Node's resolver cannot
follow. The one JS unit test that exists covers the only module that uses a
relative import (`roleOpportunityNormalization.mjs`). Resolve this first
(subpath import map in `package.json`, a small test-time resolver/loader, or
converting to relative imports) — do not change runtime behavior in the browser.

- [ ] Resolve the import-path blocker so `lib/*.js` can be imported in Node tests.
- [ ] `convictionStore.js` — Elo math (INITIAL_RATING 1000, K_FACTOR 32),
      win/loss updates, vote counting, reset, seedMatchup.
- [ ] `exportCsv.js` + `lib/devy/exportDevyCsv.js` — CSV escaping (commas,
      quotes, newlines, null/undefined cells); header/row shape.
- [ ] `compareRookies.js` — grade-delta thresholds (close 1.5 / lean 4),
      evidence-row selection + dedup, max 6 rows.
- [ ] `buildRookieBoardRows.js` — buildRookieBoardRows / sortRookieBoard /
      filterRookieBoard (position, draftClass, nameFilter) + tier derivation.
- [ ] `mapRookieToCard.js` — central data-shaping fn; cover identity, scores,
      metrics, evidence readiness, post-draft adjustments.
- [ ] `normalizeRookieIdentity.js`, `deriveRookieTier.js`,
      `deriveRookieProfileSummary.js`, `groupRookiesByTier.js`,
      `sortAndFilterRookies.js`, `selectRookieEvidenceMetrics.js` — smaller
      pure helpers, batch as time allows.

**Resume here:** Not started. First action is the import-path blocker —
prototype importing `lib/rookies/convictionStore.js` from a Node test and
pick the least invasive fix. convictionStore is the best first target
(self-contained numeric logic, guards on `window.localStorage`).

### 3. Expand `runtime-server.js` coverage beyond the smoke test
*Priority: MEDIUM.*

- [ ] `ROUTE_ALIASES` clean-URL resolution.
- [ ] `CONDITIONAL_FALLBACKS` chain (post-draft export fallback ordering).
- [ ] `/` 302 redirect semantics (intentionally not in ROUTE_ALIASES).
- [ ] Content-type mapping for served extensions.
- [ ] **Path-traversal safety** for the static file handler (security).

**Resume here:** Not started. Extend
`tests/runtime-server.smoke.test.cjs` (already boots the server) rather than
starting fresh.

### 4. Fill targeted Python gaps
*Priority: MEDIUM. 17 scripts untested; most are `fetch_*` network I/O (defer).*

- [ ] `validate_devy_roster_pulse.py`
- [ ] `validate_round1_draft_signal_profiles.py` /
      `validate_day2_draft_signal_profiles.py` (note: signal-profile *tests*
      exist but target other modules — confirm the validators themselves).
- [ ] `validate_devy_league_market_snapshot.py`
- [ ] `compute_yoy_trends.py`
- [ ] `compute_devy_league_market_snapshot_diff.py`
- [ ] (Lower) `fetch_*` scripts — only with recorded fixtures, no live network.

**Resume here:** Not started. Prefer the `validate_*` and `compute_*`
scripts (logic) over `fetch_*` (network I/O).

### 5. UI components (`components/`, `cards/`)
*Priority: LOW — DOM-heavy, needs jsdom/browser harness.*

- [ ] Extract pure helpers out of large components
      (`RookieCard.js`, `RookieCompareView.js`, `workbench.js`) and unit-test
      those instead of the DOM.

**Resume here:** Not started. Do not begin until items 1–3 land.

---

## Change log

- 2026-06-05 — Plan created from initial coverage analysis. No work items
  started yet.
- 2026-06-05 — Item 1 complete: added `npm test` (glob runner) and a Node CI
  job; all 4 Node tests green.
