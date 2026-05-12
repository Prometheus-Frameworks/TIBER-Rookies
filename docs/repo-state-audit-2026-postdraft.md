# TIBER-Rookies Repo State Audit — 2026 Post-Draft

**Date:** May 2026  
**Context:** Post-draft cleanup session. Repo was rushed to completeness before the 2026 draft, then dormant. This audit captures current state before the next planning pass.

---

## 1. Pipeline Health

### What runs cleanly

| Script | Status | Notes |
|---|---|---|
| `compute_production_scores.py` | OK | 40/40 players matched from CFBD, 0 failures |
| `compute_rookie_alpha.py` | OK | 40 players, 1 with missing athletic data (Kaelon Black) |
| `validate_promoted_export.py` | PASS | Clean manifest integrity |
| `build_post_draft_alpha.py` | OK | 32 players, 0 missing baselines (was 16 before today) |
| `enrich_post_draft_alpha_with_role_opportunity.py` | OK | 32 rows with `--allow-missing-role-artifacts` flag |
| `enrich_post_draft_alpha_with_team_context.py` | BROKEN | Needs `../TIBER-Teamstate/data/processed/2026_teamstate_context_v0.json` — cross-repo dependency |
| `rehearse_draft_week_handoff_2026.sh` | OK | End-to-end pre→validate→smoke runs |
| Runtime server (`runtime-server.js`) | OK | Serving on port 5000 |

### Test suite

`pytest` is not installed in the environment. 18 Python test files and 2 JS test files exist but cannot currently be run without installing pytest. This is a setup gap, not a code gap.

---

## 2. 2026 Data Coverage

### Seed pool (the authoritative producer input)

| Before today | After today |
|---|---|
| 24 players | 40 players |

16 players were drafted but never in the seed pool — they existed in `draft_capital_proxy.json` and `combine_results.json` as pre-draft watch candidates but were never promoted into the seed pool, so they had zero production scores and zero post-draft alpha.

**Fixed today:**
- All 16 added to `data/raw/2026_real_seed_pool.json`
- 14 had combine/athletic data already in `combine_results.json`; 2 (Antonio Williams, Kaelon Black) had no athletic data captured and were added with nulls
- All 16 draft capital proxy values updated from stale pre-draft big-board-rank proxies to real 2026 NFL pick values
- CFBD API fetched real production scores for all 16 (38 primary matches, 2 name-only fallbacks, 0 failures)

### Players still without athletic data

- **Kaelon Black** (RB, Indiana, R3 P90, 49ers) — no combine metrics captured; model defaults to 50.0 for RAS, noted in logs
- **Antonio Williams** (WR, Clemson, R3 P71, Commanders) — same situation

These won't meaningfully distort rankings given their Day 3 capital, but the gap should be closed if real combine numbers are locatable.

### Post-draft profile coverage

| Source | Players |
|---|---|
| Round 1 signal profiles | 9 |
| Day 2 signal profiles | 23 |
| **Post-draft total** | **32** |
| Pre-draft seed pool | 40 |
| Pre-draft players NOT in any post-draft profile | 8 |

**8 pre-draft players with no post-draft profile** (undrafted or unprofiled):

| Player | Position | Alpha |
|---|---|---|
| Fernando Mendoza | QB | 67.0 |
| Jonah Coleman | RB | 54.6 |
| Elijah Sarratt | WR | 53.3 |
| Garrett Nussmeier | QB | 52.0 |
| Mike Washington Jr. | RB | 50.8 |
| Dae'Quan Wright | TE | 50.3 |
| Nick Singleton | RB | 41.6 |
| Brenen Thompson | WR | 44.2 |

