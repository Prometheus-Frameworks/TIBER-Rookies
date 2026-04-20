# TIBER-Rookies Source-of-Truth Audit (Weekend cleanup)

## Scope

This audit maps rookie-data ownership in `TIBER-Rookies` and establishes a single authoritative source per data domain, plus a promotion shape for `Prometheus-Frameworks/TIBER-Data`.

Target doctrine:

- Raw → canonical → derived → display/export.
- One authoritative source per domain.
- Model code reads canonical model-input artifacts.
- UI reads canonical output/display artifacts.
- Raw artifacts stay reproducible inputs, not UI truth.

---

## Current repo flow (high level)

1. **Raw inputs**
   - `data/raw/{season}_combine_results.json`
   - `data/raw/{season}_real_seed_pool.json`
2. **Canonical per-domain processed artifacts**
   - production, draft proxy, context, consensus in `data/processed/`
3. **Derived artifacts**
   - age-adjusted production, projections, trends, route/play profiles
4. **Canonical model output**
   - `exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.json` (+ CSV + manifest)
5. **UI display mapping**
   - `lib/rookies/getRookieCardData.js` + `lib/rookies/mapRookieToCard.js`

---

## Domain ownership contract

## 1) Player identity and metadata

**Authoritative source**

- `exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.json` player row + `context` block for `school`, `class_year`, optional metadata.

**Canonical producer inputs**

- Identity alignment still originates upstream in:
  - `data/raw/{season}_combine_results.json`
  - `data/processed/{season}_college_production.json`
  - `data/processed/{season}_draft_capital_proxy.json`

**Downstream consumers**

- UI mapping: `lib/rookies/normalizeRookieIdentity.js`, `lib/rookies/mapRookieToCard.js`.
- Model merge logic: `scripts/compute_rookie_alpha.py`.

**Notes**

- UI should treat promoted export row + context as identity truth.
- Raw/processed identity rows remain producer-layer inputs only.

## 2) Athletic testing (RAS/SPORQ/combine)

**Authoritative source**

- Model-consumable athletic signal in promoted export:
  - `scores.ras_0_100`
  - `scores.athletic_score_0_100`
  - `scores.athletic_source`
  - `scores.athletic_confidence`
  - `scores.athletic_explainer`

**Canonical producer input**

- `data/raw/{season}_combine_results.json`.

**Auxiliary historical reference (not rookie truth)**

- `data/historical/sporq_historical.json` for historical comp display.

**Downstream consumers**

- Producer: `scripts/compute_rookie_alpha.py`.
- UI display: `lib/rookies/mapRookieToCard.js`; detailed SPORQ comps in `cards/rookies/player.html` via `lib/rookies/sporqHistorical.js`.

## 3) Production

**Authoritative canonical production artifact**

- `data/processed/{season}_college_production.json`.

**Derived production artifacts**

- `data/processed/{season}_age_adjusted_production.json`.
- `data/processed/{season}_player_stats.json`.
- `data/processed/wr_route_profiles/*.json`, `rb_play_profiles/*.json`, `qb_play_profiles/*.json`.

**Model-consumed production source of truth**

- Promoted export `scores.production_0_100` (plus optional `scores.age_adjusted_production_0_100`).

**Downstream consumers**

- Producer computation: `scripts/compute_rookie_alpha.py`.
- Supporting scripts: `scripts/compute_production_scores.py`, `scripts/compute_age_adjusted_production.py`, `scripts/fetch_missing_stats.py`.

## 4) Model inputs

**Authoritative model-input bundle (by season)**

- `data/raw/{season}_combine_results.json`
- `data/processed/{season}_college_production.json`
- `data/processed/{season}_draft_capital_proxy.json`
- optional additive:
  - `data/processed/{season}_prospect_context.json`
  - `data/processed/{season}_age_adjusted_production.json`
  - `data/processed/{season}_positional_consensus.json`

**Canonical consumer**

- `scripts/compute_rookie_alpha.py`.

## 5) Model outputs

**Authoritative source**

- `exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.json`.
- Companion contract files:
  - `exports/promoted/rookie-alpha/{season}_rookie_alpha_predraft_v0.csv`
  - `exports/promoted/rookie-alpha/{season}_manifest.json`

**Other derived output families**

- `exports/promoted/historical-comps/{season}_historical_comps_v0.json`
- `exports/promoted/rookie-ml-lane/*`

## 6) UI display payloads

**Canonical UI base source**

- Promoted Rookie Alpha export JSON above.

**Canonical additive UI supplements**

- `data/processed/{season}_player_stats.json`
- `data/processed/{season}_ppr_projections.json`
- `data/processed/{season}_dynasty_adp.json`
- `data/processed/{season}_yoy_trends.json`

**Display mapping layer**

- `lib/rookies/getRookieCardData.js`
- `lib/rookies/mapRookieToCard.js`
- Board/detail/compare components in `components/rookies/` and `cards/rookies/`.

---

