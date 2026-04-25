# 2026 Post-Draft Alpha Role-and-Opportunity Join (v0)

## Purpose

This document defines an **inspect-only** join layer that enriches rookie post-draft/team-context rows with Role-and-Opportunity artifacts.

## Ownership boundaries

- **Role-and-Opportunity-model owns role profile and baseline artifacts.**
- **TIBER-Rookies owns Rookie Alpha and inspection outputs.**
- This join does **not** mutate upstream model artifacts.

## v0 doctrine

- Inspect-only join for analyst review.
- `pre_draft_alpha`, `post_draft_alpha`, and `post_draft_delta` remain unchanged.
- Rookie Alpha scoring is unchanged.
- Upstream Role-and-Opportunity inputs are read-only.

## Inputs

- `exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_team_context_v0.json`
- `../Role-and-opportunity-model/data/processed/2026_team_role_opportunity_profiles.json`
- `../Role-and-opportunity-model/data/processed/2026_role_to_fantasy_baselines.json`

## Outputs

- `exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_role_context_v0.json`
- `exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_role_context_v0.csv`

## Added row fields

- `role_opportunity_found`
- `candidate_roles`
- `matched_role_profiles`
- `matched_role_baselines`
- `role_context_tags`
- `role_risk_tags`
- `role_context_notes`
- `role_context_source_status`
- `combined_context_tags_with_role`
- `combined_risk_tags_with_role`

## Matching behavior (heuristic v0)

- Candidate roles are inferred from position + existing translator/context/risk tags.
- Team names are normalized to NFL team codes prior to profile lookup.
- If no team profile exists: `role_opportunity_found=false`, role match arrays are empty, and notes describe missing team profile.
- If team exists but no heuristic role match: `role_opportunity_found=false` and notes indicate no role match.
- If candidates exist and team profile contains those roles: matching profile rows and role baselines are attached.

## Future versions

Future versions may use richer signal fusion or scorer-level policy updates, but **v0 remains inspect-only and non-scoring**.
