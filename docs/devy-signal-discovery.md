# Devy signal discovery foundation

TIBER-Devy is a **signal discovery layer**, not a rankings engine. Its first job is
to organize long-horizon uncertainty before Rookie Alpha inputs are stable enough
for deterministic scoring.

This layer helps users answer three questions:

1. How far is the player from likely NFL draft liquidity?
2. What lifecycle stage best describes the player's current development state?
3. How strong, actionable, confident, and volatile is the current signal?

It does **not** predict future NFL draft capital, produce decimal grades, replace
Rookie Alpha, or imply certainty for 2028/2029-style profiles.

## Canonical definitions

The canonical enum and validation definitions live in
`scripts/devy_signal_registry.py`.

Centralized vocabularies include:

- `DevyDevelopmentHorizon`: `NEAR_TERM`, `MEDIUM_TERM`, `LONG_HORIZON`, `PREP_OR_FUTURE`
- `DevyLifecycleStage`: `PREP`, `TRUE_FRESHMAN`, `ROTATIONAL`, `EMERGING`, `BREAKOUT_WINDOW`, `NFL_TRACK`, `DECLARE_RISK`, `SENIOR_HOLD`, `STALLED`
- `DevyDevelopmentTag`: `LONG_HORIZON`, `LONG_HORIZON_WATCHLIST`, `HIGH_RECRUITING_CAPITAL`, `MULTI_SPORT_PROFILE`, `INJURY_REHAB_WATCH`, `INSULATED_PROGRAM`, `SIZE_PROFILE`, `EARLY_DECLARE_CANDIDATE`, `PATHWAY_BLOCKED`, `PATHWAY_CLEARING`, `TRANSFER_RISK`, `ASCENDING`, `STALLED_SIGNAL`, `RAW_TRAITS`, `PRODUCTION_PENDING`, `ROLE_UNCERTAIN`
- Signal bands: `LOW`, `MODERATE`, `STRONG`, `ELITE`
- Confidence bands: `LOW`, `MEDIUM`, `HIGH`
- Actionability bands: `WATCHLIST`, `MONITOR`, `TARGET`, `PRIORITY`
- Volatility bands: `LOW`, `MEDIUM`, `HIGH`, `EXTREME`

## Fixture registry

The fixture registry lives at `data/fixtures/devy_prospect_registry_v0_fixture.json`.
It is intentionally fixture-only and uses illustrative placeholder rows rather
than player facts. The fixture covers:

- a 2029-type long-horizon WR profile,
- a near-term draft-eligible RB profile,
- an emerging underclassman QB profile, and
- a stalled/uncertain TE profile.

These rows validate schema behavior only. They must not be promoted, treated as
rankings, or used as sourced scouting claims without documented provenance.

## Real seed watchlist

The first real-name seed watchlist lives at
`data/devy/devy_seed_watchlist_2026.json`. It is still a **non-promoted seed
artifact**: the rows are for discovery and operator monitoring only, not
rankings, Rookie Alpha inputs, promoted scouting truth, or future NFL draft-capital
claims.

The key distinction from the fixture registry is provenance. Fixture rows are
placeholder schema examples; seed-watchlist rows may contain real player names
only when each row separates:

Current seed coverage intentionally spans near-term (2027), medium-term (2028), and
long-horizon (2029) windows across QB/RB/WR/TE so operators can discover names
without turning this artifact into rankings. The post-#226 discovery-v2 pass broadens
2029 coverage with additional deep-dynasty watchlist candidates sourced from
player-level recruiting profiles while preserving unresolved program mappings as
`unknown` when roster-level verification is unavailable.

- `identity_provenance` (for name/school/position),
- `timeline_provenance` (for projected/earliest draft-class context), and
- `signal_provenance` (for interpretive tags and bands).

Each provenance object must include canonical `source_type`, non-empty
`source_notes`, and a `last_verified_year` no later than artifact
`as_of_year`; `source_urls` are optional but must be valid HTTP(S) links when
present. Source types are validated per provenance category, not only against
a global canonical list:

- `identity_provenance`: `official_roster` or `recruiting_profile`
- `timeline_provenance`: `manual_eligibility_context` or `recruiting_profile`
- `signal_provenance`: `manual_curated_seed_signal`, `recruiting_profile`,
  `production_data`, or `team_context_artifact`

