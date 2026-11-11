#!/usr/bin/env python3
"""Phase 1 prospect discovery: build/refresh the producer-only shadow pool.

Implements step 3 of docs/prospect-discovery-pipeline-design.md.

For class_year C, discovery_season = C - 1. The script:
  1. fetches the FBS team list for discovery_season (CFBD /teams/fbs),
  2. fetches each team's roster (CFBD /roster?team=&year=, via the existing
     compute_breakout_age.fetch_roster helper) for discovery_season and the
     two seasons before it, and filters positions locally,
  3. fetches season-to-date passing/rushing/receiving player stats
     (CFBD /stats/player/season?year=&category=, via the existing
     compute_production_scores.fetch_cfbd_category helper, cached — 3 requests total),
  4. keeps players with academic year >= 3, or academic year == 2 with a
     breakout under the existing compute_breakout_age thresholds,
  5. merges additively into data/raw/{class_year}_shadow_pool.json.

The shadow pool is NOT a model input and NOT runtime-visible. Promotion into the
real seed pool remains an operator decision (Phase 2, not implemented here).

Observed production notes (null-honest):
  - Team totals are sums of CFBD player rows for that team in the same category.
  - CFBD season stats carry no targets stat, so target_share and targets are
    always null. They are not estimated from receptions.
  - A player with no stat row in a category gets null for that category's
    fields, not zero. A sophomore whose breakout cannot be evaluated (null) is
    not admitted.
  - Stats are season-to-date as of the run date; reruns refresh them.

Academic year (verified against live CFBD on 2026-11-11): CFBD's roster
`year` field is not usable — 134/138 FBS rosters for 2026 report year 1 for
every player, and the 2025 rosters report year 1 for nearly everyone. So class
standing is derived from FBS roster tenure by CFBD player id instead (NFL
eligibility is three years removed from high school):
  - on any FBS roster two seasons before discovery_season -> academic_year 3
    (a lower bound: third season or later) -> eligible
  - first FBS roster one season before discovery_season -> academic_year 2
    -> eligible only with a breakout
  - on neither -> unknown (true freshmen, and FCS/JUCO arrivals) -> skipped
    and counted; add such players manually if wanted.
Redshirts are not distinguished.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import cfbd_cache
from scripts.cfbd_plays import REQUEST_DELAY_S, cfbd_headers, write_json
from scripts.compute_breakout_age import (
    BREAKOUT_THRESHOLDS,
    SHARE_BREAKOUT_CRITERIA,
    fetch_roster,
    roster_url,
)
from scripts.cfbd_cache import fetch_category as fetch_cfbd_category
from scripts.compute_production_scores import (
    CFBD_BASE_URL,
    normalize_identity,
    pivot_stats,
)

DISCOVERY_POSITIONS = ["WR", "RB", "TE", "QB"]
DISCOVERY_CLASS_YEAR = 2027

SCHEMA_VERSION = "prospect-shadow-pool-v0.1.0"
DISCLAIMER = (
    "Producer-only discovery list. Not rankings, not Rookie Alpha inputs, not "
    "runtime-visible, not draft predictions. Inclusion means only that CFBD roster "
    "data placed the player at a tracked position with draft-eligible academic "
    "standing (or a sophomore breakout). Promotion to the real seed pool is an "
    "operator decision."
)
OBSERVATION_METHOD = (
    "Season-to-date CFBD /stats/player/season. Shares divide player totals by the "
    "sum of all CFBD player rows for the same team and category. target_share and "
    "targets are null because CFBD season stats carry no targets stat. Missing stat "
    "rows are null, never zero."
)

# Fields that a rerun may refresh from source. Everything else on an existing
# entry (identity, operator_notes, manually_added, status, status_history,
# combine_invited) is preserved.
REFRESHABLE_FIELDS = (
    "position",
    "school",
    "academic_year",
    "academic_year_source",
    "discovery_source",
    "discovery_season",
    "observed_production",
    "breakout_flagged",
    "young_breakout",
    "last_seen_date",
)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize_identity(value)).strip("-")


def make_player_id(position: str, name: str, school: str) -> str:
    return f"{position.lower()}-{slugify(name)}-{slugify(school)}"


def roster_name(entry: dict[str, Any]) -> str:
    first = entry.get("firstName") or entry.get("first_name") or ""
    last = entry.get("lastName") or entry.get("last_name") or ""
    return " ".join(f"{first} {last}".split())


def roster_ids(rosters: dict[str, list[dict[str, Any]]]) -> set[str]:
    return {str(e["id"]) for roster in rosters.values() for e in roster if e.get("id") is not None}


def tenure_academic_year(
    entry: dict[str, Any], ids_two_back: set[str], ids_one_back: set[str]
) -> int | None:
    """Lower-bound class standing from FBS roster tenure; None when unknown."""
    cfbd_id = entry.get("id")
    if cfbd_id is None:
        return None
    if str(cfbd_id) in ids_two_back:
        return 3
    if str(cfbd_id) in ids_one_back:
        return 2
    return None


def team_totals(pivoted: dict[tuple[str, str], dict[str, Any]], stat: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    for (_, norm_team), data in pivoted.items():
        value = data["stats"].get(stat)
        if value is not None:
            totals[norm_team] = totals.get(norm_team, 0.0) + value
    return totals


def _share(value: float | None, total: float | None) -> float | None:
    if value is None or not total:
        return None
    return round(value / total, 4)


def observe_production(
    name: str,
    school: str,
    passing: dict[tuple[str, str], dict[str, Any]],
    rushing: dict[tuple[str, str], dict[str, Any]],
    receiving: dict[tuple[str, str], dict[str, Any]],
    totals: dict[str, dict[str, float]],
) -> dict[str, float | None]:
    key = (normalize_identity(name), normalize_identity(school))
    team = key[1]
    pass_stats = passing.get(key, {}).get("stats", {})
    rush_stats = rushing.get(key, {}).get("stats", {})
    rec_stats = receiving.get(key, {}).get("stats", {})

    rec_yds = rec_stats.get("YDS")
    carries = rush_stats.get("CAR")
    rush_yds = rush_stats.get("YDS")
    return {
        "pass_attempts": pass_stats.get("ATT"),
        "rush_attempts": carries,
        "rush_yards": rush_yds,
        "receptions": rec_stats.get("REC"),
        "receiving_yards": rec_yds,
        "targets": None,
        "target_share": None,
        "receiving_yard_share": _share(rec_yds, totals["rec_yds"].get(team)),
        "rush_share": _share(carries, totals["rush_att"].get(team)),
        "rush_yard_share": _share(rush_yds, totals["rush_yds"].get(team)),
    }


def evaluate_breakout(position: str, observed: dict[str, float | None]) -> bool | None:
    """True/False against existing breakout thresholds; None when nothing is observable."""
    had_data = False
    for field, threshold in SHARE_BREAKOUT_CRITERIA.get(position, []):
        value = observed.get(field)
        if value is not None:
            had_data = True
            if value >= threshold:
                return True
    field, threshold = BREAKOUT_THRESHOLDS[position]
    value = observed.get(field)
    if value is not None:
        had_data = True
        if value >= threshold:
            return True
    return False if had_data else None


def build_candidates(
    rosters: dict[str, list[dict[str, Any]]],
    passing: dict[tuple[str, str], dict[str, Any]],
    rushing: dict[tuple[str, str], dict[str, Any]],
    receiving: dict[tuple[str, str], dict[str, Any]],
    class_year: int,
    run_date: str,
    ids_two_back: set[str],
    ids_one_back: set[str],
    positions: list[str] = DISCOVERY_POSITIONS,
) -> tuple[list[dict[str, Any]], int]:
    """Return (eligible candidate entries, count skipped for unknown academic year)."""
    discovery_season = class_year - 1
    totals = {
        "rec_yds": team_totals(receiving, "YDS"),
        "rush_att": team_totals(rushing, "CAR"),
        "rush_yds": team_totals(rushing, "YDS"),
    }
    candidates: list[dict[str, Any]] = []
    unknown_year = 0
    for school in sorted(rosters):
        for entry in rosters[school]:
            position = str(entry.get("position") or "").strip().upper()
            name = roster_name(entry)
            if position not in positions or not name:
                continue
            academic_year = tenure_academic_year(entry, ids_two_back, ids_one_back)
            if academic_year is None:
                unknown_year += 1
                continue
            observed = observe_production(name, school, passing, rushing, receiving, totals)
            breakout = evaluate_breakout(position, observed)
            if academic_year == 2 and breakout is not True:
                continue
            candidates.append(
                {
                    "player_id": make_player_id(position, name, school),
                    "cfbd_player_id": str(entry["id"]) if entry.get("id") is not None else None,
                    "player_name": name,
                    "position": position,
                    "school": school,
                    "class_year": class_year,
                    "academic_year": academic_year,
                    "academic_year_source": "cfbd_fbs_roster_tenure",
                    "discovery_source": "cfbd_roster",
                    "discovery_season": discovery_season,
                    "status": "watchlist",
                    "status_history": [
                        {"status": "watchlist", "date": run_date, "reason": "cfbd_roster_discovery"}
                    ],
                    "observed_production": {
                        "season": discovery_season,
                        "through_date": run_date,
                        **observed,
                    },
                    "breakout_flagged": breakout,
                    "young_breakout": academic_year == 2 and breakout is True,
                    "combine_invited": False,
                    "operator_notes": "",
                    "manually_added": False,
                    "last_seen_date": run_date,
                }
            )
    return candidates, unknown_year


def _merge_key(entry: dict[str, Any]) -> str:
    cfbd_id = entry.get("cfbd_player_id")
    return f"cfbd:{cfbd_id}" if cfbd_id else f"id:{entry['player_id']}"


def merge_players(
    existing: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int, int]:
    """Additive merge. Returns (players, added_count, refreshed_count).

    Existing entries are never removed or demoted. Matching is by CFBD player id
    when present, else by player_id.
    """
    by_key: dict[str, dict[str, Any]] = {}
    for entry in existing:
        by_key[_merge_key(entry)] = entry
        by_key.setdefault(f"id:{entry['player_id']}", entry)

    added = refreshed = 0
    for candidate in candidates:
        current = by_key.get(_merge_key(candidate)) or by_key.get(f"id:{candidate['player_id']}")
        if current is None:
            existing.append(candidate)
            by_key[_merge_key(candidate)] = candidate
            by_key.setdefault(f"id:{candidate['player_id']}", candidate)
            added += 1
            continue
        for field in REFRESHABLE_FIELDS:
            current[field] = candidate[field]
        if not current.get("cfbd_player_id") and candidate.get("cfbd_player_id"):
            current["cfbd_player_id"] = candidate["cfbd_player_id"]
        refreshed += 1

    return sorted(existing, key=lambda e: e["player_id"]), added, refreshed


def fetch_fbs_teams(year: int, max_retries: int = 5) -> list[str]:
    url = f"{CFBD_BASE_URL}/teams/fbs?{urlencode({'year': year})}"
    payload = cfbd_cache.load(url)
    if payload is not cfbd_cache.MISS:
        return sorted({str(t["school"]) for t in payload if t.get("school")})
    for attempt in range(max_retries):
        try:
            with urlopen(Request(url, headers=cfbd_headers()), timeout=60) as resp:
                payload = json.load(resp)
            break
        except HTTPError as exc:
            if exc.code == 429 and attempt < max_retries - 1:
                wait = max(10, 5 * (2 ** attempt))
                logging.warning("Rate limited (429) fetching FBS teams — retrying in %ds", wait)
                time.sleep(wait)
                continue
            raise SystemExit(f"CFBD /teams/fbs failed for year={year}: HTTP {exc.code}") from exc
        except URLError as exc:
            raise SystemExit(f"CFBD /teams/fbs failed for year={year}: {exc.reason}") from exc
    else:
        raise SystemExit(f"CFBD /teams/fbs rate limited after {max_retries} attempts")
    if not isinstance(payload, list):
        raise SystemExit(f"Unexpected /teams/fbs payload: {type(payload).__name__}")
    cfbd_cache.store(url, payload)
    return sorted({str(t["school"]) for t in payload if t.get("school")})


def fetch_rosters(
    teams: list[str], year: int, fetch: Callable[[str, int], list[dict[str, Any]]] = fetch_roster
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    rosters: dict[str, list[dict[str, Any]]] = {}
    empty_or_failed: list[str] = []
    for i, team in enumerate(teams, 1):
        if cfbd_cache.load(roster_url(team, year)) is cfbd_cache.MISS:
            time.sleep(REQUEST_DELAY_S)
        roster = fetch(team, year)
        if roster:
            rosters[team] = roster
        else:
            empty_or_failed.append(team)
        if i % 20 == 0:
            logging.info("Fetched %d/%d rosters", i, len(teams))
    return rosters, empty_or_failed


def load_existing(path: Path, class_year: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("class_year") != class_year:
        raise SystemExit(f"{path} is for class_year {payload.get('class_year')}, not {class_year}")
    return list(payload.get("players", []))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover/refresh the producer-only prospect shadow pool")
    parser.add_argument("--class-year", type=int, default=DISCOVERY_CLASS_YEAR)
    parser.add_argument("--output", type=Path, default=None,
                        help="Defaults to data/raw/{class_year}_shadow_pool.json")
    parser.add_argument("--run-date", default=datetime.date.today().isoformat(),
                        help="Date stamped on status_history and observations (YYYY-MM-DD)")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    class_year = args.class_year
    season = class_year - 1
    output = args.output or Path(f"data/raw/{class_year}_shadow_pool.json")
    existing = load_existing(output, class_year)

    teams = fetch_fbs_teams(season)
    logging.info("%d FBS teams for %d", len(teams), season)
    rosters, empty_or_failed = fetch_rosters(teams, season)
    tenure: dict[int, set[str]] = {}
    for back in (1, 2):
        year = season - back
        logging.info("Fetching %d rosters for roster tenure", year)
        prior, _ = fetch_rosters(fetch_fbs_teams(year), year)
        tenure[back] = roster_ids(prior)

    stats = {}
    for category in ("passing", "rushing", "receiving"):
        time.sleep(REQUEST_DELAY_S)
        stats[category] = pivot_stats(fetch_cfbd_category(season, category))

    candidates, unknown_year = build_candidates(
        rosters, stats["passing"], stats["rushing"], stats["receiving"], class_year, args.run_date,
        ids_two_back=tenure[2],
        ids_one_back=tenure[1],
    )
    players, added, refreshed = merge_players(existing, candidates)

    write_json(output, {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "prospect_shadow_pool",
        "status": "producer_only",
        "class_year": class_year,
        "discovery_season": season,
        "disclaimer": DISCLAIMER,
        "observation_method": OBSERVATION_METHOD,
        "eligibility_rule": "academic_year >= 3, or academic_year == 2 with breakout_flagged == true",
        "academic_year_rule": "FBS roster tenure by CFBD player id: on a roster two seasons back -> 3 (lower bound); first roster one season back -> 2; else unknown and skipped",
        "positions": DISCOVERY_POSITIONS,
        "last_run": {
            "run_date": args.run_date,
            "fbs_teams_requested": len(teams),
            "rosters_empty_or_failed": empty_or_failed,
            "fbs_roster_ids_two_seasons_back": len(tenure[2]),
            "fbs_roster_ids_one_season_back": len(tenure[1]),
            "skipped_unknown_academic_year": unknown_year,
            "candidates_this_run": len(candidates),
            "added": added,
            "refreshed": refreshed,
        },
        "players": players,
    })
    logging.info(
        "Wrote %s: %d players (%d added, %d refreshed, %d rosters empty/failed, %d unknown-year skipped)",
        output, len(players), added, refreshed, len(empty_or_failed), unknown_year,
    )


if __name__ == "__main__":
    main()
