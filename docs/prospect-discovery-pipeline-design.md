# TIBER-Rookies — Prospect Discovery Pipeline Design

**Status:** Planning / Pre-implementation  
**Author:** Operator  
**Applies to:** 2027 class and all future classes  
**Last updated:** 2026-05-16

---

## Problem Statement

The 2026 class was seeded entirely by hand from consensus big boards and combine invite lists. This means:

- Players below the top-50 consensus radar were invisible until after the draft
- 16 2026 players were never in the seed pool despite being drafted — they had to be backfilled post-draft
- The 2027 watchlist currently has 3 manually entered entries with no discovery logic behind them
- There is no repeatable process for future classes

The goal of this design is a two-phase, CFBD-driven funnel that surfaces prospects early and broadly, then narrows through an explicit operator promotion gate as the season and draft calendar progress. The shadow pool is producer-only discovery state; it is not model-active and is not runtime-visible until a later PR intentionally promotes players into the real seed/watchlist path.

---

## Design: Two-Phase Funnel

```
PHASE 1 — Broad Tracking           PHASE 2 — Model Activation
──────────────────────────────      ──────────────────────────────
Trigger: Season begins (Sept)       Trigger: Combine invite list drops (~Feb)
Population: All skill-pos players   Population: Phase 1 players w/ invite
             w/ 2+ college seasons               OR manually promoted
Output: Shadow pool JSON            Output: Active seed pool → full alpha
Status: "watchlist"                 Status: "combine_invited" → "active"
```

This mirrors how actual scouting departments operate: cast wide early, then funnel as hard data (combine, draft capital) arrives.

---

## Phase 1 — Broad Tracking

### Trigger and cadence

- Runs once at the start of each college football season (September)
- Can be re-run mid-season to pick up transfers or newly eligible players
- Output is additive — existing player identity fields, manual notes, and current status are preserved; source-observed fields may be refreshed; new candidates may be added

### Discovery source

CFBD roster data, with the API shape verified before implementation. Do **not** assume CFBD supports a class-wide or position-wide query such as `/roster?year={year}&position={position}`.

Known repo-compatible default: fetch rosters by team + season, then filter positions locally. This matches the existing `compute_breakout_age.py` roster-fetching pattern. If implementation verifies a better supported endpoint exists, document that verification in the implementation PR before using it.

The roster payload is expected to provide each player’s `year` (academic year: 1=FR, 2=SO, 3=JR, 4=SR, 5=5th year) or an equivalent field that can be mapped without fabricating eligibility.

### Eligibility filter

For a `class_year`, define `discovery_season = class_year - 1`. A 2027 class shadow pool is initially discovered from the 2026 college season and can be rerun during the 2026 season as roster and production data update.

A player enters the shadow pool if:

| Condition | Rule |
|---|---|
| Academic year | `year >= 3` (junior or above) → guaranteed draft-eligible class |
| OR young breakout | `year == 2` AND meets position breakout threshold (see below) |
| Conference tier | No filter — all FBS conferences included |
| Position | WR, RB, TE, QB (configurable via `DISCOVERY_POSITIONS`) |

The `year >= 3` rule covers the standard case. The sophomore breakout exception preserves players like Jeremiah Smith who warrant tracking before they reach junior year.

### Breakout thresholds (reuse existing logic)

`compute_breakout_age.py` already defines module-level breakout threshold constants. The discovery script should reuse those existing module-level constants rather than duplicating or renaming them. It must also reuse the existing production/breakout field semantics (for example `receiving_yard_share`) instead of creating new aliases. Extract threshold evaluation into a reusable helper only if implementation needs logic beyond the raw constants.

| Position | Share criteria (preferred) | Volume fallback |
|---|---|---|
| WR | target_share ≥ 0.20 OR receiving_yard_share ≥ 0.25 | targets ≥ 50 |
| TE | target_share ≥ 0.15 OR receiving_yard_share ≥ 0.20 | targets ≥ 35 |
| RB | rush_share ≥ 0.30 OR rush_yard_share ≥ 0.30 | rush_attempts ≥ 80 |
| QB | — | pass_attempts ≥ 150 |

### Output file

`data/raw/{class_year}_shadow_pool.json`

Example: `data/raw/2027_shadow_pool.json`

This is distinct from the watchlist stub (`2027_watchlist_seed.json`) and from the real seed pool. It is the machine-generated discovery layer and remains producer-only until an operator-approved promotion writes candidates into the real seed/watchlist path.

---

## Phase 2 — Model Activation

### Trigger

Combine invite list is released by the NFL (~late January / early February). An operator manually runs the activation step, or it is triggered by a dated flag in the config.

### Promotion logic

