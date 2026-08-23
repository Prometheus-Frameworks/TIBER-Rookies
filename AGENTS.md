# AGENTS.md — TIBER-Rookies

## 1) Repo purpose
TIBER-Rookies is the authoritative **Rookie Alpha producer lab** and a **minimal standalone static runtime** for rookie surfaces.

It owns rookie evaluation/model work, rookie cards, rookie board UI, rookie data shaping, promoted rookie exports, manifest validation, and rookie-specific handoff artifacts.

## 2) Non-goals / repo boundaries
- Not a full draft room.
- Not a live backend.
- Not the runtime dependency for TIBER-Fantasy.
- Not the canonical cross-repo data authority.

Cross-repo framing:
- **TIBER-Data** owns canonical contracts and governed cross-repo handoff artifacts.
- **TIBER-Fantasy** is a downstream consumer/product/API surface.
- **TIBER-FORGE** is a deterministic grading/ranking engine over canonical inputs.

## 3) Agent roles
When operating in this repo, agents should:
- Keep Rookie Alpha producer outputs reproducible and validated.
- Keep standalone rookie runtime behavior stable.
- Preserve clear downstream handoff artifacts.
- Prefer explicit uncertainty (`unknown` / `unavailable`) over fabricated continuity.
- If source truth is missing, reduce scope instead of inventing details.

## 4) Common failure modes
- Treating temporary 2026 proxy draft capital as true draft capital.
- Silent export schema or manifest semantic changes.
- Breaking downstream assumptions in promoted artifacts.
- Fabricating player facts/stats/scouting blurbs to fill missing data.
- Removing or weakening ML lane warnings that it is experimental/additive.
- Automating away manual operator decision points in handoff flow without explicit request.

## 5) Legal and data-source hygiene
- Never scrape, copy, store, or model on proprietary/paywalled third-party analyst content unless explicit written permission/licensing is documented.
- Preserve source metadata and provenance.
- Never fabricate player facts, scouting claims, production stats, team mappings, draft capital, RAS/SPORQ values, or sourced blurbs.

## 6) Rookie model rules
- Do not modify model logic unless explicitly requested.
- As currently documented, the deterministic pre-draft Rookie Alpha formula is:
  - RAS 35%
  - Production 45%
  - Draft capital proxy 20%
  - Age-at-entry not implemented
- Before modifying model logic, verify the current formula against README/docs and relevant producer scripts.
- Never treat 2026 proxy draft capital as true draft capital outcomes.

## 7) Export/manifest/contract rules
- Never silently change export schemas or manifest semantics.
- Preserve manifest/export contract behavior and metadata consistency.
- If touching export logic, run validation or explain exactly why not.
- Preserve downstream compatibility expectations for consumer ingest.

## 8) Runtime/UI rules
- Preserve standalone static runtime behavior and route expectations.
- If touching runtime routes, run smoke tests or explain exactly why not.
- Do not introduce runtime recomputation of model logic at request time.

## 9) ML lane rules
- ML lane is experimental and additive; it does not replace deterministic Rookie Alpha scoring.
- ML lane is **not a promoted family**. Its frozen archive lives under `exports/experimental/rookie-ml-lane/`, never under `exports/promoted/` (#286 WP-2).
- The frozen archive is immutable. Generated runs go to `runs/rookie-ml-lane/` (gitignored); never point the producer at the archive, and never regenerate the nine pinned historical artifacts.
- Its probability-shaped fields are not calibrated probabilities and confer no promotion eligibility. Never surface them as probabilities or wire them into a promoted, Forecast, or Fantasy contract.
- If touching ML lane work, preserve warnings that outputs are directional when data is sparse or provenance is weak.
- Keep provenance and warning artifacts intact, including the `experimental_status_v0.json` sidecar every run emits.
- Promoting this lane is a separate governed decision, not an implementation detail of any other change.

## 10) Known commands
Only use/document known canonical commands from repo docs and scripts.

### Node/runtime
- `npm start`
- `npm run test:runtime-smoke`
- `npm run ops:rehearse-2026`

### Producer + validation
- `python3 scripts/compute_rookie_alpha.py`
- `python3 scripts/validate_promoted_export.py \
  --export-json exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
  --manifest exports/promoted/rookie-alpha/2026_manifest.json`

### Experimental ML lane
- `python3 scripts/compute_rookie_ml_lane.py`
- `python3 scripts/validate_experimental_integrity.py`
- `python3 scripts/validate_experimental_integrity.py --run-dir runs/rookie-ml-lane`

If a requested command is not listed in `package.json`, `README.md`, or repo scripts, do not guess. Mark it non-canonical and ask for confirmation.

## 11) PR checklist
Before opening a PR:
- Confirm scope is limited to requested files.
- Confirm no fabricated player/content facts were introduced.
- Confirm legal/data-source hygiene constraints are preserved.
- If export logic changed: run `python3 scripts/validate_promoted_export.py ...` or explain exactly why not.
- If runtime route behavior changed: run `npm run test:runtime-smoke` or explain exactly why not.
- If ML lane changed: keep explicit experimental/additive warnings and run `python3 scripts/validate_experimental_integrity.py`.
- If handoff flow changed: preserve manual operator decision points unless explicitly asked to change them.
- Summarize downstream impact and residual risk explicitly.

## 12) Done criteria
A task is done when:
- Requested scope is complete and no prohibited files/logic/data were modified.
- Contract-sensitive changes include validation evidence or explicit rationale for not running checks.
- Any runtime-sensitive changes include smoke-test evidence or explicit rationale for not running checks.
- No fabricated facts are present.
- Unknown/missing truth is represented honestly (`unknown` / `unavailable`) or scope is reduced.
