# Player Card Verification Audit — 2026-07-18

**Auditor role:** TIBER Player Card Verification Auditor (automated scheduled routine)  
**Scope:** 2025 and 2026 rookie-alpha predraft exports, all `evidence_summary` text, `score_caveats`, `context_flags`, and rendered card sources  
**Policy:** Approved-source policy — explicit URL-backed source mappings required; `manual_seed_*` and `manual_historical_seed` count as internal seeds with no external URL.  
**Rule:** Flag any claim involving violence, arrests, shootings, medical/mental health, suspension, or reputationally harmful events unless explicitly backed by an approved source reference.

---

## SUMMARY

| Severity | Count |
|---|---|
| BLOCKER | 1 |
| WARNING | 17 |
| DATA GAP | 1 |
| VERIFIED / LOW-RISK | ~95+ players |

**Immediate action required:** 1 blocker in the 2025 class (Travis Hunter, evidence_summary). Do not publish this card with current text.

---

## BLOCKER FINDINGS

### Travis Hunter — 2025 class, WR, Rank 8

- **Status:** BLOCKER
- **File:** `exports/promoted/rookie-alpha/2025_rookie_alpha_predraft_v0.json` (line 763)
- **Source field:** `evidence.context_source = "manual_historical_seed"` (no URL)
- **Unsupported claims:**
  - `"recovered from gunshot injury in 2023"` — shooting/violence claim about a real person with zero URL-backed source
- **Missing source mappings:** No external reference. `manual_historical_seed` is an internal seed type with no publicly verifiable URL. Per approved-source policy, this claim cannot be published.
- **High-risk claims:** This sentence directly describes a violent crime victimizing a named real person. If inaccurate in any detail (date, nature of injury, whether "gunshot" is the correct term), it creates serious reputational and legal exposure. Even if accurate, it requires an explicit approved-source URL (e.g., a news article URL) before being shown on a published card.
- **Suggested rewrite:** Remove the gunshot reference entirely. If the event is relevant to the player's profile path (e.g., as a factor in the timeline of their freshman impact season), rephrase without naming the injury cause: _"First true impact at 19 as Colorado freshman; timeline affected by a personal event in 2023."_ Or simply omit the explanatory clause if the underlying fact (age-19 impact) is the relevant signal.
- **Verdict: DO NOT PUBLISH** — Remove or replace the shooting reference before this card is shown publicly.

---

## WARNING FINDINGS — 2025 CLASS

All 2025 injury claims below share the same source issue: `context_source = "manual_historical_seed"` (no URL). The card renderer does not currently display a caveat on `evidence_summary` text in a way that disclaims specific factual claims about injury type/timing.

### TreVeyon Henderson — 2025 class, RB, Rank 20

- **Status:** WARNING
- **Source:** `manual_historical_seed` (no URL)
- **Unsupported claims:** `"Injuries in 2022-2023 limited ceiling; injury risk a persistent context flag."` — no URL to confirm injury timing, type, or ongoing risk assessment
- **High-risk claims:** "Persistent" injury risk characterization presented as fact could affect how NFL teams or users perceive the player without a source to verify the claim
- **Suggested rewrite:** `"Injuries in 2022–2023 carry a context flag on this profile; the model did not independently verify injury details."` Or flag via `context_flags` rather than stating as prose fact.
- **Verdict: NEEDS REVISION**

### Tyler Shough — 2025 class, QB, Rank 25

- **Status:** WARNING (low severity)
- **Source:** `manual_historical_seed` (no URL)
- **Unsupported claims:** `"lengthy injury-plagued career at Texas Tech"` — unspecified injuries over an unspecified career duration; no source
- **Suggested rewrite:** `"multi-season career at Texas Tech"` — retain the factual context without characterizing injury severity without a source
- **Verdict: NEEDS REVISION**

### Tre Harris — 2025 class, WR, Rank 33

