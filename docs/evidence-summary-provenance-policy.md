# Evidence Summary Provenance Policy

**Status:** v1 (governance baseline)
**Applies to:** the `evidence.evidence_summary` and `evidence.context_source` fields in the
Rookie Alpha promoted exports (`exports/promoted/rookie-alpha/*`) and their upstream source
`data/processed/{season}_prospect_context.json`.
**Related:** [`export-contract.md`](export-contract.md) · [`2026-evidence-summary-provenance-audit.md`](2026-evidence-summary-provenance-audit.md) · Issue #245 · Issue #248 · PR #247

## 1. Purpose

`evidence_summary` is a human-readable scouting/research note rendered on public cards. It is
useful for context, but it has repeatedly mixed canonical model facts with unverified third-party
claims presented as fact. This policy defines how such content must be categorized, attributed,
and treated so that research context never masquerades as canonical model truth.

This is a data-governance baseline, not a one-time text cleanup. It is the policy that PR 2 of
Issue #248 will apply to the 2026 data.

## 2. Core principle

> **`evidence_summary` is NOT a canonical model-input truth surface.**

Canonical model truth lives only in the scored, contracted fields (e.g. `scores.*`,
`model_inputs_missing`, `consensus_delta_positional`) defined in `export-contract.md`. Anything in
`evidence_summary` is research/scouting context. The model score is computed from canonical inputs;
it is **not** derived from the prose in `evidence_summary`. The UI already states this via a
persistent caveat (PR #247):

> Research notes may include non-canonical context. Treat as scouting context, not model input truth.

Nothing in `evidence_summary` may contradict or override a canonical field. Where a research note
conflicts with a canonical score (e.g. athletic claims on a `NEUTRAL_DEFAULT` ATH card), it must be
explicitly qualified per §4.

## 3. Claim categories

Every sentence/claim in an `evidence_summary` falls into exactly one of these categories:

| # | Category | Definition | Default treatment |
|---|----------|------------|-------------------|
| 1 | **Canonical model input** | A value that is also a contracted scored field (production, draft capital proxy, ATH source, consensus delta, etc.). | Allowed. Should match the canonical field. Prefer referencing the field rather than restating a number that can drift. |
| 2 | **Sourced public fact** | An objectively checkable, public, free-to-verify fact: official college box-score stats, combine measurements, awards/honors, school, class year. | Allowed. Keep specific and attributable to a public record. |
| 3 | **Attributed external / scouting note** | A named third party's opinion or board placement: analyst big boards, mock-draft ranks, qualitative scouting takes, player comps. | Allowed **only with explicit attribution and as opinion** (see §4). Never stated as fact. |
| 4 | **Unverified research note** | A claim from informal/aggregated research (e.g. "X research batch"), proprietary/paywalled metrics, or historical-leaderboard rankings that cannot be reproduced from public free sources. | Allowed **only** behind an explicit unverified marker, or downgraded to qualitative language. Never stated as a bare fact or precise leaderboard rank. |
| 5 | **Unsupported / remove** | Medical/health causality, injury diagnoses, counterfactual speculation ("would have done X if healthy"), or any claim with no acceptable source. | **Remove or neutralize.** (This is the class PR #247 fixed for Love/Tyson.) |

## 4. Attribution rules by claim type

These are the high-risk claim types most common in the current data. Each has a required treatment.

### 4.1 External analyst boards & mock-draft ranks
*(Brugler / The Athletic, Mel Kiper / ESPN, Tankathon, Bleacher Report, Steelers Depot, "dynasty community", etc.)*

- Must be **attributed to the named source** and phrased as that source's opinion, e.g.
  "Dane Brugler (The Athletic) ranks him 22nd overall" — not "he is the 22nd overall prospect".
- Must not be presented as TIBER's ranking or as consensus fact.
- A retrieval date is preferred where ranks are volatile.

### 4.2 Historical / all-time leaderboards
*("4th all-time since 2014", "#1 all-time since 2004 ahead of Calvin Johnson", "class leader", "fastest since John Ross 2017")*

- These imply a complete, reproducible historical dataset. If TIBER cannot reproduce the leaderboard
  from a free public source, treat as **Category 4 (unverified research note)**.
- Downgrade absolute superlatives to **qualitative, bounded** language
  ("among the top P4 backs by MTF/touch in the available sample") and/or place behind an explicit
  unverified marker. Do not assert a precise all-time rank as fact.
- Cross-player superlatives that name other real players in a ranking ("ahead of Puka Nacua",
  "ahead of Calvin Johnson") require either a reproducible source or removal.

### 4.3 Proprietary / paywalled metrics
*(PFF grades, RAS, SPORQ, NGS model scores, Reception Perception, Dominator Rating, QBR, PBE)*

- Treat as **qualitative context only, never canonical model truth.** A proprietary metric must not
  be used as if it were a TIBER model input.
- Attribute to the metric's owner (e.g. "PFF offense grade", "NGS model").
- Prefer qualitative tiering ("elite per PFF") over a precise paywalled number stated as fact;
  if a number is retained, mark it as the provider's metric, not a TIBER value.
- Where a proprietary athletic claim conflicts with a `NEUTRAL_DEFAULT` ATH score, it must carry the
  qualifier established in PR #247: "Athletic testing data was not incorporated into the model score."

### 4.4 Player comps
*("DJ Moore / Jarvis Landry comp", "Comp (high): Tetairoa McMillan")*

- Allowed as **explicitly labeled projections/opinions** ("comp", "projection"), never as equivalence
  or prediction of outcome. Attribution to a source is preferred when the comp originates externally.

## 5. `context_source` requirements

- Every non-null `evidence_summary` must carry a `context_source` provenance label.
- `context_source` should name the actual sources and, where practical, a retrieval date.
- Informal aggregators (e.g. "X research batch") are acceptable as a provenance label **only** when
  the dependent claims are treated as Category 4 (unverified) per §3–§4 — i.e. the weak source must
  be reflected in weaker claim phrasing, not laundered into bare facts.

## 6. What this policy does NOT change

- It does **not** change model scoring, player ranks, grade formulas, or projection math.
- It does **not** mandate mass-deletion of scouting context. The goal is to **separate canonical
  model truth from research notes** and to attribute/qualify, not to erase useful signal.
- It does **not** require verifying every individual claim. Verification of specific leaderboard
  claims is handled incrementally; this policy defines the *treatment rules*, the audit
  (`2026-evidence-summary-provenance-audit.md`) identifies *where they apply*.

## 7. Application workflow

1. Author/curator classifies each claim using §3.
2. Apply the §4 treatment for the claim type.
3. Edits are made to the **upstream source** (`data/processed/{season}_prospect_context.json`), then
   the promoted export + manifest are regenerated via `scripts/compute_rookie_alpha.py` so the change
   is reproducible (the path established in PR #247).
4. The promoted-export validation step must remain green.
