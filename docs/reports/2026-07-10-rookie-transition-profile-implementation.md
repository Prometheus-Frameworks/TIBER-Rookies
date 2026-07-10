# Rookie Transition Profile v0 — Implementation Report

**Date:** 2026-07-10
**Issue:** [#263](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/263)
**Implements the design from:** [#261](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/261) /
`docs/rookie-transition-profile-v0-design.md`

## What was implemented

- `scripts/validate_rookie_transition_profile.py` — schema constants (`source_type` enum,
  observed/inferred frozensets, `confidence_band` mapping), row/field/provenance shape validation,
  and manifest/hash cross-validation (mirroring `scripts/devy_signal_registry.py`'s enum-validation
  style and `scripts/validate_promoted_export.py`'s hash-validation style).
- `scripts/compute_rookie_transition_profile.py` — the producer. Reads the already-promoted
  Rookie Alpha predraft export plus three processed source files
  (`{season}_draft_capital_proxy.json`, `{season}_college_production.json`,
  `{season}_prospect_context.json`) and repackages them under the new contract. Computes no new
  score — `age_at_entry` is the one derived value, and it's an exact copy of the
  `age_from_dob` formula already in `scripts/compute_breakout_age.py`.
- `exports/promoted/rookie-transition-profile/2026_rookie_transition_profile_v0.{json,csv}` +
  `2026_manifest.json` — the real, promoted 2026 artifact (48 players).
- `docs/rookie-transition-profile-contract.md` — the implemented contract, including three
  implementation decisions not pinned by the design doc (see below).
- `tests/test_validate_rookie_transition_profile.py` (23 tests) and
  `tests/test_compute_rookie_transition_profile.py` (16 tests) — regression coverage, including
  two tests that validate the actual committed 2026 artifact end-to-end.

Full `pytest` suite: **419 passed** (380 pre-existing + 39 new).

## Coverage of the real 2026 artifact

```text
players_total: 48
players_with_draft_capital: 48
players_with_age_at_entry: 47   (1 player has no dob on file — correctly unavailable, not fabricated)
players_with_athletic_testing: 32  (16 players are NEUTRAL_DEFAULT — correctly unavailable, not the 50.0 placeholder)
players_with_college_production: 48
players_with_all_families: 32
```

## Implementation decisions beyond the design doc

The design doc's example JSON used illustrative confidence numbers that don't all resolve through
one consistent `confidence_to_band()` threshold function (e.g. it showed confidence `0.5` mapping
to `MEDIUM` and `0.8` mapping to `HIGH`, which isn't a single clean rule). Rather than force the
validator to special-case bands per field family — which would break the artifact's own
uniform-provenance invariant — three choices were made explicitly during implementation and are
documented in `docs/rookie-transition-profile-contract.md`:

1. `confidence_to_band`: `<0.65 → LOW`, `0.65–0.84 → MEDIUM`, `>=0.85 → HIGH` (one rule, applied
   everywhere, including to Rookie Alpha's existing variable `athletic_confidence` values).
2. `draft_capital` confidence fixed at `0.65` (→ `MEDIUM`) — a real but proxy-quality signal.
3. `college_production` confidence fixed at `0.85` (→ `HIGH`) — real, deterministic CFBD season
   stats, not a proxy.

These are reasoned, self-consistent choices, not literal implementations of the design doc's
illustrative numbers (which were never asserted as binding). The design's *qualitative* decisions
— the `{value, provenance}` pairing, `source_type`-driven observed/inferred classification, no
row-level composite score — are all implemented exactly as designed.

One additional decision not explicit in the design doc: Rookie Alpha's `NEUTRAL_DEFAULT` athletic
rows (a fixed `50.0` internal scoring placeholder for players with no usable RAS/SPORQ data) are
classified `unavailable` here, not copied as if they were a measurement. Presenting that
placeholder as observed athletic evidence would have reintroduced exactly the kind of
misrepresentation issue #257 was about.

## Hard-boundary compliance checklist

- [x] No changes to TIBER-Forecast (not in scope for this session; nothing outside TIBER-Rookies touched).
- [x] No Forecast mirror created.
- [x] No predictive value evaluated or claimed — the artifact's fixed `disclaimer` field states this explicitly.
- [x] No new rankings or scores beyond the approved design — every governed value is either copied
      verbatim from an already-promoted/processed source or a deterministic, pre-existing formula
      (`age_from_dob`).
- [x] No role projection, landing-spot modeling, or production binding — these field families were
      excluded per the #261 design and remain excluded here.

## Validation performed

```bash
python3 scripts/validate_rookie_transition_profile.py \
  --export-json exports/promoted/rookie-transition-profile/2026_rookie_transition_profile_v0.json \
  --manifest exports/promoted/rookie-transition-profile/2026_manifest.json
# ROOKIE TRANSITION PROFILE VALIDATION PASSED
```

## Decision

```text
may_open_rookie_transition_profile_promotion_review_issue
```

This authorizes only a future promotion-review issue for `rookie_transition_profile_v0`. It does
not authorize Forecast consumption, predictive use, or cross-repo promotion.