- **Status:** WARNING
- **Source:** `manual_historical_seed` (no URL)
- **Unsupported claims:** `"Injury limited his final year to 8 of 12 games."` — specific game-count claim for injury cause, no URL
- **Suggested rewrite:** `"Appeared in 8 of 12 games in his final season."` (state the fact; omit the causal attribution to injury unless a source URL is present)
- **Verdict: NEEDS REVISION**

### Jalen Royals — 2025 class, WR, Rank 48

- **Status:** WARNING
- **Source:** `manual_historical_seed` (no URL)
- **Unsupported claims:** `"before foot injury ended season"` — specific injury type (foot), no URL
- **Suggested rewrite:** `"before his season ended early"` — retain the factual context (truncated season) without specifying the medical cause
- **Verdict: NEEDS REVISION**

### Tory Horton — 2025 class, WR, Rank 56

- **Status:** WARNING
- **Source:** `manual_historical_seed` (no URL)
- **Unsupported claims:** `"Knee injury in 2024 (5 games, 26/353/1 TDs)"` — specific injury body part (knee) as causal explanation, no URL
- **Suggested rewrite:** `"2024 was truncated (5 games, 26/353/1 TDs)"` — state the volume fact; drop the injury type attribution without a source
- **Verdict: NEEDS REVISION**

### Arian Smith — 2025 class, WR, Rank 57

- **Status:** WARNING (elevated)
- **Source:** `manual_historical_seed` (no URL)
- **Unsupported claims:** `"Extensive injury history (wrist, knee, fibula, ankle)"` — lists four named body parts as a factual injury history claim; no URL
- **High-risk claims:** A multi-injury list presents as clinical/medical fact and directly impacts the player's perceived durability. If any body part is incorrect, this creates reputational risk. Four named injuries require at minimum one source URL.
- **Suggested rewrite:** `"Has carried multiple injury context flags during his college career; specific history not independently verified."` Or list only what has an approved source.
- **Verdict: NEEDS REVISION**

### Quinn Ewers — 2025 class, QB, Rank 62

- **Status:** WARNING (low severity)
- **Source:** `manual_historical_seed` (no URL)
- **Unsupported claims:** `"dealing with injury concerns and inconsistency that dropped him to the 7th round"` — injury concerns attributed as causal for draft position; no URL
- **Suggested rewrite:** `"fell to the 7th round"` — omit the causal injury attribution without a source
- **Verdict: NEEDS REVISION**

---

## WARNING FINDINGS — 2026 CLASS

### Chris Bell — 2026 class, WR, Rank 15

- **Status:** WARNING + INCONSISTENCY
- **File:** `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json` (lines 1440, 1492, 1498)
- **Source:** `context_source = "Research agent 2026-04-09 (KeepTradeCut / Dynasty Nerds / PlayerProfiler post-injury consensus)"` (no direct URL; third-party aggregator sourcing)
- **Unsupported claims:**
  - `score_caveats`: `"ACL tear (pre-draft 2026)"` — specific injury type, no URL
  - `context_flags`: `"pre_draft_acl_march_2026"` — specific month claim
  - `evidence_summary`: `"Carries a pre-draft injury context flag (November 2025)"` — says November 2025
- **Inconsistency:** The `evidence_summary` attributes the pre-draft injury context to **November 2025**, while the `context_flags` name encodes **March 2026** and `score_caveats` says **pre-draft 2026** without a month. These three fields are in conflict about when the injury-relevant event occurred. This inconsistency itself is a claim-accuracy problem regardless of source.
- **High-risk claims:** If the ACL and the November 2025 event are two different injuries, the card simultaneously references both without distinguishing them. If they are the same event with a date error, one of these fields is factually wrong.
- **Suggested action:** Reconcile the date across all three fields before publishing. Require a URL to confirm the ACL timing. If the November 2025 date was an earlier (non-ACL) event, clarify both separately or omit the injury type from cards.
- **Verdict: NEEDS REVISION**

### Jadarian Price — 2026 class, TE, Rank 28

