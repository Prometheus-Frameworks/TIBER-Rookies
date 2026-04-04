#!/usr/bin/env python3
"""Compute breakout_age and young_breakout_flag for 2026 prospects.

For each player, finds the earliest season in their play profile data where
they met the position-specific breakout threshold. Uses CFBD roster data to
get academic year (1=FR, 2=SO, 3=JR, 4=SR, 5=5th year), then estimates age
as 17 + academic_year. This is a ±1 year approximation; exact DOBs are not
available from CFBD.

Limitation: only looks at seasons present in play profile files (2024, 2025 by
default). Players whose breakout predates those seasons (e.g. Nick Singleton
2022) will show breakout_age=null. This is a known data gap, not a bug.

Breakout thresholds (inclusive):
  WR / TE  — targets  >= 50
  QB       — pass_attempts >= 150
  RB       — rush_attempts >= 80

young_breakout_flag: True if breakout_age <= 20
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.cfbd_plays import cfbd_headers, load_json, write_json
from scripts.compute_production_scores import CFBD_BASE_URL, normalize_identity

DEFAULT_PLAYERS_INPUT = Path("data/processed/2026_college_production.json")
DEFAULT_CONTEXT_PATH = Path("data/processed/2026_prospect_context.json")
DEFAULT_WR_DIR = Path("data/processed/wr_route_profiles")
DEFAULT_QB_DIR = Path("data/processed/qb_play_profiles")
DEFAULT_RB_DIR = Path("data/processed/rb_play_profiles")

# Breakout thresholds by position
BREAKOUT_THRESHOLDS: dict[str, tuple[str, int]] = {
    "WR": ("targets", 50),
    "TE": ("targets", 50),
    "QB": ("pass_attempts", 150),
    "RB": ("rush_attempts", 80),
}

YOUNG_BREAKOUT_MAX_AGE = 20  # breakout_age <= this → young_breakout_flag = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute breakout age for 2026 prospects")
    parser.add_argument("--players-input", type=Path, default=DEFAULT_PLAYERS_INPUT)
    parser.add_argument("--context-path", type=Path, default=DEFAULT_CONTEXT_PATH)
    parser.add_argument("--wr-dir", type=Path, default=DEFAULT_WR_DIR)
    parser.add_argument("--qb-dir", type=Path, default=DEFAULT_QB_DIR)
    parser.add_argument("--rb-dir", type=Path, default=DEFAULT_RB_DIR)
    return parser.parse_args()


def profile_dir_for_position(position: str, args: argparse.Namespace) -> Path:
    if position == "QB":
        return args.qb_dir
    if position == "RB":
        return args.rb_dir
    return args.wr_dir  # WR and TE


def fetch_roster(team: str, year: int) -> list[dict[str, Any]]:
    """Fetch CFBD roster for team/year. Returns empty list on failure."""
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError

    params = urlencode({"team": team, "year": year})
    url = f"{CFBD_BASE_URL}/roster?{params}"
    try:
        req = Request(url, headers=cfbd_headers())
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data if isinstance(data, list) else []
    except (HTTPError, URLError, Exception) as exc:
        logging.warning("Could not fetch roster for %s %s: %s", team, year, exc)
        return []


def find_academic_year(roster: list[dict[str, Any]], player_name: str) -> int | None:
    """Find a player's academic year in a roster by name matching."""
    normalized_target = normalize_identity(player_name)
    for entry in roster:
        full = str(entry.get("fullName") or entry.get("full_name") or
                   f"{entry.get('first_name', '')} {entry.get('last_name', '')}").strip()
        if normalize_identity(full) == normalized_target:
            year = entry.get("year") or entry.get("eligibilityYear")
            if year is not None:
                try:
                    return int(year)
                except (TypeError, ValueError):
                    pass
    return None


def estimated_age(academic_year: int) -> int:
    """Approximate age at season start given college academic year (1–5)."""
    return 17 + academic_year


def load_profile_seasons(
    player_id: str,
    profile_dir: Path,
    seasons: list[int],
) -> list[tuple[int, dict[str, Any]]]:
    """Load (season, profile_data) pairs for available season files."""
    results = []
    for season in sorted(seasons):
        path = profile_dir / f"{player_id}_{season}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                results.append((season, data))
            except json.JSONDecodeError:
                logging.warning("Could not parse %s", path)
    return results


