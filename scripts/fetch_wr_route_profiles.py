#!/usr/bin/env python3
"""Fetch WR/TE route profile proxies from CFBD season-level receiving stats.

Uses /stats/player/season?year=Y&category=receiving — one request per year
rather than week-by-week play-by-play (hundreds of requests).  Targets are
estimated from receptions / assumed_catch_rate when CFBD does not return a
TGT stat type directly.
"""

from __future__ import annotations

import argparse
import logging
import re
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
DEFAULT_OUTPUT_DIR = Path("data/processed/wr_route_profiles")

ASSUMED_CATCH_RATE = 0.70  # used to estimate targets when TGT not in CFBD stats

METHODOLOGY_NOTE = (
    "Targets derived from CFBD /stats/player/season receiving stats. "
    "If CFBD does not supply a TGT stat type, targets are estimated as "
    f"receptions / {ASSUMED_CATCH_RATE:.2f} (industry avg catch rate). "
    "yards_per_target is total receiving yards / estimated targets. "
    "screen_target_rate and depth_tag_coverage_rate are always null — "
    "season-level stats carry no route/scheme descriptors."
)

DEPTH_TAG_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("deep", ("deep left", "deep middle", "deep right")),
    ("short", ("short left", "short middle", "short right")),
)


def parse_screen_flag(play_text: str) -> bool:
    """Return True when play text indicates a screen target."""
    return "screen" in str(play_text).lower()


def parse_depth_tag(play_text: str) -> str | None:
    """Extract normalized depth bucket from play text."""
    lowered = str(play_text).lower()
    for depth_tag, phrases in DEPTH_TAG_PATTERNS:
        if any(phrase in lowered for phrase in phrases):
            return depth_tag
    return None


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def is_targeted_player(play_text: str, player_name: str) -> bool:
    """Heuristic target attribution by normalized player-name token inclusion."""
    normalized_text = _normalize_name(str(play_text))
    normalized_player = _normalize_name(str(player_name))
    return bool(normalized_player) and normalized_player in normalized_text