This keeps the Devy lane from inventing continuity when rosters, transfers,
development stages, or eligibility assumptions become stale.

### Contextual (non-scoring) discovery tags

The Devy seed watchlist supports contextual inspection tags that are explicitly
non-scoring and non-promoted:

- `MULTI_SPORT_PROFILE`: sourced evidence of meaningful participation in
  another sport (for operator context only).
- `INJURY_REHAB_WATCH`: sourced injury/rehab context that should be monitored
  before near-term decisions.
- `HIGH_RECRUITING_CAPITAL`: broad recruiting-context discovery signal only.
- `LONG_HORIZON_WATCHLIST`: optional explicit long-horizon tracking tag when a
  row exists primarily for future-cycle monitoring.

These tags do **not** imply player quality, safety, model uplift, medical
evaluation, Rookie Alpha score impact, ranking movement, or downstream
promotion eligibility.

Real players can enter this lane when a human curator can represent the row with
coarse, honest context:

- identity fields such as name, school, and position come from documented public
  sources;
- timeline fields are framed as projected/earliest-possible draft context, not
  guaranteed declaration years;
- signal, confidence, actionability, and volatility remain broad bands instead of
  numeric grades; and
- `summary` / `why_it_matters` explain why the player is worth monitoring without
  copying scouting reports or asserting unsupported traits.

Long-horizon rows should be interpreted as early watchlist signals. For example,
a 2029-type player in an `as_of_year` 2026 artifact must validate as
`LONG_HORIZON` and cannot be `TARGET` or `PRIORITY` actionable. This lets TIBER
surface names before the fantasy market stabilizes while preserving that the row
is not ready for a rookie-ranking or promoted-export workflow.


### Intake audit trail

The seed watchlist now carries an artifact-level `intake_audit` block to document
how rows entered the registry and preserve honest Devy v1 claims:

- `intake_method`: curated/manual/Codex lineage (not autonomous scraping),
- `introduced_by_issue` and `introduced_by_pr`: traceability back to issue/PR,
- `validation_command`: exact validator command used as the schema guardrail,
- `promotion_status`: non-promoted discovery posture, and
- `downstream_eligibility`: explicit block from rookie/NFL scoring surfaces
  until a governed transition path exists.

This captures the Derrek Cooper path (`Issue #227 -> PR #228 -> seed watchlist ->
validator`) as a documented curated workflow rather than an ingestion pipeline.

## Horizon logic

The validator derives horizon expectations from `years_to_projected_draft`:

| Years to projected draft | Expected horizon |
| --- | --- |
| `0` or `1` | `NEAR_TERM` |
| `2` | `MEDIUM_TERM` |
| `3` | `LONG_HORIZON` |
| `4+` | `PREP_OR_FUTURE` |

A `PREP` lifecycle stage also maps to `PREP_OR_FUTURE`.

The important guardrail: a 2029-type prospect in an `as_of_year` 2026 registry is
three years from projected liquidity, so validation requires `LONG_HORIZON` and
prevents `TARGET` / `PRIORITY` actionability. This keeps early devy assets from
being handled like next-cycle rookie prospects.

## Validation

Run the validator against the fixture registry:

```bash
python3 scripts/devy_signal_registry.py --registry data/fixtures/devy_prospect_registry_v0_fixture.json
```

Run the validator against the real seed watchlist:

```bash
python3 scripts/devy_signal_registry.py --registry data/devy/devy_seed_watchlist_2026.json
```

Run the focused Devy registry tests:

```bash
python3 -m pytest tests/test_devy_signal_registry.py
```

The validator checks required fields, canonical enum values, duplicate IDs,
draft-class chronology, `years_to_projected_draft`, horizon consistency,
artifact disclaimers, split seed-watchlist provenance categories, canonical
source types, source URL format, `last_verified_year` bounds, and the
long-horizon actionability guardrail.

## Relationship to Rookie Alpha

Rookie Alpha remains the deterministic rookie evaluation model. Devy signal
discovery is upstream and additive: it can surface names and uncertainty before
combine data, production normalization, true draft capital, and landing spot are
available.

Do not route Devy rows into Rookie Alpha scoring unless a future issue explicitly
adds a governed ingestion path with provenance, validation, and downstream
contract review.

## Monthly Devy roster pulse (v1 design)