def compute_breakout_for_player(
    player: dict[str, Any],
    args: argparse.Namespace,
    roster_cache: dict[tuple[str, int], list[dict[str, Any]]],
) -> dict[str, Any]:
    """Return breakout fields for one player."""
    player_id = str(player.get("player_id", ""))
    player_name = str(player.get("player_name", ""))
    position = str(player.get("position", ""))
    school = str(player.get("school", ""))
    class_year = int(player.get("class_year", 0))

    profile_dir = profile_dir_for_position(position, args)
    seasons_to_check = [class_year - 2, class_year - 1]
    season_profiles = load_profile_seasons(player_id, profile_dir, seasons_to_check)

    if position not in BREAKOUT_THRESHOLDS:
        return {"breakout_age": None, "age_at_first_impact_season": None, "young_breakout_flag": None}

    threshold_field, threshold_value = BREAKOUT_THRESHOLDS[position]

    breakout_age: int | None = None
    age_at_first_impact: int | None = None

    for season, profile in season_profiles:
        # Check if this season meets the breakout threshold
        stat_value = profile.get(threshold_field) or 0
        if stat_value < threshold_value:
            continue  # below threshold — not a breakout season

        # Fetch roster for academic year (cached)
        cache_key = (school, season)
        if cache_key not in roster_cache:
            roster_cache[cache_key] = fetch_roster(school, season)
        roster = roster_cache[cache_key]

        academic_yr = find_academic_year(roster, player_name)
        if academic_yr is None:
            logging.warning(
                "Could not find %s in %s %s roster; skipping season for age calc",
                player_name, school, season,
            )
            continue

        age = estimated_age(academic_yr)

        # Track earliest impact season
        if age_at_first_impact is None:
            age_at_first_impact = age

        # Breakout is the first qualifying season
        if breakout_age is None:
            breakout_age = age
            break  # earliest qualifying season found

    young_breakout_flag: bool | None = None
    if breakout_age is not None:
        young_breakout_flag = breakout_age <= YOUNG_BREAKOUT_MAX_AGE

    return {
        "breakout_age": breakout_age,
        "age_at_first_impact_season": age_at_first_impact,
        "young_breakout_flag": young_breakout_flag,
    }


def update_context_entry(
    existing: dict[str, Any],
    breakout_data: dict[str, Any],
    player: dict[str, Any],
) -> dict[str, Any]:
    """Merge breakout fields into an existing context entry."""
    updated = dict(existing)
    updated["breakout_age"] = breakout_data["breakout_age"]
    updated["age_at_first_impact_season"] = breakout_data["age_at_first_impact_season"]
    updated["young_breakout_flag"] = breakout_data["young_breakout_flag"]

    # Add/remove young_breakout evidence tag
    tags = list(updated.get("evidence_tags") or [])
    if "young_breakout" in tags:
        tags.remove("young_breakout")
    if breakout_data["young_breakout_flag"] is True:
        tags.insert(0, "young_breakout")
    updated["evidence_tags"] = tags

    return updated


def make_minimal_context_entry(
    player: dict[str, Any],
    breakout_data: dict[str, Any],
) -> dict[str, Any]:
    """Create a minimal context entry for a player not yet in the context file."""
    tags = []
    if breakout_data["young_breakout_flag"] is True:
        tags.append("young_breakout")
    if player.get("early_declare_flag"):
        tags.append("early_declare")

    return {
        "player_id": player.get("player_id"),
        "player_name": player.get("player_name"),
        "position": player.get("position"),
        "school": player.get("school"),
        "class_year": player.get("class_year"),
        "early_declare_flag": player.get("early_declare_flag", None),
        "breakout_age": breakout_data["breakout_age"],
        "age_at_first_impact_season": breakout_data["age_at_first_impact_season"],
        "young_breakout_flag": breakout_data["young_breakout_flag"],
        "evidence_tags": tags,
        "context_flags": [],
        "evidence_summary": None,
        "context_source": "compute_breakout_age.py",
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    players: list[dict[str, Any]] = load_json(args.players_input)
    if not isinstance(players, list):
        raise SystemExit("players-input must be a JSON array")

    # Load existing context entries, keyed by player_id
    context_entries: list[dict[str, Any]] = []
    if args.context_path.exists():
        raw = json.loads(args.context_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            context_entries = raw
    context_by_id = {str(e.get("player_id", "")): e for e in context_entries}

    roster_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
    updated_entries: list[dict[str, Any]] = []

    for player in players:
        player_id = str(player.get("player_id", ""))
        player_name = player.get("player_name", "unknown")
        position = player.get("position", "")

        if position not in BREAKOUT_THRESHOLDS:
            logging.info("Skipping %s (%s) — no breakout threshold defined", player_name, position)
            continue

        breakout_data = compute_breakout_for_player(player, args, roster_cache)

        if player_id in context_by_id:
            entry = update_context_entry(context_by_id[player_id], breakout_data, player)
        else:
            entry = make_minimal_context_entry(player, breakout_data)

        updated_entries.append(entry)

        age_str = str(breakout_data["breakout_age"]) if breakout_data["breakout_age"] else "null"
        flag_str = "young ✓" if breakout_data["young_breakout_flag"] else (
            "late" if breakout_data["young_breakout_flag"] is False else "unknown"
        )
        print(f"{player_name:30} {position} breakout_age={age_str:4} ({flag_str})")

    write_json(args.context_path, updated_entries)
    logging.info("Updated %s with %d entries", args.context_path, len(updated_entries))


if __name__ == "__main__":
    main()
