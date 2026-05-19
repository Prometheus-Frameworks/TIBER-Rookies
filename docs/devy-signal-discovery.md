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
- `DevyDevelopmentTag`: `LONG_HORIZON`, `HIGH_RECRUITING_CAPITAL`, `INSULATED_PROGRAM`, `SIZE_PROFILE`, `EARLY_DECLARE_CANDIDATE`, `PATHWAY_BLOCKED`, `PATHWAY_CLEARING`, `TRANSFER_RISK`, `ASCENDING`, `STALLED_SIGNAL`, `RAW_TRAITS`, `PRODUCTION_PENDING`, `ROLE_UNCERTAIN`
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
only when each row includes source notes, a manual-curation source type, source
URLs when available, and a `last_verified_year`. This keeps the Devy lane from
inventing continuity when rosters, transfers, development stages, or eligibility
assumptions become stale.

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
artifact disclaimers, seed-watchlist provenance/source notes, and the
long-horizon actionability guardrail.

## Relationship to Rookie Alpha

Rookie Alpha remains the deterministic rookie evaluation model. Devy signal
discovery is upstream and additive: it can surface names and uncertainty before
combine data, production normalization, true draft capital, and landing spot are
available.

Do not route Devy rows into Rookie Alpha scoring unless a future issue explicitly
adds a governed ingestion path with provenance, validation, and downstream
contract review.
