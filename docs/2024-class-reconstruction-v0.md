# 2024 class coverage and MHJ reconstruction candidate

This candidate addresses [#301](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/301) after Joe authorized execution on October 10, 2026. It adds a complete **78-player drafted QB/RB/WR/TE census**, a coverage record for every subject, sourced final-season college observations for the existing 15 seeds plus MHJ, and separate MHJ college/pre-draft and draft-day cards. Independent review remains pending.

The candidate emits **zero qualified new grades**. Twelve of the 15 legacy raw-production rows contradict primary school records; none of the 15 manual normalized scores has a retained, reproducible 2023 reference population. The current producer's neutral defaults would produce numbers without repairing that evidence. Existing processed inputs, promoted outputs, manifests, runtime and the frozen ML archive are preserved.

## Scope and evidence

| Census domain | Subjects |
|---|---:|
| QB | 11 |
| RB | 20 |
| WR | 35 |
| TE | 12 |
| Total | 78 |

The denominator comes from the [official NFL 2024 Record & Fact Book](https://static.www.nfl.com/image/upload/league/apps/league-site/media-guides/2024/2024_Record_and_Fact_Book_incl_Supplemental.pdf), printed/PDF pages 34–37. Individual draft facts are reconciled with a retained [nflverse factual identity CSV](https://raw.githubusercontent.com/nflverse/nfldata/master/data/draft_picks.csv). Only draft/identity fields from that CSV are admitted; its NFL performance fields are excluded. Source-document hashes and current retrieval times are in the source ledger; publisher documents and analyst content are not republished.

Sione Vaki is included as an NFL-drafted **RB**, although the secondary CSV position is empty. Filtering that CSV alone would incorrectly return 77. The factbook prints Ja'Lynn Polk in round 1 at overall pick 37; the candidate explicitly reconciles his round to 2. Eight name, suffix, position or round reconciliations are recorded. IDs for previously absent prospects are proposed local keys, not canonical Data admissions. School labels from the primary record are preserved, including Southern California/legacy USC.

UDFAs are a separate supplemental cohort, requiring an explicit signing source and inclusion decision. No UDFA is inferred from absence in the draft census. This is skill-position coverage, not a census of all NFL positions.

## Coverage and input-integrity result

| Measure | Result |
|---|---:|
| Census subjects with an identity/coverage record | 78 |
| Previously represented in the legacy seed/export | 15 |
| Previously absent from seed/export | 63 |
| Final-season college-production candidates sourced in this pass | 16 |
| Identity-only records, college production not yet acquired | 62 |
| Legacy raw-production rows with contradictions | 12 / 15 |
| Qualified new pre-draft or post-draft grades | 0 |

Representative final-season raw discrepancies are below; the machine-readable audit checks **all 15** subjects and retains each original manual score/source claim. School sources and factual counts are in [source facts](../data/historical/reconstruction_2024/source_facts_v0.json).

| Subject | Legacy 2023 claim | Primary-source candidate |
|---|---|---|
| Caleb Williams | 252 completions / 373 attempts | 266 / 388 |
| Jayden Daniels | 300 completions / 415 attempts | 236 / 327 |
| Drake Maye | 276 / 436; 5 interceptions | 269 / 425; 9 interceptions |
| Xavier Worthy | 57 catches / 760 yards / 9 TD | 75 / 1,014 / 5 |
| Ladd McConkey | 61 / 841 / 5 | 30 / 478 / 2 |
| Brock Bowers | 71 / 1,182 / 6 | 56 / 714 / 6 |
| Jonathon Brooks | 175 carries; 21 catches / 147 receiving yards | 187 carries; 25 / 286 |
| Blake Corum | 226 carries / 1,240 yards / 12 TD | 258 / 1,245 / 27 |
| Trey Benson | 213 / 1,401 / 13 | 156 / 906 / 14, with explicit school-source conflict |
| MarShawn Lloyd | 156 / 969 / 9; 14 catches / 97 receiving yards | 116 / 820 / 9; 13 / 232 |
| Braelon Allen | 219 / 1,100; 29 catches / 205 receiving yards | 181 / 984; 28 / 132 |
| Adonai Mitchell | 46 catches / 845 yards / 8 TD | 55 / 845 / 11 |

Nabers, Odunze and Brian Thomas Jr. reconcile on the selected raw operands. That does **not** qualify their normalized scores, testing, context, consensus or expected-capital inputs. The audit's derived one-decimal efficiency rates use factual numerators/denominators rather than preserving inaccurate source text.

Benson's March 2024 school recap prints **905** rushing yards in its player career table (PDF page 28), while its narrative and current school roster report **906**. The candidate retains 906 provisionally, records both observations and requires review. It does not silently erase the one-yard source conflict; either value still contradicts the legacy 1,401.

## MHJ profile and historical separation

The [MHJ pre-draft candidate](../data/historical/reconstruction_2024/predraft_cards/2024_wr_marvin_harrison_jr_predraft_v0.json) has sourced 2021–2023 receiving production and his 2022/2023 unanimous All-American and 2023 Biletnikoff facts. Its pre-draft cutoff is April 24, 2024, 23:59:59 UTC. No actual draft pick/team or NFL performance is an input to that card.

Testing is unavailable: the existing historical SPORQ row is `DNQ` with no timed/jump operands. It is used only to audit missingness, not to ingest a third-party grade. DNQ means neither zero nor a demonstrated athletic weakness. Age/declaration, team shares, route/alignment and separation fields are left unavailable where evidence has not been qualified.

The [separate landing candidate](../data/historical/reconstruction_2024/landing_context/2024_wr_marvin_harrison_jr_landing_context_v0.json) records 2024 round 1, pick 4, Arizona. These public facts do not substitute for a canonical Data draft-results handoff. NFL outcomes live only in the linked [Research study](https://github.com/Prometheus-Frameworks/TIBER-Research/issues/33).

The shared builder reads draft facts for the census and player identity. College-lane validation rejects actual draft fields, and explicit card field selection excludes pick/team and NFL outcomes; this is an output exclusion guarantee, not structural isolation of builder inputs.

All sources were retrieved now. A historical factual reconstruction is not an original 2024 TIBER forecast, and no immutable contemporaneous expectation receipt is claimed. These candidate cards extend the 2023 pilot's separation principles without changing its contract or admitting a new runtime family.

## Grading qualification and next work

The model binding pins base commit `e78df9df32adb6568ccfbe8ff2b7210d9d99e8a6`, the current Alpha and production producer hashes, and the legacy input/export bytes. The published historical export reports model `rookie-alpha-predraft-v0.5.0`. The documented base weighting is 35% athletic, 45% production, 20% expected draft capital; the current producer also implements adjustments and missing-data defaults. No formula, weighting or contextual penalty is changed, and no Alpha scoring pass is represented as completed.

The existing production producer needs the full eligible **2023** positional reference populations to reconstruct the 2024 class. An unauthenticated CFBD request returned HTTP 401 and this environment has no CFBD API key. Replacing that population with the 78 draftees, or translating factual corrections into invented z-scores, would change the model. The candidate therefore leaves normalized scores and grades unavailable.

The remaining work is concrete:

1. Independently review the retained factual rows, all eight identity resolutions and the Benson source conflict.
2. Acquire/qualify the remaining 62 college records and the positional reference populations through an eligible source path, preserving season filters and receipts.
3. Qualify testing, context and contemporaneous expected-capital evidence. Any neutral defaults need an explicitly disclosed sensitivity/qualification decision rather than automatic completeness.
4. Coordinate [#242](https://github.com/Prometheus-Frameworks/TIBER-Rookies/issues/242) for a canonical Data 2024 draft-results handoff. Do not copy this census into the empty processed runtime draft file.
5. Run the pinned model only for qualified subjects, identify retrospective pre-draft and post-draft grades separately, and review the candidate before any separately authorized promotion.

## Reproduction and validation

```bash
python3 scripts/build_2024_reconstruction.py
python3 scripts/build_2024_reconstruction.py --check
python3 -m unittest discover -s tests -p 'test_build_2024_reconstruction.py'
```

The builder performs no network access. `--check` validates input hashes, identities, census counts, college source bindings and byte-identical generated output without writing. The focused tests reject incomplete cohorts, duplicate identities, future draft operands in the college lane, unresolved sources, and numeric fallback grades. It writes only the historical candidate directory.

Runtime/export/ML validators are not required for this isolated addition because none of those producer contracts or artifacts change. A protected-file hash comparison against the pinned base is included in the execution record. Independent review and new grades remain pending; neither #301 nor #242 is closed by this candidate.
