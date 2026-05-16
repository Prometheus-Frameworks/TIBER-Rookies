# Cross-Repo Draft Results Ingestion

**Relates to:** Issue #211  
**Status:** Ingestion adapter implemented; upstream artifact pending TIBER-Data promotion  
**Last updated:** 2026-05-16

---

## Boundary

```
TIBER-Data
  Official NFL Draft result facts + provenance tracking
    ↓  (exports/promoted/nfl_draft_results/nfl_draft_results_{year}.json)
TIBER-Rookies
  Draft capital proxy scoring, rookie alpha, post-draft adjustment logic
    ↓  (data/processed/{year}_draft_results.json)
FORGE (future)
  Prospect-quality context for fantasy player evaluation
  — consumes promoted TIBER-Rookies interpretation, not raw draft facts
```

Each layer owns its interpretation. TIBER-Rookies never passes raw draft facts to FORGE, and TIBER-Data never runs scoring logic.

---

## Upstream contract (TIBER-Data)

**Contract version:** `tiber-data.nfl-draft-results.v1.0.0`  
**Source file:** `src/contracts/v1/nflDraftResults.ts`  
**Artifact path:** `exports/promoted/nfl_draft_results/nfl_draft_results_{year}.json`

Key fields per row:

| Field | Type | Notes |
|---|---|---|
| `draft_year` | integer | Draft class year |
| `player_id` | string \| null | TIBER player ID; null when unresolved |
| `player_name` | string | |
| `position` | string | |
| `team` | string | NFL team abbreviation |
| `round` | integer | Draft round (1–7) |
| `pick_in_round` | integer | |
| `overall_pick` | integer | |
| `source` | string | Source name |
| `source_url` | string \| null | |
| `generated_at` | ISO datetime | |
| `provenance_status` | enum | See below |

**Provenance statuses:**

| Status | Meaning | Ingestion behaviour |
|---|---|---|
| `source_verified` | Source-backed, player ID confirmed | Accepted |
| `source_verified_player_id_unresolved` | Source-backed, player ID not yet matched | Skipped (can't match to model) |
| `needs_verification` | Source exists, needs human review | Accepted with warning flag |
| `fixture_only` | Test data, not real results | Rejected unconditionally |

---

## TIBER-Rookies model-facing schema

**File:** `data/processed/{year}_draft_results.json`  
**Used by:** `lib/rookies/draftResults.js` → `mapRookieToCard.js` → post-draft adjustment logic

Key fields:

| Field | Source | Notes |
|---|---|---|
| `player_id` | upstream `player_id` (lowercased) | Must match alpha export player IDs |
| `nfl_team` | upstream `team` | |
| `draft_round` | upstream `round` | |
| `overall_pick` | upstream `overall_pick` | |
| `draft_day` | derived from `round` | 1=R1, 2=R2-R3, 3=R4-R7 |
| `is_udfa` | always `false` | UDFAs are not in the draft results artifact |
| `draft_result_status` | always `"drafted"` | |
| `source_status` | mapped from `provenance_status` | |
| `upstream_provenance_status` | preserved from upstream | Audit trail |
| `ingested_from` | `"tiber_data_nfl_draft_results_v1"` | Traceability |

**Note on UDFAs:** Players who go undrafted are not present in the NFL Draft Results artifact (they were not drafted). UDFA tracking (`is_udfa: true` entries) remains a separate manual input path in TIBER-Rookies and is not produced by this ingestion script.

---

## Running the ingestion

Once TIBER-Data has promoted the canonical artifact:

```bash
# Dry run — validate and preview without writing
python scripts/ingest_draft_results_from_tiber_data.py \
  --upstream path/to/nfl_draft_results_2026.json \
  --year 2026 \
  --dry-run

# Live run
python scripts/ingest_draft_results_from_tiber_data.py \
  --upstream path/to/nfl_draft_results_2026.json \
  --year 2026
  # writes to data/processed/2026_draft_results.json
```

The script exits non-zero without writing output if:
- The upstream file does not exist
- The upstream file is not a valid JSON array
- The upstream file is an empty array
- Zero rows survive validation (all fixture-only or all null-IDs)

---

## Fail-closed guarantees

The ingestion is designed so that a bad or missing upstream artifact cannot create false post-draft grades:

1. Missing artifact → script errors loudly, file is not touched
2. All-fixture artifact → zero rows accepted, file is not written
3. Empty artifact → exits non-zero before mapping
4. `fixture_only` rows → unconditionally rejected, never reach the model
5. `player_id=null` rows → skipped, cannot create phantom grade adjustments

In all failure cases the existing `data/processed/{year}_draft_results.json` is preserved unchanged.

---

## When upstream artifact is not yet available

TIBER-Data issue #112 / PR #113 established the v1 contract. The `exports/promoted/nfl_draft_results/` directory does not yet contain promoted artifacts. Until it does:

- The 2026 class uses the manually curated `data/processed/2026_draft_results.json` (40 entries, externally verified against The Football Database)
- Historical classes (2022–2025) have empty stub files — post-draft grades show as pending for those classes on the board
- This is correct and expected behaviour per the fail-closed design

Once TIBER-Data promotes the artifact, run the ingestion script and commit the updated processed file.

---

## Future: FORGE handoff

FORGE should eventually consume promoted TIBER-Rookies prospect interpretation, not raw draft facts. The intended path is:

```
TIBER-Rookies exports/promoted/rookie-alpha/{year}_rookie_alpha_postdraft_*.json
  → FORGE prospect-quality context signals
```

This is out of scope for issue #211 and will be addressed in a future cross-repo contract PR.
