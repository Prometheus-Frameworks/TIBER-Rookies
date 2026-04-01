# WR route profile outputs

This directory contains per-player route profile proxy files generated from CFBD play-by-play.

## Regeneration

```bash
python scripts/fetch_wr_route_profiles.py
```

Set `CFBD_API_KEY` in your environment for authenticated historical CFBD access.

## Output schema

Each file is named `{player_id}_{season}.json` and includes:

- `player_id`, `player_name`, `team`, `season`, `season_type`
- `targets`, `receptions`, `screen_targets`
- `screen_target_rate` (`screen_targets / targets`, null if no targets)
- `yards_per_target` (YAC-inclusive yards proxy, null if no targets)
- `deep_target_rate` (deep-tagged targets / depth-tagged targets)
- `depth_tag_coverage_rate` (depth-tagged targets / total targets)
- `team_pass_plays`, `team_screen_plays`, `team_screen_rate`, `team_yards_per_pass`
- `source_name`, `source_url`, `methodology_notes`

## Limitations

- `yards_per_target` is YAC-inclusive and is **not** true aDOT.
- Depth tags depend on CFBD play text (`short*`/`deep*`) and coverage varies by team/season.
- Target attribution relies on normalized player-name matching in play text and may miss targets when naming differs.
