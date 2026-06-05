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

### 2. Make `lib/*.js` unit-testable, then cover pure-logic modules — MOSTLY DONE (2026-06-05)
*Priority: HIGH — unblocks ~20 currently untestable modules.*

**Blocker (RESOLVED):** within `lib/`, only `compareRookies.js` and
`exportCsv.js` used browser-absolute imports (`from '/lib/...'`) that Node
can't resolve. Fixed with a **test-only ESM resolve hook**
(`tests/helpers/absolute-import-hooks.mjs`, registered via
`tests/helpers/register-hooks.mjs` and wired into `npm test` with
`--import`). It rewrites `/lib`, `/components`, `/cards` specifiers to
repo-root file URLs. Source files keep their deliberate browser-absolute
style — no runtime/browser behavior changed. Also added `lib/package.json`
(`{"type":"module"}`) to silence the `MODULE_TYPELESS_PACKAGE_JSON` reparse
warning (lib `.js` files genuinely are ES modules; nothing `require()`s them).

- [x] Resolve the import-path blocker (resolve hook above). Verified by
      importing `compareRookies.js` via its `/lib/...` path in a real test.
- [x] `convictionStore.js` — `tests/convictionStore.test.mjs` (Elo K=32 math,
      symmetric +/-16 even match, upset swing, reset, seedMatchup, no-storage
      degradation). Uses an in-memory `window.localStorage` mock.
- [x] `exportCsv.js` + `lib/devy/exportDevyCsv.js` —
      `tests/exportCsv.test.mjs`, `tests/exportDevyCsv.test.mjs` (comma/quote/
      newline escaping, null vs 0 formatting, board_rank, devy status
      derivation, pipe-joined arrays).
- [x] `compareRookies.js` — `tests/compareRookies.test.mjs` (overallDelta,
      lean/close/insufficient verdicts, cross-position, direction-aware
      40-yd evidence winner). Doubles as the resolve-hook integration test.
- [x] `buildRookieBoardRows.js` — `tests/buildRookieBoardRows.test.mjs`
      (mapping, post-draft tier override, profile fallbacks, all 4 sorts,
      no-mutation, position/class/name filters).
- [ ] `mapRookieToCard.js` — NOT YET. Central 256-line data-shaping fn; the
      biggest remaining unit. Needs realistic `alphaPlayer/statsRow/pprRow/...`
      fixtures. Highest-value next target.
- [x] `normalizeRookieIdentity.js` — `tests/normalizeRookieIdentity.test.mjs`.
- [x] `deriveRookieTier.js` — `tests/deriveRookieTier.test.mjs`.
- [ ] Remaining small helpers: `deriveRookieProfileSummary.js`,
      `groupRookiesByTier.js`, `sortAndFilterRookies.js`,
      `selectRookieEvidenceMetrics.js` (the last is indirectly exercised via
      compareRookies but has no direct test).

**Resume here:** Blocker resolved; 6 modules covered (Node suite 4 → 47
tests, all green). Next: `mapRookieToCard.js` — read it, build fixtures for
each input row, assert the produced card's identity/scores/metrics/evidence
readiness and post-draft adjustment fields. Then mop up the 4 remaining
small helpers (each is a quick pure-function test like deriveRookieTier).

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
- 2026-06-05 — Item 2 mostly complete: added a test-only resolve hook to
  unblock browser-absolute imports, plus 6 new module test files
  (convictionStore, exportCsv, exportDevyCsv, compareRookies,
  buildRookieBoardRows, normalizeRookieIdentity, deriveRookieTier). Node
  suite 4 → 47 tests, all green. Remaining: `mapRookieToCard.js` + 4 small
  helpers.
