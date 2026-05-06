# TIBER-Rookies Handoff Audit
**Date:** 2026-05-06 (Post-Draft)
**Audience:** Downstream engineer picking up TIBER-Rookies work

---

## Executive Summary

TIBER-Rookies is in good operational state post-draft. The producer layer is locked and reproducible. The standalone runtime is healthy. Pre-draft export is validated and ready for TIBER-Fantasy ingest.

**Two blockers before post-draft artifacts are finalized:**
1. `data/processed/2026_draft_results.json` is still empty — this is an operator task, not a code bug.
2. No `CFBD_API_KEY` set — a subset of production scores remain on manual/estimated seeds; a re-run of `compute_production_scores.py` with a key would clean these up.

---

## Component Readiness

| Component | Status | Handoff Ready? |
|---|---|---|
| Pre-draft export (100 players) | Complete, validated | ✅ Yes |
| Post-draft translator (32 players) | Generated, non-scoring | ⚠️ Depends on draft results |
| Team context join | Generated, inspect-only | ⚠️ Depends on Teamstate artifact |
| Role context join | Generated, inspect-only | ⚠️ Depends on RoleOpp artifact |
| Standalone runtime | Smoke-tested, healthy | ✅ Yes |
| Documentation & runbooks | Current and detailed | ✅ Yes |
| Draft results logging | **Empty** | ❌ Operator task pending |

---

## 1. What's Complete

- **Pre-draft export** (`2026_rookie_alpha_predraft_v0.*`): 100 players, generated 2026-04-22, manifest validated. Model version `rookie-alpha-predraft-v0.5.0`. Formula: RAS 35% / Production 45% / Draft capital proxy 20%.
- **Post-draft translator layer**: Deterministic draft-capital adjustments applied to 32 profiled/drafted players. Pre-draft scores frozen; post-draft adds bounded translator delta with explicit reason codes (`talent_confirmation` / `opportunity_insulation`).
- **Post-draft enrichment exports**: `postdraft_team_context_v0` and `postdraft_role_context_v0` generated as read-only inspect joins (non-scoring).
- **Standalone runtime**: `runtime-server.js` zero-dependency Node server. Health, gallery, board, detail, compare routes all passing `npm run test:runtime-smoke`.
- **ML lane**: Full evaluation suite in `exports/promoted/rookie-ml-lane/`. Explicitly experimental/additive; warnings preserved in artifacts.
- **Historical comps**: Scaffold output in `exports/promoted/historical-comps/`. Sample data only (not a production-grade dataset).
- **Operator tooling**: `npm run ops:rehearse-2026` rehearsal script, manifest validation, post-draft build scripts.

---

## 2. Blocking Issues

### B1 — Draft Results Not Populated (High Priority)

**File:** `data/processed/2026_draft_results.json`
**Current state:** Empty array `[]`
**Expected:** Array of `{ player_id, nfl_team, draft_round, overall_pick, is_udfa }` for all 32+ drafted seed-pool players
**Impact:** Post-draft enrichment joins (team context, role context) cannot look up team assignment. Current postdraft artifacts are valid but team context fields may be incomplete.
**Fix:** Log all 2026 picks and UDFAs, then re-run:
```bash
python3 scripts/build_post_draft_alpha.py
python3 scripts/enrich_post_draft_alpha_with_team_context.py
python3 scripts/enrich_post_draft_alpha_with_role_opportunity.py
```

### B2 — Production Scores: Mixed Sources (Medium Priority)

**File:** `data/processed/2026_college_production.json`
**Current state:** 100 players, 0 nulls, but mixed source quality:
- Cleanly CFBD-sourced: a subset of QB/RB/WR/TE (script ran, partially succeeded)
- `manual_seed`: majority of players — estimates with archetype tags, not real stats
- `Research agent estimate` / `Estimated from...`: several entries with explicit "verify with CFBD" flags
- One entry marked "CFBD verification pending"

**Root cause:** CFBD API was rate-limiting during draft-season traffic. The script (`scripts/compute_production_scores.py`) is fully implemented with retry logic. No API key was set, so unauthenticated requests hit rate limits.

**Fix:** Set `CFBD_API_KEY` (free at collegefootballdata.com) and run:
```bash
python3 scripts/compute_production_scores.py
```
Post-draft is a good time — API traffic is much lower. Then re-run the full producer pipeline and validate.

### B3 — Upstream Artifacts Not Verified

