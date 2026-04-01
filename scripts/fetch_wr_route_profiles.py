#!/usr/bin/env python3
"""Fetch WR route profile proxies from CFBD play-by-play."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.compute_production_scores import CFBD_BASE_URL, normalize_identity

DEFAULT_PLAYERS_INPUT = Path("data/processed/2026_college_production.json")
DEFAULT_OUTPUT_DIR = Path("data/processed/wr_route_profiles")
PASS_PLAY_TYPES = {"Pass Completion", "Pass Incompletion", "Pass Touchdown", "Passing Touchdown"}
COMPLETION_PLAY_TYPES = {"Pass Completion", "Pass Touchdown", "Passing Touchdown"}
METHODOLOGY_NOTE = (
    "yards_per_target is YAC-inclusive; true aDOT not available from CFBD play-by-play. "
    "screen_target_rate derived from play text containing 'screen'. "
    "depth_tag_coverage_rate indicates fraction of this player's targets with a parseable depth descriptor."
)

_WARNED_MISSING_KEY = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch WR route profile proxies from CFBD play-by-play")
    parser.add_argument("--players-input", type=Path, default=DEFAULT_PLAYERS_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--season-type", choices=["regular", "both"], default="regular")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc.msg} (line {exc.lineno}, column {exc.colno})") from exc


def parse_screen_flag(play_text: str) -> bool:
    return "screen" in play_text.lower()


def parse_depth_tag(play_text: str) -> str | None:
    lowered = play_text.lower()
    if "deep" in lowered:
        return "deep"
    if "short" in lowered:
        return "short"
    return None


def is_targeted_player(play_text: str, player_name: str) -> bool:
    normalized_text = normalize_identity(play_text)
    normalized_player = normalize_identity(player_name)
    if normalized_player in normalized_text:
        return True
    # CFBD play text uses abbreviated first names (e.g. "C. Tate" not "Carnell Tate").
    # Also check first-initial + last-name form.
    parts = normalized_player.split()
    if len(parts) >= 2:
        abbreviated = f"{parts[0][0]} {' '.join(parts[1:])}"
        if abbreviated in normalized_text:
            return True
    return False


def safe_rate(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def cfbd_headers() -> dict[str, str]:
    global _WARNED_MISSING_KEY
    headers = {"Accept": "application/json"}
    api_key = os.getenv("CFBD_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif not _WARNED_MISSING_KEY:
        logging.warning("CFBD_API_KEY not set; using unauthenticated CFBD requests (may be rate-limited).")
        _WARNED_MISSING_KEY = True
    return headers


def fetch_team_plays(year: int, team: str, season_type: str) -> list[dict[str, Any]]:
    # CFBD /plays requires a week parameter — fetch week-by-week and aggregate.
    season_types = ["regular", "postseason"] if season_type == "both" else ["regular"]
    week_ranges = {"regular": range(1, 19), "postseason": range(1, 6)}
    plays: list[dict[str, Any]] = []

    for single_type in season_types:
        for week in week_ranges[single_type]:
            params = urlencode({"year": year, "team": team, "seasonType": single_type, "week": week})
            url = f"{CFBD_BASE_URL}/plays?{params}"
            request = Request(url=url, headers=cfbd_headers())
            try:
                with urlopen(request, timeout=60) as response:
                    payload = json.load(response)
            except HTTPError as exc:
                raise SystemExit(
                    f"CFBD API request failed for {team} {year} week {week} ({single_type}): HTTP {exc.code}"
                ) from exc
            except URLError as exc:
                raise SystemExit(
                    f"CFBD API request failed for {team} {year} week {week} ({single_type}): {exc.reason}"
                ) from exc

            if not isinstance(payload, list):
                raise SystemExit(
                    f"Unexpected CFBD response for {team} {year} week {week}: expected list, got {type(payload).__name__}"
                )

            plays.extend(payload)

    return plays


def summarize_player(player: dict[str, Any], plays: list[dict[str, Any]], season_type: str) -> dict[str, Any]:
    team_pass_plays = [play for play in plays if play.get("play_type") in PASS_PLAY_TYPES]
    team_screen_plays = [play for play in team_pass_plays if parse_screen_flag(str(play.get("play_text", "")))]

    targeted: list[dict[str, Any]] = []
    for play in team_pass_plays:
        if is_targeted_player(str(play.get("play_text", "")), str(player.get("player_name", ""))):
            targeted.append(play)

    screen_targets = [play for play in targeted if parse_screen_flag(str(play.get("play_text", "")))]
    depth_tags = [parse_depth_tag(str(play.get("play_text", ""))) for play in targeted]
    tagged_depths = [tag for tag in depth_tags if tag is not None]

    targets = len(targeted)
    receptions = sum(1 for play in targeted if play.get("play_type") in COMPLETION_PLAY_TYPES)
    screen_target_rate = safe_rate(len(screen_targets), targets)

    yards_total = 0.0
    for play in targeted:
        yards = play.get("yards_gained", 0)
        try:
            yards_total += float(yards)
        except (TypeError, ValueError):
            continue
    yards_per_target = safe_rate(yards_total, targets)

    deep_target_rate = safe_rate(tagged_depths.count("deep"), len(tagged_depths))
    depth_tag_coverage_rate = safe_rate(len(tagged_depths), targets)

    team_yards_sum = 0.0
    for play in team_pass_plays:
        try:
            team_yards_sum += float(play.get("yards_gained", 0))
        except (TypeError, ValueError):
            continue
    team_yards_per_pass = safe_rate(team_yards_sum, len(team_pass_plays))

    methodology_notes = METHODOLOGY_NOTE
    if targets == 0:
        methodology_notes += " No targets matched in play text; attribution may have failed due to name mismatch."

    season = int(player.get("source_season"))
    team = str(player.get("school", "")).strip()

    return {
        "player_id": player.get("player_id"),
        "player_name": player.get("player_name"),
        "team": team,
        "season": season,
        "season_type": season_type,
        "targets": targets,
        "receptions": receptions,
        "screen_targets": len(screen_targets),
        "screen_target_rate": screen_target_rate,
        "yards_per_target": yards_per_target,
        "deep_target_rate": deep_target_rate,
        "depth_tag_coverage_rate": depth_tag_coverage_rate,
        "team_pass_plays": len(team_pass_plays),
        "team_screen_plays": len(team_screen_plays),
        "team_screen_rate": safe_rate(len(team_screen_plays), len(team_pass_plays)),
        "team_yards_per_pass": team_yards_per_pass,
        "source_name": f"CFBD play-by-play (year={season}, team={team})",
        "source_url": f"{CFBD_BASE_URL}/plays?{urlencode({'year': season, 'team': team, 'seasonType': 'regular' if season_type == 'regular' else 'both'})}",
        "methodology_notes": methodology_notes,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    players = load_json(args.players_input)
    if not isinstance(players, list):
        raise SystemExit("players-input must be a JSON array")

    for player in players:
        if player.get("position") != "WR":
            continue
        team = str(player.get("school", "")).strip()
        season = int(player.get("source_season", player.get("class_year", 0) - 1))
        if not team or season <= 0:
            logging.warning("Skipping %s due to missing school/source_season", player.get("player_id", "unknown-player"))
            continue

        team_plays = fetch_team_plays(season, team, args.season_type)
        summary = summarize_player({**player, "source_season": season}, team_plays, args.season_type)

        output_path = args.output_dir / f"{player.get('player_id')}_{season}.json"
        write_json(output_path, summary)

        screen_pct = (summary["screen_target_rate"] or 0.0) * 100.0
        depth_pct = (summary["depth_tag_coverage_rate"] or 0.0) * 100.0
        ypt = summary["yards_per_target"] or 0.0
        print(
            f"{summary['player_name']} ({summary['team']} {summary['season']}): "
            f"{summary['targets']} targets, {screen_pct:.1f}% screen rate, "
            f"{ypt:.1f} yds/target, depth tag coverage {depth_pct:.0f}%"
        )


if __name__ == "__main__":
    main()
