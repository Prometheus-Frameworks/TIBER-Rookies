# Design: `rookie_transition_profile_v0`

**Status:** design only — not implemented.
**Issue:** [#261](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/261)
**Builds on:** [#255](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/255) (audit),
[#257](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/257) (TE quarantine),
[#259](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/259) (historical-comps
regeneration).

This document designs the first governed rookie evidence artifact. It does not implement it,
does not modify Forecast, does not claim predictive value, and does not convert any existing
prose into production data. Nothing here is authorized for implementation until a separate issue
picks it up.

## Why this artifact, and why not a new score

Rookie Alpha (`exports/promoted/rookie-alpha/`) already produces a governed, scored artifact.
This is deliberately **not** another scoring model. The #255 audit found that the facts feeding
Rookie Alpha — draft capital, age, athletic testing, production — are real, but scattered across
many files with inconsistent, per-family provenance conventions, and that no artifact in the repo
separates "observed fact" from "derived/proxy value" in a single standardized way. `rookieDataContract.js`
was found to be a misnomer (an unenforced path builder), and `evidence_summary` prose was found
to still be the primary "evidence" surface despite an explicit policy that it must never be
canonical.

`rookie_transition_profile_v0` is an **evidence consolidation layer**: one governed artifact per
draft class that repackages already-computed observed facts under one schema, with mandatory
per-field provenance, and nothing else. It answers "what do we actually know about this rookie,
and how do we know it" — not "how good is this rookie." If TIBER-Forecast ever wants rookie
evidence, this is the file it would read; Rookie Alpha remains the file it would read for scores,
unchanged.

## Artifact purpose

Provide a single, versioned, provenance-backed record per rookie-class player that:

- consolidates observed/sourced facts already computed elsewhere (draft capital, age, athletic
  testing, production) under one schema instead of requiring a consumer to read five files with
  five different provenance conventions;
- makes the observed-vs-inferred boundary a validated, machine-checkable property of every
  field, not a convention a consumer has to intuit from field names or prose;
- makes zero predictive or scoring claims — it is not a ranking and must never be presented as one.

## Row grain

**One row per `(player_id, season)`**, where `season` is the player's rookie/draft season —
matching the existing convention used by `data/processed/{season}_*.json` and
`exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.json`. A player appears in
exactly one season's artifact (their draft class), not once per year of eligibility (that is
Devy's job, and Devy is explicitly out of scope here — see "Excluded scope" below).

v0 covers the **pre-draft** snapshot only, mirroring Rookie Alpha's predraft/postdraft split.
A postdraft revision (analogous to `..._postdraft_v0.json`) is deferred; see open questions.

## Schema / contract (proposed)

Path convention (mirrors `exports/promoted/rookie-alpha/` and `exports/promoted/historical-comps/`):

```text
exports/promoted/rookie-transition-profile/
  {season}_rookie_transition_profile_v0.json
  {season}_rookie_transition_profile_v0.csv
  {season}_manifest.json
```

Top level:

```json
{
  "schema_version": "rookie-transition-profile-v0.1.0",
  "artifact_type": "rookie_transition_profile",
  "season": 2026,
  "generated_at": "2026-07-09T00:00:00+00:00",
  "run_id": "rookie-transition-profile-2026-<timestamp>",
  "disclaimer": "This artifact is an evidence consolidation layer. It contains no scores, no rankings, and no predictive claims. It is not Rookie Alpha and does not replace it.",
  "source_files_used": ["..."],
  "coverage_summary": { "players_total": 0, "players_with_any_missing_field": 0 },
  "rows": [ /* see below */ ]
}
```

Per-row shape — every non-identity field is a `{value, provenance}` pair, never a bare value:

```json
{
  "player_id": "wr-jordyn-tyson",
  "player_name": "Jordyn Tyson",
  "position": "WR",
  "school": "Arizona State",
  "class_year": 2026,

  "draft_capital": {
    "value": { "big_board_rank": 6, "draft_capital_proxy_0_100": 95.0 },
    "provenance": {
      "source_type": "market_derived_proxy",
      "source_name": "Seeded big-board rank, pre-draft proxy conversion",
      "source_url": null,
      "confidence": 0.5,
      "confidence_band": "MEDIUM",
      "last_verified_at": "2026-04-01",
      "notes": "Not equivalent to realized NFL draft capital; see export-contract.md 2026 proxy rule."
    }
  },
  "age_at_entry": {
    "value": 21,
    "provenance": {
      "source_type": "measured_identity_fact",
      "source_name": "dob (data/processed/2026_prospect_context.json)",
      "source_url": null,
      "confidence": 0.9,
      "confidence_band": "HIGH",
      "last_verified_at": "2026-03-15",
      "notes": "Computed via age_from_dob(dob, season) as of Sept 1 of season, matching compute_breakout_age.py."
    }
  },
  "athletic_testing": {
    "value": { "athletic_score_0_100": 82.8, "athletic_source": "RAS_SPORQ_BLEND" },
    "provenance": {
      "source_type": "measured_combine",
      "source_name": "RAS/SPORQ blend per compute_rookie_alpha.py",
      "source_url": null,
      "confidence": 0.85,
      "confidence_band": "HIGH",
      "last_verified_at": "2026-03-20",
      "notes": "See docs/athletic-score-normalization-audit.md: this is an in-house composite, not the Kent Lee Platte RAS percentile the field name may suggest."
    }
  },
  "college_production": {
    "value": { "production_score_0_100": 81.2 },
    "provenance": {
      "source_type": "measured_production_stats",
      "source_name": "CFBD 2025 season stats (normalized production score)",
      "source_url": null,
      "confidence": 0.8,
      "confidence_band": "HIGH",
      "last_verified_at": "2026-03-10",
      "notes": null
    }
  }
}
```

CSV companion: one flattened row per player with dotted column names
(`draft_capital.value.draft_capital_proxy_0_100`, `draft_capital.provenance.source_type`, etc.),
mirroring how `docs/export-contract.md`'s CSV flattens the JSON's nested `scores` block.

Manifest: identical shape to the existing rookie-alpha manifest (`input_files` with
`sha256`/`row_count`, `output_files` with `sha256`, `export_metadata` mirroring the top-level
export metadata) — no new manifest schema is needed.

## Provenance model

One canonical provenance object shape, reused by every field family (generalizes the
per-category provenance objects already used by `scripts/devy_signal_registry.py` and the
`athletic_source`/`athletic_confidence`/`athletic_explainer` triplet already used by
`compute_rookie_alpha.py`):

| Key | Type | Notes |
|---|---|---|
| `source_type` | enum (below) | Determines observed-vs-inferred classification |
| `source_name` | string | Human-readable source description |
| `source_url` | string \| null | Present when the source is a fetchable URL (e.g. a CFBD query) |
| `confidence` | float 0.0–1.0 | Matches existing `athletic_confidence`/`breakout_confidence` convention |
| `confidence_band` | enum `LOW`\|`MEDIUM`\|`HIGH` | Matches devy's `DevyConfidenceBand`; coarse, UI-facing |
| `last_verified_at` | date string | May not be later than the artifact's `season`-implied cutoff |
| `notes` | string \| null | Free text; used for caveats like the athletic-score semantic-drift note |

`source_type` enum (initial, extendable):

```text
measured_combine            # observed
measured_production_stats   # observed
measured_identity_fact       # observed (dob, school, class_year)
official_draft_result        # observed (post-draft only)
market_derived_proxy          # inferred (draft_capital_proxy_0_100, big_board_rank)
operator_seeded                # inferred (matches devy/day2-signal convention)
estimated_manual_research     # inferred (matches the wr_route_profiles "estimated" rows found in #255)
unavailable                    # neither; value is null and must carry a reason in notes
```

A field is never allowed to appear without its provenance object. This is the artifact's core
enforcement mechanism, and it directly targets the specific failure mode #255 and #257 found:
data whose real nature (observed vs. relabeled/estimated) was undiscoverable without manually
reading source code. Validation must reject any row where a value is present but its provenance
object is missing, or where `source_type` is missing/invalid.

## Observed versus inferred

Classification is a pure function of `provenance.source_type`, not a per-field ad hoc judgment
call — mirroring the `frozenset` "compatible scopes" membership-test pattern already used in
`scripts/compute_historical_comps.py`:

```python
OBSERVED_SOURCE_TYPES = frozenset({
    "measured_combine", "measured_production_stats",
    "measured_identity_fact", "official_draft_result",
})
INFERRED_SOURCE_TYPES = frozenset({
    "market_derived_proxy", "operator_seeded", "estimated_manual_research",
})
```

`unavailable` is neither — it is an explicit absence, not a value of either kind. This mirrors
`data/processed/2026_yoy_trends.json`-style `null` handling but makes the *reason* for nullness a
required field rather than an implicit one.

## Confidence / evidence semantics

- `confidence` (float) and `confidence_band` (enum) live **only** inside each field's provenance
  object — there is no single blended row-level "evidence quality score." Inventing one would be
  a new derived ranking dressed as evidence, which the issue's hard boundary explicitly forbids
  ("do not claim predictive value").
- `evidence_summary`-style free prose is **excluded from v0 entirely**. Per
  `docs/evidence-summary-provenance-policy.md`, that field is explicitly non-canonical, and this
  artifact's entire purpose is to be a canonical, structured alternative — mixing prose back in
  would undermine it. A future version could add a `context.narrative_notes` block **only** if it
  reuses the existing 5-category claim classification and carries its own `context_source`,
  never as a substitute for a `provenance` object on a real field.

## Versioning strategy

- `schema_version` follows the existing `rookie-alpha-predraft-v0.X.Y` convention:
  `rookie-transition-profile-v0.1.0`.
- Additive-only changes (new optional field families, new `source_type` enum values) bump minor.
- Any field removal, rename, or semantic change (e.g. changing what `market_derived_proxy` means)
  bumps major and requires updating this document, per `AGENTS.md`'s existing rule: "Never
  silently change export schemas or manifest semantics."
- No field may be removed without a deprecation note, mirroring how
  `market_investment_delta_legacy` was deprecated-not-deleted in the Rookie Alpha contract.

## Promotion path

Follows the same producer → validate → promote path already established by every other governed
artifact in this repo, and the promotion gate already defined in `docs/source-of-truth-audit.md`
("Promotion criteria (gate)": reproducible from checked-in scripts, versioned with explicit
schema label, validated with hash/count checks, semantically classified):

1. A producer script (e.g. `scripts/compute_rookie_transition_profile.py`, not implemented here)
   would read already-computed sources (`data/raw/{season}_combine_results.json`,
   `data/processed/{season}_college_production.json`,
   `data/processed/{season}_draft_capital_proxy.json`,
   `data/processed/{season}_prospect_context.json`'s `dob`) and **only repackage** them under
   this schema — it must not compute any new derived score.
2. A validator script (e.g. `scripts/validate_rookie_transition_profile.py`, mirroring
   `scripts/validate_promoted_export.py`'s hash/field checks and
   `scripts/devy_signal_registry.py`'s enum/shape checks) enforces the schema, the
   provenance-object-required rule, and manifest hash/row-count integrity.
3. Promotion to `exports/promoted/rookie-transition-profile/` only after the validator passes,
   matching every other promoted family in this repo.
4. Cross-repo promotion (e.g. into TIBER-Data, per the proposed folder shape in
   `docs/source-of-truth-audit.md`) is explicitly **not** part of v0 and is not authorized by this
   design.

## Validation expectations

A validator for this artifact must check, at minimum:

1. `schema_version` matches the current constant (mirrors devy's
   `CURRENT_DEVY_SCHEMA_VERSION` check).
2. Required top-level fields present (`disclaimer`, `season`, `generated_at`, `run_id`,
   `source_files_used`, `coverage_summary`, `rows`).
3. Every row has required identity fields (`player_id`, `player_name`, `position`, `school`,
   `class_year`) and no duplicate `player_id`.
4. **Every non-null field value has a `provenance` object; every `provenance` object has a valid
   `source_type` from the enum.** This is the artifact's signature invariant and the direct
   answer to what #257 found missing: a machine-checkable rule that would have caught "WR data
   relabeled as TE" or "estimated route-profile rows presented as CFBD-observed" at validation
   time instead of via manual audit.
5. `last_verified_at` is not later than the artifact's season-implied cutoff (mirrors devy's
   `last_verified_year <= as_of_year` check).
6. Manifest hash/row-count cross-check identical to `scripts/validate_promoted_export.py`.
7. Artifact is deterministic for identical inputs and `generated_at` (mirrors the historical-comps
   contract's determinism requirement).

## Forecast-consumability requirements

Modeled directly on `docs/tiber-fantasy-consumer-contract.md`, which already defines how a real
downstream consumer ingests a promoted triplet from this repo:

1. Required files: `{season}_rookie_transition_profile_v0.json`, `.csv`, `{season}_manifest.json`.
   Missing any file is a hard ingest failure.
2. Manifest/export metadata must match exactly; input/output hashes must match recomputed SHA-256
   values; `row_count` must match where present.
3. **A consumer must never treat a field whose `provenance.source_type` is in
   `INFERRED_SOURCE_TYPES` as ground truth.** This is the artifact-specific addition beyond the
   generic Rookie Alpha contract: it operationalizes the observed-vs-inferred distinction for the
   actual downstream reader, not just as an internal convention.
4. Fields with `source_type: "unavailable"` must be treated as missing, never defaulted or
   imputed by the consumer.
5. This artifact does not replace Rookie Alpha. A consumer wanting scores still reads Rookie
   Alpha; this artifact is additive evidence context only.

### How this would eventually enter the Forecast capability path

Per #255's framing of Forecast's reference path (`governed source artifact → Forecast
mirror/rehearsal path → validation → threshold review → production-binding review →
implementation → activation verification`), `rookie_transition_profile_v0` — once actually
implemented and promoted — would be a candidate for step 1 only: **the governed source artifact**.
Every subsequent step (a Forecast-side mirror/rehearsal reader, validation against Forecast's own
gates, threshold review, production-binding review, implementation, activation verification) is
explicitly out of scope for this design and would each require their own separate authorization
in TIBER-Forecast. This design does not authorize any of them.

## Candidate field families evaluated

| Family | v0 decision | Why |
|---|---|---|
| Identity (`player_id`, `player_name`, `position`, `school`, `class_year`) | **In** | Required join key; already observed with existing per-field `*_source` provenance in `data/raw/*_real_seed_pool.json`. |
| Draft capital context | **In, as inferred** | Real signal, but #255 confirmed `draft_capital_proxy_0_100` is explicitly a temporary market-investment proxy, not realized draft capital — included with `source_type: market_derived_proxy` and a mandatory caveat note, never silently presented as a fact. |
| Age | **In, as observed** | `dob` + `age_from_dob()` is a mature, real, already-computed fact (`scripts/compute_breakout_age.py`). Included as `measured_identity_fact`. |
| Athletic testing | **In, as observed, with a caveat** | The `athletic_source`/`athletic_confidence` pattern is the best-governed observed-vs-inferred mechanism already in the repo. Included verbatim, but every row's provenance `notes` must carry the semantic-drift caveat from `docs/athletic-score-normalization-audit.md` (the field is an in-house composite, not literally Kent Lee Platte RAS) so a Forecast consumer can't inherit that ambiguity silently. |
| College production profile | **Partial — aggregate score only** | `production_score_0_100` (from `compute_production_scores.py`) is a real, governed, single computed value with clean provenance and is included. The granular `wr_route_profiles/` family is **excluded from v0**: #255 found only 12 of 66 files are genuinely CFBD-observed (`source_url` present) while 54 are `source_url: null` estimated/manual rows with no structural flag distinguishing them. Consolidating that mixed family into a "governed" artifact today would import the same ambiguity this artifact exists to remove. Cleaning up that family is a natural prerequisite follow-up, not part of this design. |
| Role/archetype descriptors | **Excluded from v0** | The only existing role data (`docs/post-draft-alpha-role-opportunity-join-2026.md`) is explicitly self-documented as inspect-only, "heuristic v0," and non-scoring, and per the #255 audit its underlying join script was found `BROKEN` in the last internal audit with the fix not re-verified. Not safe to promote as governed evidence yet. |
| Landing-spot context | **Excluded from v0** | Same reasoning as role/archetype: `docs/post-draft-alpha-team-context-join-2026.md`'s join is explicitly inspect-only/non-scoring and was also found broken. The one exception: `nfl_team` (which team drafted the player) is a pure observed fact once `official_draft_result` provenance exists post-draft — deferred to a postdraft revision of this artifact (see open questions), not v0. |
| Evidence quality/confidence | **In, as a mechanism, not a score** | Implemented as the per-field `confidence`/`confidence_band` inside each provenance object (see above) — deliberately not a row-level composite, to avoid smuggling in a new implicit ranking. |

## Open questions

1. **Postdraft revision.** Should there be a `rookie_transition_profile_v0` postdraft companion
   (mirroring Rookie Alpha's predraft/postdraft split) that adds `official_draft_result`-sourced
   `nfl_team`/`draft_round`/`overall_pick`? Left open; v0 as designed is predraft-only.
2. **Age framing.** Should `age_at_entry` be absolute (as designed) or class-relative (e.g. a
   percentile within the draft class)? A relative framing edges toward a derived/scored dimension
   and needs its own discussion before being added.
3. **Devy boundary.** Should any Devy-discovered prospect ever graduate into this artifact once
   they enter their actual draft season? Proposed answer: yes, at that point they stop being a
   Devy prospect and become a normal row here like any other rookie — but the transition mechanism
   itself is not designed here and should be its own follow-up.
4. **Route-profile cleanup dependency.** If the `wr_route_profiles/` mixed-provenance issue found
   in #255 is cleaned up (adding a structural `is_estimated` flag or splitting the family), should
   this artifact's `college_production` field family expand to include per-route detail? Left as
   a natural v0.2 candidate once that prerequisite lands.
5. **CSV flattening depth.** Dotted-column flattening of nested `{value, provenance}` objects
   could get wide once several field families are included. Whether to also emit a
   provenance-omitted "values-only" CSV variant for simple consumers is left open.

## Excluded scope (explicit)

- No implementation of the producer or validator script.
- No modification to Rookie Alpha, its formula, or its weights.
- No modification to TIBER-Forecast.
- No claim that any field in this design predicts NFL outcomes.
- No conversion of `evidence_summary` or any other existing prose into structured fields.
- No redesign of Devy, the role-opportunity join, the team-context join, or any other existing
  Rookies system — those are referenced only to explain why their outputs are excluded from v0.

## Decision

```text
rookie_evidence_artifact_design_recorded
```

This records only the architecture above. It does not authorize implementation of the producer
or validator scripts, does not authorize promotion of any artifact, and does not authorize
Forecast consumption of Rookies data in any form.
