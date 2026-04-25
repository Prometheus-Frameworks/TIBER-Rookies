# 2026 Post-Draft Rookie Alpha Adjustments (v0)

## Purpose

This artifact adds a transparent **post-draft translator layer** on top of frozen pre-draft Rookie Alpha.

- Pre-draft model outputs are preserved and not overwritten.
- Post-draft grades are deterministic profile-driven adjustments.
- Every non-zero adjustment is explainable via `delta_reason_codes`.

## Input artifacts

- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json`
- `data/processed/2026_round1_draft_signal_profiles.json`
- `data/processed/2026_day2_draft_signal_profiles.json`

## Output artifacts

- `exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_v0.json`
- `exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_v0.csv`
- `exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_missing_baselines_v0.json`

## Doctrine and guardrails

- **Pre-draft alpha is frozen** (`pre_draft_alpha` copies pre-draft score).
- **Post-draft alpha is translator-adjusted** (`post_draft_alpha = pre_draft_alpha + post_draft_delta`, bounded to 0-100).
- **Draft capital is split into two components**:
  - `talent_confirmation:*` reason codes
  - `opportunity_insulation:*` reason codes
- **Risk modifiers** reduce/limit early bumps when uncertainty remains.
- **No proprietary analyst content** is introduced.

## Deterministic v0 adjustment framework

Bands are encoded in `scripts/build_post_draft_alpha.py` and selected deterministically using profile signal strengths and translator tags.

### Round 1 bands

- `top5_skill_capital`: +6 to +8
- `top10_skill_capital`: +4 to +6
- `round1_wr_capital`: +3 to +5
- `late_round1_wr_capital`: +2 to +3
- `round1_market_confirmation`: +2 to +3
- `model_wr1_validation`: +2 to +3
- `fifth_year_option_signal`: +0.8 to +1.5
- `round1_rb_capital`: +5 to +7
- `round1_te_capital`: +3 to +5
- `round1_qb_capital`: +3 to +5
- `trade_up_conviction`: +1 to +2
- `elite_developmental_environment`: +1 to +3 (opportunity-insulation confirmation)
- `delayed_start_insulation`: +0.8 to +1.5 (long-term insulation signal)
- `class_inflation_adjustment_candidate`: talent-confirmation reduction only

### Day 2 bands

- `near_round1_skill_capital`: +7 to +10 (requires pre-draft stance context)
- `early_day2_capital`: +4 to +6
- `round2_skill_capital`: +3 to +5
- `round3_skill_capital`: +1 to +3
- `round3_qb_capital`: +1 to +2 (paired with developmental limits)
- `day2_te_cluster`: +1 to +2 (with delayed TE runway guardrail)
- `scarce_day2_rb_capital`: +2 to +4

### Risk modifiers and caps

- `target_room_competition_watch`: -1 to -3 equivalent scaling
- `year1_volume_uncertainty`: -1 to -2 equivalent conservative reduction
- `delayed_te_translation_watch`: short-term TE bump constraint
- `developmental_qb_capital`: QB upside cap pressure
- `landing_spot_volatility`: mild validation discount and cap pressure
- `delayed_start_insulation`: delayed runway penalty and cap guardrail
- Opportunity insulation caps:
  - `opportunity_insulation_limited`
  - `opportunity_insulation_moderate`
  - `opportunity_insulation_strong` / `elite`

## Missing baseline reconciliation

- Profiles without a pre-draft baseline still pass through as `pre_draft_alpha = 0.0`, `post_draft_alpha = 0.0`, with `baseline:predraft_missing_pass_through` in `delta_reason_codes`.
- Those same rows are now surfaced in `2026_rookie_alpha_postdraft_missing_baselines_v0.json` with `reason = predraft_baseline_not_found` for reconciliation workflows.

## Coverage behavior in v0

Only players with a Round 1 or Day 2 signal profile are emitted in `postdraft_v0`.
Players without those profiles are omitted from the post-draft artifact and remain represented in pre-draft outputs only.

## Build command

```bash
python scripts/build_post_draft_alpha.py
```
