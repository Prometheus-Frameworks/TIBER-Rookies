# 2023 Historical Reconstruction Pilot (issue #283)

> Audit + reconstruction pilot. Produced 2026-08-04 on branch
> `claude/github-issue-283-q5rm50`. No promoted artifact, current card,
> ranking, or Forecast output was mutated. All new artifacts live under
> `data/historical/reconstruction_2023/`, `docs/`, and `scripts/`.

## Terminal decision

```text
historical_2023_reconstruction_requires_cross_repo_interface
```

The three required pilot cards, landing contexts, frozen expectation records,
and the outcome layer were **completed** with pilot-local evidence — so the
pilot itself is not blocked. The decision above is chosen because scaling
beyond the three worked examples (full-class reconstruction, governed landing
context) cannot proceed inside TIBER-Rookies alone: 2022 team context, draft
results backfill, and identity resolution are TIBER-Data / Teamstate
interfaces that do not exist yet (details in §3). Secondarily,
`rookie_model_relevance_requires_operator_decision` applies to §5's
retain/retire/refactor recommendation, which is an operator call under repo
governance.

## 1. Phase 1 — 2023 class coverage audit

Artifact: `data/historical/reconstruction_2023/2023_skill_class_census_v0.{json,csv}`
Builder: `scripts/build_2023_reconstruction_census.py`
Census backbone: nflverse `draft_picks` public release (audit census only —
not the governed TIBER-Data draft-results lane, which still has no
historical backfill; issue #242).

**80 drafted 2023 QB/RB/WR/TE** (14 QB, 18 RB, 33 WR, 15 TE):

| Classification | Count | Meaning |
|---|---:|---|
| `governed_profile_available` | 13 | standalone row in the promoted 2023 rookie-alpha export |
| `partial_reconstructable` | 34 | in-repo athletic testing + ≥1 governed college production season |
| `reference_only` | 31 | only SPORQ/reference-population/outcome rows |
| `missing` | 2 | no in-repo artifact at all (Stetson Bennett, Max Duggan) |

Key structural facts:

- **All 13 "governed" profiles are hindsight-contaminated** (see §4). They are
  renderable cards with reproducible math, but they are not clean pre-draft
  reconstructions.
- The 13-player set is itself an outcome-selected calibration set (Rice,
  Dell, Achane, Nacua… chosen because of their NFL careers), not a census
  sample. Coverage of the class by the promoted export is 13/80 ≈ 16%.
- Josh Downs — a top-80 pick with two 1,000-yard seasons — had **no**
  standalone profile before this pilot, exactly as issue #283 anticipated.
- SPORQ covers WR/RB/TE only; **no QB athletic layer exists** (all 14 QBs cap
  at reference/partial).
- TE reference-population files exist but are **empty**; WR populations stop
  at 2021, so no 2022 final-season college line is governed for anyone in
  this class.

## 2. Phase 2/3 — reconstructed pilot artifacts

Contract: `docs/historical-reconstruction-contract.md` (pre-draft schema,
landing-context schema, hindsight firewall, freeze semantics).

| Layer | Files |
|---|---|
| Pre-draft cards (cutoff 2023-04-26T23:59:59Z) | `predraft_cards/2023_wr_{puka_nacua,zay_flowers,josh_downs}_predraft_v0.json` |
| Landing contexts (cutoff = evening of each pick) | `landing_context/2023_wr_*_landing_context_v0.json` |
| Frozen expectation records (sha256-pinned) | `expectation_records/2023_wr_*_expectation_record_v0.json` via `scripts/freeze_2023_expectation_records.py` |
| Post-freeze outcomes 2023–2025 | `outcomes/2023_2025_pilot_outcomes_v0.json` via `scripts/build_2023_pilot_outcomes.py` (verifies freeze first) |

Firewall properties actually enforced:

- Pre-draft cards contain **no actual draft capital** (asserted by
  `actual_draft_capital_present: false`; expected capital is qualitative and
  labeled as expectation).
- Landing contexts admit only facts observable at the pick (verified
  transaction dates: A-Rob trade 04-18, OBJ 04-13, Agholor 03-29, Campbell
  03-16, Minshew 03-16, Monken hire 02-14, Lamar extension 04-27 pre-Round 1).
- Every non-re-verified fact carries `needs_verification: true`; every
  depth-chart row is tagged observation vs inference.
- The outcome builder refuses to run if any frozen layer's hash changed.

### Input-integrity findings surfaced while reconstructing

These are defects in **existing** repo inputs found during the pilot (not
fixed here — surgical scope; they need their own remediation issue):

1. `data/raw/2023_combine_results.json` credits Puka Nacua with
   forty 4.57 / vertical 36.5 / broad 122 as "NFL combine 2023 (official)".
   The nflverse combine release and the repo's own SPORQ table show he
   **did not test at the combine** (SPORQ: DNQ). Provenance is wrong;
   values are unverifiable (possibly pro-day numbers).
2. Same file: Zay Flowers vertical 41.0 / broad 129 vs 35.5 / 127 in both
   nflverse and SPORQ.
3. `data/processed/2023_college_production.json` claims Nacua's 2022 =
   "1594 yds/10 TDs". Web-verified 2022 line is 48/625/5; the governed 2021
   CFBD line is 805 yds. 1594 appears to be an unlabeled multi-season or
   scrimmage aggregate presented as a single-season stat.
4. `data/processed/2023_prospect_context.json` marks Flowers
   `early_declare_flag: true`; he was a four-year senior.
5. Promoted outcome rows for 2023 report **18 games** for Nacua/Flowers —
   more than the 17-game regular season — suggesting REG+POST mixing in the
   legacy nflverse `player_stats` path of `build_nfl_fantasy_outcomes.py`.

## 3. Historical source-data availability (landing-context reconstruction)

Cross-repo inventory of TIBER-Data, Teamstate, Forecast, Strategy,
Role-and-opportunity-model, FORGE:

| Source family | Classification | Basis |
|---|---|---|
| 2023 draft results (skill players with NFL stats) | `available_requires_adapter` | `TIBER-Data exports/promoted/nfl/player_season_coverage_v0.json` carries source-verified draft_year/round/pick/team for 68 drafted + 26 UDFA 2023 rookies; needs a draft-results-shaped projection + `LA→LAR` normalization |
| Full 2023 draft board (all 259 picks) | `external_research_required` | governed `nfl_draft_results` exists **for 2026 only**; historical backfill explicitly excluded (TIBER-Rookies #242 open) |
| 2022 team target / air-yards distributions | `available_requires_adapter` | 609 governed 2022 player-season rows (all 32 teams) with target_share/air_yards_share; needs an aggregation adapter that does not exist |
| 2022 routes / snaps / route participation | `unavailable` | 100% null upstream by design (`nflreadpy.load_player_stats` does not expose them) |
| 2022 offense quality (pace, PROE, EPA, red zone) | `external_research_required` | real team-week data exists for 2024 only; 2022 rebuild = new governed ingest project |
| Depth-chart snapshots (April 2023) | `unavailable` | no artifact anywhere; coverage artifact's consumer-safety rules explicitly forbid depth-chart inference |
| Offseason departures/additions, transactions | `unavailable` as held facts | `roster_snapshot_v0` is contract+schema only, no pipeline; derivable only by inference or external research |
| QB / coaching state 2022–2023 | `external_research_required` | no coach/play-caller values held for any season in any repo |
| Injury/availability state | `unavailable` | `games_missed` 100% null; consumer-safety forbids availability claims |
| 2023 rookie NFL outcomes | `governed_available` | 576 governed 2023 player-season rows incl. all three pilots |

For this pilot, team-context values were computed directly from the public
nflverse release and stamped as pilot-local evidence; the contract states the
durable owner is a TIBER-Data aggregation + Teamstate landing-context
instance (Teamstate's `rookie-landing-context-tags-2026.md` is the closest
existing analogue, but its validator hardcodes season 2026 and its data is
operator-seeded-unknown).

Cross-repo defects worth their own issues:

- **Nacua GSIS conflict**: Forecast Run 1 keys Nacua as `00-0038543`;
  the governed TIBER-Data artifact and nflverse say `00-0039075`.
- **`LA` vs `LAR`** team-code split between the coverage artifact and every
  downstream normalizer.
- Four player-ID spaces in play (GSIS, `tiber-data-player-YYYY-slug`,
  Rookies slugs, Forecast's row IDs) with a 25-row crosswalk that covers no
  2023 rookie at class scale.

## 4. Phase 4 — Rookies model relevance & reproducibility audit

Answers to the nine questions in issue #283:

1. **What code produces rookie scores?** Deterministic:
   `scripts/compute_rookie_alpha.py` (pre-draft Rookie Alpha v0.5.0 — RAS 35%
   / production 45% / draft-capital proxy 20%, plus athletic blending,
   market-conviction overrides, WR translation penalties). Experimental:
   `scripts/compute_rookie_ml_lane.py` (logistic "hit probability" eval
   lane). Adjacent: post-draft adjustment and transition-profile scripts
   (2026-scoped).
2. **Can it execute against a reconstructed 2023 input set?** Yes.
   Re-executed in this pilot with outputs redirected to scratch:
   **score-level reproduction of the promoted 2023 export was exact** (all 13
   players, all fields). The pipeline itself is healthy and season-agnostic
   via CLI paths.
3. **What target was the ML lane trained to predict?** Binary
   "fantasy-relevant hit by year 3" (positional finish thresholds:
   WR/RB ≤ 24, TE ≤ 12, QB ≤ 15, tier-label fallbacks), not a career
   probability distribution.
4. **Training population/seasons?** 37 labeled rows, draft classes
   2018–2023 (25 WR, 10 TE, 2 QB, 0 RB) — **including 2 synthetic
   "sample-fixture" players** — loaded from files literally named
   `historical_prospect_features.sample.json` /
   `historical_player_outcomes.ml_sample.json`. The time-aware test slice for
   2023 is a **single row** (Sam LaPorta). None of the three pilot players is
   in the feature set.
5. **Artifacts/config/feature order/hashes preserved?** Deterministic lane:
   yes — per-season manifests with input/output sha256 and row counts, and
   reproduction verified. ML lane: reports and probabilities are exported,
   but **no model binary is persisted**; reproducibility relies on retraining
   with `--seed 42` over the same inputs. Feature order is code-constant.
6. **Probabilistic estimate, ranking score, or heuristic composite?**
   Deterministic Rookie Alpha is a **heuristic composite ranking score**
   (0–100) with hand-set weights and override rules — not calibrated, not
   probabilistic. The ML lane emits probabilities but is evaluation-only,
   n=37, and gated by its own warnings as experimental/additive.
7. **Can the original 2023 prediction be reproduced without outcome
   leakage?** **No.** The math reproduces exactly, but the 2023 *inputs* are
   structurally contaminated:
   - `2023_draft_capital_proxy.json` stores **actual** pick/round/team
     (Nacua `actual_pick: 177`) as the "pre-draft" capital feature;
   - evidence strings contain post-draft knowledge ("105 catches rookie
     year", "Pro Bowl 2023 (first year)", "the model should score him very
     high", "that tension is the point");
   - the 13-player roster was itself selected with knowledge of outcomes.
   A leakage-free 2023 run requires rebuilding inputs under the
   reconstruction contract (expected capital instead of actual; evidence
   cutoff 2023-04-26) — which this pilot's three cards demonstrate is
   feasible for WRs from governed + public sources.
8. **Which parts remain useful alongside Forecast?** The deterministic
   producer pipeline (merge, manifest, validation, export contract) and the
   evidence-tag vocabulary are sound infrastructure. The prospect-level
   signal families (age-adjusted production, breakout timing, athletic
   testing, expected capital) are exactly what Forecast does **not** model —
   Forecast Run 1 predicts 2025 seasonal PPR from 2024 NFL box-score
   features and contains no draft, landing, or prospect features at all.
   There is no responsibility overlap today, and the intended boundary
   (Rookies = prospect→NFL translation priors before NFL history; Forecast =
   seasonal inference once governed history exists) is **not violated in
   code** — but it is also not *implemented* as a handoff: nothing consumes
   Rookie Alpha as a prior, and Forecast's rookie-transition crosswalk is
   100% unresolved.
9. **Retain / retire / refactor?** **Refactor** (operator decision required):
   - **Retain** the deterministic pre-draft producer pipeline, export
     contract, manifest/validation machinery, and SPORQ/reference-population
     data layers.
   - **Retire** the contaminated 2023 "historical seed" inputs as
     calibration fixtures (quarantine, don't delete: they are the record of
     what was run) and stop treating the promoted 2023 export as a
     historical reconstruction — it is a hindsight demo.
   - **Refactor** the ML lane's dataset lane from sample fixtures to the
     governed reconstruction path this pilot establishes before any claim of
     validated hit-rates is made; keep it evaluation-only until then.
   - Formalize the Rookies→Forecast boundary as an interface: Rookies emits
     a frozen pre-draft prior + landing-context artifact per class;
     Forecast may consume it as a rookie-year prior feature once identity
     resolution (GSIS crosswalk) exists.

## 5. Phase 5 — post-freeze outcome comparison (2023–2025)

Outcome layer built only after `freeze` verification. PPR = same formula as
the promoted outcomes builder. **Season-type bases are not uniform**: the
2023 AND 2024 rows are copied from the promoted export whose legacy path
mixes REG+POST in 31/132 draft-class-2023 player-seasons (per the #285/#287
audit — e.g. Nacua 2023 shows 18G/114/1667 vs true REG 17/105/1486), while
2025 rows are REG-only. Each row now carries a `season_type_basis` field;
cross-season comparisons below must be read with that caveat until the
promoted family is regenerated with the REG-only builder fix.

| Player | 2023 | 2024 | 2025 | Read against frozen expectation |
|---|---|---|---|---|
| Puka Nacua | 114-1667-7, 331.4 PPR (18.4/g) | 90-1131-3, 232.4 (17.9/g) | 129-1715, 377.0 (23.6/g) | Frozen pre-draft card: old-ish breakout, no verified athletic testing, Day-3 expected capital — the prospect model as constituted would have scored him low, and honestly so. Frozen landing context read "excellent role-path, uncertain environment" (thinnest WR2 depth chart in the league, scheme archetype fit, Kupp/Stafford health contingencies). The outcome is a tail event no calibrated pre-draft model should be judged for missing outright — but the **landing-context layer carried real, reconstructable signal** that the prospect layer lacked. Traits that translated: target earning, YAC physicality. |
| Zay Flowers | 86-1014-6, 235.4 (13.1/g) | 74-1059-4, 209.5 (12.3/g) | 86-1211, 249.3 (14.7/g) | Frozen expectation: immediate starter on R1 capital; ceiling gated by Andrews' share, veteran room, and franchise pass-volume floor. Outcome: instant every-down role, steady WR2-band production, no elite target spike — the gating mechanism named at freeze time is the one that operated. Best calibration match of the three. |
| Josh Downs | 68-771-2, 157.1 (9.2/g) | 72-803-5, 182.2 (13.0/g) | 58-566, 138.4 (8.7/g) | Frozen expectation: "role-favorable, environment-risky" — cleanest slot vacancy in the class, capped by the rawest QB room. Outcome: immediate slot job and steady targets (the role prediction hit), but production and 2025 regression tracked the QB environment exactly as the risk clause anticipated. Traits translated (separation, target earning); environment suppressed ceiling. |
| Forecast Run 1 (Nacua only) | — | inputs | predicted 261.3 vs actual 314.7 | Underestimate within reasonable error; recorded under the conflicting GSIS ID `00-0038543` (defect, §3). Flowers/Downs absent from the 39-row cohort. |

Evaluation takeaways for the model-relevance decision:

- The **two-layer separation earned its keep**: in all three cases the
  landing-context layer contained the decision-relevant information that the
  pure prospect layer could not carry, and none of it required hindsight.
- Draft-capital-as-proxy did most of the ranking work in the existing 2023
  export; a reconstruction that replaces actual capital with expected
  capital will move Nacua down, not up — the honest result. Chasing the
  Nacua tail by re-weighting would be hindsight tuning, exactly what the
  firewall prohibits.
- The Rookies layer's durable value is the **frozen expectation record**:
  it lets outcome evaluation (this section) be run against what was actually
  knowable, class after class, without self-deception.

## 6. Acceptance criteria status

- [x] Every drafted 2023 QB/RB/WR/TE classified (80/80, census artifact)
- [x] Standalone pre-draft-only reconstructed cards for Puka, Zay, Downs
- [x] Exact source lineage + explicit reconstruction cutoff on each card
- [x] Actual draft capital absent from the pre-draft layer (asserted field)
- [x] Landing context separate from prospect quality (separate artifacts)
- [x] Rams/Ravens/Colts artifacts include contemporaneous depth chart, vacancy, QB, coaching, prior-offense context
- [x] Later NFL outcomes cannot affect frozen layers (sha256 freeze + verifying outcome builder)
- [x] Puka's Rams landing spot assessed from April 2023 information only
- [x] ML/model path executed reproducibly (deterministic: exact reproduction) and classified (ML lane: experimental, fixture-fed, non-validated)
- [x] Clear retain/retire/refactor recommendation (§4.9 — operator decision)
- [x] No current card, Forecast output, ranking, or promoted artifact mutated

## Review acknowledgments (PR #284 review, 2026-08-05)

- **Expected-draft-capital lineage (M1).** The reviewer is right that every
  `expected_draft_capital` range rests on `agent_recall_needs_verification`
  written by an author who knows the outcomes — the soft-leak channel #283
  warns about. The cards label this honestly, but the "exact source lineage"
  acceptance criterion should be read as **partially met** for that field
  family. Closing it requires a licensed or archived April-2023 consensus
  board source; until then the ranges are context, not evidence.
- **Freeze governance (M3).** `freeze` now fails closed when layers changed
  (silent re-pin removed; `--refreeze-reason` is required and logged into the
  record), and `tests/test_freeze_2023_expectation_records.py` runs `verify`
  against the committed records in CI. The single-commit history limitation
  is real and cannot be repaired retroactively; the freeze remains protection
  against accidental drift, with intent-level integrity resting on review.
- **Erratum (L4).** The frozen Downs card describes 2022 Drake Maye as a
  "true freshman"; he was a redshirt freshman. The field is already flagged
  agent-recall; recorded here rather than editing the frozen card.
- **Operator note (pairing with #287).** The frozen Nacua card states pro-day
  data was unavailable *as of this pilot's construction*; PR #287 has since
  sourced a pro-day candidate line. Both statements are correct in their
  time-scopes. If the operator wants the card updated, that is a logged
  re-freeze (`freeze --refreeze-reason ...`), not a silent edit.

## Follow-up issues recommended (not filed here)

1. Remediate the five input-integrity findings in §2 (2023 combine/production/context files).
2. TIBER-Data: historical draft-results backfill (#242) and a 2022 team-context aggregation adapter over `player_season_coverage_v0`.
3. Identity: resolve the Nacua GSIS conflict and extend the crosswalk to the 2023 class.
4. Rebuild the ML lane dataset from reconstruction-contract inputs; retire sample fixtures from promoted exports.
5. Decide the Rookies→Forecast prior interface (operator).