- **Status:** WARNING
- **Source:** `context_source = "manual_seed_2026"` (no URL)
- **Unsupported claims:** `"missed nearly two full seasons early in his career (injury-affected)"` — duration and causation asserted without URL
- **Suggested rewrite:** `"limited availability early in his career"` or omit the clause if not URL-backed
- **Verdict: NEEDS REVISION**

### Justin Joly — 2026 class, TE, Rank 30

- **Status:** WARNING (low severity)
- **Source:** `context_source = "manual_seed_2026"` (no URL)
- **Unsupported claims:** `"did not run the 40 at the combine (injury-affected)"` — attributes the decision to an injury without URL
- **Note:** The combine skipping is publicly verifiable from combine results; the injury cause attribution is not. The combine result itself is low-risk; the parenthetical injury attribution is the gap.
- **Suggested rewrite:** `"did not run the 40 at the combine"` — drop the injury attribution unless a URL is added
- **Verdict: NEEDS REVISION**

### Deion Burks — 2026 class, WR, Rank 39

- **Status:** WARNING (low severity)
- **Source:** `context_source = "manual_seed_2026"` (no URL)
- **Unsupported claims:** `"injury-affected 2024"` — vague but still a medical cause claim without URL
- **Suggested rewrite:** `"limited 2024 season"` — factual description without attributing to injury without a source
- **Verdict: NEEDS REVISION**

---

## WARNING FINDINGS — NAMED ANALYST RANKINGS WITHOUT URLs (2026 CLASS)

The following `manual_seed_2026` entries cite named external analysts or publications with specific ranking numbers but without source URLs. Under the approved-source policy, named third-party rankings require URL evidence.

| Player | Rank | Unsupported Named Claim | Source Field |
|---|---|---|---|
| Omar Cooper Jr. | 14 | "Dane Brugler ranks him 22nd overall (The Athletic), Tankathon has him at #24" | `manual_seed_2026` |
| Germie Bernard | 20 | "first Georgia State player on The Athletic's College Freaks List" | `manual_seed_2026` |
| Elijah Sarratt | 22 | "Mel Kiper ranked him 9th among WRs; Tankathon projects him #50 overall; DJ Moore/Jarvis Landry comp" | `manual_seed_2026` |
| Deion Burks | 39 | "Bleacher Report ranks him #11 WR post-combine" | `manual_seed_2026` |
| Ja'Kobi Lane | 40 | "Bleacher Report ranks him 21st among WRs; ESPN Scouts Inc. places him 91st overall" | `manual_seed_2026` |
| Zavion Thomas | 43 | "ESPN Matt Miller projects him at pick 268" | `manual_seed_2026` |

**Status for all above: WARNING**  
**Verdict: NEEDS REVISION** — Either add URL citations or rewrite to remove the named-analyst attribution. Presenting a specific analyst's ranking as a fact without the URL to verify it exposes the system to accuracy claims if rankings have changed or were misremembered.

**Note on hedging:** Carson Beck (rank 33) self-flags `"top 2% ever' not independently verified"` in his evidence_summary — this is the appropriate pattern. The analyst ranking claims above do not have equivalent hedging.

---

## DATA GAP

### Kaelon Black — 2026 class, RB, Rank 31

- **Status:** DATA GAP
- **File:** `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json` (line 2880)
- **Issue:** Kaelon Black is the only player among all 48 in the 2026 export with no `evidence` object at all. His entry contains `player_id`, `player_name`, `position`, `scores`, `model_inputs_missing`, and `rookie_alpha_rank`, but there is no `context` block and no `evidence` block.
- **Card impact:** `mapRookieToCard.js` and `deriveRookieProfileSummary.js` derive all rendered text from `alphaPlayer.context` and `alphaPlayer.evidence`. For this player, `evidenceSummary` will be null, `evidenceTags`, `contextFlags`, and `translationFlags` will all be empty arrays, `contextSignals.raw` will be null, and `breakoutAge` / `youngBreakoutFlag` / `breakoutLabel` will all be null/false.
- **Risk:** The card will render with a blank "Research Notes & Translation Signals" section and 0/7 evidence metrics. This is misleading — it implies insufficient_evidence (his `evidence_tier` is `"insufficient_evidence"`) with no explanation, rather than a data entry gap.
- **Verdict: NEEDS REVISION** — Add a minimal `context` and `evidence` block or add an explicit note that this player's context data was not populated at export time.

