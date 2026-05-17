#!/usr/bin/env python3
"""Ingest canonical TIBER-Data NFL Draft result artifacts into TIBER-Rookies.

Reads a canonical TIBER-Data artifact at the path produced by:
  exports/promoted/nfl_draft_results/nfl_draft_results_{year}.json

Maps upstream fields to the TIBER-Rookies model-facing schema used by
  data/processed/{year}_draft_results.json

Cross-repo boundary
-------------------
TIBER-Data owns:  official draft result facts, provenance tracking, source verification.
TIBER-Rookies owns: draft capital proxy scoring, rookie alpha, post-draft adjustment logic.

This script is the ingestion seam. It maps facts; it does not score or interpret.

Fail-closed rules
-----------------
- Rows with provenance_status='fixture_only' are rejected unconditionally.
- Rows with player_id=null are skipped (cannot match to alpha model players).
- Rows with provenance_status='needs_verification' are passed through but flagged.
- If zero rows survive validation, the script exits non-zero without writing output.
- An upstream file that does not exist causes a clear error (no silent empty result).

Usage
-----
  python scripts/ingest_draft_results_from_tiber_data.py \\
    --upstream path/to/nfl_draft_results_2026.json \\
    --year 2026 \\
    [--output data/processed/2026_draft_results.json] \\
    [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

ACCEPTED_PROVENANCE_STATUSES = {
    "source_verified",
    "source_verified_player_id_unresolved",
    "needs_verification",
    "fixture_only",
}

VERIFIED_STATUSES = {"source_verified", "source_verified_player_id_unresolved"}
WARN_STATUSES = {"needs_verification"}
REJECT_STATUSES = {"fixture_only"}

# TIBER-Data uses full team names (e.g. "Las Vegas Raiders") and may append trade
# notation (e.g. "Los Angeles Rams from Atlanta Falcons"). This table maps the base
# team name to the two- or three-letter abbreviation used in TIBER-Rookies.
# Generated from the TIBER-Data PR #114 promoted artifact (2026 class).
_NFL_TEAM_FULL_TO_ABBREV: dict[str, str] = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}


def normalize_team_name(raw_team: str) -> str:
    """Normalize a TIBER-Data team field to a TIBER-Rookies abbreviation.

    Strips trade notation ("Team A from Team B" → "Team A") before lookup.
    Raises ValueError for unrecognised team names so callers fail loudly.
    """
    base = raw_team.split(" from ")[0].strip()
    abbrev = _NFL_TEAM_FULL_TO_ABBREV.get(base)
    if abbrev is None:
        raise ValueError(
            f"Unknown team name {base!r} (raw: {raw_team!r}). "
            "Update _NFL_TEAM_FULL_TO_ABBREV in ingest_draft_results_from_tiber_data.py."
        )
    return abbrev


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest TIBER-Data draft results artifact")
    parser.add_argument(
        "--upstream",
        type=Path,
        required=True,
        help="Path to canonical TIBER-Data artifact (nfl_draft_results_{year}.json)",
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Draft class year (e.g. 2026)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path (default: data/processed/{year}_draft_results.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and preview without writing output",
    )
    return parser.parse_args()


def load_upstream(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        log.error("Upstream artifact not found: %s", path)
        log.error(
            "TIBER-Data must produce and promote this file before ingestion can run. "
            "Expected path: exports/promoted/nfl_draft_results/nfl_draft_results_{year}.json"
        )
        sys.exit(1)

    raw = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw, list):
        log.error("Upstream artifact must be a JSON array. Got: %s", type(raw).__name__)
        sys.exit(1)

    if len(raw) == 0:
        log.error("Upstream artifact is an empty array. No draft results to ingest.")
        sys.exit(1)

    return raw


def validate_row(row: dict[str, Any], idx: int) -> str | None:
    """Validate a single upstream row. Returns a skip reason string, or None if the row is valid."""
    provenance = row.get("provenance_status", "")

    if provenance not in ACCEPTED_PROVENANCE_STATUSES:
        return f"unknown provenance_status={provenance!r}"

    if provenance in REJECT_STATUSES:
        return f"provenance_status={provenance!r} rows are not accepted"

    if row.get("player_id") is None:
        if provenance not in ("source_verified_player_id_unresolved", "needs_verification"):
            return "player_id is null without an appropriate provenance_status"
        return "player_id is null — cannot match to alpha model players"

    player_id = str(row.get("player_id", "")).strip()
    if not player_id:
        return "player_id is empty string"

    if not isinstance(row.get("round"), int) or row["round"] < 1:
        return f"invalid round={row.get('round')!r}"

    if not isinstance(row.get("overall_pick"), int) or row["overall_pick"] < 1:
        return f"invalid overall_pick={row.get('overall_pick')!r}"

    if not isinstance(row.get("team"), str) or not row["team"].strip():
        return f"missing or empty team={row.get('team')!r}"

    return None


def map_row(row: dict[str, Any], year: int) -> dict[str, Any]:
    """Map a validated upstream row to the TIBER-Rookies model-facing schema."""
    provenance = row.get("provenance_status", "")
    player_id = str(row["player_id"]).strip().lower()
    draft_round = int(row["round"])
    overall_pick = int(row["overall_pick"])
    raw_team = str(row.get("team", "")).strip()
    nfl_team = normalize_team_name(raw_team)

    # Derive draft_day from round (consistent with lib/rookies/draftResults.js)
    day_by_round = {1: 1, 2: 2, 3: 2}
    draft_day = day_by_round.get(draft_round, 3)

    source_status = "external_verified" if provenance in VERIFIED_STATUSES else "needs_verification"

    return {
        "player_id": player_id,
        "player_name": row.get("player_name", ""),
        "position": row.get("position", ""),
        "nfl_team": nfl_team,
        "draft_round": draft_round,
        "overall_pick": overall_pick,
        "draft_day": draft_day,
        "is_udfa": False,
        "draft_result_status": "drafted",
        "source_name": str(row.get("source", "")),
        "source_url": row.get("source_url"),
        "source_status": source_status,
        "upstream_provenance_status": provenance,
        "ingested_from": "tiber_data_nfl_draft_results_v1",
        "ingested_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }


def ingest(upstream_path: Path, year: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = load_upstream(upstream_path)
    log.info("Loaded %d rows from upstream artifact", len(rows))

    stats = {"total": len(rows), "accepted": 0, "skipped_fixture": 0, "skipped_null_id": 0, "skipped_other": 0, "warned": 0}
    output: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        skip_reason = validate_row(row, idx)
        if skip_reason:
            provenance = row.get("provenance_status", "")
            if provenance in REJECT_STATUSES:
                stats["skipped_fixture"] += 1
                log.warning("Row %d skipped (fixture): %s — %s", idx, row.get("player_name"), skip_reason)
            elif "player_id is null" in skip_reason:
                stats["skipped_null_id"] += 1
                log.warning("Row %d skipped (null id): %s — %s", idx, row.get("player_name"), skip_reason)
            else:
                stats["skipped_other"] += 1
                log.warning("Row %d skipped: %s — %s", idx, row.get("player_name"), skip_reason)
            continue

        if row.get("provenance_status") in WARN_STATUSES:
            stats["warned"] += 1
            log.warning(
                "Row %d accepted with warning (needs_verification): %s",
                idx, row.get("player_name"),
            )

        mapped = map_row(row, year)
        output.append(mapped)
        stats["accepted"] += 1

    return output, stats


def main() -> None:
    args = parse_args()

    output_path = args.output or (REPO_ROOT / "data" / "processed" / f"{args.year}_draft_results.json")

    log.info("Ingesting TIBER-Data draft results for %d", args.year)
    log.info("  Upstream: %s", args.upstream)
    log.info("  Output:   %s", output_path)

    output_rows, stats = ingest(args.upstream, args.year)

    log.info(
        "Ingestion summary: %d accepted / %d total "
        "(%d fixture-rejected, %d null-id skipped, %d other skipped, %d warned)",
        stats["accepted"], stats["total"],
        stats["skipped_fixture"], stats["skipped_null_id"],
        stats["skipped_other"], stats["warned"],
    )

    if stats["accepted"] == 0:
        log.error(
            "Zero rows accepted from upstream artifact. "
            "Output file will NOT be written. Verify upstream data quality."
        )
        sys.exit(1)

    if args.dry_run:
        log.info("Dry run — not writing output. First accepted row:")
        print(json.dumps(output_rows[0], indent=2))
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output_rows, indent=2), encoding="utf-8")
    log.info("Wrote %d rows to %s", len(output_rows), output_path)


if __name__ == "__main__":
    main()
