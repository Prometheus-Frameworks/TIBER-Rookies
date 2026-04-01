#!/usr/bin/env python3
"""Fetch CFBD TE season populations for historical methodology compatibility."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.compute_production_scores import CFBD_BASE_URL, fetch_cfbd_category, pivot_stats

DEFAULT_YEARS = (2017, 2018, 2019, 2020, 2021)
DEFAULT_OUTPUT_DIR = Path("data/historical/te_reference_populations")
PRIMARY_POSITIONS = {"TE"}
FALLBACK_POSITIONS = {"TE", "H-BACK", "FB"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch TE reference population files from CFBD season stats")
    parser.add_argument("--years", nargs="+", type=int, default=list(DEFAULT_YEARS))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def _build_rows_from_positions(
    pivoted: dict[str, dict[str, Any]],
    *,
    year: int,
    source_url: str,
    allowed_positions: set[str],
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    filtered_out = 0
    for entry in pivoted.values():
        position = str(entry.get("position") or "").strip().upper()
        if position not in allowed_positions:
            continue

        stats = entry.get("stats", {})
        receptions = stats.get("REC", 0.0)
        try:
            receptions_int = int(float(receptions))
        except (TypeError, ValueError):
            filtered_out += 1
            continue

        if receptions_int < 20:
            filtered_out += 1
            continue

        receiving_yards = stats.get("YDS", 0.0)
        receiving_tds = stats.get("TD", 0.0)
        try:
            receiving_yards_int = int(float(receiving_yards))
            receiving_tds_int = int(float(receiving_tds))
        except (TypeError, ValueError):
            filtered_out += 1
            continue

        rows.append(
            {
                "player_name": str(entry.get("player", "")).strip(),
                "position": position,
                "source_season": year,
                "receptions": receptions_int,
                "receiving_yards": receiving_yards_int,
                "receiving_tds": receiving_tds_int,
                "source_name": f"CFBD receiving stats (year={year})",
                "source_url": source_url,
            }
        )

    rows.sort(key=lambda row: (row["player_name"].lower(), -row["receptions"], -row["receiving_yards"]))
    return rows, filtered_out


def build_rows_for_year(year: int) -> tuple[list[dict[str, Any]], int, str, str]:
    raw_rows = fetch_cfbd_category(year, "receiving")
    pivoted = pivot_stats(raw_rows)
    source_url = f"{CFBD_BASE_URL}/stats/player/season?{urlencode({'year': year, 'category': 'receiving'})}"

    rows, filtered_out = _build_rows_from_positions(
        pivoted,
        year=year,
        source_url=source_url,
        allowed_positions=PRIMARY_POSITIONS,
    )
    position_mode = "TE-only"
    if len(rows) < 30:
        rows, filtered_out = _build_rows_from_positions(
            pivoted,
            year=year,
            source_url=source_url,
            allowed_positions=FALLBACK_POSITIONS,
        )
        position_mode = "TE/H-BACK/FB fallback"

    return rows, filtered_out, source_url, position_mode


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    for year in args.years:
        rows, filtered_out, source_url, position_mode = build_rows_for_year(year)
        output_path = args.output_dir / f"{year}_te_receiving_population.json"
        write_json(output_path, rows)
        print(
            f"year={year} wrote={len(rows)} filtered_out={filtered_out} "
            f"position_mode={position_mode} output={output_path} source_url={source_url}"
        )


if __name__ == "__main__":
    main()