A shadow pool player is promoted to `"combine_invited"` status when:
- Their name appears in `data/raw/{class_year}_combine_results.json` (the combine file is populated when invites are announced), OR
- An operator manually sets their status to `"combine_invited"` or `"active"` (manual override path)

A player at `"combine_invited"` status is eligible to be promoted into the real seed pool (`{class_year}_real_seed_pool.json`) by running the promotion script.

### Promotion script (new — `scripts/promote_shadow_to_seed.py`)

Responsibilities:
1. Read `data/raw/{class_year}_shadow_pool.json`
2. Cross-reference `data/raw/{class_year}_combine_results.json`
3. For each shadow pool player with a combine entry: set status `"combine_invited"`, copy combine measurements into the entry
4. Operator confirms — script writes approved players to `data/raw/{class_year}_real_seed_pool.json`
5. Players not invited remain in shadow pool at `"watchlist"` status (they may still be promoted manually for UDFA tracking)

---

## Data Model

### Shadow pool entry schema

```json
{
  "player_id": "wr-eugene-wilson-florida",
  "player_name": "Eugene Wilson",
  "position": "WR",
  "school": "Florida",
  "class_year": 2027,
  "academic_year": 3,
  "discovery_source": "cfbd_roster",
  "discovery_season": 2026,
  "status": "watchlist",
  "status_history": [
    { "status": "watchlist", "date": "2026-09-01", "reason": "cfbd_roster_discovery" }
  ],
  "breakout_flagged": false,
  "young_breakout": false,
  "combine_invited": false,
  "operator_notes": "",
  "manually_added": false
}
```

### Additive merge and status lifecycle

Reruns are append/additive, not destructive. Existing player identity fields, `operator_notes`, `manually_added`, and current `status` are preserved. Source-observed fields such as school, academic year, position, discovery provenance, and production/breakout observations may be refreshed when a current source provides updated values. `status_history` is append-only: add a new event when status changes, but never rewrite or truncate prior events. Reruns must not automatically demote, remove, or withdraw players that disappear from a later CFBD response; those decisions remain manual operator actions. Newly discovered candidates may be appended.

### Status lifecycle

```
watchlist
    │
    ├─── combine_invited  (combine invite confirmed)
    │         │
    │         └─── active  (promoted to real seed pool → full alpha pipeline)
    │                   │
    │                   ├─── drafted
    │                   └─── undrafted_signed / undrafted_cut
    │
    └─── withdrawn  (transfer, medical, eligibility loss, etc.)
```

### Real seed pool (unchanged schema)

The existing `{class_year}_real_seed_pool.json` schema does not change. Promotion from shadow pool populates it using the same field contract the 2026 class uses. Shadow pool entries that don't have all required fields at promotion time are flagged as incomplete rather than silently promoted with nulls.

---

## File Layout

```
data/raw/
  {year}_shadow_pool.json          ← Phase 1 output (new, machine-generated)
  {year}_combine_results.json      ← Combine measurements (existing)
  {year}_real_seed_pool.json       ← Phase 2 output / authoritative model input (existing)

data/raw/watchlist_overrides.json  ← Manual additions that bypass CFBD discovery
                                      (e.g. players in non-CFBD-covered schools,
                                       operator intuition calls)

scripts/
  discover_shadow_pool.py          ← new: Phase 1 CFBD roster fetch + eligibility filter
  promote_shadow_to_seed.py        ← new: Phase 2 combine gate + promotion
  compute_breakout_age.py          ← existing: breakout logic (imported, not forked)
  compute_production_scores.py     ← existing: unchanged, reads real seed pool
```

---

## Scripts to Build

### 1. `scripts/discover_shadow_pool.py`

| Attribute | Detail |
|---|---|
| Input | CFBD roster data for `discovery_season = class_year - 1`; implementation must verify supported API shape first. Default to team + season roster fetches and local position filtering unless endpoint verification proves a better supported query. |
| Eligibility filter | academic year ≥ 3, OR academic year == 2 with breakout flag |
| Output | `data/raw/{class_year}_shadow_pool.json` |
| Merge behavior | Additive — preserve existing identity fields, `operator_notes`, `manually_added`, and current `status`; refresh source-observed fields when CFBD/provenance data changes; append status history only when status changes; never auto-demote, auto-remove, or erase existing candidates on rerun; append newly discovered candidates |
| Rate limiting | Reuse `cfbd_headers()` from `scripts/cfbd_plays.py`; follow the retry/backoff pattern already used by `compute_breakout_age.py` |
| Config | `DISCOVERY_POSITIONS = ["WR", "RB", "TE", "QB"]`, `DISCOVERY_CLASS_YEAR = 2027`; derive `discovery_season = DISCOVERY_CLASS_YEAR - 1` |

### 2. `scripts/promote_shadow_to_seed.py`