Fernando Mendoza (#1 pre-draft QB at 67.0 alpha) is the most notable gap — he needs either a round1/day2 profile or an explicit "undrafted" marker.

### Round 1 profiles with TBD team

- **Jeremiyah Love** (R1 P3) — team still TBD in profile
- **Kenyon Sadiq** (R1 P16) — team still TBD in profile

These need to be backfilled with the actual teams from the 2026 draft.

---

## 3. Data File State

| File | State | Issue |
|---|---|---|
| `data/processed/2026_draft_results.json` | EMPTY (0 rows) | Never populated post-draft. Blocking canonical draft reconciliation |
| `data/processed/2026_dynasty_adp.json` | 28 entries, all null ADP | Schema scaffolded but no real data ingested |
| `data/processed/2026_ppr_projections.json` | 100 entries, all null projection | Same — schema built, no values |
| `data/processed/2026_yoy_trends.json` | 18 entries | Present, not verified for accuracy |
| `data/processed/2026_prospect_context.json` | 100 entries | Covers more than seed pool; appears complete |
| `data/processed/2026_age_adjusted_production.json` | Present | Used in model blend (60% age-adj, 40% raw) |
| `data/historical/` | Populated | Historical outcomes and features present |
| `data/operator-journal/raw/` | 13 entries | Raw journal entries present |
| `data/operator-journal/processed/` | 18 signal candidates | `build_operator_signal_candidates.py` has been run |

### Operator journal note

The 13 raw entries and 18 candidates exist but none appear to have been promoted into `prospect_context`, `round1/day2 profiles`, or any scoring artifact. The operator journal pipeline is functioning as a holding buffer — human review and promotion step hasn't happened yet.

---

## 4. Export Artifact State

| Artifact | State |
|---|---|
| `2026_rookie_alpha_predraft_v0.json` | 40 players, clean, VALIDATION PASSED |
| `2026_rookie_alpha_predraft_v0.csv` | 40 players |
| `2026_manifest.json` | Clean |
| `2026_rookie_alpha_postdraft_v0.json` | 32 players, 0 missing baselines |
| `2026_rookie_alpha_postdraft_role_context_v0.json` | 32 players (role join with empty stubs) |
| `2026_rookie_alpha_postdraft_team_context_v0.json` | **Stale** — from previous run, team context enrichment broken |
| `exports/promoted/historical-comps/2026_historical_comps_v0.json` | 20 players |
| `exports/promoted/rookie-ml-lane/historical_labeled_dataset.json` | 37 historical rows, not 2026 |

---

## 5. Current Rankings (Reference)

### Pre-draft alpha (top 15, updated with real CFBD data)

| Rank | Player | Pos | Alpha |
|---|---|---|---|
| 1 | Jeremiyah Love | RB | 80.1 |
| 2 | Fernando Mendoza | QB | 67.0 |
| 3 | Carnell Tate | WR | 66.4 |
| 4 | Jordyn Tyson | WR | 67.7 |
| 5 | Denzel Boston | WR | 67.6 |
| 6 | KC Concepcion | WR | 71.9 |
| 7 | Makai Lemon | WR | 68.9 |
| 8 | Drew Allar | QB | 66.8 |
| 9 | Kenyon Sadiq | TE | 65.3 |
| 10 | Eli Stowers | TE | 64.7 |

### Post-draft alpha (top 15)

| Rank | Player | Pos | Team | Pre | Post | Delta |
|---|---|---|---|---|---|---|
| 1 | Jeremiyah Love | RB | TBD | 80.1 | 89.6 | +9.5 |
| 2 | KC Concepcion | WR | Browns | 71.9 | 77.9 | +6.0 |
| 3 | Makai Lemon | WR | Eagles | 68.9 | 76.4 | +7.5 |
| 4 | Carnell Tate | WR | Titans | 66.4 | 74.4 | +8.0 |
| 5 | Jordyn Tyson | WR | Saints | 67.7 | 74.4 | +6.7 |
| 6 | Denzel Boston | WR | Browns | 67.6 | 74.2 | +6.6 |
| 7 | Kenyon Sadiq | TE | TBD | 65.3 | 71.0 | +5.7 |
| 8 | Drew Allar | QB | Steelers | 66.8 | 68.8 | +2.0 |
| 9 | Eli Stowers | TE | Eagles | 64.7 | 67.7 | +3.0 |
| 10 | Omar Cooper Jr. | WR | Jets | 58.1 | 65.2 | +7.1 |
| 11 | De'Zhaun Stribling | WR | 49ers | 55.1 | 62.1 | +7.0 |
| 12 | Sam Roush | TE | Bears | 59.3 | 60.4 | +1.1 |
| 13 | Zachariah Branch | WR | Falcons | 58.3 | 57.5 | −0.8 |
| 14 | Ty Simpson | QB | Rams | 50.9 | 56.9 | +6.0 |
| 15 | Jadarian Price | RB | Seahawks | 48.5 | 56.2 | +7.7 |

---

## 6. Model Formula State

| Component | Weight | Status |
|---|---|---|
| RAS | 35% | Implemented |
| Production | 45% | Implemented — now using real CFBD data (was seeded) |
| Draft capital proxy | 20% | Implemented — now using real pick bands (was pre-draft proxy) |
| Age-at-entry | — | Not implemented. Flagged in docs as future work |

The "proxy" in draft capital is still a band conversion (picks 1–10→95, 11–20→85, etc.) rather than a continuous curve. This is the documented v0 approach.

---

## 7. TIBERverse Alignment Gaps

### TIBER-Teamstate
- The team context enrichment script (`enrich_post_draft_alpha_with_team_context.py`) has a hardcoded relative path to `../TIBER-Teamstate/data/processed/2026_teamstate_context_v0.json`
- This is a blocking cross-repo dependency — nothing in TIBER-Rookies can resolve it without the Teamstate repo present
- The stale `2026_rookie_alpha_postdraft_team_context_v0.json` in exports was from a previous run

### TIBER-Fantasy
- Consumer contract is documented and clean
- Handoff is manual (copy 3 files → run ingest gate → verify `/rookies`)
- No automation or CI hook exists — intentional v0 decision, but should be revisited

### TIBER-Data
- `source-of-truth-audit.md` proposes a structured folder export shape for TIBER-Data promotion
- None of that promotion has been implemented — it exists as a spec only

### Role-and-Opportunity repo
- Referenced in operator journal candidates as a downstream target (`"downstream_targets": ["Role-and-Opportunity"]`)
- No integration or handoff mechanism exists in this repo

### ML Lane
- `exports/promoted/rookie-ml-lane/historical_labeled_dataset.json` has 37 historical rows
- This is a phase 1 experimental dataset, not yet applied to the 2026 class
- `compute_rookie_ml_lane.py` exists but hasn't been run post-draft

---

## 8. UI/Prototype Layer State

### Static rookie surfaces (`cards/rookies/`)
- Gallery, board, detail, compare, swipe, workbench — all routes present
- Data is artifact-backed via `lib/rookies/getRookieCardData.js`
- Covers seasons 2022–2026 per `rookieDataContract.js`
- The board currently serves the predraft artifacts; postdraft artifacts are in exports but the board's data contract path and the fallback chain in the runtime server should serve them when the right query params are used

### Prototype dir (`prototype/`)
- Isolated prototype with fabricated sample data (`window.ROOKIES`)
- Per PR153 audit: this is NOT the production path — `cards/rookies/` uses the canonical artifact-backed flow
- The prototype is essentially dead weight unless someone explicitly wants to port its visual ideas into the active stack

### lib/rookies/ modules
Full module set present and documented:
`buildRookieBoardRows`, `compareRookies`, `convictionStore`, `deriveRookieProfileSummary`, `deriveRookieTier`, `draftResults`, `exportCsv`, `getRookieCardData`, `groupRookiesByTier`, `mapRookieToCard`, `normalizeRookieIdentity`, `postDraftAdjustments`, `rookieDataContract`, `rookieQueueStore`, `selectRookieEvidenceMetrics`, `sortAndFilterRookies`, `sporqHistorical`, `teamLogos`

---

## 9. Prioritized Gap List

**Blocking / High priority**

1. **`2026_draft_results.json` is empty** — this is the intended canonical source for team/round/pick and reconciliation, but was never populated. Round1 and Day2 profiles are all `operator_seeded` and pending reconciliation against it.
2. **Jeremiyah Love + Kenyon Sadiq TBD teams** — need actual team names in round1 profiles before post-draft output is trustworthy for those players.
3. **8 pre-draft players with no post-draft handling** — Fernando Mendoza especially. Need either profiles or explicit "undrafted" markers.
4. **TIBER-Teamstate cross-repo dependency** — team context enrichment cannot run without a workaround.

**Data quality / Medium priority**

5. **Dynasty ADP null values** — 28 entries with zero actual ADP data. KTC integration (`fetch_ktc_values.py`) exists but has not produced real values.
6. **PPR projections all null** — `compute_ppr_projections.py` ran but produced no values; needs investigation.
7. **Kaelon Black and Antonio Williams missing athletic data** — both score at model default (50.0 RAS); real combine numbers should be sourced if available.
8. **Operator journal candidates not promoted** — 18 candidates sitting in review limbo; needs a human pass to decide which become context or profile inputs.

**Infrastructure / Lower priority**

9. **pytest not installed** — 18 Python test files + 2 JS test files exist but the suite can't run. Easy fix.
10. **ML lane not applied to 2026** — phase 1 experimental dataset exists; a 2026 evaluation run would give a parallel confidence signal.
11. **Historical comps covers only 20 of 40 players** — half the class has no comp data.
12. **`prototype/` directory is orphaned** — either port useful visuals to active stack or remove.

---

## 10. What's in Good Shape

- Core producer pipeline is clean and reproducible
- Export contract + validation is well-specified and passing
- Post-draft translator doctrine is solid — transparent, auditable, non-destructive
- CFBD integration works reliably (40/40 matches, rate-limited only during peak season)
- Runtime server is lightweight and correct
- Architecture docs, source-of-truth audit, and operator journal doctrine are above-average quality for a rushed pre-draft build
- The separation between pre-draft frozen grades and post-draft translator is a genuinely good design decision

---

## 11. Branch Disposition Log

### `codex/transform-2026-seed-pool-into-canonical-files` — DELETED 2026-05-12

**Status:** Deleted without merging. Do not recreate or open a PR from this branch.

**Reason:**
- Was 461 commits behind main and only 1 commit ahead at time of deletion
- Touched canonical 2026 files: `2026_real_seed_pool.json`, `2026_combine_results.json`, `2026_draft_capital_proxy.json`, `2026_rookie_alpha_predraft_v0.*`, `2026_manifest.json`
- Almost certainly predates the post-draft/canonical-data work merged in PRs #208 and #209 (2026-05-11)
- Merging would have reintroduced stale pre-draft proxies over source-backed, current files
- Main is the source of truth. All canonical 2026 seed/draft/combine data is current as of today's session.
