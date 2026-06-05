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

# Node tests — currently must be run individually; `node --test tests/`
# is broken (mixes .py files in tests/). See item 1.
node --test tests/runtime-server.smoke.test.cjs
node --test tests/role-opportunity-normalization.test.mjs
```

---

## Work items (the checkpoints)

### 1. Wire Node tests into CI + a working `npm test`
*Priority: HIGH — lowest effort, highest ROI. Tests exist but never run in CI.*

- [ ] Add an `npm test` script that runs all Node tests reliably (the
      default `node --test tests/` fails with `MODULE_NOT_FOUND` because
      `tests/` mixes `.py` and Node test files — use an explicit glob like
      `tests/**/*.test.{mjs,cjs}` or move Node tests to a subdir).
- [ ] Add a Node job to `.github/workflows/ci.yml` (currently Python-only)
      so `runtime-server.smoke.test.cjs` and the `.mjs` unit tests gate PRs.
- [ ] Confirm both existing Node tests run green in the new CI job.

**Resume here:** Not started. Inspect `package.json` scripts and
`.github/workflows/ci.yml`. Decide between a glob in the test script vs.
relocating Node tests into `tests/node/`. Keep the change surgical.

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
