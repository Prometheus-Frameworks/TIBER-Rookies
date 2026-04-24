#!/usr/bin/env python3
"""Build normalized NFL player-season PPR outcomes for draft cohorts.

Public-source lane only: nflverse release data (player_stats + draft_picks).
This script intentionally does not touch Rookie Alpha scoring artifacts.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path("exports/promoted/nfl-fantasy-outcomes")
OUTPUT_JSON = OUTPUT_DIR / "player_year_ppr_outcomes_v1.json"
OUTPUT_CSV = OUTPUT_DIR / "player_year_ppr_outcomes_v1.csv"

CACHE_DIR = Path("data/external/nflverse")
STATS_CACHE = CACHE_DIR / "player_stats.csv"
DRAFT_CACHE = CACHE_DIR / "draft_picks.csv"

NFLVERSE_PLAYER_STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats.csv.gz"
)
NFLVERSE_DRAFT_PICKS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/draft_picks/draft_picks.csv.gz"
)

POSITIONS = {"WR", "RB", "TE", "QB"}

FIELDNAMES = [
    "player_id",
    "player_name",
    "position",
    "draft_year",
    "draft_round",
    "overall_pick",
    "nfl_team_drafted",
    "nfl_season",
    "career_year",
    "games",
    "ppr_points",
    "ppr_per_game",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "rushing_yards",
    "rushing_tds",
    "source",
    "source_notes",
]


def slugify_player_name(name: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return clean or "unknown-player"


def to_int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_ppr(receptions: float, receiving_yards: float, receiving_tds: float, rushing_yards: float, rushing_tds: float) -> float:
    return (
        receptions * 1.0
        + receiving_yards * 0.1
        + receiving_tds * 6.0
        + rushing_yards * 0.1
        + rushing_tds * 6.0
    )


def career_year_for_season(draft_year: int, nfl_season: int) -> int:
    return nfl_season - draft_year + 1


def download_csv_gz(url: str) -> list[dict[str, str]]:
    with urllib.request.urlopen(url, timeout=60) as response:
        compressed = response.read()
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as gz:
        text = gz.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_source_rows(url: str, cache_path: Path, refresh: bool) -> tuple[list[dict[str, str]], str]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if refresh:
        rows = download_csv_gz(url)
        write_csv(cache_path, rows, list(rows[0].keys()) if rows else [])
        return rows, "download"
    if cache_path.exists():
        return read_csv(cache_path), "cache"

    rows = download_csv_gz(url)
    write_csv(cache_path, rows, list(rows[0].keys()) if rows else [])
    return rows, "download"


def build_draft_index(draft_rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in draft_rows:
        position = (row.get("position") or row.get("pos") or "").upper()
        if position not in POSITIONS:
            continue
        draft_year = to_int(row.get("season") or row.get("draft_year"), 0)
        if draft_year <= 0:
            continue
        stable_id = (
            row.get("gsis_id")
            or row.get("player_id")
            or row.get("pfr_player_id")
            or f"{slugify_player_name(row.get('player_name', ''))}-{draft_year}"
        )
        index[stable_id] = {
            "player_id": stable_id,
            "player_name": row.get("player_name", ""),
            "position": position,
            "draft_year": draft_year,
            "draft_round": to_int(row.get("round") or row.get("draft_round"), 0),
            "overall_pick": to_int(row.get("pick") or row.get("overall_pick"), 0),
            "nfl_team_drafted": row.get("team") or row.get("draft_team") or "",
        }
    return index


def map_stat_row_to_drafted_player(stat_row: dict[str, str], draft_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    keys = [
        stat_row.get("player_id"),
        stat_row.get("gsis_id"),
        stat_row.get("pfr_player_id"),
    ]
    for k in keys:
        if k and k in draft_index:
            return draft_index[k]

    name = stat_row.get("player_name", "")
    season = to_int(stat_row.get("season"), 0)
    # Fallback name+draft_year lookup for datasets lacking common IDs.
    for rec in draft_index.values():
        if rec["player_name"].strip().lower() == name.strip().lower() and rec["draft_year"] <= season:
            return rec
    return None


def build_player_outcome_rows(
    stats_rows: list[dict[str, str]],
    draft_rows: list[dict[str, str]],
    source_notes: str,
) -> list[dict[str, Any]]:
    draft_index = build_draft_index(draft_rows)
    out: list[dict[str, Any]] = []

    for row in stats_rows:
        pos = (row.get("position") or row.get("pos") or "").upper()
        if pos not in POSITIONS:
            continue

        draft = map_stat_row_to_drafted_player(row, draft_index)
        if not draft:
            continue

        nfl_season = to_int(row.get("season"), 0)
        if nfl_season <= 0:
            continue

        receptions = to_float(row.get("receptions"))
        receiving_yards = to_float(row.get("receiving_yards"))
        receiving_tds = to_float(row.get("receiving_tds"))
        rushing_yards = to_float(row.get("rushing_yards"))
        rushing_tds = to_float(row.get("rushing_tds"))
        games = to_int(row.get("games"), 0)

        ppr_points = round(compute_ppr(receptions, receiving_yards, receiving_tds, rushing_yards, rushing_tds), 2)
        ppr_per_game = round(ppr_points / games, 3) if games > 0 else 0.0

        out.append(
            {
                "player_id": draft["player_id"],
                "player_name": draft["player_name"] or row.get("player_name", ""),
                "position": draft["position"],
                "draft_year": draft["draft_year"],
                "draft_round": draft["draft_round"],
                "overall_pick": draft["overall_pick"],
                "nfl_team_drafted": draft["nfl_team_drafted"],
                "nfl_season": nfl_season,
                "career_year": career_year_for_season(draft["draft_year"], nfl_season),
                "games": games,
                "ppr_points": ppr_points,
                "ppr_per_game": ppr_per_game,
                "receptions": receptions,
                "receiving_yards": receiving_yards,
                "receiving_tds": receiving_tds,
                "rushing_yards": rushing_yards,
                "rushing_tds": rushing_tds,
                "source": "nflverse_public_release",
                "source_notes": source_notes,
            }
        )

    out.sort(key=lambda r: (r["draft_year"], r["player_name"], r["nfl_season"]))
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build NFL fantasy outcome calibration player-year artifacts")
    parser.add_argument("--refresh", action="store_true", help="Force download fresh nflverse source snapshots")
    parser.add_argument("--stats-cache", type=Path, default=STATS_CACHE)
    parser.add_argument("--draft-cache", type=Path, default=DRAFT_CACHE)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    stats_rows, stats_mode = load_source_rows(NFLVERSE_PLAYER_STATS_URL, args.stats_cache, refresh=args.refresh)
    draft_rows, draft_mode = load_source_rows(NFLVERSE_DRAFT_PICKS_URL, args.draft_cache, refresh=args.refresh)

    notes = f"player_stats={stats_mode}:{args.stats_cache}; draft_picks={draft_mode}:{args.draft_cache}"
    rows = build_player_outcome_rows(stats_rows, draft_rows, source_notes=notes)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    write_csv(args.output_csv, rows, FIELDNAMES)

    print(f"Built {len(rows)} rows")
    print(f"JSON -> {args.output_json}")
    print(f"CSV  -> {args.output_csv}")


if __name__ == "__main__":
    main()