`monthly_devy_roster_pulse` is the next conservative discovery lane after Devy v1
seed curation. It runs approximately monthly (manual or scheduled later), and
its only output is a candidate-delta snapshot for human review.

### Safety boundary

- Discovery-only output. No scoring/ranking/promotion.
- No direct mutation of `data/devy/devy_seed_watchlist_2026.json`.
- No routing into Rookie Alpha, promoted rookie exports, NFL scoring identity
  tables, FORGE, Point Prediction, or TIBER-Fantasy active NFL surfaces.
- Missing truth remains explicit as `unknown`/`unresolved` and `needs_manual_review=true`.

### Artifact shape

Pulse artifacts live under:

- `data/devy/monthly_pulse/devy_roster_pulse_YYYY_MM.json`

Canonical v1 shape is validated by `scripts/validate_devy_roster_pulse.py` and
uses `artifact_type = devy_roster_pulse_candidate_delta`.

Each candidate row captures roster-status deltas, watchlist match context,
class-year evidence source, optional production evidence, candidate tags,
confidence, provenance URLs/notes, and a hard block against automatic seed
watchlist mutation (`auto_seed_watchlist_mutation = "none"`).

### Freshman inference guardrail

Missing prior college production is **not** enough to confirm freshman status.

Allowed examples:

- `prior_college_production_found = false`
- `candidate_tags` include `potential_2029_candidate`,
  `no_prior_college_production_found`, `needs_class_year_verification`

Disallowed examples:

- `candidate_tags` includes `confirmed_freshman` when production is missing
  without explicit class-year/recruiting evidence.
- `freshman_status = confirmed` when `prior_college_production_found=false`
  and `class_year_source=unknown`.

### Validation + tests

Validate sample artifact:

```bash
python3 scripts/validate_devy_roster_pulse.py --artifact data/devy/monthly_pulse/devy_roster_pulse_2026_05.json
```

Focused validator tests:

```bash
python3 -m pytest tests/test_devy_roster_pulse_validator.py
```

## Operator-supplied deep Devy draft market snapshots (fixture workflow)

To capture real-world Devy draft coverage signals without polluting scoring or promotion layers,
TIBER-Rookies now supports an anonymized fixture workflow for operator-supplied draft snapshots.

Artifacts:

- Snapshot fixture input:
  - `data/devy/league_market_snapshots/deep_devy_draft_snapshot_2026_fixture.json`
- Coverage diff output:
  - `data/devy/league_market_snapshots/deep_devy_draft_snapshot_2026_coverage_diff.json`

Scope semantics:

- This fixture currently sets `snapshot_scope: "fixture_subset"`.
- The diff field `tiber_seed_not_present_in_snapshot_fixture` means only that a seed row was not observed in the fixture rows provided.
- It must **not** be interpreted as true league availability unless the snapshot includes complete anonymized draft history for the league window.

Guardrails:

- Discovery intelligence only (market/coverage snapshot), not scouting truth or player-quality inference.
- No Rookie Alpha wiring.
- No automatic seed-watchlist mutation.
- No promoted-artifact export behavior.
- No NFL scoring, FORGE, Point Prediction, or TIBER-Fantasy active NFL search integration.

The fixture includes explicit known test rows:

- Derrek Cooper (supplemental `5.05`) should resolve as known by TIBER when present in
  `data/devy/devy_seed_watchlist_2026.json`.
- Aaron Gregory (supplemental `5.06`) should resolve as drafted-missing, coverage-gap candidate,
  and monthly-pulse candidate (`auto_seed_watchlist_mutation = none`).

Validation command:

```bash
python3 scripts/validate_devy_league_market_snapshot.py --artifact data/devy/league_market_snapshots/deep_devy_draft_snapshot_2026_fixture.json
```

Coverage diff command:

```bash
python3 scripts/compute_devy_league_market_snapshot_diff.py \
  --snapshot data/devy/league_market_snapshots/deep_devy_draft_snapshot_2026_fixture.json \
  --seed-watchlist data/devy/devy_seed_watchlist_2026.json \
  --output data/devy/league_market_snapshots/deep_devy_draft_snapshot_2026_coverage_diff.json
```

Use this as a manual review helper only. Drafted-missing names are candidate deltas for
monthly pulse/operator review and must not be auto-added to the seed watchlist.
