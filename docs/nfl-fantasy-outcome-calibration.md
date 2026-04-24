# NFL Fantasy Outcome Calibration Lane (Public Data)

## Purpose

This lane is a **research/calibration artifact** for historical NFL outcomes by draft/context cohorts (for example: WRs drafted top-10 since 2022). It is intentionally separate from Rookie Alpha scoring so the main model remains stable while we evaluate historical hit-rate context.

## Public data source

- Source family: **nflverse public releases**.
- Script endpoint defaults:
  - `stats_player` release assets (preferred), selecting regular-season player summary CSV when available.
  - `player_stats.csv.gz` (legacy fallback) from nflverse release assets.
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
- Source freshness sidecar:
  - `exports/promoted/nfl-fantasy-outcomes/source_metadata_v1.json`

## PPR formula

Initial focus is WR/RB/TE-style receiving/rushing PPR:

`PPR = receptions*1 + receiving_yards*0.1 + receiving_tds*6 + rushing_yards*0.1 + rushing_tds*6`

QB passing fantasy scoring is not included in the base formula in v1; QB cohort outputs are therefore **rushing/receiving-only** in v1 and should be interpreted cautiously.

## Source mode visibility

Each output row carries a `source_notes` marker with one of:
- `source_mode=seasonal_source` (source rows already seasonal)
- `source_mode=weekly_aggregated` (multiple weekly/game rows were aggregated to one player-season row)

When `weekly_aggregated` is used, receiving/rushing stats are summed across rows and `games` is computed from distinct participated game/week markers.

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

## Source freshness checks

The build script now reports source freshness diagnostics every run:
- `player_stats` row count
- `draft_picks` row count
- `latest_stats_season` (max season present in player stats rows)
- `latest_draft_year` (max season/draft year present in draft rows)
- `stats_source` and `stats_url` used for the run
- detected source mode (`seasonal_source` or `weekly_aggregated`)

`source_metadata_v1.json` records `latest_stats_season`, `latest_draft_year`, and staleness flags so downstream cohort summaries can explicitly report current coverage.

You can optionally set an expected season floor:

```bash
python scripts/build_nfl_fantasy_outcomes.py --refresh --expected-latest-season 2025
```

If source rows lag that expectation, the script prints a loud warning.

To fail fast before writing promoted outputs when stale:

```bash
python scripts/build_nfl_fantasy_outcomes.py --refresh --expected-latest-season 2025 --fail-on-stale-source
```

The sidecar metadata file includes staleness fields (`expected_latest_season`, `is_stale_relative_to_expected`) so downstream summarization can log current coverage context. Cohort interpretations are only as current as `latest_stats_season`.

### Stats source options

Use `--stats-source` to select source family:

- `--stats-source stats_player` (default): prefers `stats_player` regular-season summary release assets and is preferred for 2025+ coverage.
- `--stats-source legacy_player_stats`: uses legacy `player_stats` release (`player_stats.csv.gz`), which may only be current through the 2024 season.

Optional override for custom/testing URLs:

```bash
python scripts/build_nfl_fantasy_outcomes.py --stats-source-url https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_reg.csv.gz
```

If `stats_player` lookup/load fails, the script falls back to `legacy_player_stats` unless you explicitly pin `--stats-source-url`.

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

Optional cohort-inclusion validation for known 2025 top-10 skill picks:

```bash
python scripts/summarize_context_flag_outcomes.py --validate-known-2025-skill-picks
```

Current expected validation set:
- Travis Hunter (WR, 2025, pick 2)
- Tetairoa McMillan (WR, 2025, pick 8)
- Colston Loveland (TE, 2025, pick 10)

If expected players are missing, the summarizer prints warnings with likely reasons:
- missing 2025 draft data
- missing 2025 player stats
- position mismatch
- ID join mismatch

If network access is unavailable, pre-populate caches at:
- `data/external/nflverse/player_stats.csv`
- `data/external/nflverse/stats_player_reg.csv`
- `data/external/nflverse/draft_picks.csv`

Then run without `--refresh`.
