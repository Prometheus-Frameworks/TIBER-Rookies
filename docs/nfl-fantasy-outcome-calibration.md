# NFL Fantasy Outcome Calibration Lane (Public Data)

## Purpose

This lane is a **research/calibration artifact** for historical NFL outcomes by draft/context cohorts (for example: WRs drafted top-10 since 2022). It is intentionally separate from Rookie Alpha scoring so the main model remains stable while we evaluate historical hit-rate context.

## Public data source

- Source family: **nflverse public releases**.
- Script endpoint defaults:
  - `player_stats.csv.gz` from nflverse release assets.
  - `draft_picks.csv.gz` from nflverse release assets.
- Cache location: `data/external/nflverse/`.

No proprietary analyst rankings, projections, screenshots, or scraped paid content are used in this lane. See `docs/legal/external-source-hygiene-policy.md`.

## Outputs

- Player-season outcomes:
  - `exports/promoted/nfl-fantasy-outcomes/player_year_ppr_outcomes_v1.json`
  - `exports/promoted/nfl-fantasy-outcomes/player_year_ppr_outcomes_v1.csv`
- Cohort summaries:
  - `exports/promoted/nfl-fantasy-outcomes/context_flag_outcome_summary_v1.json`
  - `exports/promoted/nfl-fantasy-outcomes/context_flag_outcome_summary_v1.csv`

## PPR formula

Initial focus is WR/RB/TE-style receiving/rushing PPR:

`PPR = receptions*1 + receiving_yards*0.1 + receiving_tds*6 + rushing_yards*0.1 + rushing_tds*6`

QB passing fantasy scoring is not included in the base formula in v1; QB cohorts are still included with the same rushing/receiving-only formula for now and should be interpreted cautiously.

## Career-year definition

`career_year = nfl_season - draft_year + 1`

Examples:
- Drafted in 2022, 2022 season row => career year 1.
- Drafted in 2022, 2024 season row => career year 3.

## Incomplete-year handling

The cohort summary script separates:
1. **Not enough seasons elapsed yet** (e.g., player drafted too recently for Year 3).
2. **Season elapsed but no player stat row** (DNP/no stats in source table).

It reports both in `incomplete_notes`, along with small-sample warnings.

## Why separate from Rookie Alpha

This lane is descriptive/historical calibration and **does not alter**:
- Rookie Alpha formulas
- Rookie Alpha weights
- Existing promoted Rookie Alpha artifacts

It is intended to later support post-draft translator tags such as:
- `top10_skill_capital`
- `round1_trade_up_conviction`
- `depth_chart_volume_cap`
- `shared_backfield_context`
- `market_conviction_override`

## Runbook

From repo root:

```bash
python scripts/build_nfl_fantasy_outcomes.py --refresh
python scripts/summarize_context_flag_outcomes.py
```

If network access is unavailable, pre-populate caches at:
- `data/external/nflverse/player_stats.csv`
- `data/external/nflverse/draft_picks.csv`

Then run without `--refresh`.
