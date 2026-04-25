# 2026 Post-Draft Alpha Team Context Join (v0)

## Purpose

This document defines how TIBER-Rookies enriches post-draft alpha outputs with team landing context from TIBER-Teamstate.

## Ownership boundaries

- **TIBER-Teamstate owns team/environment context** tags (offensive environment, depth-chart dynamics, volatility, team-level risk framing).
- **TIBER-Rookies owns prospect and post-draft alpha** (prospect grading, draft translation, and post-draft alpha values).

## v0 behavior

- The join is **inspect-only** enrichment.
- No scoring logic is changed.
- `pre_draft_alpha`, `post_draft_alpha`, and `post_draft_delta` are preserved exactly.
- Team context is joined by normalized team code.

## Artifacts

- Input post-draft alpha:
  - `exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_v0.json`
- Input Teamstate context (configurable path):
  - `../TIBER-Teamstate/data/processed/2026_team_landing_context_tags.json`
- Output enriched artifacts:
  - `exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_team_context_v0.json`
  - `exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_team_context_v0.csv`

## Join notes

- Team names in post-draft rows are normalized to team codes before lookup (for example `49ers -> SF`, `Browns -> CLE`).
- Already-normalized codes are passed through.
- If team is `TBD` or no context exists, `team_context_found=false` and context arrays remain empty.
- Enrichment also emits:
  - `combined_context_tags`: ordered union of `translator_tags` + `team_context_tags`
  - `combined_risk_tags`: ordered union of `remaining_risks` + `risk_team_context_tags`

## Future versions

Future versions may optionally incorporate Teamstate context into scoring policy, but **v0 is explicitly join-only and non-scoring**.
