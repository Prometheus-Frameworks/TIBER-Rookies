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
  - `../TIBER-Teamstate/data/processed/2026_teamstate_context_v0.json`
- Output enriched artifacts:
  - `exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_team_context_v0.json`
  - `exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_team_context_v0.csv`

## Join notes

- Team names in post-draft rows are normalized to team codes before lookup (for example `49ers -> SF`, `Browns -> CLE`).
- Already-normalized codes are passed through.
- If team is `TBD`/unknown or no Teamstate profile exists, `team_context_found=false` and context arrays remain empty.
- Enrichment also emits:
  - `team_context_team_code`: normalized team code used for lookup (`TBD`/blank when unknown)
  - `team_context_source_status`: `operator_seeded` when joined, `operator_seeded_unknown` when not joined
  - `combined_context_tags`: ordered union of `translator_tags` + `team_context_tags`
  - `combined_risk_tags`: ordered union of `remaining_risks` + `risk_team_context_tags`

## Workbench expectation

When this artifact is generated with known drafted teams, Workbench should display `team_context_found=true` for those players. This remains inspect-only and does not change alpha scoring.

## Future versions

Future versions may optionally incorporate Teamstate context into scoring policy, but **v0 is explicitly join-only and non-scoring**.
