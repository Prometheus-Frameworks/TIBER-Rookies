#!/usr/bin/env python3
"""Compute normalized college production scores from CFBD season stats."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CFBD_BASE_URL = "https://api.collegefootballdata.com"
DEFAULT_SEED_INPUT = Path("data/raw/2026_real_seed_pool.json")
DEFAULT_PRODUCTION_OUTPUT = Path("data/processed/2026_college_production.json")
DEFAULT_SEED_OUTPUT = Path("data/raw/2026_real_seed_pool.json")

POSITION_LIMITS = {
    "QB": 100.0,
    "RB": 50.0,
    "WR": 20.0,
    "TE": 10.0,
}


@dataclass(frozen=True)
class PopulationPlayer:
    name: str
    school: str
    position: str
    metrics: dict[str, float]


@dataclass(frozen=True)
class MatchResult:
    player_id: str
    player_name: str
    school: str
    position: str
    score: float | None
    source: str | None
    match_mode: str


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc.msg} (line {exc.lineno}, column {exc.colno})") from exc
    except OSError as exc:
        raise SystemExit(f"Unable to read input file {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute CFBD-based normalized production scores")
    parser.add_argument("--season", type=int, default=2026, help="Rookie season (CFBD year will be season - 1)")
    parser.add_argument("--seed-input", type=Path, default=DEFAULT_SEED_INPUT)
    parser.add_argument("--production-output", type=Path, default=DEFAULT_PRODUCTION_OUTPUT)
    parser.add_argument("--seed-output", type=Path, default=DEFAULT_SEED_OUTPUT)
    return parser.parse_args()


def normalize_identity(value: str) -> str:
    cleaned = re.sub(r"[.'-]", "", value.lower())
    return " ".join(cleaned.split())


def school_aliases(raw_school: str) -> set[str]:
    normalized = normalize_identity(raw_school)
    aliases = {normalized}
    normalized_no_parens = normalized.replace("(", "").replace(")", "")
    aliases.add(normalized_no_parens)
    if normalized in {"miami (fl)", "miami fl"}:
        aliases.update({"miami", "miami (fl)", "miami fl"})
    if normalized == "miami":
        aliases.update({"miami (fl)", "miami fl"})
    if normalized == "mississippi state":
        aliases.add("miss st")
    if normalized == "miss st":
        aliases.add("mississippi state")
    return aliases


def fetch_cfbd_category(year: int, category: str) -> list[dict[str, Any]]:
    params = urlencode({"year": year, "category": category})
    url = f"{CFBD_BASE_URL}/stats/player/season?{params}"
    headers = {"Accept": "application/json"}
    api_key = os.getenv("CFBD_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        logging.warning("CFBD_API_KEY not set; using unauthenticated CFBD requests (may be rate-limited).")

    request = Request(url=url, headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise SystemExit(f"CFBD API request failed for {category}: HTTP {exc.code}") from exc
    except URLError as exc:
        raise SystemExit(f"CFBD API request failed for {category}: {exc.reason}") from exc

    if not isinstance(payload, list):
        raise SystemExit(f"Unexpected CFBD response for {category}: expected list, got {type(payload).__name__}")
    return payload


def pivot_stats(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    players: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        player_name = str(row.get("player", "")).strip()
        team = str(row.get("team", "")).strip()
        if not player_name:
            continue
        key = (normalize_identity(player_name), normalize_identity(team))
        entry = players.setdefault(
            key,
            {
                "player": player_name,
                "team": team,
                "stats": {},
            },
        )
        stat_type = str(row.get("statType", "")).strip().upper()
        stat_raw = row.get("stat")
        if not stat_type:
            continue
        try:
            stat_value = float(stat_raw)
        except (TypeError, ValueError):
            continue
        entry["stats"][stat_type] = stat_value
    return players


def safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def build_population(
    position: str,
    passing_stats: dict[tuple[str, str], dict[str, Any]],
    rushing_stats: dict[tuple[str, str], dict[str, Any]],
    receiving_stats: dict[tuple[str, str], dict[str, Any]],
) -> list[PopulationPlayer]:
    candidates: list[PopulationPlayer] = []

    if position == "QB":
        for data in passing_stats.values():
            stats = data["stats"]
            att = stats.get("ATT", 0.0)
            if att < POSITION_LIMITS["QB"]:
                continue
            completion_pct = safe_div(stats.get("COMPLETIONS", 0.0), att)
            ypa = safe_div(stats.get("YDS", 0.0), att)
            td_rate = safe_div(stats.get("TD", 0.0), att)
            int_rate = safe_div(stats.get("INT", 0.0), att)
            metrics = {
                "completion_pct": completion_pct or 0.0,
                "yards_per_attempt": ypa or 0.0,
                "td_rate": td_rate or 0.0,
                "int_rate": int_rate or 0.0,
            }
            candidates.append(
                PopulationPlayer(
                    name=str(data["player"]),
                    school=str(data["team"]),
                    position="QB",
                    metrics=metrics,
                )
            )

    elif position == "RB":
        receiving_name_map: dict[tuple[str, str], float] = {
            key: rec_data["stats"].get("YDS", 0.0) for key, rec_data in receiving_stats.items()
        }
        for key, rush_data in rushing_stats.items():
            stats = rush_data["stats"]
            car = stats.get("CAR", 0.0)
            if car < POSITION_LIMITS["RB"]:
                continue
            ypc = safe_div(stats.get("YDS", 0.0), car)
            td_rate = safe_div(stats.get("TD", 0.0), car)
            metrics = {
                "yards_per_carry": ypc or 0.0,
                "td_rate": td_rate or 0.0,
                "receiving_yds": receiving_name_map.get(key, 0.0),
            }
            candidates.append(
                PopulationPlayer(
                    name=str(rush_data["player"]),
                    school=str(rush_data["team"]),
                    position="RB",
                    metrics=metrics,
                )
            )

    elif position in {"WR", "TE"}:
        for rec_data in receiving_stats.values():
            stats = rec_data["stats"]
            rec = stats.get("REC", 0.0)
            if rec < POSITION_LIMITS[position]:
                continue
            ypr = safe_div(stats.get("YDS", 0.0), rec)
            td_rate = safe_div(stats.get("TD", 0.0), rec)
            metrics = {
                "yards_per_reception": ypr or 0.0,
                "td_rate": td_rate or 0.0,
                "total_yards": stats.get("YDS", 0.0),
            }
            candidates.append(
                PopulationPlayer(
                    name=str(rec_data["player"]),
                    school=str(rec_data["team"]),
                    position=position,
                    metrics=metrics,
                )
            )

    return candidates


def population_metric_stats(players: list[PopulationPlayer]) -> dict[str, tuple[float, float]]:
    metric_names = sorted(players[0].metrics.keys()) if players else []
    results: dict[str, tuple[float, float]] = {}
    for metric in metric_names:
        values = [player.metrics[metric] for player in players]
        mu = mean(values)
        sd = pstdev(values) if len(values) > 1 else 0.0
        results[metric] = (mu, sd)
    return results


def z_score(value: float, mu: float, sd: float) -> float:
    if sd == 0:
        return 0.0
    return (value - mu) / sd


def z_to_score(z: float) -> float:
    return max(0.0, min(100.0, round(50.0 + (z * 15.0), 1)))


def composite_z(position: str, metric_z: dict[str, float]) -> float:
    if position == "QB":
        return (
            (0.30 * metric_z["completion_pct"])
            + (0.35 * metric_z["yards_per_attempt"])
            + (0.25 * metric_z["td_rate"])
            - (0.10 * metric_z["int_rate"])
        )
    if position == "RB":
        return (
            (0.45 * metric_z["yards_per_carry"])
            + (0.35 * metric_z["td_rate"])
            + (0.20 * metric_z["receiving_yds"])
        )
    return (
        (0.40 * metric_z["yards_per_reception"])
        + (0.35 * metric_z["total_yards"])
        + (0.25 * metric_z["td_rate"])
    )


def build_match_maps(population: list[PopulationPlayer]) -> tuple[dict[tuple[str, str], PopulationPlayer], dict[str, list[PopulationPlayer]]]:
    by_name_school: dict[tuple[str, str], PopulationPlayer] = {}
    by_name: dict[str, list[PopulationPlayer]] = {}
    for player in population:
        normalized_name = normalize_identity(player.name)
        normalized_school = normalize_identity(player.school)
        by_name_school[(normalized_name, normalized_school)] = player
        by_name.setdefault(normalized_name, []).append(player)
    return by_name_school, by_name


def match_seed_player(
    seed_row: dict[str, Any],
    position_population: list[PopulationPlayer],
) -> tuple[PopulationPlayer | None, str]:
    by_name_school, by_name = build_match_maps(position_population)
    normalized_name = normalize_identity(str(seed_row.get("player_name", "")))
    school_options = school_aliases(str(seed_row.get("school", "")))
    for school in school_options:
        match = by_name_school.get((normalized_name, school))
        if match:
            return match, "primary"
    fallback_candidates = by_name.get(normalized_name, [])
    if fallback_candidates:
        return fallback_candidates[0], "name-only"
    return None, "failed"


def compute_scores_for_seed(
    seed_rows: list[dict[str, Any]],
    passing_stats: dict[tuple[str, str], dict[str, Any]],
    rushing_stats: dict[tuple[str, str], dict[str, Any]],
    receiving_stats: dict[tuple[str, str], dict[str, Any]],
) -> list[MatchResult]:
    populations: dict[str, list[PopulationPlayer]] = {
        "QB": build_population("QB", passing_stats, rushing_stats, receiving_stats),
        "RB": build_population("RB", passing_stats, rushing_stats, receiving_stats),
        "WR": build_population("WR", passing_stats, rushing_stats, receiving_stats),
        "TE": build_population("TE", passing_stats, rushing_stats, receiving_stats),
    }
    population_stats = {
        position: population_metric_stats(players) for position, players in populations.items() if players
    }

    results: list[MatchResult] = []
    for row in seed_rows:
        position = str(row.get("position", "")).upper()
        player_id = str(row.get("player_id", ""))
        player_name = str(row.get("player_name", ""))
        school = str(row.get("school", ""))

        if position not in populations or not populations[position]:
            logging.warning("MATCH FAILED: %s (%s) - unsupported or empty position population %s", player_name, school, position)
            results.append(MatchResult(player_id, player_name, school, position, None, None, "failed"))
            continue

        matched, mode = match_seed_player(row, populations[position])
        if matched is None:
            logging.warning("MATCH FAILED: %s (%s)", player_name, school)
            results.append(MatchResult(player_id, player_name, school, position, None, None, "failed"))
            continue

        if mode == "name-only":
            logging.warning(
                "MATCH FALLBACK(name-only): %s (%s) matched to CFBD school %s",
                player_name,
                school,
                matched.school,
            )

        metric_z: dict[str, float] = {}
        for metric, value in matched.metrics.items():
            mu, sd = population_stats[position][metric]
            metric_z[metric] = z_score(value, mu, sd)
        score = z_to_score(composite_z(position, metric_z))
        source = f"CFBD 2025 season stats (normalized {position} production score)"
        results.append(MatchResult(player_id, player_name, school, position, score, source, mode))

    return results


def apply_results(seed_rows: list[dict[str, Any]], results: list[MatchResult]) -> list[dict[str, Any]]:
    result_map = {result.player_id: result for result in results}
    updated: list[dict[str, Any]] = []
    for row in seed_rows:
        pid = str(row.get("player_id", ""))
        result = result_map.get(pid)
        next_row = dict(row)
        if result:
            next_row["production_score_0_100"] = result.score
            next_row["production_score_source"] = result.source
        updated.append(next_row)
    return updated


def to_production_rows(seed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in seed_rows:
        output.append(
            {
                "player_id": row.get("player_id"),
                "player_name": row.get("player_name"),
                "position": row.get("position"),
                "school": row.get("school"),
                "class_year": row.get("class_year"),
                "production_score_0_100": row.get("production_score_0_100"),
                "production_score_source": row.get("production_score_source"),
            }
        )
    return output


def print_summary(results: list[MatchResult]) -> None:
    print("=== CFBD match summary ===")
    primary = [r for r in results if r.match_mode == "primary"]
    fallback = [r for r in results if r.match_mode == "name-only"]
    failed = [r for r in results if r.match_mode == "failed"]

    print(f"Primary matches: {len(primary)}")
    for item in primary:
        print(f"  - {item.player_name} ({item.school})")

    print(f"Fallback name-only matches: {len(fallback)}")
    for item in fallback:
        print(f"  - {item.player_name} ({item.school})")

    print(f"Match failures: {len(failed)}")
    for item in failed:
        print(f"  - {item.player_name} ({item.school})")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    seed_rows = load_json(args.seed_input)
    if not isinstance(seed_rows, list):
        raise SystemExit(f"Seed input must be a JSON array: {args.seed_input}")

    cfbd_year = args.season - 1
    passing_rows = fetch_cfbd_category(cfbd_year, "passing")
    rushing_rows = fetch_cfbd_category(cfbd_year, "rushing")
    receiving_rows = fetch_cfbd_category(cfbd_year, "receiving")

    passing_stats = pivot_stats(passing_rows)
    rushing_stats = pivot_stats(rushing_rows)
    receiving_stats = pivot_stats(receiving_rows)

    results = compute_scores_for_seed(seed_rows, passing_stats, rushing_stats, receiving_stats)
    updated_seed = apply_results(seed_rows, results)
    production_rows = to_production_rows(updated_seed)

    write_json(args.seed_output, updated_seed)
    write_json(args.production_output, production_rows)

    print_summary(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