| Attribute | Detail |
|---|---|
| Input | `{year}_shadow_pool.json` + `{year}_combine_results.json` |
| Match logic | Fuzzy name + school match (reuse `normalize_identity()` from `compute_production_scores.py`) |
| Output | Updates shadow pool statuses; writes approved players to `{year}_real_seed_pool.json` |
| Operator gate | `--dry-run` flag shows what would be promoted; `--confirm` writes it |
| Manual override | Reads `watchlist_overrides.json` and includes those players regardless of combine status |

---

## Existing Scripts — Required Updates

| Script | Change needed |
|---|---|
| `compute_production_scores.py` | None — already reads from real seed pool, no changes needed |
| `compute_breakout_age.py` | Prefer no change if `SHARE_BREAKOUT_CRITERIA` and `BREAKOUT_THRESHOLDS` remain module-level importable; extract threshold evaluation into a reusable helper only if `discover_shadow_pool.py` needs logic beyond the raw constants |
| `lib/rookies/rookieDataContract.js` | None for the initial implementation — shadow pool is producer-only and not runtime-visible |

---

## Runtime Exposure

Initial decision: shadow pool is producer-only for now. No runtime contract, route, helper, or data-contract change should be made merely to create or rerun the shadow pool. Model-active and runtime-visible surfaces continue to flow through the existing real seed/watchlist/promoted paths after operator approval.

If a future PR intentionally makes shadow pool data runtime-visible, it should add explicit helpers such as `rookieShadowPoolPath(season)` and `getShadowPoolSeasons()` in that PR, with smoke tests and downstream contract notes. Do not add those helpers in the discovery-script implementation PR unless runtime exposure is explicitly requested.

---

## What This Replaces

| Current approach | Replaced by |
|---|---|
| Hand-curated seed pool from big boards | `discover_shadow_pool.py` CFBD roster discovery |
| Manual combine cross-reference | `promote_shadow_to_seed.py` gate |
| `2027_watchlist_seed.json` (3-entry stub) | `2027_shadow_pool.json` (machine-generated, operator-reviewable) |
| Post-draft backfill of missed players | Shadow pool catches them before the draft |

The manual watchlist stub (`2027_watchlist_seed.json`) can be retired once the shadow pool is populated for 2027 — or its three entries can be migrated in as `manually_added: true` override entries.

---

## What This Does NOT Replace

- **Operator judgment** — the shadow pool is a producer-only candidate list, not a model input. Promotion to the real seed pool is still an operator-confirmed step
- **SPORQ / cohort-stability blending** — downstream of the seed pool, unchanged
- **Combine measurement entry** — still populated manually or from a sourced feed into `{year}_combine_results.json`
- **Post-draft alpha translator** — unchanged; operates on the real seed pool after draft capital is known

---

## Open Questions (resolved)

| Question | Decision |
|---|---|
| Positions in scope | WR, RB, TE, QB — configurable via `DISCOVERY_POSITIONS` |
| Season threshold | 2+ seasons (academic year ≥ 3) + sophomore breakout exception |
| Phase 2 gate | Combine invite (primary) + manual operator override |
| Storage format | Separate producer-only shadow pool file per class year; status field tracks lifecycle |
| Manual override path | `watchlist_overrides.json` — operator can force-include any player |

---

## Implementation Order

Recommended sequence for Codex / Claude agent work:

1. **Verify CFBD roster API shape** — confirm whether team + season roster fetching remains required, or document a better supported endpoint before using it
2. **Reuse breakout threshold constants** from `compute_breakout_age.py`; extract a helper only if raw constants are not enough for implementation
3. **Build `discover_shadow_pool.py`** — CFBD roster fetch, local position filter, eligibility filter, additive shadow pool write
4. **Populate `2027_shadow_pool.json`** — run discovery with `discovery_season = 2026` for `class_year = 2027`
5. **Build `promote_shadow_to_seed.py`** — combine gate + promotion logic
6. **Optionally retire `2027_watchlist_seed.json` later** — only after the shadow pool is populated and operator-approved entries have a contract-safe replacement path; do not change runtime data-contract helpers as part of the producer-only discovery script
7. **Add runbook** to `docs/runbooks/` covering the annual cadence (when to run each script)

Step 1 is unblocked. Steps 2–4 depend on confirming the reusable breakout path and CFBD roster shape. Step 5 depends on step 4. Step 6 depends on an explicit operator decision.

---

## Annual Cadence (future reference)

| Month | Action |
|---|---|
| September | Run `discover_shadow_pool.py` for the upcoming draft class |
| October–January | Shadow pool is read-only; production scores accumulate via CFBD |
| February (combine invites) | Run `promote_shadow_to_seed.py --dry-run`, review, `--confirm` |
| February–April (combine week / draft) | Populate combine measurements; update draft capital post-draft |
| Post-draft | Run full alpha pipeline on promoted real seed pool |
