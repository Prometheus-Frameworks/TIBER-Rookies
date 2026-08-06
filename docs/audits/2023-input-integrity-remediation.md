# 2023 input-integrity remediation audit

Issue: [TIBER-Rookies #285](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/285)  
Base: `524bc549940926792aff24e4fb109d5e30122697`  
Posture: candidate-only; operator review required

## Result

All five reported defects are confirmed. The contaminated source rows remain
byte-for-byte unchanged and are copied into a non-authoritative archive
fixture. Corrections are isolated under
`data/candidate/2023_input_integrity/v0.1.0/`; nothing in
`exports/promoted/**` was regenerated.

The appropriate handoff decision is:

```text
historical_2023_promoted_artifact_deprecation_requires_operator_decision
```

That is a recommendation for review, not a deprecation or promotion action.

## Defect-by-defect source audit

### 1. Puka Nacua combine/pro-day conflation — confirmed

The legacy combine row claims official testing at 4.57 / 36.5 / 122 with a
72-inch, 205-pound measurement. The [nflverse combine release](https://github.com/nflverse/nflverse-data/releases/download/combine/combine.csv)
instead records Puka at 6-2, 201 with every athletic test blank; the repo's
SPORQ row also records all tests null and `dnq: true`.
[Contemporaneous reporting](https://gephardtdaily.com/sports/10-players-with-utah-ties-among-pro-prospects-invited-to-2023-nfl-scouting-combine/)
states that he attended but did not compete in any scored drills. The
candidate therefore uses `attended_no_scored_testing`, not a broader claim
that he performed no combine activity.

Puka did test at BYU's March 24 pro day, but the published 2023 line is
different: KSL reported a 4.55 forty, 33-inch vertical, 10-foot-1/121-inch
broad jump, 7.30 three-cone, 4.36 shuttle, and 15 bench reps. BYU confirms the
event and Puka's participation. Sources:
[KSL results](https://sports.ksl.com/ncaa/byu/byu-pro-day-2023-jaren-hall-puka-nacua-results-nfl-draft/499843),
[BYU event report](https://byucougars.com/news/2023/03/24/hayes-brooks-highlight-byus-2023-nfl-pro-day).

The seed's 4.57 forty and 36.5 vertical also match an
[ESPN Class-of-2019 recruiting-combine profile](https://www.espn.com/college-sports/football/recruiting/player/combine/_/id/227660/puka-nacua/1000).
That is a strong cross-year-conflation clue, not proven lineage: the seed has
no URL, and its 122-inch broad jump is not part of the ESPN result.

Conclusion: the legacy tuple is not one coherent 2023 event record. The
combine candidate keeps all Puka tests null. A separate, explicitly
unofficial-timing pro-day candidate carries the sourced KSL line; no pro-day
number is relabeled as combine testing.

### 2. Zay Flowers vertical/broad conflict — confirmed

The seed says 41.0-inch vertical / 129-inch broad and lists his height as 68
inches. Both the nflverse combine release and
`data/historical/sporq_historical.json` give 35.5 / 127 and 69 inches at 182
pounds. A [Baltimore Ravens combine recap](https://www.baltimoreravens.com/news/jaxon-smith-njigba-zay-flowers-jalin-hyatt-wide-receiver-prospects-combine)
published before the draft corroborates 35.5 and 10-foot-7/127. The candidate
uses the agreeing result and retains the 4.42 forty.

### 3. Puka 2022 production ambiguity — confirmed and unreconciled

The college-production seed presents `1594 yds / 10 TDs` as a 2022 line. The
same unsupported aggregate appears in Puka's prospect-context summary alongside
post-cutoff draft capital and NFL rookie production. The verified 2022
receiving line is 48 receptions, 625 yards, and five touchdowns. He also had
25 carries for 209 yards and five rushing touchdowns in nine games.
[BYU's January 2023 season review](https://byucougars.com/news/2023/01/12/byu-football-2022-season-review)
labels the year as 834 all-purpose yards and 10 total touchdowns;
[cfbstats](https://cfbstats.com/2022/player/77/1106480/index.html) provides the
same component receiving/rushing lines.

Ten is therefore explainable only after combining receiving and rushing
touchdowns. `1594` matches none of the checked 2022 receiving, scrimmage,
all-purpose, BYU-career receiving, or full college-career receiving scopes.
It is not silently relabeled. The candidate stores granular 2022 facts with
`stat_scope: single_season_receiving` and leaves
`production_score_0_100: null` / `needs_verification`; re-scoring is outside
this issue. The context candidate replaces the entire contaminated summary
with the same cutoff-safe, explicitly scoped components; it does not preserve
the draft or rookie hindsight.

### 4. Zay Flowers early-declare flag — confirmed under explicit semantics

Boston College called Flowers a senior during and after the 2022 season:
[AP All-America release](https://bceagles.com/news/2022/12/12/football-flowers-picks-up-ap-all-america-honor),
[Golden Helmet release](https://bceagles.com/news/2022/11/28/football-flowers-tabbed-season-golden-helmet-winner).
He played 2019, 2020, 2021, and 2022.

Candidate semantics define an early declare as entry before the player's
senior/fourth played season. COVID-era remaining eligibility does not turn a
completed senior season into an early declare. The candidate sets the flag
false and explicitly removes the stale `early_declare` evidence tag. It also
uses a cutoff-safe summary rather than copying the legacy row's post-draft
Pro Bowl hindsight.

### 5. REG/POST mixing — confirmed

The legacy weekly nflverse path aggregated rows without applying its
`season_type` field. That reproduces exact regular-plus-postseason totals:

| Player | Promoted mixed row | Regular-season source |
|---|---|---|
| Puka Nacua | 18 G, 114-1,667-7 | 17 G, 105-1,486-6 |
| Zay Flowers | 18 G, 86-1,014-6 | 16 G, 77-858-5 |

The promoted JSON contains 35 NFL-season-2023 rows with more than 17 games;
six are 2023-drafted skill players (Gibbs, Nacua, Rice, LaPorta, Palmer,
Flowers). This is a minimum visible count, not a claim that only those rows
are affected: postseason mixing can also contaminate a player who missed
regular-season games without pushing `games` above 17.

Replaying the current
[nflverse legacy release](https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats.csv.gz)
(retrieved 2026-08-04; SHA-256
`01a8db3ce4f576c51fc46ee329d789b3141d83e81a02323ef49f9744c1e1012e`)
finds 31 of 132 draft-class-2023 player-seasons in 2023-2024 (23.5%) with
positive postseason receiving/rushing fields.
For all 31, the emitted games and five builder-consumed receiving/rushing
fields exactly match the old algorithm's current-release REG+POST aggregation,
and none match REG-only. This is a reproducible current-release blast radius,
not cryptographic proof of the historical input release: the promoted artifact
cites a mutable local download path but records no source asset hash or release
timestamp. Historical source-version lineage therefore remains
`needs_verification`.

Separate from REG/POST mixing, weekly-mode `games` counts stat-participation
weeks, not an authoritative games-played field. The season filter fixes playoff
inflation but does not prove complete appearance counts for zero-touch games;
that semantic gap remains explicit and outside this candidate correction.

The builder now filters weekly rows to `REG` before aggregation, excludes
`POST`, and fails closed when weekly season type is missing or unknown. The
six obvious rookie rows are copied from the
[nflverse regular-season 2023 source](https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_reg_2023.csv.gz)
as candidate inputs only. No promoted outcome was regenerated.

## Correction lineage and migration boundary

- Archived defect rows:
  `data/fixtures/archived/2023_input_integrity/contaminated_seed_rows_v0.json`
- Candidate manifest:
  `data/candidate/2023_input_integrity/v0.1.0/manifest.json`
- Machine-readable audit:
  `docs/audits/2023-input-integrity-remediation.json`
- Candidate validator:
  `scripts/validate_2023_input_integrity.py`

The manifest pins all candidate files plus the untouched source/promoted
files. Candidate files are overlays for review, not drop-in governed inputs.
They cannot be promoted or used to overwrite the existing seeds under this
authority.

## Affected-artifact inventory

| Artifact family | Relationship | This PR |
|---|---|---|
| `exports/promoted/rookie-alpha/2023_*` | Directly built from the contaminated combine, production, and context seeds | Unchanged |
| `exports/promoted/rookie-alpha/historical_class_comparison.*` | Includes promoted 2023 Rookie Alpha rows | Unchanged |
| `exports/promoted/nfl-fantasy-outcomes/player_year_ppr_outcomes_v1.*` | Direct REG/POST contamination | Unchanged |
| `exports/promoted/nfl-fantasy-outcomes/context_flag_outcome_summary_v1.*` | Downstream outcome summary | Unchanged |
| `exports/promoted/rookie-ml-lane/*` | Potential consumer of historical scores/outcomes; disposition belongs to parked #286 | Not evaluated or modified |

## Regression gates

`tests/test_validate_2023_input_integrity.py` rejects:

1. combine/pro-day conflation;
2. aggregate college stats without explicit season/scope semantics;
3. four-season class-year rows marked early declare;
4. any `POST` row in the regular-season candidate input.

`tests/test_build_nfl_fantasy_outcomes.py` additionally proves the builder
excludes postseason rows and refuses ambiguous weekly inputs.

Run:

```bash
python3 scripts/validate_2023_input_integrity.py
python3 -m unittest tests.test_validate_2023_input_integrity tests.test_build_nfl_fantasy_outcomes -v
python3 scripts/validate_promoted_export.py \
  --export-json exports/promoted/rookie-alpha/2023_rookie_alpha_predraft_v0.json \
  --manifest exports/promoted/rookie-alpha/2023_manifest.json
```

## Promotion/deprecation recommendation

Do not overwrite the old seeds or repair promoted files in place. Preserve
them as the record of prior runs. After operator review, the clean options
are an explicit limitation/deprecation record or a separately authorized,
versioned superseding artifact built from reviewed candidates. Model-lane
disposition remains parked in #286.
