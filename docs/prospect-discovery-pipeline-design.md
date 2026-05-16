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

The goal of this design is a two-phase, CFBD-driven funnel that surfaces prospects early and broadly, then narrows automatically as the season and draft calendar progress.

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
- Output is additive — existing entries are not overwritten, only new ones added

### Discovery source

CFBD `/roster` endpoint, queried by position and year. Example:

```
GET /roster?year=2026&position=WR
```

Returns all rostered WRs that season with `year` (academic year: 1=FR, 2=SO, 3=JR, 4=SR, 5=5th year).

### Eligibility filter

A player enters the shadow pool if:

| Condition | Rule |
|---|---|
| Academic year | `year >= 3` (junior or above) → guaranteed draft-eligible class |
| OR young breakout | `year == 2` AND meets position breakout threshold (see below) |
| Conference tier | No filter — all FBS conferences included |
| Position | WR, RB, TE, QB (configurable via `DISCOVERY_POSITIONS`) |

The `year >= 3` rule covers the standard case. The sophomore breakout exception preserves players like Jeremiah Smith who warrant tracking before they reach junior year.

### Breakout thresholds (reuse existing logic)

`compute_breakout_age.py` already defines these — the discovery script imports and reuses them:

| Position | Share criteria (preferred) | Volume fallback |
|---|---|---|
| WR | target_share ≥ 0.20 OR rec_yard_share ≥ 0.25 | targets ≥ 50 |
| TE | target_share ≥ 0.15 OR rec_yard_share ≥ 0.20 | targets ≥ 35 |
| RB | rush_share ≥ 0.30 OR rush_yard_share ≥ 0.30 | rush_attempts ≥ 80 |
| QB | — | pass_attempts ≥ 150 |

### Output file

`data/raw/{class_year}_shadow_pool.json`

Example: `data/raw/2027_shadow_pool.json`

This is distinct from the watchlist stub (`2027_watchlist_seed.json`) and from the real seed pool. It is the machine-generated discovery layer.

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
  discover_shadow_pool.py          ← new: Phase 1 CFBD query + eligibility filter
  promote_shadow_to_seed.py        ← new: Phase 2 combine gate + promotion
  compute_breakout_age.py          ← existing: breakout logic (imported, not forked)
  compute_production_scores.py     ← existing: unchanged, reads real seed pool
```

---

## Scripts to Build

### 1. `scripts/discover_shadow_pool.py`

| Attribute | Detail |
|---|---|
| Input | CFBD `/roster?year={season}&position={pos}` for each position in `DISCOVERY_POSITIONS` |
| Eligibility filter | academic year ≥ 3, OR academic year == 2 with breakout flag |
| Output | `data/raw/{class_year}_shadow_pool.json` |
| Merge behavior | Additive — existing entries updated in place (status preserved), new entries appended |
| Rate limiting | Reuse `cfbd_headers()` + exponential backoff from `compute_breakout_age.py` |
| Config | `DISCOVERY_POSITIONS = ["WR", "RB", "TE", "QB"]`, `DISCOVERY_CLASS_YEAR = 2027` |

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
| `compute_breakout_age.py` | Export `SHARE_BREAKOUT_CRITERIA` and `BREAKOUT_THRESHOLDS` so `discover_shadow_pool.py` can import them without duplication |
| `lib/rookies/rookieDataContract.js` | Add `SHADOW_POOL_SEASONS = [2027]` alongside `WATCHLIST_SEASONS` |

---

## What This Replaces

| Current approach | Replaced by |
|---|---|
| Hand-curated seed pool from big boards | `discover_shadow_pool.py` CFBD query |
| Manual combine cross-reference | `promote_shadow_to_seed.py` gate |
| `2027_watchlist_seed.json` (3-entry stub) | `2027_shadow_pool.json` (machine-generated, operator-reviewable) |
| Post-draft backfill of missed players | Shadow pool catches them before the draft |

The manual watchlist stub (`2027_watchlist_seed.json`) can be retired once the shadow pool is populated for 2027 — or its three entries can be migrated in as `manually_added: true` override entries.

---

## What This Does NOT Replace

- **Operator judgment** — the shadow pool is a candidate list, not a model input. Promotion to the real seed pool is still an operator-confirmed step
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
| Storage format | Separate shadow pool file per class year; status field tracks lifecycle |
| Manual override path | `watchlist_overrides.json` — operator can force-include any player |

---

## Implementation Order

Recommended sequence for Codex / Claude agent work:

1. **Export breakout constants** from `compute_breakout_age.py` (small, safe refactor — prerequisite for step 2)
2. **Build `discover_shadow_pool.py`** — CFBD query, eligibility filter, shadow pool write
3. **Populate `2027_shadow_pool.json`** — run discovery against 2026 college season roster data
4. **Build `promote_shadow_to_seed.py`** — combine gate + promotion logic
5. **Retire `2027_watchlist_seed.json`** — migrate its 3 entries into shadow pool as `manually_added: true`, update `rookieDataContract.js`
6. **Add runbook** to `docs/runbooks/` covering the annual cadence (when to run each script)

Steps 1–2 are unblocked. Steps 3–4 depend on step 2. Step 5 depends on step 3.

---

## Annual Cadence (future reference)

| Month | Action |
|---|---|
| September | Run `discover_shadow_pool.py` for the upcoming draft class |
| October–January | Shadow pool is read-only; production scores accumulate via CFBD |
| February (combine invites) | Run `promote_shadow_to_seed.py --dry-run`, review, `--confirm` |
| February–April (combine week / draft) | Populate combine measurements; update draft capital post-draft |
| Post-draft | Run full alpha pipeline on promoted real seed pool |
