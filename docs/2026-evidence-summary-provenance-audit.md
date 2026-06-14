# 2026 Evidence Summary Provenance Audit

**Status:** v1 (representative survey, not an exhaustive claim-by-claim verification)
**Scope:** `evidence.evidence_summary` across the 2026 promoted Rookie Alpha export
(`exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json`) and its source
`data/processed/2026_prospect_context.json`.
**Policy:** [`evidence-summary-provenance-policy.md`](evidence-summary-provenance-policy.md)
**Related:** Issue #248 · PR #247

## How to read this

This audit identifies the **claim classes** present in the 2026 summaries and recommends a treatment
for each class, using the categories from the provenance policy (§3). Per the policy, it does **not**
verify every individual claim — it gives representative examples and marks each class as **safe**,
**needs qualifier/attribution**, or **remove/mark-unverified**. Treatment is applied later (PR 2 of
Issue #248) at the source, then regenerated.

## Coverage snapshot

- Players in 2026 export: **48**
- Players with a non-null `evidence_summary`: **38**
- Players with `evidence_summary: null`: **10** (no action)
- Dominant `context_source`: informal aggregated research — "X research batch (April 2026):
  @ffdataroma, Scott Barrett, …" and "Wikipedia + X research …". Per policy §5, claims resting on
  these labels default to **Category 4 (unverified)** treatment unless independently public-sourced.

Approximate class incidence across the 38 summaries (a summary can contain several classes):

| Claim class | ~Count | Policy category |
|---|---|---|
| Historical / all-time leaderboards | ~16 | 4 — unverified research note |
| Proprietary / paywalled metrics | ~13 | 4 — qualitative only |
| Player comps | ~12 | 3 — attributed opinion |
| External analyst boards / mock ranks | ~6 | 3 — attributed opinion |
| Sourced public facts (stats/combine/awards) | most | 2 — allowed |
| Medical / health causality | (fixed in PR #247) | 5 — remove/neutralize |

## Class-by-class findings

### A. Sourced public facts — **SAFE**
*Category 2.* Box-score production, combine measurements, awards, school/class.

- Examples: "49 catches for 545 yards and 2 TDs in 2025, leading ACC TEs in receiving yards"
  (Sam Roush); "4.26 40-yard dash (fastest at 2026 combine)" (Brenen Thompson); "Biletnikoff
  semifinalist" (Germie Bernard).
- **Treatment:** keep. Ensure each remains specific and attributable to a public record. No change
  required beyond removing any that turn out to be unverifiable.

### B. External analyst boards & mock-draft ranks — **NEEDS ATTRIBUTION**
*Category 3.* Named third-party board placements.

- Examples: "Dane Brugler ranks him 22nd overall (The Athletic), Tankathon has him at #24"
  (Omar Cooper Jr.); "Mel Kiper ranked him 9th among WRs; Tankathon projects him #50 overall"
  (Germie Bernard); "Bleacher Report ranks him #11 WR post-combine" (Deion Burks); "Dynasty
  community ranks him RB2 of class" (Jadarian Price).
- **Status today:** mostly already attributed to a named source — good.
- **Treatment:** ensure phrasing is **opinion, not fact** ("Brugler ranks him 22nd", not "he is the
  22nd prospect"); never present as TIBER's or consensus ranking. Add retrieval dates where volatile.
  "Dynasty community ranks him RB2" needs a concrete source or downgrade to Category 4.

### C. Historical / all-time leaderboards — **REMOVE OR MARK UNVERIFIED**
*Category 4.* Absolute superlatives implying a complete reproducible dataset.

- Examples: "Career 0.335 MTF/touch (P4, min 425 carries since 2014): 4th all-time behind Bijan
  Robinson, David Montgomery, Bucky Irving" (Jeremiyah Love); "Dominator Rating 0.43 at age <19 …
  #1 all-time since 2004 (ahead of Calvin Johnson 0.40)" (KC Concepcion); "31.2% career target rate
  — #1 since 2021 among non-slot WRs (ahead of Puka Nacua 30.6%)" (Jordyn Tyson); "fastest WR since
  John Ross 4.22 in 2017" (Brenen Thompson); recurring "class leader".
- **Highest-risk class.** These read as authoritative facts but rest on informal research and cannot
  be reproduced from a free public source. Cross-player superlatives that name real players are
  especially sensitive.
- **Treatment:** downgrade to bounded/qualitative language ("among the top P4 backs by MTF/touch in
  the available sample") and/or place behind an explicit unverified marker. Do not assert a precise
  all-time rank as fact. Remove "ahead of <named player>" claims unless reproducibly sourced.

### D. Proprietary / paywalled metrics — **QUALITATIVE ONLY**
*Category 4.* Provider-owned scores.

- Examples: "SPORQ 95.6", "PFF Offense Grade 89.9 (class leader)" (Jeremiyah Love); "77.6 overall
  PFF grade" (Ja'Kobi Lane); "9.98 RAS (top 2% ever)" (Malachi Fields); "NGS model: #1 in 2026 FBS
  class (86.19)", "Zone success rate 85.6% (Reception Perception)" (Jordyn Tyson).
- **Treatment:** attribute to the provider and treat as qualitative context, never as a TIBER model
  input. Prefer tiering ("elite per PFF") over a precise paywalled number stated as fact. Where a
  proprietary athletic claim sits on a `NEUTRAL_DEFAULT` ATH card, retain the PR #247 qualifier:
  "Athletic testing data was not incorporated into the model score."

### E. Player comps — **LABEL AS PROJECTION**
*Category 3.*

- Examples: "DJ Moore / Jarvis Landry comp"; "Comp (high): Tetairoa McMillan / Allen Robinson.
  Comp (low): Josh Doctson" (Jordyn Tyson); "comp: AJ Brown 3.28, Ja'Marr Chase 3.75" (Makai Lemon).
- **Treatment:** keep but ensure each is explicitly labeled a comp/projection (most already are),
  never an equivalence or outcome prediction.

### F. Medical / health causality — **ALREADY HANDLED**
*Category 5.* Injury diagnoses, body-part claims, health counterfactuals.

- Status: neutralized for Jeremiyah Love (knee) and Jordyn Tyson (hamstring / "confirmed healthy" /
  injury-causality) in **PR #247**, at source + regenerated export. A scan of the current 2026 source
  and export shows the targeted phrases removed.
- **Treatment:** spot-check remaining summaries for any other medical-causality phrasing during PR 2;
  apply the same neutralization. No known outstanding instances at time of writing.

## Recommended PR 2 ordering (when policy is approved)

1. Class C (historical leaderboards) and Class D athletic claims on `NEUTRAL_DEFAULT` cards — highest
   risk of presenting unverifiable/conflicting claims as fact.
2. Class B attribution tightening and the un-sourced "dynasty community" style claims.
3. Class D remaining proprietary numbers → qualitative/attributed.
4. Final Class F spot-check.

All edits go to `data/processed/2026_prospect_context.json`, then regenerate the promoted export +
manifest via `scripts/compute_rookie_alpha.py`, keeping the promoted-export validation step green.
Preserve useful scouting signal by qualifying/attributing rather than deleting.
