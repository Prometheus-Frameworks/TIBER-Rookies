# Candidate Export Contract: Rookie Transition Profile (v0)

**Status:** implemented as a **candidate artifact** (issue [#263](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/263)),
**schema_version `v0.2.0`** — extended in issue [#267](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/267)
to add `official_postdraft_outcome` (see [`2026-07-10-rookie-transition-profile-postdraft-split-design.md`](reports/2026-07-10-rookie-transition-profile-postdraft-split-design.md)
for that design decision) after a promotion review ([#265](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/265)/
PR [#266](https://github.com/Prometheus-Frameworks/TIBER-Rookies/pull/266)) found `draft_capital`
was being presented as unresolved for players who already had verified post-draft outcomes.
**Architecture:** [`docs/rookie-transition-profile-v0-design.md`](rookie-transition-profile-v0-design.md) (issue #261).

This artifact is an **evidence consolidation layer**, not a score or ranking. It repackages
already-computed values from other promoted/processed artifacts under one schema with mandatory
per-field provenance. It does not replace Rookie Alpha (`docs/export-contract.md`), which remains
the scored artifact.

**This is not a promoted artifact.** Per issue #263's decision enum, a positive decision here
(`may_open_rookie_transition_profile_promotion_review_issue`) authorizes only a *future*
promotion-review issue — it does not itself promote anything. The producer, validator, and the
2026 candidate bytes below are implemented and validated, but they live under
`exports/candidate/`, not `exports/promoted/`, until a separate promotion-review issue explicitly
authorizes copying reviewed bytes into the promoted path.

## Canonical candidate path + filename contract

```text
exports/candidate/rookie-transition-profile/
  {season}_rookie_transition_profile_v0.json
  {season}_rookie_transition_profile_v0.csv
  {season}_manifest.json
```

A future promotion-review issue decides whether, and how, reviewed bytes from this path are
copied into `exports/promoted/rookie-transition-profile/`. Nothing in this document authorizes
that copy in advance.

## JSON contract

Top-level fields:

- `schema_version`: `rookie-transition-profile-v0.2.0`
- `artifact_type`: `rookie_transition_profile`
- `season`
- `generated_at`: ISO-8601 UTC timestamp
- `run_id`
- `disclaimer`: fixed string stating this artifact carries no scores/rankings/predictive claims
- `source_files_used`: the rookie-alpha predraft export plus the five upstream processed files
  read for provenance labels (draft capital proxy, college production, prospect context, drafted
  outcomes, UDFA-signed outcomes)
- `coverage_summary`: `players_total` and, per field family, `players_with_<family>` /
  `players_with_all_families`
- `rows`: one entry per `(player_id, season)`

Row fields:

- `player_id`, `player_name`, `position`, `school`, `class_year` — identity, required
- `draft_capital`, `age_at_entry`, `athletic_testing`, `college_production`,
  `official_postdraft_outcome` — each either absent or a `{value, provenance}` pair (see below)

### The `{value, provenance}` pair

Every governed field is either fully present (`value` populated, `provenance.source_type` one of
the observed/inferred enum values) or fully absent (`value: null`,
`provenance.source_type: "unavailable"`, with a required `notes` explaining why). A field is never
a bare value.

`provenance` object:

| Key | Type | Notes |
|---|---|---|
| `source_type` | enum | See below. Determines observed-vs-inferred. |
| `source_name` | string \| null | Null only when `source_type` is `unavailable`. |
| `source_url` | string \| null | Present when the source is a fetchable URL. |
| `confidence` | float 0.0–1.0 \| null | Null only when `source_type` is `unavailable`. |
| `confidence_band` | `LOW`\|`MEDIUM`\|`HIGH` \| null | Must equal `confidence_to_band(confidence)`. |
| `last_verified_at` | date string \| null | Year must not exceed the artifact's `season`. |
| `notes` | string \| null | Required non-empty when `source_type` is `unavailable`. |

`source_type` enum:

```text
measured_combine            # observed
measured_production_stats   # observed
measured_identity_fact       # observed
official_draft_result        # observed (used by official_postdraft_outcome since v0.2.0)
market_derived_proxy          # inferred
operator_seeded                # inferred (reserved; not used by v0)
estimated_manual_research     # inferred (reserved; not used by v0)
unavailable                    # neither — value is null and notes explains why
```

## Field families implemented in v0

| Family | `source_type` when present | Confidence | Notes |
|---|---|---|---|
| `draft_capital` | `market_derived_proxy` | 0.65 (`MEDIUM`), fixed | `value` is `{big_board_rank, draft_capital_proxy_0_100}`, copied verbatim from the promoted Rookie Alpha export's `scores.draft_capital_proxy_0_100`; `big_board_rank` and the human-readable proxy-rule description are looked up from `data/processed/{season}_draft_capital_proxy.json` by `player_id`. Explicitly labeled a temporary market-investment proxy, not realized draft capital. |
| `age_at_entry` | `measured_identity_fact` | 0.9 (`HIGH`), fixed | Computed via `age_from_dob(dob, season)`, an exact copy of the formula in `scripts/compute_breakout_age.py` (age as of September 1 of the season). `dob` is read from `data/processed/{season}_prospect_context.json`. |
| `athletic_testing` | `measured_combine` | verbatim `athletic_confidence` from Rookie Alpha | `value` is `{athletic_score_0_100, athletic_source}`, copied verbatim from Rookie Alpha's `scores` block. **`NEUTRAL_DEFAULT` rows are treated as `unavailable`, not copied** — see "Known limitations." |
| `college_production` | `measured_production_stats` | 0.85 (`HIGH`), fixed | `value` is `{production_score_0_100}`, copied verbatim from Rookie Alpha's `scores.production_0_100`; the source description is looked up from `data/processed/{season}_college_production.json`. |
| `official_postdraft_outcome` | `official_draft_result` | 0.95 (`HIGH`), fixed | Added in v0.2.0 (#267). `value` is `{status, nfl_team, draft_round, overall_pick, is_udfa, source_status, upstream_provenance_status}`. See below. |

**`official_postdraft_outcome` is deliberately independent of `draft_capital`.** It represents the
*observed* post-draft result; `draft_capital` continues to represent the *pre-draft market proxy*
and is never overwritten or reclassified once an official outcome exists — see the
[design doc](reports/2026-07-10-rookie-transition-profile-postdraft-split-design.md) for why a
single polymorphic field was rejected.

- `value.status`: `"drafted"` or `"udfa_signed"`.
- `value.draft_round` / `value.overall_pick`: integers when `status == "drafted"`; `null` when
  `status == "udfa_signed"` (there is no round/pick for an undrafted signing).
- `value.is_udfa`: boolean, always consistent with `status` (`false` for `drafted`, `true` for
  `udfa_signed`) — validated explicitly.
- `value.source_status` / `value.upstream_provenance_status`: carried through from the source row
  as descriptive value content (the same pattern `draft_capital.value` already uses for
  `big_board_rank`), distinct from this artifact's own `provenance` object.
  `upstream_provenance_status` is `null` when the source has no equivalent field (the UDFA file
  doesn't carry one).
- Sourced from `data/processed/{season}_draft_results.json` first; falls back to
  `data/processed/{season}_day3_udfa_draft_result_profiles.json` only when the player is absent
  from the first (this is how `te-daequan-wright`'s UDFA signing is captured). `unavailable` only
  when neither source has a verified record.

Per the approved design, the following are **not implemented in v0** and must not be added without
a new design review: role/archetype descriptors, landing-spot context (an NFL team is present only
as part of the observed `official_postdraft_outcome`, never as modeled landing-spot analysis),
granular `wr_route_profiles` production detail, any row-level composite "evidence quality" score,
and any `evidence_summary`-style free text.

## Known limitations (implementation notes beyond the design doc)

- **No per-field verification timestamps exist upstream.** `data/processed/{season}_draft_capital_proxy.json`,
  `..._college_production.json`, and `..._prospect_context.json` carry no per-row date. `last_verified_at`
  is therefore set to the artifact's own `generated_at` date for every field in every row — an
  honest "as of this run" timestamp, not a claim about when the underlying fact was individually
  re-verified. A future version should add real per-source timestamps if the upstream files gain them.
- **`NEUTRAL_DEFAULT` athletic rows are `unavailable`, not `measured_combine`.** Rookie Alpha
  assigns a fixed `50.0` placeholder score internally when no usable RAS/SPORQ data exists, purely
  for its own scoring math. Copying that placeholder into this artifact as if it were a measurement
  would misrepresent absence of evidence as evidence, so it is intentionally treated as
  `unavailable` here instead.
- **The athletic-score semantic-drift caveat is carried in `notes`.** Per
  `docs/athletic-score-normalization-audit.md`, the `athletic_score_0_100`/`athletic_source` fields
  are an in-house composite, not the Kent Lee Platte RAS percentile the name may suggest. Every
  `athletic_testing` field's `provenance.notes` repeats this caveat so a consumer reading only this
  artifact still sees it.
- **Confidence constants for `draft_capital`, `college_production`, and
  `official_postdraft_outcome` are fixed, not per-row.** Unlike athletic testing (which reuses
  Rookie Alpha's already-variable `athletic_confidence`), these families don't have an existing
  per-player confidence signal upstream, so a single reasoned constant is used for the whole
  family (0.65/MEDIUM for the proxy, 0.85/HIGH for production, 0.95/HIGH for the observed
  post-draft outcome — the highest fixed constant in the artifact, since `external_verified`
  sourced outcomes are about as certain as this repo's provenance model gets). This is a
  deliberate simplification for v0, not a discovered fact.
- **`official_postdraft_outcome.provenance.last_verified_at` uses the source row's own
  `ingested_at` field when present** (`data/processed/{season}_draft_results.json` rows carry
  one), falling back to the artifact's `generated_at` date only when the source has no per-row
  timestamp (the UDFA file has none). This is the one field family in the artifact that prefers a
  real upstream timestamp over the "as of this run" fallback used everywhere else.
- **`data/processed/{season}_draft_capital_proxy.json`'s `draft_capital_proxy_source` text was
  repaired (#267)** for the 17 rows the #266 review flagged as leaking real draft-outcome text
  (e.g. "2026 NFL Draft actual pick: Round 3, Pick 69") into what should be proxy-methodology-only
  text. Only the free-text field was edited; `draft_capital_proxy_0_100`, `big_board_rank`, and
  `draft_capital_proxy_pending_conversion` were left untouched for all 101 rows in that file.

## Validation

Schema-level (mirrors `scripts/devy_signal_registry.py`'s enum/shape validation style):

```bash
python3 -c "
from pathlib import Path
import json
from scripts.validate_rookie_transition_profile import validate_artifact_shape
payload = json.loads(Path('exports/candidate/rookie-transition-profile/2026_rookie_transition_profile_v0.json').read_text())
errors = validate_artifact_shape(payload)
print('PASSED' if not errors else errors)
"
```

Manifest + hash validation (mirrors `scripts/validate_promoted_export.py`):

```bash
python3 scripts/validate_rookie_transition_profile.py \
  --export-json exports/candidate/rookie-transition-profile/2026_rookie_transition_profile_v0.json \
  --manifest exports/candidate/rookie-transition-profile/2026_manifest.json
```

Expected output: `ROOKIE TRANSITION PROFILE VALIDATION PASSED`.

The validator's signature invariant — enforced on every row and field — is that **no value may
appear without a provenance object, and every provenance object must declare a valid
`source_type`**. This directly targets the class of defect found in issue #257 (data whose real
nature was undiscoverable without reading source code).

Passing this validator is a **precondition** for a future promotion-review issue to consider
promoting this candidate — it is not itself a promotion event.

## Regenerating the candidate artifact

```bash
python3 scripts/compute_rookie_transition_profile.py --season 2026
```

Reads (all defaulted by season, overridable via flags):

- `exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.json` (base player population,
  athletic testing, production score, draft capital proxy score — already a promoted artifact)
- `data/processed/{season}_draft_capital_proxy.json` (big-board rank + proxy-rule source text)
- `data/processed/{season}_college_production.json` (production-score source text)
- `data/processed/{season}_prospect_context.json` (`dob`)
- `data/processed/{season}_draft_results.json` (verified drafted outcomes, checked first)
- `data/processed/{season}_day3_udfa_draft_result_profiles.json` (verified UDFA-signing outcomes,
  checked only when a player is absent from the drafted-outcomes file)

Writes the JSON/CSV/manifest triplet under `exports/candidate/rookie-transition-profile/`. No new
score, rank, or derived value is computed — every governed field is either copied verbatim from an
already-promoted/processed source or a deterministic lookup (age from date of birth).

## Path to promotion (not yet authorized)

This document describes the artifact and its validation, and confirms it already satisfies the
mechanical shape of `docs/source-of-truth-audit.md`'s promotion gate (reproducible from
checked-in scripts, versioned with an explicit schema label, validated, semantically
classifiable as a **repackaged/derived-passthrough** artifact). Satisfying that shape is
necessary but not sufficient for promotion.

**Promotion itself — copying or pointing reviewed bytes into
`exports/promoted/rookie-transition-profile/` — requires a separate, future promotion-review
issue**, per issue #263's decision enum: a positive decision from this implementation issue
(`may_open_rookie_transition_profile_promotion_review_issue`) authorizes opening that review
issue, nothing more. This document does not authorize promotion, cross-repo promotion (e.g. into
TIBER-Data), or any Forecast consumption. See the design doc's "Forecast-consumability
requirements" section, which this implementation satisfies structurally but which still requires
separate authorization to act on.

## Regression tests

- `tests/test_validate_rookie_transition_profile.py` — schema/enum/provenance-shape validation,
  manifest-consistency checks, `official_postdraft_outcome`-specific semantics (status enum,
  `is_udfa`/status agreement, drafted-requires-round/pick, udfa-forbids-round/pick), plus tests
  that run full validation against the real committed 2026 candidate artifact and assert its
  48/48 post-draft-outcome coverage and that `draft_capital` never leaks outcome text.
- `tests/test_compute_rookie_transition_profile.py` — per-field builder tests (including the
  `NEUTRAL_DEFAULT`-is-unavailable rule, the `age_from_dob` formula match, drafted/UDFA-signed/
  unavailable outcome building, and drafted-results-take-priority-over-UDFA-file ordering),
  coverage-summary counting, and JSON/CSV output writing.
