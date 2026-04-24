#!/usr/bin/env python3
"""Summarize cohort outcomes from player_year_ppr_outcomes_v1 artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

INPUT_JSON = Path("exports/promoted/nfl-fantasy-outcomes/player_year_ppr_outcomes_v1.json")
OUTPUT_DIR = Path("exports/promoted/nfl-fantasy-outcomes")
OUTPUT_JSON = OUTPUT_DIR / "context_flag_outcome_summary_v1.json"
OUTPUT_CSV = OUTPUT_DIR / "context_flag_outcome_summary_v1.csv"

COHORTS = {
    "wr_top10_since_2022": {"position": "WR", "since": 2022, "max_pick": 10},
    "wr_round1_since_2022": {"position": "WR", "since": 2022, "draft_round": 1},
    "rb_round1_since_2022": {"position": "RB", "since": 2022, "draft_round": 1},
    "rb_top10_since_2022": {"position": "RB", "since": 2022, "max_pick": 10},
    "te_round1_since_2022": {"position": "TE", "since": 2022, "draft_round": 1},
    "qb_round1_since_2022": {"position": "QB", "since": 2022, "draft_round": 1},
}

FIELDNAMES = [
    "cohort",
    "player_count",
    "players",
    "year_1_avg_ppr",
    "year_2_avg_ppr",
    "year_3_avg_ppr",
    "year_1_median_ppr",
    "year_2_median_ppr",
    "year_3_median_ppr",
    "year_1_avg_ppr_per_game",
    "year_2_avg_ppr_per_game",
    "year_3_avg_ppr_per_game",
    "complete_year_1_count",
    "complete_year_2_count",
    "complete_year_3_count",
    "incomplete_notes",
]


def to_int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def to_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def season_coverage_note(player: dict[str, Any], target_career_year: int, latest_nfl_season: int) -> str | None:
    latest_possible = latest_nfl_season - player["draft_year"] + 1
    if latest_possible < target_career_year:
        return (
            f"{player['player_name']}: year_{target_career_year} not yet elapsed "
            f"(draft_year={player['draft_year']}, latest_season={latest_nfl_season})"
        )
    return None


def aggregate_year_stats(players: list[dict[str, Any]], target_career_year: int, latest_nfl_season: int) -> tuple[dict[str, float | int | None], list[str]]:
    ppr_vals: list[float] = []
    ppg_vals: list[float] = []
    complete = 0
    notes: list[str] = []

    for player in players:
        elapsed_note = season_coverage_note(player, target_career_year, latest_nfl_season)
        row = player["years"].get(target_career_year)

        if row is None:
            if elapsed_note:
                notes.append(elapsed_note)
            else:
                notes.append(f"{player['player_name']}: year_{target_career_year} elapsed but no stat row (DNP/no stats)")
            continue

        ppr_vals.append(row["ppr_points"])
        ppg_vals.append(row["ppr_per_game"])
        complete += 1

    return (
        {
            "avg_ppr": round(sum(ppr_vals) / len(ppr_vals), 2) if ppr_vals else None,
            "median_ppr": round(statistics.median(ppr_vals), 2) if ppr_vals else None,
            "avg_ppg": round(sum(ppg_vals) / len(ppg_vals), 3) if ppg_vals else None,
            "complete_count": complete,
        },
        notes,
    )


def build_cohort_players(rows: list[dict[str, Any]], rule: dict[str, Any]) -> list[dict[str, Any]]:
    bucket: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["position"] != rule["position"]:
            continue
        if row["draft_year"] < rule["since"]:
            continue
        if "draft_round" in rule and row["draft_round"] != rule["draft_round"]:
            continue
        if "max_pick" in rule and row["overall_pick"] > rule["max_pick"]:
            continue

        pid = row["player_id"]
        if pid not in bucket:
            bucket[pid] = {
                "player_id": pid,
                "player_name": row["player_name"],
                "draft_year": row["draft_year"],
                "years": {},
            }

        cy = row["career_year"]
        if cy in (1, 2, 3):
            bucket[pid]["years"][cy] = {
                "ppr_points": row["ppr_points"],
                "ppr_per_game": row["ppr_per_game"],
            }

    return sorted(bucket.values(), key=lambda x: (x["draft_year"], x["player_name"]))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize context-flag fantasy outcome cohorts")
    parser.add_argument("--input", type=Path, default=INPUT_JSON)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = json.loads(args.input.read_text(encoding="utf-8"))

    normalized_rows = []
    for row in rows:
        normalized_rows.append(
            {
                **row,
                "draft_year": to_int(row.get("draft_year")),
                "draft_round": to_int(row.get("draft_round")),
                "overall_pick": to_int(row.get("overall_pick")),
                "career_year": to_int(row.get("career_year")),
                "nfl_season": to_int(row.get("nfl_season")),
                "ppr_points": to_float(row.get("ppr_points")),
                "ppr_per_game": to_float(row.get("ppr_per_game")),
            }
        )

    latest_nfl_season = max((r["nfl_season"] for r in normalized_rows), default=0)
    summaries: list[dict[str, Any]] = []

    for cohort_name, rule in COHORTS.items():
        players = build_cohort_players(normalized_rows, rule)

        year1, notes1 = aggregate_year_stats(players, 1, latest_nfl_season)
        year2, notes2 = aggregate_year_stats(players, 2, latest_nfl_season)
        year3, notes3 = aggregate_year_stats(players, 3, latest_nfl_season)

        notes = notes1 + notes2 + notes3
        if len(players) < 3:
            notes.append(f"Small sample warning: {len(players)} players in cohort")

        summaries.append(
            {
                "cohort": cohort_name,
                "player_count": len(players),
                "players": "|".join(p["player_name"] for p in players),
                "year_1_avg_ppr": year1["avg_ppr"],
                "year_2_avg_ppr": year2["avg_ppr"],
                "year_3_avg_ppr": year3["avg_ppr"],
                "year_1_median_ppr": year1["median_ppr"],
                "year_2_median_ppr": year2["median_ppr"],
                "year_3_median_ppr": year3["median_ppr"],
                "year_1_avg_ppr_per_game": year1["avg_ppg"],
                "year_2_avg_ppr_per_game": year2["avg_ppg"],
                "year_3_avg_ppr_per_game": year3["avg_ppg"],
                "complete_year_1_count": year1["complete_count"],
                "complete_year_2_count": year2["complete_count"],
                "complete_year_3_count": year3["complete_count"],
                "incomplete_notes": " ; ".join(notes),
            }
        )

    summaries.sort(key=lambda r: r["cohort"])
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")
    write_csv(args.output_csv, summaries)

    print(f"Built {len(summaries)} cohort summaries")
    print(f"JSON -> {args.output_json}")
    print(f"CSV  -> {args.output_csv}")


if __name__ == "__main__":
    main()
