# Runbook: 2026 Draft-Week Promoted Artifact Handoff (TIBER-Rookies → TIBER-Fantasy)

## Scope and boundary

This runbook is the operational rehearsal path for draft week.

- **TIBER-Rookies** is the authoritative producer lab.
- **TIBER-Fantasy** is the downstream consumer.
- No runtime coupling is introduced.
- Model recompute remains offline (`scripts/compute_rookie_alpha.py`), not in server requests.

## Preconditions

1. You are on the intended commit/tag in `Prometheus-Frameworks/TIBER-Rookies`.
2. Python 3 and Node.js 20+ are available.
3. 2026 source inputs exist:
   - `data/raw/2026_combine_results.json`
   - `data/processed/2026_college_production.json`
   - `data/processed/2026_draft_capital_proxy.json`
   - all three files represent the same 24-player real seed pool identity set (matching `player_id`/`player_name`/`position`/`school`/`class_year`)
   - `production_score_0_100` may still be `null` for a subset of players; this runbook requires canonical identity alignment, not production-score completeness
4. You have write access to `exports/promoted/rookie-alpha/`.
5. You have a handoff channel/path to TIBER-Fantasy (manual bridge).

## Operator checklist (end-to-end)

### 1) Generate the 2026 promoted artifact set

Run:

```bash
python3 scripts/compute_rookie_alpha.py \
  --season 2026 \
  --combine-input data/raw/2026_combine_results.json \
  --production-input data/processed/2026_college_production.json \
  --draft-proxy-input data/processed/2026_draft_capital_proxy.json \
  --output-json exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
  --output-csv exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.csv \
  --output-manifest exports/promoted/rookie-alpha/2026_manifest.json
```

Expected artifacts:

- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json`
- `exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.csv`
- `exports/promoted/rookie-alpha/2026_manifest.json`

### 2) Validate artifact + manifest

Run:

```bash
python3 scripts/validate_promoted_export.py \
  --export-json exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json \
  --manifest exports/promoted/rookie-alpha/2026_manifest.json
```

Expected terminal output:

```text
VALIDATION PASSED
```

If validation fails: stop handoff and regenerate/fix inputs before continuing.

Also review `coverage_summary.input_alignment` in the export JSON/manifest to confirm there were no hidden exclusions from identity mismatches or missing-source joins.

### 3) Verify standalone TIBER-Rookies lab against that artifact

Local smoke check:

```bash
npm run test:runtime-smoke
```

Expected: command exits `0`.

Optional deployed probe (Railway URL):

```bash
curl -fsS https://<tiber-rookies-url>/health
curl -fsSI https://<tiber-rookies-url>/
curl -fsSI "https://<tiber-rookies-url>/cards/rookies/player.html?slug=wr-jordyn-tyson"
curl -fsSI "https://<tiber-rookies-url>/cards/rookies/compare/index.html?left=wr-jordyn-tyson&right=te-kenyon-sadiq"
```

Expected:

- `/health` returns `200` and `status: "ok"`
- `/` returns `302` to `/cards/rookies/board/index.html`
- detail/compare deep links return `200`

### 4) Hand off **the same files** to TIBER-Fantasy

Manual bridge (explicitly still manual):

1. Copy these files from TIBER-Rookies to agreed TIBER-Fantasy ingest staging:
   - `2026_rookie_alpha_predraft_v0.json`
   - `2026_rookie_alpha_predraft_v0.csv`
   - `2026_manifest.json`
2. Preserve filenames exactly.
3. Record source commit SHA from this repo in handoff notes.

### 4b) Post-draft: populate `2026_draft_results.json` and regenerate

After picks are announced, populate `data/processed/2026_draft_results.json` with one entry per drafted or UDFA seed-pool player. The file must be a JSON array — it starts as `[]`.

**Required fields per entry:**

| field | type | notes |
|---|---|---|
| `player_id` | string | must match the seed-pool `player_id` exactly |
| `nfl_team` | string | team abbreviation (e.g. `"KC"`, `"PHI"`) |
| `draft_round` | integer | 1–7 |
| `overall_pick` | integer | overall selection number |
| `is_udfa` | boolean | `true` only for undrafted free agents; omit or set `false` for drafted players |

`draft_day` (1/2/3) and `draft_capital_tier` are derived automatically by `lib/rookies/draftResults.js` and do not need to be populated manually.

**Example — one Day 1 pick, one Day 3 pick, one UDFA:**

```json
[
  {
    "player_id": "wr-jordyn-tyson",
    "nfl_team": "PHI",
    "draft_round": 1,
    "overall_pick": 22,
    "is_udfa": false
  },
  {
    "player_id": "te-tanner-koziol",
    "nfl_team": "KC",
    "draft_round": 5,
    "overall_pick": 158,
    "is_udfa": false
  },
  {
    "player_id": "wr-brenen-thompson",
    "nfl_team": "DEN",
    "draft_round": 7,
    "overall_pick": 245,
    "is_udfa": false
  }
]
```

Seed-pool players who go undrafted and do not sign as UDFAs can be omitted from the file entirely; the UI will treat them as `post_draft_pending`.

After populating, re-run the rehearsal to regenerate artifacts with real draft-capital outcomes:

```bash
npm run ops:rehearse-2026
```

The post-draft UI layer (`postDraftAdjustments.js`) will then apply draft-capital deltas when cards are loaded. Note that only the `computeDraftCapitalAdjustment` function is implemented in v0 — landing-spot, opportunity-path, environment-fit, and insulation adjustments are reserved for future research and return `delta: 0` in this phase.

### 5) Verify `/rookies` in TIBER-Fantasy after ingest

In the TIBER-Fantasy repo/environment, run its ingest gate and then verify the surfaced rookie data at `/rookies`.

Minimum checks in TIBER-Fantasy:

- ingest gate passes for all three files,
- season and model version match expected 2026 pre-draft v0 export metadata,
- `/rookies` renders the promoted cohort without ingest errors.

## Optional one-command rehearsal helper

For local rehearsal in this repo:

```bash
npm run ops:rehearse-2026
```

For local + deployed URL probes:

```bash
RUN_REMOTE_CURLS=1 BASE_URL="https://<tiber-rookies-url>" npm run ops:rehearse-2026
```

This helper reduces operator mistakes but does **not** automate cross-repo handoff.

## Draft-week ready definition (operational)

`TIBER-Rookies` is draft-week ready when all are true on the same commit:

1. 2026 promoted artifact set generated.
2. Validator returns `VALIDATION PASSED`.
3. Standalone smoke verification passes.
4. Manual handoff package is complete (json/csv/manifest, exact names).
5. TIBER-Fantasy confirms successful ingest and `/rookies` verification.

## Remaining limitations (explicit)

- Handoff between repos is still manual.
- No shared auth/persistence/live sync between TIBER-Rookies and TIBER-Fantasy.
- No runtime model recompute.
- This runbook does not replace TIBER-Fantasy's own deploy/rollout runbooks.