## Conflict ledger

| Domain | Competing files / loaders | Current consumers | Recommended canonical source | Migration action | Safe to deprecate/delete? |
|---|---|---|---|---|---|
| Identity + metadata | UI loader previously merged identity from promoted export **and** combine/production/draft rows. | `lib/rookies/getRookieCardData.js`, `lib/rookies/normalizeRookieIdentity.js` | Promoted export row + `context` block. | UI mapping now resolves identity from promoted export/context only. | Yes for UI-path usage of raw identity joins; keep producer inputs. |
| Athletic display fields | UI card-level athletic truth came from both promoted scores and raw combine rows. | `lib/rookies/mapRookieToCard.js` | Promoted export `scores.*athletic*` fields. | Keep combine raw strictly producer-layer input; card display should not depend on raw row fallback. | Yes for direct UI dependency on `data/raw/*combine_results.json`. |
| Production display fields | `production_0_100` was fetched from both production artifact and promoted export. | `lib/rookies/mapRookieToCard.js` | Promoted export `scores.production_0_100`. | Use promoted score as display truth; keep production file as producer input only. | Yes for UI direct dependency. |
| Draft-capital display fields | `draft_capital_proxy_0_100` was fetched from both draft-proxy artifact and promoted export. | `lib/rookies/mapRookieToCard.js` | Promoted export `scores.draft_capital_proxy_0_100`. | Use promoted score as display truth. | Yes for UI direct dependency. |
| Legacy docs vs runtime behavior | Prototype docs referenced runtime loading of raw + processed inputs directly for UI. | `docs/rookie-card-prototype.md`, runbooks | Promoted export as base UI truth + processed supplements. | Update docs/runbooks to discourage UI raw-file ownership. | No (docs need updates, not deletion). |
| Consensus delta naming | Historical `consensus_delta` concept vs canonical `consensus_delta_positional`. | UI mapping + external consumers | `scores.consensus_delta_positional`. | Enforce positional delta usage and keep market legacy metric marked deprecated. | No (legacy field retained for backward compatibility). |

---

## Refactor decisions applied in this cleanup

1. **UI loader now anchors on promoted exports first** and only supplements display-only artifacts (`player_stats`, `ppr_projections`, `dynasty_adp`, `yoy_trends`).
2. **UI identity normalization now uses promoted export/context** rather than raw combine/production/draft merges.
3. **UI score fields for athletic/production/draft now resolve from promoted output scores**, not raw producer inputs.
4. Added a small **UI data-contract path module** (`lib/rookies/rookieDataContract.js`) to centralize canonical display-loader paths.

---

## Migration notes

### Immediate (this PR)

- Keep raw and processed artifacts intact for reproducibility.
- Remove UI ownership ambiguity by stopping direct UI reads of raw combine/production/draft inputs.

### Next pass

- Add explicit deprecation note in docs for direct UI reads from `data/raw/*` and model-input processed files.
- Optionally emit a dedicated UI-ready seasonal display payload (`exports/promoted/rookie-display/{season}_rookie_display_v1.json`) to reduce runtime multi-file joins.

### Safety notes

- No model formula changes.
- No data fabrication.
- No silent field aliasing beyond documented source precedence.

---

## Proposed promotion/export plan for `TIBER-Data`

Promote only stable, reproducible, clearly named artifacts.

## Recommended folder shape

```text
rookies/
  identity/
    {season}_rookie_identity_registry_v1.json
  athletic/
    {season}_rookie_athletic_testing_registry_v1.json
  production/
    {season}_rookie_production_stats_v1.json
    {season}_rookie_derived_production_v1.json
  model-inputs/
    {season}_rookie_model_inputs_canonical_v1.json
  model-outputs/
    {season}_rookie_alpha_predraft_v0.json
    {season}_rookie_alpha_predraft_v0.csv
    {season}_rookie_alpha_manifest_v0.json
  display/
    {season}_rookie_display_payload_v1.json
```

## Artifact-family guidance

1. **rookie identity registry**
   - Stable keys: `player_id`, `player_name`, `position`, `school`, `class_year`.
   - Provenance fields required.
2. **rookie athletic testing registry**
   - Raw combine metrics + normalized athletic outputs.
   - Include `athletic_source` and confidence.
3. **rookie production stats**
   - Season-level raw/normalized production inputs.
4. **rookie derived production scores**
   - age-adjusted outputs + breakout/explainability signals.
5. **rookie canonical model inputs**
   - Joined, model-ready row schema used by producer (immutable per run).
6. **rookie model outputs/export payloads**
   - Existing promoted alpha bundle and manifests.

## Promotion criteria (gate)

Promote only artifacts that are:

- reproducible from checked-in scripts,
- versioned with explicit schema label,
- validated (hash/count checks where applicable),
- semantically classified (`raw`, `canonical`, `derived`, `display`).

Do **not** promote one-off intermediates, ad hoc debug dumps, or ambiguous fallback artifacts.
