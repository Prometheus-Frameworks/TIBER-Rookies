#!/usr/bin/env python3
"""Fetch QB play profile proxies from CFBD play-by-play."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.compute_production_scores import CFBD_BASE_URL, normalize_identity
from scripts.cfbd_plays import (
    fetch_team_plays,
    filter_offense_plays,
    is_targeted_player,
    load_json,
    play_text_of,
    play_type_of,
    safe_rate,
    write_json,
    yards_gained_of,
)

DEFAULT_PLAYERS_INPUT = Path("data/processed/2026_college_production.json")
DEFAULT_OUTPUT_DIR = Path("data/processed/qb_play_profiles")

PASS_PLAY_TYPES = {
    "Pass Reception", "Pass Completion",
    "Pass Incompletion", "Pass Touchdown",
    "Passing Touchdown",
}
COMPLETION_PLAY_TYPES = {
    "Pass Reception", "Pass Completion",
    "Pass Touchdown", "Passing Touchdown",
}
RUSH_PLAY_TYPES = {"Rush", "Rushing Touchdown"}

BIG_PLAY_THRESHOLD = 20  # passing yards gained to count as a big play

METHODOLOGY_NOTE = (
    "Pass attempts, completions, yards, and TDs attributed by QB name appearing in CFBD play text. "
    "Interceptions are not included — CFBD logs INTs as separate defensive play types that cannot "
    "be reliably attributed to the QB from play text alone. "
    "Rush stats include designed runs and scrambles where QB name appears in rush play text. "
    "Play text does not include scheme descriptors; big_play_rate counts completions >= "
    f"{BIG_PLAY_THRESHOLD} yards gained."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch QB play profile proxies from CFBD play-by-play")
    parser.add_argument("--players-input", type=Path, default=DEFAULT_PLAYERS_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--season-type", choices=["regular", "both"], default="both")
    return parser.parse_args()


def summarize_player(player: dict[str, Any], plays: list[dict[str, Any]], season_type: str) -> dict[str, Any]:
    player_name = str(player.get("player_name", ""))
    player_team = normalize_identity(str(player.get("school", "") or player.get("team", "")))
    offense_plays = filter_offense_plays(plays, player_team)

    # Pass plays attributed to this QB (name appears as the passer in play text)
    all_pass_plays = [play for play in offense_plays if play_type_of(play) in PASS_PLAY_TYPES]
    qb_pass_plays = [p for p in all_pass_plays if is_targeted_player(play_text_of(p), player_name)]

    pass_attempts = len(qb_pass_plays)
    completions = sum(1 for p in qb_pass_plays if play_type_of(p) in COMPLETION_PLAY_TYPES)
    passing_yards = sum(yards_gained_of(p) for p in qb_pass_plays if play_type_of(p) in COMPLETION_PLAY_TYPES)
    passing_tds = sum(
        1 for p in qb_pass_plays
        if play_type_of(p) in {"Pass Touchdown", "Passing Touchdown"}
    )
    big_pass_plays = sum(
        1 for p in qb_pass_plays
        if play_type_of(p) in COMPLETION_PLAY_TYPES and yards_gained_of(p) >= BIG_PLAY_THRESHOLD
    )

    # Rush plays attributed to this QB
    all_rush_plays = [play for play in offense_plays if play_type_of(play) in RUSH_PLAY_TYPES]
    qb_rush_plays = [p for p in all_rush_plays if is_targeted_player(play_text_of(p), player_name)]

    rush_attempts = len(qb_rush_plays)
    rush_yards = sum(yards_gained_of(p) for p in qb_rush_plays)
    rush_tds = sum(1 for p in qb_rush_plays if play_type_of(p) == "Rushing Touchdown")

    methodology_notes = METHODOLOGY_NOTE
    if pass_attempts == 0:
        methodology_notes += " No pass plays matched; attribution may have failed due to name mismatch."

    season = int(player.get("source_season"))
    team = str(player.get("school", "")).strip()

    return {
        "player_id": player.get("player_id"),
        "player_name": player_name,
        "team": team,
        "season": season,
        "season_type": season_type,
        "pass_attempts": pass_attempts,
        "completions": completions,
        "completion_pct": safe_rate(completions * 100.0, pass_attempts),
        "passing_yards": passing_yards,
        "passing_tds": passing_tds,
        "yards_per_attempt": safe_rate(passing_yards, pass_attempts),
        "big_pass_plays": big_pass_plays,
        "big_play_rate": safe_rate(big_pass_plays, pass_attempts),
        "rush_attempts": rush_attempts,
        "rush_yards": rush_yards,
        "rush_tds": rush_tds,
        "yards_per_carry": safe_rate(rush_yards, rush_attempts),
        "team_pass_plays": len(all_pass_plays),
        "source_name": f"CFBD play-by-play (year={season}, team={team})",
        "source_url": f"{CFBD_BASE_URL}/plays?{urlencode({'year': season, 'team': team, 'seasonType': 'regular' if season_type == 'regular' else 'both'})}",
        "methodology_notes": methodology_notes,
    }


def main() -> None:
    args = parse_args()
    players = load_json(args.players_input)
    if not isinstance(players, list):
        raise SystemExit("players-input must be a JSON array")

    for player in players:
        if player.get("position") != "QB":
            continue
        team = str(player.get("school", "")).strip()
        class_year = int(player.get("class_year", 0))
        if not team or class_year <= 0:
            logging.warning("Skipping %s due to missing school/class_year", player.get("player_id", "unknown-player"))
            continue

        for season in (class_year - 2, class_year - 1):
            team_plays = fetch_team_plays(season, team, args.season_type)
            summary = summarize_player({**player, "source_season": season}, team_plays, args.season_type)

            output_path = args.output_dir / f"{player.get('player_id')}_{season}.json"
            write_json(output_path, summary)

            comp_pct = summary["completion_pct"] or 0.0
            ypa = summary["yards_per_attempt"] or 0.0
            big_pct = (summary["big_play_rate"] or 0.0) * 100.0
            print(
                f"{summary['player_name']} ({summary['team']} {summary['season']}): "
                f"{summary['pass_attempts']} att, {comp_pct:.1f}% comp, "
                f"{ypa:.1f} YPA, {summary['passing_tds']} TD, "
                f"{summary['rush_attempts']} rush att, {big_pct:.1f}% big plays"
            )


if __name__ == "__main__":
    main()