Post-draft enrichment assumes these paths exist relative to repo root:
- `../TIBER-Teamstate/data/processed/2026_teamstate_context_v0.json`
- `../Role-and-opportunity-model/data/processed/2026_team_role_opportunity_profiles.json`
- `../Role-and-opportunity-model/data/processed/2026_role_to_fantasy_baselines.json`

These are read-only inspect joins (non-scoring), but team and role fields in postdraft exports will be empty if the paths are missing or stale. Confirm availability before handoff.

---

## 3. Minor Issues

- **`rb-kaelon-black` missing pre-draft baseline**: Captured in `2026_rookie_alpha_postdraft_missing_baselines_v0.json`. Day 3 pick not in original seed pool. Non-blocking but should be reconciled when seed pool is expanded.
- **README still describes pre-draft framing**: Post-draft exports (`postdraft_v0`, `postdraft_team_context_v0`, etc.) are not documented in README. The layout section is stale.
- **No summary doc for the pre → post → enrichment flow**: A new reader has to piece together the pipeline from individual doc files. A one-pager flowchart would help.

---

## 4. Open GitHub Issues (Not Addressed)

These issues were opened pre-draft and remain open. They represent intended model improvements, not bugs:

| Issue | Title | Description |
|---|---|---|
| #126 | SPORQ pipeline gap | WR SPORQ scores exist in `sporq_historical.json` but are never written into `exceptional_metrics` in context files. The compute script reads from `exceptional_metrics`, so SPORQ never reaches the model for WRs. Two parts: pipeline fix + WR trust level design decision. |
| #130 | WR evidence standard: Bell vs Lemon redesign | Core model redesign proposal: evidence completeness score, consensus delta capping by completeness tier, context flag score adjustments, partial RAS confidence correction. 5-step implementation plan in the issue. |
| #134 | Carnell Tate stress test | Depends on #130 landing. Pre-draft framing; still useful as a model calibration audit post-draft. |
| #167 | Compare page rebuild | Has a zip attachment, minimal description. Needs clarification before implementation. |
| #31 | CFBD production score pipeline | Superseded — the script exists and is implemented. Issue was opened when it was just a spec. Can be closed once a successful CFBD run completes and manual seeds are replaced. |

---

## 5. Architecture Recap

```
data/raw/ + data/processed/  (inputs)
        ↓
compute_rookie_alpha.py       (pre-draft producer, frozen formula)
        ↓
exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.*  +  manifest
        ↓
[Draft happens — operator populates 2026_draft_results.json]
        ↓
build_post_draft_alpha.py     (translator, non-scoring delta)
enrich_*_with_team_context    (read-only join from Teamstate)
enrich_*_with_role_opportunity (read-only join from RoleOpp)
        ↓
exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_*.*
        ↓
[Manual operator handoff to TIBER-Fantasy]
        ↓
TIBER-Fantasy ingest gate → /rookies surface
```

Key cross-repo boundaries:
- **TIBER-Data**: Cross-repo artifact governance (future)
- **TIBER-Teamstate**: Team/environment context (read-only join, not a runtime dep)
- **Role-and-Opportunity-model**: Role/baselines (read-only join, not a runtime dep)
- **TIBER-Fantasy**: Downstream consumer; should ingest promoted exports as versioned artifacts, not treat this repo as a live dep

---

## 6. Immediate Action Items

1. **Populate `data/processed/2026_draft_results.json`** with 2026 picks and UDFAs
2. **Get a CFBD API key** and re-run `compute_production_scores.py` to replace manual seeds
3. **Re-run post-draft builder scripts** after #1 completes
4. **Confirm upstream Teamstate + RoleOpp artifact paths** are available
5. **Ingest pre-draft export to TIBER-Fantasy** — safe to do now, doesn't depend on #1–4
6. **Close issue #31** once CFBD run succeeds

## 7. Near-Term Work (Next 2 Weeks)

- Address issue #126 (SPORQ pipeline fix — concrete, low risk)
- Assess issues #130 / #134 (WR model redesign — significant, requires design decision)
- Update README to document post-draft export variants
- Collect post-draft outcome signals (snaps, targets) to begin validating model calibration

---

## 8. Known Non-Issues

These are confirmed working as designed — not bugs:
- Age-at-entry adjustment not implemented (explicit placeholder in v0)
- 2026 draft capital is temporary big-board proxy, not true NFL capital (documented)
- Queue state is browser-local only (no auth/sync by design)
- Runtime is static-only (no server-side recompute by design)
- Cross-repo handoff is manual (operator decision point preserved by design)
- 15 players missing combine data in pre-draft export (expected, flagged in manifest)
