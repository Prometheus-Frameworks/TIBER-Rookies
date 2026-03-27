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
   - all three files represent the same placeholder/proxy prototype pool (matching `player_id`/`player_name`/`position`)
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
curl -fsSI "https://<tiber-rookies-url>/cards/rookies/player.html?slug=wr-malik-ford"
curl -fsSI "https://<tiber-rookies-url>/cards/rookies/compare/index.html?left=wr-malik-ford&right=te-owen-hale"
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
