#!/usr/bin/env python3
"""Shared CFBD play-by-play fetch utilities used by position-specific profile scripts."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from http.client import IncompleteRead
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.compute_production_scores import CFBD_BASE_URL, normalize_identity

_WARNED_MISSING_KEY = False


def cfbd_headers() -> dict[str, str]:
    global _WARNED_MISSING_KEY
    headers = {"Accept": "application/json"}
    api_key = (os.getenv("CFBD_API_KEY") or "").strip().strip('"').strip("'")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif not _WARNED_MISSING_KEY:
        logging.warning("CFBD_API_KEY not set; using unauthenticated CFBD requests (may be rate-limited).")
        _WARNED_MISSING_KEY = True
    return headers


REQUEST_DELAY_S = 1.1  # seconds between CFBD requests — stays well under rate limits


def fetch_team_plays(year: int, team: str, season_type: str) -> list[dict[str, Any]]:
    """Fetch all plays for a team/year from CFBD, week-by-week with retry."""
    season_types = ["regular", "postseason"] if season_type == "both" else ["regular"]
    week_ranges = {"regular": range(1, 19), "postseason": range(1, 6)}
    plays: list[dict[str, Any]] = []

    for single_type in season_types:
        for week in week_ranges[single_type]:
            params = urlencode({"year": year, "team": team, "seasonType": single_type, "week": week})
            url = f"{CFBD_BASE_URL}/plays?{params}"
            payload: list[dict[str, Any]] | None = None
            for attempt in range(5):
                try:
                    time.sleep(REQUEST_DELAY_S)
                    request = Request(url=url, headers=cfbd_headers())
                    with urlopen(request, timeout=60) as response:
                        payload = json.load(response)
                    break
                except IncompleteRead:
                    wait = 2 ** attempt
                    logging.warning(
                        "IncompleteRead for %s week %s attempt %s — retrying in %ss",
                        team, week, attempt + 1, wait,
                    )
                    time.sleep(wait)
                except HTTPError as exc:
                    if exc.code == 429:
                        wait = 10 * (2 ** attempt)
                        logging.warning(
                            "Rate limited (429) for %s week %s attempt %s — retrying in %ss",
                            team, week, attempt + 1, wait,
                        )
                        time.sleep(wait)
                    else:
                        raise SystemExit(
                            f"CFBD API request failed for {team} {year} week {week} ({single_type}): HTTP {exc.code}"
                        ) from exc
                except URLError as exc:
                    raise SystemExit(
                        f"CFBD API request failed for {team} {year} week {week} ({single_type}): {exc.reason}"
                    ) from exc
            if payload is None:
                raise SystemExit(f"CFBD API failed after 5 attempts for {team} {year} week {week}")
            if not isinstance(payload, list):
                raise SystemExit(
                    f"Unexpected CFBD response for {team} {year} week {week}: "
                    f"expected list, got {type(payload).__name__}"
                )
            plays.extend(payload)

    return plays


def safe_rate(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc.msg} (line {exc.lineno}, column {exc.colno})") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def is_targeted_player(play_text: str, player_name: str) -> bool:
    """Return True if player_name (or its first-initial abbreviation) appears in play_text."""
    normalized_text = normalize_identity(play_text)
    normalized_player = normalize_identity(player_name)
    if normalized_player in normalized_text:
        return True
    # CFBD play text uses abbreviated first names (e.g. "C. Tate" not "Carnell Tate").
    parts = normalized_player.split()
    if len(parts) >= 2:
        abbreviated = f"{parts[0][0]} {' '.join(parts[1:])}"
        if abbreviated in normalized_text:
            return True
    return False


def play_type_of(p: dict[str, Any]) -> str:
    return str(p.get("playType") or p.get("play_type") or "")


def play_text_of(p: dict[str, Any]) -> str:
    return str(p.get("playText") or p.get("play_text") or "")


def yards_gained_of(p: dict[str, Any]) -> float:
    val = p.get("yardsGained") if p.get("yardsGained") is not None else p.get("yards_gained", 0)
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def filter_offense_plays(plays: list[dict[str, Any]], player_team: str) -> list[dict[str, Any]]:
    """Return only plays where player_team is on offense.

    Plays without an offense field are kept (e.g. test fixtures).
    """
    return [
        play for play in plays
        if not (play.get("offense") or play.get("offenseTeam"))
        or normalize_identity(str(play.get("offense") or play.get("offenseTeam") or "")) == player_team
    ]
