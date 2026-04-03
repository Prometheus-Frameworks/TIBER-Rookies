#!/usr/bin/env python3
"""Fetch RB play profile proxies from CFBD play-by-play."""

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
DEFAULT_OUTPUT_DIR = Path("data/processed/rb_play_profiles")

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

EXPLOSION_THRESHOLD = 10  # rush yards gained to count as an explosion play

METHODOLOGY_NOTE = (
    "Rush stats attributed by RB name appearing in CFBD rush play text. "
    "Receiving stats attributed by RB name appearing in CFBD pass play text as target. "
    f"Explosion plays are rushes with yards_gained >= {EXPLOSION_THRESHOLD}. "
    "Play text does not include formation or scheme descriptors."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch RB play profile proxies from CFBD play-by-play")
    parser.add_argument("--players-input", type=Path, default=DEFAULT_PLAYERS_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--season-type", choices=["regular", "both"], default="both")
    return parser.parse_args()


def summarize_player(player: dict[str, Any], plays: list[dict[str, Any]], season_type: str) -> dict[str, Any]:
    player_name = str(player.get("player_name", ""))
    player_team = normalize_identity(str(player.get("school", "") or player.get("team", "")))
    offense_plays = filter_offense_plays(plays, player_team)

    # Rush plays attributed to this RB
    all_rush_plays = [play for play in offense_plays if play_type_of(play) in RUSH_PLAY_TYPES]
    rb_rush_plays = [p for p in all_rush_plays if is_targeted_player(play_text_of(p), player_name)]

    rush_attempts = len(rb_rush_plays)
    rush_yards = sum(yards_gained_of(p) for p in rb_rush_plays)
    rush_tds = sum(1 for p in rb_rush_plays if play_type_of(p) == "Rushing Touchdown")
    explosion_plays = sum(1 for p in rb_rush_plays if yards_gained_of(p) >= EXPLOSION_THRESHOLD)

    # Receiving plays attributed to this RB (as target/receiver)
    all_pass_plays = [play for play in offense_plays if play_type_of(play) in PASS_PLAY_TYPES]
    rb_pass_plays = [p for p in all_pass_plays if is_targeted_player(play_text_of(p), player_name)]

    targets = len(rb_pass_plays)
    receptions = sum(1 for p in rb_pass_plays if play_type_of(p) in COMPLETION_PLAY_TYPES)
    receiving_yards = sum(
        yards_gained_of(p) for p in rb_pass_plays
        if play_type_of(p) in COMPLETION_PLAY_TYPES
    )
    receiving_tds = sum(
        1 for p in rb_pass_plays
        if play_type_of(p) in {"Pass Touchdown", "Passing Touchdown"}
    )

    methodology_notes = METHODOLOGY_NOTE
    if rush_attempts == 0:
        methodology_notes += " No rush plays matched; attribution may have failed due to name mismatch."

    season = int(player.get("source_season"))
    team = str(player.get("school", "")).strip()

    return {
        "player_id": player.get("player_id"),
        "player_name": player_name,
        "team": team,
        "season": season,
        "season_type": season_type,
        "rush_attempts": rush_attempts,
        "rush_yards": rush_yards,
        "rush_tds": rush_tds,
        "yards_per_carry": safe_rate(rush_yards, rush_attempts),
        "explosion_plays": explosion_plays,
        "explosion_rate": safe_rate(explosion_plays, rush_attempts),
        "targets": targets,
        "receptions": receptions,
        "receiving_yards": receiving_yards,
        "receiving_tds": receiving_tds,
        "yards_per_reception": safe_rate(receiving_yards, receptions),
        "catch_rate": safe_rate(receptions, targets),
        "team_rush_plays": len(all_rush_plays),
        "rush_share": safe_rate(rush_attempts, len(all_rush_plays)),
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
        if player.get("position") != "RB":
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

            ypc = summary["yards_per_carry"] or 0.0
            exp_pct = (summary["explosion_rate"] or 0.0) * 100.0
            print(
                f"{summary['player_name']} ({summary['team']} {summary['season']}): "
                f"{summary['rush_attempts']} rush att, {ypc:.1f} YPC, "
                f"{summary['rush_tds']} rush TD, {exp_pct:.1f}% explosion, "
                f"{summary['targets']} targets, {summary['receiving_yards']} rec yds"
            )


if __name__ == "__main__":
    main()
