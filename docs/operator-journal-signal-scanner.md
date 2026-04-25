# Operator Journal Signal Scanner (v0)

## Purpose

The operator journal signal scanner is a **human-in-the-loop extraction layer** for football notes captured in the local Notes workflow.

This v0 pipeline:
- stores operator journal entries as raw source-of-truth notes,
- converts notes into deterministic candidate context tags,
- keeps all outputs inspectable,
- and **does not** directly change Rookie Alpha or post-draft alpha scoring.

## Doctrine

- Operator journal entries are human observation inputs.
- Source type is always `operator_journal`.
- Candidate outputs are suggestions, not scoring truth.
- Default candidate `review_status` is `needs_human_review`.
- Candidate tags require review before promotion into Rookie Alpha, Teamstate, Role-Opportunity, or TIBER-Data.

## Files

- Raw entries: `data/operator-journal/raw/2026_rookie_journal_entries.json`
- Processed candidates: `data/operator-journal/processed/2026_operator_signal_candidates.json`
- Builder script: `scripts/build_operator_signal_candidates.py`

## Build command

```bash
python scripts/build_operator_signal_candidates.py
```

## What v0 emits

Each candidate includes:
- entity links (`player`, `team`, `team_meta`, `market_watchlist`, or `cohort` style context),
- claim summary,
- positive signal tags,
- risk tags,
- context tags,
- confidence,
- review status,
- and optional downstream repository targets.

## Review and promotion model

Candidate tags are created for analyst review before any downstream use:
- `TIBER-Teamstate`
- `Role-and-Opportunity`
- `TIBER-Rookies`
- `TIBER-Data`

Model-edge notes can be positive or negative and are always treated as candidate-tag context, not score changes.
- Positive model edge plus NFL/landing-spot confirmation is a validation-watch candidate.
- Negative model edge plus better landing spot is tracked as a "landing spot over profile" candidate.
- Missing-data observations become audit candidates and profile-completeness review tasks, not retroactive score edits.

Only reviewed/promoted items should be consumed by Teamstate, Role-Opportunity, post-draft alpha, or any TIBER-Data downstream workflows. The scanner's goal is to turn hobby notes into a repeatable information layer without bypassing model governance.

## Durability guardrails

- Candidate IDs are derived from the source entry (`cand_${source_entry_id}_...`) to keep IDs stable and unique across repeated themes.
- Unmapped entries fail loudly by default so new operator notes cannot silently disappear.
- Optional override: `--allow-unmapped` skips unmapped entries when you explicitly want a partial build.
