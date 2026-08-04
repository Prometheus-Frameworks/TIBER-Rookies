#!/usr/bin/env python3
"""Build the post-freeze 2023-2025 outcome layer for the #283 pilot players.

Runs ONLY after scripts/freeze_2023_expectation_records.py has frozen the
historical layers (this script verifies the freeze first and refuses to run
if any frozen layer changed).

Sources:
- 2023/2024 seasons: promoted exports/promoted/nfl-fantasy-outcomes rows (read-only)
- 2025 season: nflverse stats_player_reg_2025.csv cache under data/external/nflverse/
  (same upstream family and PPR formula as scripts/build_nfl_fantasy_outcomes.py)
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROMOTED_OUTCOMES = Path("exports/promoted/nfl-fantasy-outcomes/player_year_ppr_outcomes_v1.json")
STATS_2025 = Path("data/external/nflverse/stats_player_reg_2025.csv")
OUTPUT = Path("data/historical/reconstruction_2023/outcomes/2023_2025_pilot_outcomes_v0.json")

PILOTS = {
    "00-0039075": "wr-puka-nacua",
    "00-0039064": "wr-zay-flowers",
    "00-0038997": "wr-josh-downs",
}


def compute_ppr(receptions, receiving_yards, receiving_tds, rushing_yards, rushing_tds) -> float:
    # Same formula as scripts/build_nfl_fantasy_outcomes.py::compute_ppr
    return (
        receptions * 1.0
        + receiving_yards * 0.1
        + receiving_tds * 6.0
        + rushing_yards * 0.1
        + rushing_tds * 6.0
    )


def main() -> None:
    check = subprocess.run(
        [sys.executable, "scripts/freeze_2023_expectation_records.py", "verify"],
        capture_output=True, text=True,
    )
    if check.returncode != 0:
        sys.exit(f"Refusing to build outcomes: frozen layers modified.\n{check.stdout}")

    rows = []
    for row in json.loads(PROMOTED_OUTCOMES.read_text()):
        if row.get("player_id") in PILOTS and row.get("nfl_season") in (2023, 2024):
            rows.append({
                "canonical_player_id": PILOTS[row["player_id"]],
                "gsis_id": row["player_id"],
                "nfl_season": row["nfl_season"],
                "career_year": row["career_year"],
                "games": row["games"],
                "receptions": row["receptions"],
                "receiving_yards": row["receiving_yards"],
                "receiving_tds": row["receiving_tds"],
                "rushing_yards": row["rushing_yards"],
                "rushing_tds": row["rushing_tds"],
                "ppr_points": row["ppr_points"],
                "ppr_per_game": row["ppr_per_game"],
                "source": "exports/promoted/nfl-fantasy-outcomes/player_year_ppr_outcomes_v1.json (read-only)",
            })

    if not STATS_2025.exists():
        sys.exit(f"Missing {STATS_2025}; download the nflverse stats_player release for 2025 first.")
    with STATS_2025.open() as fh:
        for stat in csv.DictReader(fh):
            gsis = stat.get("player_id")
            if gsis in PILOTS:
                receptions = float(stat.get("receptions") or 0)
                rec_yds = float(stat.get("receiving_yards") or 0)
                rec_tds = float(stat.get("receiving_tds") or 0)
                rush_yds = float(stat.get("rushing_yards") or 0)
                rush_tds = float(stat.get("rushing_tds") or 0)
                games = int(float(stat.get("games") or 0))
                ppr = round(compute_ppr(receptions, rec_yds, rec_tds, rush_yds, rush_tds), 1)
                rows.append({
                    "canonical_player_id": PILOTS[gsis],
                    "gsis_id": gsis,
                    "nfl_season": 2025,
                    "career_year": 3,
                    "games": games,
                    "receptions": receptions,
                    "receiving_yards": rec_yds,
                    "receiving_tds": rec_tds,
                    "rushing_yards": rush_yds,
                    "rushing_tds": rush_tds,
                    "ppr_points": ppr,
                    "ppr_per_game": round(ppr / games, 3) if games else 0.0,
                    "source": "nflverse stats_player_reg_2025 (public release; same formula as promoted builder)",
                })

    rows.sort(key=lambda r: (r["canonical_player_id"], r["nfl_season"]))
    payload = {
        "artifact": "pilot_outcomes_2023_2025_v0",
        "issue": "Prometheus-Frameworks/TIBER-Rookies#283",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "built_after_freeze": True,
        "boundary_note": (
            "Outcome layer only. Must never be read by, merged into, or used to "
            "edit the frozen pre-draft cards, landing contexts, or expectation records."
        ),
        "forecast_run1_reference": {
            "puka_nacua_row_exists": True,
            "detail": (
                "TIBER-Forecast Run 1 (2024 inputs -> 2025 seasonal PPR) contains a "
                "Nacua row: predicted_ppr 261.28 vs actual 314.7 under player_id "
                "00-0038543, which CONFLICTS with the governed GSIS id 00-0039075. "
                "Flowers and Downs are not in the 39-row Run 1 cohort. Recorded as a "
                "cross-repo identity defect; see the pilot report."
            ),
        },
        "rows": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {OUTPUT} with {len(rows)} player-season rows")


if __name__ == "__main__":
    main()
