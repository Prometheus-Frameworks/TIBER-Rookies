#!/usr/bin/env python3
"""
Fetch CFBD college stats for players missing from player_stats.json.

Reads the full college_production.json for a given draft class, identifies
players whose stats weren't fetched by the original seed-pool script, and
appends them to player_stats.json.

Usage:
  python3 scripts/fetch_missing_stats.py --season 2025
  python3 scripts/fetch_missing_stats.py --season 2026
  python3 scripts/fetch_missing_stats.py --season 2025 --season 2026
  python3 scripts/fetch_missing_stats.py --season 2025 --skip-qb
  python3 scripts/fetch_missing_stats.py --all

Set CFBD_API_KEY env var for higher rate limits (optional but recommended).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any

BASE_DIR = Path(__file__).parent.parent
DATA_PROCESSED = BASE_DIR / "data" / "processed"
CFBD_BASE_URL = "https://api.collegefootballdata.com"

# Known CFBD name variations (extend as needed)
PLAYER_NAME_ALIASES: dict[str, list[str]] = {
    "mike washington jr": ["michael washington"],
    "nick singleton": ["nicholas singleton"],
    "kc concepcion": ["kevin concepcion"],
    "jj mccarthy": ["j.j. mccarthy"],
    "tre harris": ["treyaun harris"],
}


# ── helpers ──────────────────────────────────────────────────────────────────

def normalize(value: str) -> str:
    cleaned = re.sub(r"[.'\-]", "", value.lower())
    return " ".join(cleaned.split())


def school_aliases(raw: str) -> set[str]:
    n = normalize(raw)
    aliases = {n, n.replace("(", "").replace(")", "")}
    if n in {"miami (fl)", "miami fl"}:
        aliases.update({"miami", "miami (fl)", "miami fl"})
    if n == "miami":
        aliases.update({"miami (fl)", "miami fl"})
    if n == "mississippi state":
        aliases.add("miss st")
    if n == "miss st":
        aliases.add("mississippi state")
    # Common alternates
    EXTRAS = {
        "nc state": {"north carolina state"},
        "north carolina state": {"nc state"},
        "usc": {"southern california"},
        "southern california": {"usc"},
        "lsu": {"louisiana state"},
        "louisiana state": {"lsu"},
        "ole miss": {"mississippi"},
        "mississippi": {"ole miss"},
        "pitt": {"pittsburgh"},
        "pittsburgh": {"pitt"},
        "ucf": {"central florida"},
        "central florida": {"ucf"},
        "smu": {"southern methodist"},
        "southern methodist": {"smu"},
        "tcu": {"texas christian"},
        "texas christian": {"tcu"},
        "penn st": {"penn state"},
        "penn state": {"penn st"},
    }
    aliases.update(EXTRAS.get(n, set()))
    return aliases


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def safe_div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den == 0:
        return None
    return num / den


def rounded(v: float) -> int | float:
    return int(v) if float(v).is_integer() else round(v, 1)


# ── CFBD fetch ────────────────────────────────────────────────────────────────

def fetch_category(year: int, category: str, max_retries: int = 5) -> list[dict]:
    params = urlencode({"year": year, "category": category})
    url = f"{CFBD_BASE_URL}/stats/player/season?{params}"
    headers = {"Accept": "application/json"}
    api_key = os.getenv("CFBD_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    for attempt in range(max_retries):
        req = Request(url=url, headers=headers)
        try:
            with urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except HTTPError as exc:
            if exc.code == 429:
                wait = 10 * (2 ** attempt)
                logging.warning("Rate limited (429) for %s year=%s — retrying in %ds", category, year, wait)
                time.sleep(wait)
            else:
                raise SystemExit(f"CFBD HTTP {exc.code} for {category} year={year}") from exc
        except URLError as exc:
            raise SystemExit(f"CFBD URL error for {category} year={year}: {exc.reason}") from exc

    raise SystemExit(f"CFBD gave up after {max_retries} attempts for {category} year={year}")


def pivot(rows: list[dict]) -> dict[tuple[str, str], dict]:
    """(norm_name, norm_school) → {player, team, stats:{stat_type: value}}"""
    out: dict[tuple[str, str], dict] = {}
    for row in rows:
        name = str(row.get("player", "")).strip()
        team = str(row.get("team", "")).strip()
        if not name:
            continue
        key = (normalize(name), normalize(team))
        entry = out.setdefault(key, {"player": name, "team": team, "stats": {}})
        stat_type = str(row.get("statType", "")).strip().upper()
        try:
            entry["stats"][stat_type] = float(row["stat"])
        except (TypeError, ValueError, KeyError):
            pass
    return out


# ── player matching ────────────────────────────────────────────────────────────

def find_player(name: str, school: str,
                by_name_school: dict[tuple[str, str], dict],
                by_name: dict[str, list[dict]]) -> tuple[dict | None, str]:
    """Try name+school, then aliases, then name-only. Returns (entry, mode)."""
    norm_name = normalize(name)
    schools = school_aliases(school)

    for s in schools:
        hit = by_name_school.get((norm_name, s))
        if hit:
            return hit, "primary"

    for alias in PLAYER_NAME_ALIASES.get(norm_name, []):
        for s in schools:
            hit = by_name_school.get((normalize(alias), s))
            if hit:
                return hit, "alias"

    hits = by_name.get(norm_name, [])
    if hits:
        return hits[0], "name-only"

    for alias in PLAYER_NAME_ALIASES.get(norm_name, []):
        hits = by_name.get(normalize(alias), [])
        if hits:
            return hits[0], "name-only"

    return None, "failed"


def build_lookup(stats_dict: dict[tuple[str, str], dict]):
    by_name: dict[str, list[dict]] = {}
    for (norm_name, _), entry in stats_dict.items():
        by_name.setdefault(norm_name, []).append(entry)
    return stats_dict, by_name


# ── stat-line builder ─────────────────────────────────────────────────────────

def build_stat_line(player: dict, cfbd_year: int,
                    passing: dict, rushing: dict, receiving: dict) -> dict:
    pos = player["position"].upper()
    name = player["player_name"]
    school = player["school"]

    pns, pn = build_lookup(passing)
    rushing_ns, rushing_n = build_lookup(rushing)
    rec_ns, rec_n = build_lookup(receiving)

    stats: dict[str, int | float] = {}

    def add(k, v):
        if v is not None:
            stats[k] = rounded(v)

    if pos == "QB":
        entry, mode = find_player(name, school, pns, pn)
        if entry:
            s = entry["stats"]
            att = s.get("ATT")
            comp = s.get("COMPLETIONS")
            yds = s.get("YDS")
            td = s.get("TD")
            ints = s.get("INT")
            add("completions", comp)
            add("attempts", att)
            if comp and att:
                add("completion_pct", round(comp / att * 100, 1))
            add("passing_yards", yds)
            add("passing_tds", td)
            add("interceptions", ints)
            if yds and att:
                add("yards_per_attempt", round(yds / att, 2))
            logging.info("QB %s (%s): %s", name, school, mode)
        else:
            logging.warning("QB %s (%s): no CFBD match", name, school)

    elif pos == "RB":
        rush_entry, mode = find_player(name, school, rushing_ns, rushing_n)
        rec_entry, _ = find_player(name, school, rec_ns, rec_n)
        if rush_entry:
            s = rush_entry["stats"]
            car = s.get("CAR")
            yds = s.get("YDS")
            td = s.get("TD")
            add("rush_attempts", car)
            add("rush_yards", yds)
            add("rush_tds", td)
            if yds and car:
                add("yards_per_carry", round(yds / car, 2))
            logging.info("RB %s (%s): %s", name, school, mode)
        else:
            logging.warning("RB %s (%s): no CFBD rush match", name, school)
        if rec_entry:
            rs = rec_entry["stats"]
            add("receptions", rs.get("REC"))
            add("receiving_yards", rs.get("YDS"))

    elif pos in ("WR", "TE"):
        entry, mode = find_player(name, school, rec_ns, rec_n)
        if entry:
            s = entry["stats"]
            rec = s.get("REC")
            yds = s.get("YDS")
            td = s.get("TD")
            add("receptions", rec)
            add("receiving_yards", yds)
            add("receiving_tds", td)
            if yds and rec:
                add("yards_per_reception", round(yds / rec, 2))
            add("targets", s.get("LONG"))  # CFBD doesn't expose targets; skip if unavailable
            logging.info("%s %s (%s): %s", pos, name, school, mode)
        else:
            logging.warning("%s %s (%s): no CFBD match", pos, name, school)

    return {
        "player_id": player["player_id"],
        "player_name": name,
        "position": pos,
        "school": school,
        "season": cfbd_year,
        "stats": stats,
    }


# ── main ──────────────────────────────────────────────────────────────────────

def process_season(season: int, dry_run: bool = False, skip_qb: bool = False) -> None:
    cfbd_year = season - 1  # 2026 rookies → 2025 college season
    prod_path = DATA_PROCESSED / f"{season}_college_production.json"
    stats_path = DATA_PROCESSED / f"{season}_player_stats.json"

    if not prod_path.exists():
        logging.warning("No production file for season %s — skipping", season)
        return

    all_players = load_json(prod_path)
    existing_stats: list[dict] = load_json(stats_path) if stats_path.exists() else []
    existing_ids = {p["player_id"] for p in existing_stats}

    targets = [p for p in all_players if p["player_id"] not in existing_ids]
    if not targets:
        print(f"{season}: all {len(all_players)} players already have stats — nothing to do.")
        return

    if skip_qb:
        qb_targets = [p for p in targets if str(p.get("position", "")).upper() == "QB"]
        print(f"{season}: Skipping QBs due to --skip-qb flag ({len(qb_targets)} excluded).")
        targets = [p for p in targets if str(p.get("position", "")).upper() != "QB"]
        if not targets:
            print(f"{season}: no non-QB players remain after filtering — nothing to do.")
            return

    print(f"{season}: fetching stats for {len(targets)} players (cfbd year={cfbd_year}) …")

    if dry_run:
        for p in targets:
            print(f"  DRY RUN: would fetch {p['player_name']} ({p['position']}, {p['school']})")
        return

    # Only fetch categories needed by the target positions
    positions = {str(p.get("position", "")).upper() for p in targets}

    need_passing   = "QB" in positions
    need_rushing   = any(pos in {"RB", "QB"} for pos in positions)
    need_receiving = any(pos in {"RB", "WR", "TE"} for pos in positions)

    passing   = {}
    rushing   = {}
    receiving = {}

    if need_passing:
        print(f"  Fetching passing stats for {cfbd_year}…")
        passing = pivot(fetch_category(cfbd_year, "passing"))
        time.sleep(1.0)

    if need_rushing:
        print(f"  Fetching rushing stats for {cfbd_year}…")
        rushing = pivot(fetch_category(cfbd_year, "rushing"))
        time.sleep(1.0)

    if need_receiving:
        print(f"  Fetching receiving stats for {cfbd_year}…")
        receiving = pivot(fetch_category(cfbd_year, "receiving"))
        time.sleep(1.0)

    new_entries: list[dict] = []
    matched = failed = 0

    for player in targets:
        entry = build_stat_line(player, cfbd_year, passing, rushing, receiving)
        new_entries.append(entry)
        if entry["stats"]:
            matched += 1
        else:
            failed += 1

    merged = existing_stats + new_entries
    write_json(stats_path, merged)

    print(f"  Done: {matched} matched, {failed} no stats found, {len(merged)} total in {stats_path.name}")

    # Print failures so user can add aliases
    no_stats = [e for e in new_entries if not e["stats"]]
    if no_stats:
        print(f"\n  Players with no CFBD match ({len(no_stats)}) — add to PLAYER_NAME_ALIASES if name variant differs:")
        for e in no_stats:
            print(f"    {e['player_name']} ({e['position']}, {e['school']})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch missing CFBD college stats")
    parser.add_argument("--season", type=int, action="append", dest="seasons",
                        metavar="YEAR", help="Draft class year (e.g. 2025). Repeatable.")
    parser.add_argument("--all", action="store_true", help="Process 2022–2026")
    parser.add_argument("--dry-run", action="store_true", help="Print targets without fetching")
    parser.add_argument("--skip-qb", action="store_true",
                        help="Exclude QB targets before category detection/fetching")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()

    seasons: list[int]
    if args.all:
        seasons = [2022, 2023, 2024, 2025, 2026]
    elif args.seasons:
        seasons = sorted(set(args.seasons))
    else:
        print("Specify at least one season: --season 2025  or  --all")
        return 1

    for season in seasons:
        process_season(season, dry_run=args.dry_run, skip_qb=args.skip_qb)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