---

## VERIFIED / LOW-RISK FINDINGS — 2026 CLASS

The following evidence_summary patterns are **verified or low-risk** and require no immediate action:

- **Jeremiyah Love (RB, rank 1):** Evidence summary explicitly states `"specific medical causality is not a verified model input"` for the injury-adjusted flag. This is appropriate hedging. Source is X research batch with cross-verification. **Safe to ship.**

- **Jordyn Tyson (WR, rank 4):** Evidence summary says `"two seasons carry an injury-adjusted context flag"` — framed as a context flag (not a specific injury claim). The `combine_drills_skipped_hamstring` context flag is shown as a tag chip with `"combine_drills_skipped_hamstring"` label (factual: he skipped combine drills; hamstring is the stated reason from X research batch sourcing). This is a borderline case — the combine skip is verifiable; the hamstring attribution appears in the X research batch source. **Low risk; monitor for future source upgrades.**

- **Players with null evidence_summary from `compute_breakout_age.py`:** Fernando Mendoza, Drew Allar, Chris Brazzell II, Garrett Nussmeier, Ty Simpson, Max Klare, Oscar Delp, Nick Singleton, Emmett Johnson, Kendrick Law — these have `evidence_summary: null` and are rendered with no research notes text. No fabricated claims, no risk. **Safe to ship.**

- **Players with X research batch or @ffdataroma sourcing and appropriate hedging:** Makai Lemon, KC Concepcion, Denzel Boston, Zachariah Branch, Jonah Coleman, Dae'Quan Wright, Antonio Williams, Kaytron Allen — these have named research sources with dates and explicit hedges for unverified comparative ranks. **Safe to ship.**

- **Kenyon Sadiq (TE, rank 9):** `"precise class rank unverified"` hedge present for SPORQ claim. `compute_breakout_age.py` + SPORQ notes sourcing. **Safe to ship.**

---

## SOURCE-MAPPING SYSTEMIC ISSUE

**`manual_seed_2026` and `manual_historical_seed` are internal seed types with no URL fields.** Any specific factual claim (injury type, named analyst ranking, named list membership) inside these entries is unverifiable under the approved-source policy. This affects approximately **22 players in the 2026 class** and **all ~67 players in the 2025 class** where `context_source = "manual_historical_seed"`.

The existing `evidence-summary-provenance-policy.md` document in docs/ describes the provenance approach. The gap is that the policy permits internal seeds for general profile text but does not currently enforce URL-requirement gates for specific medical claims or named-attribution rankings within those seeds.

**Recommended policy tightening (outside scope of this routine — flagged for human review):**
1. Medical claims (injury type, timing, body part) in any evidence_summary require a URL source, regardless of seed type.
2. Named analyst/publication rankings require a URL source, regardless of seed type.
3. Violence/shooting/arrest claims require a URL source — blocker gate, not a warning.

---

## APPENDIX: DETERMINISTIC CARD TEXT (LOW RISK)

These text sources are computed deterministically from numeric scores and template strings. They present no fabrication or hallucination risk:

- `deriveRookieProfileSummary.js` → `archetype`, `projection`, `profileSummary`, `identityNote`, `boardSummary` — generated from position label + score band thresholds
- `postDraftAdjustments.js` → `landingSpotNote`, `opportunityNote` — template strings driven by `draftRound`/`overallPick`/`is_udfa` fields
- `mapRookieToCard.js` → `readinessLabel`, metric display strings — computed from available metric counts

No action required on these paths.

---

*Audit completed: 2026-07-18. This file is the output of the automated TIBER Player Card Verification Auditor routine.*
