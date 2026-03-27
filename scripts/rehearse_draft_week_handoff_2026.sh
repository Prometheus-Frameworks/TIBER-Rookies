#!/usr/bin/env bash
set -euo pipefail

SEASON="2026"
EXPORT_DIR="exports/promoted/rookie-alpha"
EXPORT_JSON="${EXPORT_DIR}/${SEASON}_rookie_alpha_predraft_v0.json"
EXPORT_CSV="${EXPORT_DIR}/${SEASON}_rookie_alpha_predraft_v0.csv"
MANIFEST_JSON="${EXPORT_DIR}/${SEASON}_manifest.json"

BASE_URL="${BASE_URL:-http://localhost:3000}"
RUN_REMOTE_CURLS="${RUN_REMOTE_CURLS:-0}"

printf '\n[1/4] Generate promoted %s artifact set\n' "$SEASON"
python3 scripts/compute_rookie_alpha.py \
  --season "$SEASON" \
  --combine-input "data/raw/${SEASON}_combine_results.json" \
  --production-input "data/processed/${SEASON}_college_production.json" \
  --draft-proxy-input "data/processed/${SEASON}_draft_capital_proxy.json" \
  --output-json "$EXPORT_JSON" \
  --output-csv "$EXPORT_CSV" \
  --output-manifest "$MANIFEST_JSON"

printf 'Generated files:\n'
ls -l "$EXPORT_JSON" "$EXPORT_CSV" "$MANIFEST_JSON"

printf '\n[2/4] Validate promoted artifact set\n'
python3 scripts/validate_promoted_export.py \
  --export-json "$EXPORT_JSON" \
  --manifest "$MANIFEST_JSON"

printf '\n[3/4] Verify standalone TIBER-Rookies lab behavior\n'
npm run test:runtime-smoke

if [[ "$RUN_REMOTE_CURLS" == "1" ]]; then
  printf '\n[3b] Probe deployed standalone routes at %s\n' "$BASE_URL"
  curl -fsS "$BASE_URL/health"
  curl -fsSI "$BASE_URL/" | head -n 5
  curl -fsSI "$BASE_URL/cards/rookies/board/index.html" | head -n 5
  curl -fsSI "$BASE_URL/cards/rookies/player.html?slug=wr-malik-ford" | head -n 5
  curl -fsSI "$BASE_URL/cards/rookies/compare/index.html?left=wr-malik-ford&right=te-owen-hale" | head -n 5
fi

printf '\n[4/4] Manual handoff reminder for TIBER-Fantasy ingest\n'
printf '%s\n' "- Copy ${EXPORT_JSON} to TIBER-Fantasy ingest staging" \
              "- Copy ${EXPORT_CSV} to TIBER-Fantasy ingest staging" \
              "- Copy ${MANIFEST_JSON} to TIBER-Fantasy ingest staging" \
              "- In TIBER-Fantasy repo, run its ingest gate for the same files before promoting /rookies"

printf '\nDraft-week rehearsal for %s completed.\n\n' "$SEASON"
