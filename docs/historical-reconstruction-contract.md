# Historical reconstruction contract (2023 pilot, issue #283)

> Status: pilot contract, v0. Governs the artifacts under
> `data/historical/reconstruction_2023/`. Nothing under that directory is a
> promoted artifact, a model input, or a current-ranking surface. Nothing in
> this lane may mutate `exports/promoted/**`.

This contract defines two separated historical layers plus a frozen
combination record:

1. **Pre-draft reconstructed card** — what TIBER could have known about the
   prospect **before** the NFL Draft of the class year.
2. **Draft-day landing-context artifact** — what TIBER could have assessed
   about the landing spot **immediately after the pick**, and nothing later.
3. **Historical expectation record** — a freeze marker binding one card and
   one landing context by content hash, produced before any outcome data is
   attached.

NFL outcomes live in a fourth, strictly separate layer
(`outcomes/`) that must never feed back into layers 1–3.

## Hindsight firewall

```text
pre-draft evidence
        ↓ freeze
pre-draft reconstructed card
        ↓
draft-day landing context
        ↓ freeze
historical expectation record
        ↓
2023–2025 NFL outcomes and Forecast comparison
```

Prohibited inside layers 1–3:

- any NFL outcome (stats, fantasy points, roles, awards, injuries, trades,
  depth-chart changes after the context cutoff);
- actual draft capital inside the **pre-draft** layer (expected capital is
  allowed and must be labeled as expectation);
- grades, phrasing, or metric selection tuned to match known NFL outcomes;
- describing a landing spot with information that only became true later.

Every evidence field carries a `source_ref` and every artifact carries an
explicit cutoff. Facts recalled from public record but not re-verified
against a fetchable source are marked `needs_verification: true` — per
AGENTS.md, explicit uncertainty beats fabricated continuity.

## Layer 1 — pre-draft reconstructed card schema

Top-level required fields:

```yaml
artifact: predraft_reconstruction_card_v0
reconstruction_mode: historical_as_known_then
class_year: integer
pre_draft_cutoff: timestamp            # e.g. 2023-04-26T23:59:59Z
nfl_outcome_fields_available_to_card_builder: false
canonical_player_id: string            # repo slug convention
gsis_id: string | null                 # identity join only, not evidence
player_name: string
position: QB | RB | WR | TE
identity:                              # school, birth_date, age_at_draft,
  ...                                  # class standing, early_declare, transfers
college_production:                    # year-by-year rows, each with source_ref
  - season, school, receptions, receiving_yards, receiving_tds, other, source_ref
breakout_and_age: {breakout_age, age_adjusted_note, source_ref}
market_share_context: {status, value?, source_ref?}        # explicit missingness
efficiency_indicators: {yprr?, target_earning?, status, source_ref?}
role_and_alignment: {alignment_profile, route_role, source_ref}
separation_evidence: {status, ...}                          # man/zone, press
after_catch_and_contested: {status, ...}
athletic_testing:                      # combine/pro-day rows with source_ref;
  ...                                  # DNP fields stay null, never imputed
context_flags: [injury, transfer, qb_context, scheme, competition]
expected_draft_capital:                # PRE-DRAFT expectation only
  qualitative_range: string            # e.g. "consensus Day 3 (R4–R6)"
  basis: string
  source_status: string
  actual_draft_capital_present: false  # hard assertion for validators
missingness: [list of evidence families with no governed source]
source_lineage: [every source used, with kind/url/verification status]
```

Rules:

- `actual_draft_capital_present` must be `false`; the words used in any free
  text must not reveal the actual round, pick, or team.
- Evidence family entries use `status`:
  `governed_in_repo | verified_public_source | agent_recall_needs_verification | unavailable`.
- Third-party analyst metrics that are proprietary/paywalled (e.g. charted
  YPRR grades) may appear only as qualitative context with
  `status: qualitative_context_only`, per
  `docs/legal/external-source-hygiene-policy.md`.

## Layer 2 — draft-day landing-context schema

Top-level required fields (following the field list in issue #283):

```yaml
artifact: landing_context_v0
class_year: integer
canonical_player_id: string
landing_context:
  draft_team: string
  draft_round: integer
  overall_pick: integer
  draft_capital_tier: string
  context_cutoff: timestamp            # moment of the pick (or same evening)
  returning_receiver_depth_chart: list # each row: player, 2022 usage, status, source_ref
  returning_tight_end_depth_chart: list
  returning_running_back_depth_chart: list
  vacated_targets: {value, season_basis, source_ref}
  vacated_routes_or_snaps: {value: null allowed, source_ref}
  incumbent_target_leaders: list
  quarterback_state: object
  coaching_and_scheme_state: object
  prior_season_offense_quality: object
  projected_role_openings: list        # inference, labeled
  role_competition: list
  opportunity_interpretation:          # inference, labeled
    read: string
    confidence: low | medium | high
    contingencies: list
  limitations: list
epistemics:
  observation_vs_inference: every row tagged `observation` or `inference`
  needs_verification: flags on any non-re-verified fact
source_lineage: [...]
```

Rules:

- Only information available at `context_cutoff`. A veteran's later release,
  trade, injury, or breakout must not appear.
- `observation` rows state sourced facts (2022 usage, signed transactions,
  announced hires). `inference` rows state what a contemporaneous analyst
  could reasonably project from those facts, with confidence.
- Depth-chart rows are ordered by prior-season usage from a governed or
  public-release source, not by hindsight role.

## Layer 3 — historical expectation record schema

```yaml
artifact: historical_expectation_record_v0
canonical_player_id: string
class_year: integer
frozen_at: timestamp
predraft_card: {path, sha256}
landing_context: {path, sha256}
nfl_outcomes_included: false
freeze_note: string
```

The sha256 values pin the exact frozen content. Any later edit to a card or
landing context invalidates the expectation record and requires an explicit,
logged re-freeze — silent edits are prohibited.

## Layer 4 — outcome layer (separate)

`outcomes/` artifacts may reference expectation records by hash but must be
produced **after** the freeze. They carry NFL production, availability, role
evolution, and Forecast rows. They must not rewrite any frozen layer.

## Ownership boundary

2022 NFL team context (targets, usage, rosters, coaching state) is
TIBER-Data / TIBER-Teamstate territory. This pilot computes team-context
values directly from the public nflverse release **as pilot evidence only**,
mirroring the classification work in issue #283: the durable home for that
data is a governed TIBER-Data aggregation over
`exports/promoted/nfl/player_season_coverage_v0.json` (2022 rows) plus a
Teamstate landing-context instance. Rookies must not become a second
authority for team context.
