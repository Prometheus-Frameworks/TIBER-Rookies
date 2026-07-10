# Promoted Export Contract: Rookie Transition Profile (v0)

**Status:** implemented (issue [#263](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/263)).
**Architecture:** [`docs/rookie-transition-profile-v0-design.md`](rookie-transition-profile-v0-design.md) (issue #261).

This artifact is an **evidence consolidation layer**, not a score or ranking. It repackages
already-computed values from other promoted/processed artifacts under one schema with mandatory
per-field provenance. It does not replace Rookie Alpha (`docs/export-contract.md`), which remains
the scored artifact.

## Canonical promoted path + filename contract

```text
exports/promoted/rookie-transition-profile/
  {season}_rookie_transition_profile_v0.json
  {season}_rookie_transition_profile_v0.csv
  {season}_manifest.json
```

## JSON contract

Top-level fields:

- `schema_version`: `rookie-transition-profile-v0.1.0`
- `artifact_type`: `rookie_transition_profile`
- `season`
- `generated_at`: ISO-8601 UTC timestamp
- `run_id`
- `disclaimer`: fixed string stating this artifact carries no scores/rankings/predictive claims
- `source_files_used`: the rookie-alpha predraft export plus the three upstream processed files
  read for provenance labels (draft capital proxy, college production, prospect context)
- `coverage_summary`: `players_total` and, per field family, `players_with_<family>` /
  `players_with_all_families`
- `rows`: one entry per `(player_id, season)`

Row fields:

- `player_id`, `player_name`, `position`, `school`, `class_year` — identity, required
- `draft_capital`, `age_at_entry`, `athletic_testing`, `college_production` — each either absent
  or a `{value, provenance}` pair (see below)

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
official_draft_result        # observed (reserved; not used by v0 — see Known limitations)
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

Per the approved design, the following are **not implemented in v0** and must not be added without
a new design review: role/archetype descriptors, landing-spot context, granular
`wr_route_profiles` production detail, any row-level composite "evidence quality" score, and any
`evidence_summary`-style free text.

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
- **Confidence constants for `draft_capital` and `college_production` are fixed, not per-row.**
  Unlike athletic testing (which reuses Rookie Alpha's already-variable `athletic_confidence`),
  these two families don't have an existing per-player confidence signal upstream, so a single
  reasoned constant is used for the whole family (0.65/MEDIUM for the proxy, 0.85/HIGH for
  production). This is a deliberate simplification for v0, not a discovered fact.

## Validation

Schema-level (mirrors `scripts/devy_signal_registry.py`'s enum/shape validation style):

```bash
python3 -c "
from pathlib import Path
import json
from scripts.validate_rookie_transition_profile import validate_artifact_shape
payload = json.loads(Path('exports/promoted/rookie-transition-profile/2026_rookie_transition_profile_v0.json').read_text())
errors = validate_artifact_shape(payload)
print('PASSED' if not errors else errors)
"
```

Manifest + hash validation (mirrors `scripts/validate_promoted_export.py`):

```bash
python3 scripts/validate_rookie_transition_profile.py \
  --export-json exports/promoted/rookie-transition-profile/2026_rookie_transition_profile_v0.json \
  --manifest exports/promoted/rookie-transition-profile/2026_manifest.json
```

Expected output: `ROOKIE TRANSITION PROFILE VALIDATION PASSED`.

The validator's signature invariant — enforced on every row and field — is that **no value may
appear without a provenance object, and every provenance object must declare a valid
`source_type`**. This directly targets the class of defect found in issue #257 (data whose real
nature was undiscoverable without reading source code).

## Regenerating the artifact

```bash
python3 scripts/compute_rookie_transition_profile.py --season 2026
```

Reads (all defaulted by season, overridable via flags):

- `exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.json` (base player population,
  athletic testing, production score, draft capital proxy score)
- `data/processed/{season}_draft_capital_proxy.json` (big-board rank + proxy-rule source text)
- `data/processed/{season}_college_production.json` (production-score source text)
- `data/processed/{season}_prospect_context.json` (`dob`)

Writes the JSON/CSV/manifest triplet above. No new score, rank, or derived value is computed —
every governed field is either copied verbatim from an already-promoted/processed source or a
deterministic lookup (age from date of birth).

## Promotion path

Follows `docs/source-of-truth-audit.md`'s existing promotion gate: reproducible from checked-in
scripts (`scripts/compute_rookie_transition_profile.py`), versioned with an explicit schema label
(`schema_version`), validated (`scripts/validate_rookie_transition_profile.py`, hash/shape checks),
and semantically classified (`derived`/`display` — this artifact computes nothing new, so it is
best classified as a **repackaged/derived-passthrough** artifact, not `raw`).

This document authorizes promotion of `rookie_transition_profile_v0` within TIBER-Rookies only.
Cross-repo promotion (e.g. into TIBER-Data) and any Forecast consumption remain unauthorized and
out of scope — see the "Forecast-consumability requirements" section of the design doc, which this
implementation satisfies structurally but which requires separate authorization to act on.

## Regression tests

- `tests/test_validate_rookie_transition_profile.py` — schema/enum/provenance-shape validation,
  plus two tests that run full validation against the real committed 2026 artifact.
- `tests/test_compute_rookie_transition_profile.py` — per-field builder tests (including the
  `NEUTRAL_DEFAULT`-is-unavailable rule and the `age_from_dob` formula match), coverage-summary
  counting, and JSON/CSV output writing.