def summarize_player(
    player: dict[str, Any],
    plays: list[dict[str, Any]],
    season_type: str,
) -> dict[str, Any]:
    """Summarize route profile metrics from play-level data."""
    player_name = str(player.get("player_name", ""))
    target_plays = [play for play in plays if is_targeted_player(play.get("play_text", ""), player_name)]
    targets = len(target_plays)

    completion_types = {"pass completion", "pass touchdown", "passing touchdown"}
    receptions = sum(
        1
        for play in target_plays
        if str(play.get("play_type", "")).strip().lower() in completion_types
    )
    screen_targets = sum(1 for play in target_plays if parse_screen_flag(play.get("play_text", "")))
    tagged_targets = [play for play in target_plays if parse_depth_tag(play.get("play_text", "")) is not None]
    deep_targets = sum(1 for play in tagged_targets if parse_depth_tag(play.get("play_text", "")) == "deep")
    total_yards = sum(float(play.get("yards_gained", 0) or 0) for play in target_plays)

    return {
        "player_id": player.get("player_id"),
        "player_name": player_name,
        "team": player.get("school"),
        "season": player.get("source_season"),
        "season_type": season_type,
        "targets": targets,
        "receptions": receptions,
        "screen_targets": screen_targets,
        "screen_target_rate": (screen_targets / targets) if targets else None,
        "yards_per_target": (total_yards / targets) if targets else None,
        "deep_target_rate": (deep_targets / len(tagged_targets)) if tagged_targets else None,
        "depth_tag_coverage_rate": (len(tagged_targets) / targets) if targets else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch WR/TE route profile proxies from CFBD season stats"
    )
    parser.add_argument("--players-input", type=Path, default=DEFAULT_PLAYERS_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def build_receiving_lookup(year: int) -> dict[tuple[str, str], dict[str, float]]:
    """
    Returns a dict keyed by (norm_player_name, norm_team) → {REC, YDS, TD, TGT, ...}.
    """
    rows = fetch_cfbd_category(year, "receiving")
    pivoted = pivot_stats(rows)
    result: dict[tuple[str, str], dict[str, float]] = {}
    for key, entry in pivoted.items():
        result[key] = entry["stats"]
    return result


def find_player_stats(
    player_name: str,
    school: str,
    lookup: dict[tuple[str, str], dict[str, float]],
) -> dict[str, float] | None:
    """
    Try to match player_name + school against the CFBD lookup using aliases.
    Returns the stats dict or None if not found.
    """
    norm_player = normalize_identity(player_name)
    aliases = school_aliases(school)

    # Exact name + school alias
    for alias in aliases:
        key = (norm_player, alias)
        if key in lookup:
            return lookup[key]

    # Abbreviated first name (e.g. "antonio williams" → "a williams")
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
    stats: dict[str, float] | None,
) -> dict[str, Any]:
    team = str(player.get("school", "")).strip()
    player_id = player.get("player_id")
    player_name = player.get("player_name")

    if stats is None:
        logging.warning(
            "No CFBD receiving stats found for %s (%s) season=%s", player_name, team, season
        )
        return {
            "player_id": player_id,
            "player_name": player_name,
            "team": team,
            "season": season,
            "season_type": "regular",
            "targets": 0,
            "receptions": 0,
            "screen_targets": 0,
            "screen_target_rate": None,
            "yards_per_target": None,
            "deep_target_rate": None,
            "depth_tag_coverage_rate": None,
            "team_pass_plays": None,
            "team_screen_plays": None,
            "team_screen_rate": None,
            "team_yards_per_pass": None,
            "source_name": f"CFBD season stats (year={season}, team={team}) — player not found",
            "source_url": f"{CFBD_BASE_URL}/stats/player/season?year={season}&category=receiving",
            "methodology_notes": METHODOLOGY_NOTE + " Player not matched in CFBD data.",
        }

    receptions = stats.get("REC", 0.0)
    yards = stats.get("YDS", 0.0)

    # CFBD sometimes returns TGT; fall back to estimate
    if "TGT" in stats:
        targets = int(round(stats["TGT"]))
        tgt_source = "CFBD TGT stat"
    else:
        targets = int(round(receptions / ASSUMED_CATCH_RATE)) if receptions > 0 else 0
        tgt_source = f"estimated (REC / {ASSUMED_CATCH_RATE:.2f})"

    yards_per_target = round(yards / targets, 1) if targets > 0 else None

    return {
        "player_id": player_id,
        "player_name": player_name,
        "team": team,
        "season": season,
        "season_type": "regular",
        "targets": targets,
        "receptions": int(round(receptions)),
        "screen_targets": 0,
        "screen_target_rate": None,
        "yards_per_target": yards_per_target,
        "deep_target_rate": None,
        "depth_tag_coverage_rate": None,
        "team_pass_plays": None,
        "team_screen_plays": None,
        "team_screen_rate": None,
        "team_yards_per_pass": None,
        "source_name": f"CFBD season stats (year={season}, team={team}); targets={tgt_source}",
        "source_url": f"{CFBD_BASE_URL}/stats/player/season?year={season}&category=receiving",
        "methodology_notes": METHODOLOGY_NOTE,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    players = load_json(args.players_input)
    if not isinstance(players, list):
        raise SystemExit("players-input must be a JSON array")

    wr_te_players = [p for p in players if p.get("position") in ("WR", "TE")]

    # Determine which years we need and fetch each year once
    needed_years: set[int] = set()
    for player in wr_te_players:
        class_year = int(player.get("class_year", 0))
        if class_year > 0:
            needed_years.add(class_year - 2)
            needed_years.add(class_year - 1)

    logging.info("Fetching CFBD receiving stats for years: %s", sorted(needed_years))
    year_lookups: dict[int, dict[tuple[str, str], dict[str, float]]] = {}
    for year in sorted(needed_years):
        logging.info("  Fetching year=%s …", year)
        year_lookups[year] = build_receiving_lookup(year)
        logging.info("  → %d player-team entries", len(year_lookups[year]))

    # Build and write profiles
    for player in wr_te_players:
        class_year = int(player.get("class_year", 0))
        if class_year <= 0:
            logging.warning(
                "Skipping %s — missing class_year", player.get("player_id", "?")
            )
            continue

        for season in (class_year - 2, class_year - 1):
            lookup = year_lookups.get(season, {})
            stats = find_player_stats(
                player["player_name"], player.get("school", ""), lookup
            )
            profile = build_profile(player, season, stats)
            output_path = args.output_dir / f"{player['player_id']}_{season}.json"
            write_json(output_path, profile)
            tgt = profile["targets"]
            rec = profile["receptions"]
            ypt = profile["yards_per_target"]
            logging.info(
                "%s (%s %s): %d targets, %d rec, %.1f yds/target",
                profile["player_name"], profile["team"], season,
                tgt, rec, ypt if ypt is not None else 0.0,
            )


if __name__ == "__main__":
    main()
