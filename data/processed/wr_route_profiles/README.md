# WR route profile outputs

This directory holds per-player, per-season WR/TE receiving profiles. Despite the
historical name, **no file here contains observed route data** (routes run,
route participation, targets per route or aDOT).

## Mixed legacy family

The committed files come from three generation paths and the same numeric
`targets` field means different things across them (#303):

| Path | `source_name` pattern | `targets` evidence | Files at b9c2d87 |
| --- | --- | --- | --- |
| Manual research, catch-rate estimate | `Grok/Sports-Reference ...; targets estimated (REC / 0.70)` | **Estimated** as receptions / 0.70 | 51 |
| Synthetic career split | `ESTIMATED — derived from career ...` | **Estimated** (receptions are estimates too) | 2 |
| Older CFBD play-by-play parse | `CFBD play-by-play (year=..., team=...)` | **Parsed/partial**: name-matched in play text; may undercount (#146) | 12 |
| Invalidated | `... — INVALIDATED` | **Unavailable** (`null`) | 1 |

No committed file was produced by the current season-stat producer and none
carries a source-reported (CFBD `TGT`) count. A non-null `source_url` does not
mean targets were measured.

Where targets are estimated, `yards_per_target` is roughly
0.70 × yards per reception and adds no independent evidence of target earning
or catch efficiency.

`screen_targets: 0`, and `0.0` screen/depth rates, are **not observed
absences** in any committed file: none of these generation paths carried
route/scheme descriptors.

## Target-evidence qualification

Read qualification through `scripts/target_evidence.py` (`qualify_profile`),
never from `targets` alone. It returns a `target_evidence` block. New producer
output stores that block in each file. For legacy files it is inferred from
`source_name` / `methodology_notes` (`qualification_origin: legacy_inferred`).
Raw values are not rewritten. Contract and consumer impact:
`docs/reports/2026-10-24-wr-te-target-evidence-contract-and-impact.md`.

## Active producer

```bash
python scripts/fetch_wr_route_profiles.py
```

Do not run it with the default `--output-dir`. That overwrites the committed
legacy evidence above. Set `CFBD_API_KEY` for authenticated CFBD access.

The producer reads CFBD **season-level** receiving stats
(`/stats/player/season?category=receiving`), one request per season. For each
player-season it emits:

- `targets`: CFBD `TGT` when returned (`target_evidence.targets.status = source_reported`);
  otherwise `round(receptions / 0.70)` (`estimated`, `assumed_catch_rate: 0.70`).
- `yards_per_target`: receiving yards / `targets`. It is estimate-derived when
  targets are estimated (`yards_per_target.observed_denominator: false`).
- `screen_targets: 0` and null screen/depth rates for schema compatibility.
  `scheme_fields.status` is always `unsupported`.
- Player not matched, or CFBD returned neither `TGT` nor `REC`:
  `targets`/`receptions` are `0` placeholders, but `target_evidence.targets.status`
  is `unavailable`. That is not an observed zero.
- `receptions.status` is `source_reported` only when CFBD returned `REC`.
- A stored `target_evidence` block that fails `validate_target_evidence` is
  read as `unknown`/`unavailable`, never as observed evidence.

The estimation policy itself is unchanged by #303. Whether to move estimates
out of `targets` is deferred to a reviewed migration.

## Output schema

Each file is named `{player_id}_{season}.json` and includes:

- `player_id`, `player_name`, `team`, `season`, `season_type`
- `targets`, `receptions`, `screen_targets`
- `screen_target_rate`, `yards_per_target`, `deep_target_rate`, `depth_tag_coverage_rate`
- `team_pass_plays`, `team_screen_plays`, `team_screen_rate`, `team_yards_per_pass`
- `source_name`, `source_url`, `methodology_notes`
- `target_evidence` (producer output only; legacy files are qualified by the reader)

## Limitations

- `yards_per_target` is YAC-inclusive and is **not** aDOT.
- Downstream consumers (`compute_breakout_age.py`, `compute_age_adjusted_production.py`)
  still read `targets` numerically and treat null/missing as 0. See the impact report.
- These limits describe the generation paths used here. They do not claim
  CFBD as a provider can never supply target or depth evidence (see #293).
