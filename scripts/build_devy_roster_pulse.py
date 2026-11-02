#!/usr/bin/env python3
"""Build a monthly Devy roster pulse candidate-delta artifact from CFBD data.

Discovery-only: surfaces in-season production leaders who are eligible for a
target NFL draft class and are not on the curated seed watchlist, plus the
current roster status of every seed-watchlist row in that class. Output is for
manual review; it never mutates the seed watchlist.

Eligibility rule: a player is eligible for draft class D when they are three
seasons removed from high school, i.e. their high-school recruiting class year
is <= D - 3. When no recruiting record links to the player, the CFBD roster
class year is used as a lower-confidence fallback.

Requires CFBD_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.cfbd_plays import cfbd_headers
from scripts.compute_production_scores import CFBD_BASE_URL, normalize_identity
from scripts.validate_devy_roster_pulse import (
    CURRENT_PULSE_SCHEMA_VERSION,
    PULSE_ARTIFACT_TYPE,
    validate_devy_roster_pulse,
)

POSITIONS = ("QB", "RB", "WR", "TE")
RECRUIT_POSITION_MAP = {"PRO": "QB", "DUAL": "QB", "APB": "RB"}
STAT_CATEGORIES = ("passing", "rushing", "receiving")
DEFAULT_WATCHLIST = Path("data/devy/devy_seed_watchlist_2026.json")
REQUEST_DELAY_S = 1.1


def cfbd_get(path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    url = f"{CFBD_BASE_URL}{path}?{urlencode(params)}"
    for attempt in range(5):
        time.sleep(REQUEST_DELAY_S)
        try:
            with urlopen(Request(url=url, headers=cfbd_headers()), timeout=60) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code == 429:
                time.sleep(10 * (2 ** attempt))
                continue
            raise SystemExit(f"CFBD request failed: {url} HTTP {exc.code}") from exc
        except URLError as exc:
            raise SystemExit(f"CFBD request failed: {url} {exc.reason}") from exc
        if not isinstance(payload, list):
            raise SystemExit(f"Unexpected CFBD response for {url}: expected list")
        return payload
    raise SystemExit(f"CFBD gave up after 5 attempts: {url}")


def fetch_inputs(season: int, draft_class: int) -> dict[str, Any]:
    recruit_years = range(draft_class - 6, season + 1)
    return {
        "roster": cfbd_get("/roster", {"year": season}),
        "recruits": [
            row
            for year in recruit_years
            for row in cfbd_get("/recruiting/players", {"year": year, "classification": "HighSchool"})
        ],
        "stats": [
            row
            for category in STAT_CATEGORIES
            for row in cfbd_get("/stats/player/season", {"year": season, "category": category})
        ],
        "source_urls": [
            f"{CFBD_BASE_URL}/roster?year={season}",
            f"{CFBD_BASE_URL}/recruiting/players?year={recruit_years[0]}..{recruit_years[-1]}&classification=HighSchool",
            f"{CFBD_BASE_URL}/stats/player/season?year={season}&category=passing|rushing|receiving",
        ],
    }


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def rank_metric(position: str, stats: dict[str, dict[str, float]]) -> tuple[str, float]:
    if position == "QB":
        return "passing_yards", stats.get("passing", {}).get("YDS", 0.0)
    if position == "RB":
        return "scrimmage_yards", stats.get("rushing", {}).get("YDS", 0.0) + stats.get("receiving", {}).get("YDS", 0.0)
    return "receiving_yards", stats.get("receiving", {}).get("YDS", 0.0)


def build_pulse(
    *,
    roster: list[dict[str, Any]],
    recruits: list[dict[str, Any]],
    stats: list[dict[str, Any]],
    watchlist: dict[str, Any],
    season: int,
    draft_class: int,
    top_n: int,
    source_urls: list[str],
    generated_at: datetime,
) -> dict[str, Any]:
    max_recruit_year = draft_class - 3
    min_roster_year = draft_class - season + 2  # e.g. 2027 class in 2026 season -> roster year >= 3

    roster_by_id = {str(row.get("id")): row for row in roster if row.get("id") is not None}
    recruit_by_athlete = {
        str(row["athleteId"]): row for row in recruits if row.get("athleteId") is not None
    }

    players: dict[str, dict[str, Any]] = {}
    for row in stats:
        pid = str(row.get("playerId"))
        player = players.setdefault(
            pid, {"name": row.get("player"), "team": row.get("team"), "stats": {}}
        )
        player["stats"].setdefault(row.get("category"), {})[row.get("statType")] = _num(row.get("stat"))

    eligible: dict[str, list[dict[str, Any]]] = {pos: [] for pos in POSITIONS}
    unknown_eligibility = 0
    for pid, player in players.items():
        roster_row = roster_by_id.get(pid)
        recruit = recruit_by_athlete.get(pid)
        if roster_row is None and recruit is None:
            unknown_eligibility += 1
            continue
        position =(roster_row or {}).get("position") or RECRUIT_POSITION_MAP.get(
            (recruit or {}).get("position"), (recruit or {}).get("position")
        )
        if position not in POSITIONS:
            continue
        if recruit and recruit.get("year") is not None:
            if int(recruit["year"]) > max_recruit_year:
                continue
            class_year_source = "recruiting_profile"
        elif roster_row and roster_row.get("year") is not None:
            if int(roster_row["year"]) < min_roster_year:
                continue
            class_year_source = "roster"
        else:
            unknown_eligibility += 1
            continue  # linked record exists but carries no class year
        metric, value = rank_metric(position, player["stats"])
        eligible[position].append({
            "pid": pid,
            "name": player["name"],
            "team": player["team"],
            "position": position,
            "stats": player["stats"],
            "metric": metric,
            "value": value,
            "class_year_source": class_year_source,
            "recruiting_class_year": (recruit or {}).get("year"),
            "roster_class_year": (roster_row or {}).get("year"),
            "recruiting_stars": (recruit or {}).get("stars"),
        })

    for pos in POSITIONS:
        eligible[pos].sort(key=lambda p: p["value"], reverse=True)
        for rank, entry in enumerate(eligible[pos], start=1):
            entry["rank"] = rank

    eligible_by_name = {
        (normalize_identity(p["name"] or ""), p["position"]): p for pos in POSITIONS for p in eligible[pos]
    }
    roster_by_name = {
        (normalize_identity(f"{r.get('firstName', '')} {r.get('lastName', '')}"), r.get("position")): r
        for r in roster
    }

    def production_evidence(entry: dict[str, Any]) -> dict[str, Any]:
        return {
            "season": season,
            "rank_metric": entry["metric"],
            "rank_metric_value": entry["value"],
            "position_rank_among_eligible": entry["rank"],
            "season_stats": entry["stats"],
        }

    def eligibility_notes(entry: dict[str, Any]) -> list[str]:
        if entry["class_year_source"] == "recruiting_profile":
            return [f"Eligibility inferred from {entry['recruiting_class_year']} high-school recruiting class (<= {max_recruit_year})."]
        return [f"No linked recruiting record; eligibility inferred from CFBD roster class year {entry['roster_class_year']} only."]

    candidates: list[dict[str, Any]] = []
    tracked_keys: set[tuple[str, str]] = set()

    for row in watchlist.get("prospects", []):
        if row.get("projected_draft_class") != draft_class:
            continue
        key = (normalize_identity(row["player_name"]), row["position"])
        tracked_keys.add(key)
        entry = eligible_by_name.get(key)
        roster_row = roster_by_name.get(key)
        current_school = (entry or {}).get("team") or (roster_row or {}).get("team")
        if current_school is None:
            status, tags = "missing_from_roster", ["seed_watchlist_tracked", "not_found_on_current_roster"]
            notes = [
                f"Not found on CFBD {season} roster or stat feeds; may have declared, been drafted, left FBS, or have a name mismatch.",
            ]
        elif normalize_identity(current_school) != normalize_identity(row["school"]):
            status, tags = "program_changed", ["seed_watchlist_tracked", "program_changed"]
            notes = [f"Seed watchlist school {row['school']!r}; CFBD {season} lists {current_school!r}."]
        else:
            status, tags = "still_present", ["seed_watchlist_tracked"]
            notes = [f"Found on CFBD {season} data at {current_school}."]
        candidate = {
            "player_name": row["player_name"],
            "school": current_school or row["school"],
            "position": row["position"],
            "roster_status": status,
            "existing_seed_watchlist_match": True,
            "matched_player_id": row["player_id"],
            "class_year_source": "manual",
            "projected_draft_class_candidate": draft_class,
            "prior_college_production_found": None,
            "confidence_band": "MEDIUM",
            "candidate_tags": tags,
            "source_urls": source_urls,
            "source_notes": notes + ["Class year taken from curated seed watchlist row."],
            "needs_manual_review": True,
            "auto_seed_watchlist_mutation": "none",
        }
        if entry:
            candidate["production_evidence"] = production_evidence(entry)
        candidates.append(candidate)

    for pos in POSITIONS:
        for entry in eligible[pos][:top_n]:
            if (normalize_identity(entry["name"] or ""), pos) in tracked_keys:
                continue
            tags = [f"draft_class_{draft_class}_candidate", "season_production_leader"]
            if entry["class_year_source"] == "roster":
                tags.append("needs_class_year_verification")
            candidates.append({
                "player_name": entry["name"],
                "school": entry["team"],
                "position": pos,
                "roster_status": "still_present",
                "existing_seed_watchlist_match": False,
                "matched_player_id": None,
                "cfbd_player_id": entry["pid"],
                "class_year_source": entry["class_year_source"],
                "recruiting_class_year": entry["recruiting_class_year"],
                "recruiting_stars": entry["recruiting_stars"],
                "projected_draft_class_candidate": draft_class,
                "prior_college_production_found": None,
                "confidence_band": "MEDIUM" if entry["class_year_source"] == "recruiting_profile" else "LOW",
                "candidate_tags": tags,
                "production_evidence": production_evidence(entry),
                "source_urls": source_urls,
                "source_notes": [
                    f"Rank {entry['rank']} {pos} by {entry['metric']} among {draft_class}-eligible players in CFBD {season} season stats.",
                    *eligibility_notes(entry),
                ],
                "needs_manual_review": True,
                "auto_seed_watchlist_mutation": "none",
            })

    pulse_month = generated_at.strftime("%Y-%m")
    return {
        "schema_version": CURRENT_PULSE_SCHEMA_VERSION,
        "artifact_type": PULSE_ARTIFACT_TYPE,
        "pulse_month": pulse_month,
        "generated_at": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_draft_class": draft_class,
        "college_season": season,
        "input_sources": source_urls + [str(DEFAULT_WATCHLIST)],
        "comparison_basis": (
            f"CFBD {season} season-to-date stats for {draft_class}-eligible QB/RB/WR/TE (top {top_n} per position) "
            f"compared against {draft_class}-class rows in the curated seed watchlist."
        ),
        "candidates": candidates,
        "warnings": [
            "Season-to-date production ranks are discovery signals only, not rankings or player-quality claims.",
            "Eligibility is inferred from recruiting class or roster class year; early-declare and redshirt status need manual verification.",
            f"{unknown_eligibility} stat-feed players had no roster or recruiting record and were excluded.",
        ],
        "intake_audit": {
            "intake_method": "cfbd_api_script_generated_candidate",
            "promotion_status": "non_promoted_discovery_only",
            "validation_command": f"python3 scripts/validate_devy_roster_pulse.py --artifact data/devy/monthly_pulse/devy_roster_pulse_{pulse_month.replace('-', '_')}.json",
            "downstream_block": "blocked_until_rookie_transition",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a monthly Devy roster pulse from CFBD data")
    parser.add_argument("--season", type=int, required=True, help="College season year, e.g. 2026")
    parser.add_argument("--draft-class", type=int, required=True, help="Target NFL draft class, e.g. 2027")
    parser.add_argument("--top-n", type=int, default=15, help="Production leaders kept per position")
    parser.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST)
    parser.add_argument("--output", type=Path, help="Defaults to data/devy/monthly_pulse/devy_roster_pulse_YYYY_MM.json")
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc)
    inputs = fetch_inputs(args.season, args.draft_class)
    payload = build_pulse(
        roster=inputs["roster"],
        recruits=inputs["recruits"],
        stats=inputs["stats"],
        watchlist=json.loads(args.watchlist.read_text(encoding="utf-8")),
        season=args.season,
        draft_class=args.draft_class,
        top_n=args.top_n,
        source_urls=inputs["source_urls"],
        generated_at=generated_at,
    )
    errors = validate_devy_roster_pulse(payload)
    if errors:
        print("Generated pulse failed validation:")
        for error in errors:
            print(f" - {error}")
        return 1
    output = args.output or Path(f"data/devy/monthly_pulse/devy_roster_pulse_{generated_at:%Y_%m}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['candidates'])} candidates to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
