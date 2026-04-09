#!/usr/bin/env python3
"""Fetch RB play profile proxies from CFBD season-level rushing/receiving stats.

Uses /stats/player/season?year=Y&category=rushing and ?category=receiving —
two requests per year rather than week-by-week play-by-play (hundreds of
requests).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.compute_production_scores import (
    CFBD_BASE_URL,
    fetch_cfbd_category,
    normalize_identity,
    pivot_stats,
    school_aliases,
)
from scripts.cfbd_plays import load_json, write_json

DEFAULT_PLAYERS_INPUT = Path("data/processed/2026_college_production.json")
DEFAULT_OUTPUT_DIR = Path("data/processed/rb_play_profiles")

ASSUMED_CATCH_RATE = 0.70  # for estimating targets when TGT not in CFBD stats
EXPLOSION_THRESHOLD = 10   # yards per carry to count as explosion play (informational only)

METHODOLOGY_NOTE = (
    "Rush and receiving stats from CFBD /stats/player/season. "
    "explosion_plays and rush_share are not available from season-level stats and are set to null. "
    "If CFBD does not supply a TGT stat type, targets are estimated as "
    f"receptions / {ASSUMED_CATCH_RATE:.2f}."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch RB play profile proxies from CFBD season stats"
    )
    parser.add_argument("--players-input", type=Path, default=DEFAULT_PLAYERS_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def build_stat_lookup(year: int, category: str) -> dict[tuple[str, str], dict[str, float]]:
    rows = fetch_cfbd_category(year, category)
    pivoted = pivot_stats(rows)
    return {key: entry["stats"] for key, entry in pivoted.items()}


def find_player_stats(
    player_name: str,
    school: str,
    lookup: dict[tuple[str, str], dict[str, float]],
) -> dict[str, float] | None:
    norm_player = normalize_identity(player_name)
    aliases = school_aliases(school)

    for alias in aliases:
        key = (norm_player, alias)
        if key in lookup:
            return lookup[key]

    parts = norm_player.split()
    if len(parts) >= 2:
        abbrev_name = f"{parts[0][0]} {' '.join(parts[1:])}"
        for alias in aliases:
            key = (abbrev_name, alias)
            if key in lookup:
                return lookup[key]

    return None


def build_profile(
    player: dict[str, Any],
    season: int,
    rush_stats: dict[str, float] | None,
    recv_stats: dict[str, float] | None,
) -> dict[str, Any]:
    team = str(player.get("school", "")).strip()
    player_id = player.get("player_id")
    player_name = player.get("player_name")

    if rush_stats is None and recv_stats is None:
        logging.warning(
            "No CFBD stats found for %s (%s) season=%s", player_name, team, season
        )

    rush_attempts = int(round(rush_stats.get("CAR", rush_stats.get("ATT", 0.0)))) if rush_stats else 0
    rush_yards = rush_stats.get("YDS", 0.0) if rush_stats else 0.0
    rush_tds = int(round(rush_stats.get("TD", 0.0))) if rush_stats else 0
    ypc = round(rush_yards / rush_attempts, 2) if rush_attempts > 0 else None

    receptions = int(round(recv_stats.get("REC", 0.0))) if recv_stats else 0
    recv_yards = recv_stats.get("YDS", 0.0) if recv_stats else 0.0
    recv_tds = int(round(recv_stats.get("TD", 0.0))) if recv_stats else 0

    if recv_stats and "TGT" in recv_stats:
        targets = int(round(recv_stats["TGT"]))
        tgt_source = "CFBD TGT stat"
    else:
        targets = int(round(receptions / ASSUMED_CATCH_RATE)) if receptions > 0 else 0
        tgt_source = f"estimated (REC / {ASSUMED_CATCH_RATE:.2f})"

    catch_rate = round(receptions / targets, 3) if targets > 0 else None
    ypr = round(recv_yards / receptions, 1) if receptions > 0 else None

    source_label = "CFBD season stats"
    if rush_stats is None and recv_stats is None:
        source_label += " — player not found"

    return {
        "player_id": player_id,
        "player_name": player_name,
        "team": team,
        "season": season,
        "season_type": "regular",
        "rush_attempts": rush_attempts,
        "rush_yards": rush_yards,
        "rush_tds": rush_tds,
        "yards_per_carry": ypc,
        "explosion_plays": None,
        "explosion_rate": None,
        "targets": targets,
        "receptions": receptions,
        "receiving_yards": recv_yards,
        "receiving_tds": recv_tds,
        "yards_per_reception": ypr,
        "catch_rate": catch_rate,
        "team_rush_plays": None,
        "rush_share": None,
        "source_name": f"{source_label} (year={season}, team={team}); targets={tgt_source}",
        "source_url": f"{CFBD_BASE_URL}/stats/player/season?year={season}&category=rushing",
        "methodology_notes": METHODOLOGY_NOTE,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    players = load_json(args.players_input)
    if not isinstance(players, list):
        raise SystemExit("players-input must be a JSON array")

    rb_players = [p for p in players if p.get("position") == "RB"]

    # Collect needed years
    needed_years: set[int] = set()
    for player in rb_players:
        class_year = int(player.get("class_year", 0))
        if class_year > 0:
            needed_years.add(class_year - 2)
            needed_years.add(class_year - 1)

    logging.info("Fetching CFBD rushing+receiving stats for years: %s", sorted(needed_years))
    rush_lookups: dict[int, dict[tuple[str, str], dict[str, float]]] = {}
    recv_lookups: dict[int, dict[tuple[str, str], dict[str, float]]] = {}
    for year in sorted(needed_years):
        logging.info("  Fetching rushing year=%s …", year)
        rush_lookups[year] = build_stat_lookup(year, "rushing")
        logging.info("  Fetching receiving year=%s …", year)
        recv_lookups[year] = build_stat_lookup(year, "receiving")

    for player in rb_players:
        class_year = int(player.get("class_year", 0))
        if class_year <= 0:
            logging.warning("Skipping %s — missing class_year", player.get("player_id", "?"))
            continue

        for season in (class_year - 2, class_year - 1):
            rush_stats = find_player_stats(
                player["player_name"], player.get("school", ""), rush_lookups.get(season, {})
            )
            recv_stats = find_player_stats(
                player["player_name"], player.get("school", ""), recv_lookups.get(season, {})
            )
            profile = build_profile(player, season, rush_stats, recv_stats)
            output_path = args.output_dir / f"{player['player_id']}_{season}.json"
            write_json(output_path, profile)
            ypc = profile["yards_per_carry"] or 0.0
            logging.info(
                "%s (%s %s): %d rush att, %.1f YPC, %d rush TD, %d targets, %.0f rec yds",
                profile["player_name"], profile["team"], season,
                profile["rush_attempts"], ypc, profile["rush_tds"],
                profile["targets"], profile["receiving_yards"],
            )


if __name__ == "__main__":
    main()
