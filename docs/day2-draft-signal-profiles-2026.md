# 2026 Day 2 Draft Signal Profiles

## Purpose

This artifact captures a lightweight, human-readable **post-draft translator layer** for 2026 rookie skill players and quarterbacks selected in **Rounds 2-3**.

It complements the Round 1 signal profiles and is intentionally separated from Rookie Alpha score generation.

- It records Day 2 interpretation in a structured, auditable format.
- It does **not** alter Rookie Alpha scoring inputs or outputs.
- It allows early post-draft handling to be preserved while canonical draft artifacts are reconciled.

## Day 2 vs Round 1 Capital

Round 1 and Day 2 capital should not be treated as equivalent signals.

- **Round 1 capital** often conveys stronger organizational insulation, longer runway patience, and higher tolerance for early developmental variance.
- **Day 2 capital** still matters meaningfully, but usually carries weaker insulation and a wider range of role outcomes.

For translator logic, Day 2 should be interpreted as material opportunity and intent signal, but below Round 1 certainty.

## Why Day 2 Profiles Are Translator Notes (Not Scoring Changes)

These profiles are intentionally a translator artifact.

- Pre-draft model stance remains unchanged.
- Rookie Alpha scoring remains unchanged.
- Promoted alpha artifacts are not regenerated.

The goal is clarity and traceability: document how draft capital should adjust interpretation **without rewriting model math**.

## Outcome Calibration Connection

Day 2 profile tags and signal labels are designed for later calibration loops.

Future analysis can compare declared Day 2 expectations (talent confirmation, opportunity insulation, and runway) against realized outcomes to tune translator priors over time.

This keeps post-draft interpretation explicit while preserving pre-draft model integrity.

## Opportunity Insulation Doctrine for Day 2

Day 2 picks can indicate meaningful role path and organizational interest, but they should generally receive less opportunity insulation than comparable Round 1 selections.

Practically:

- treat Day 2 as a positive role-opportunity signal,
- avoid assigning automatic long-horizon insulation,
- require follow-up context (depth chart, coaching usage, QB room stability) to escalate confidence.

## Source Status

All current entries in `data/processed/2026_day2_draft_signal_profiles.json` are marked `operator_seeded` until canonical `draft_results` reconciliation is complete.
