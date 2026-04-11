#!/usr/bin/env python3
"""Build a cross-class historical comparison export.

Merges all available season alpha exports into a single CSV + JSON artifact,
sorted by draft_class (desc) then rookie_alpha_rank (asc) within each class.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


OUTPUT_DIR = Path("exports/promoted/rookie-alpha")
SEASONS = [2026, 2025, 2024, 2023, 2022]

FIELDNAMES = [
    "draft_class",
    "class_rank",
    "player_id",
    "player_name",
    "position",
    "ras_0_100",
    "production_0_100",
    "draft_capital_proxy_0_100",
    "talent_score_0_100",
    "rookie_alpha_0_100",
    "consensus_delta",
    "talent_rank",
    "draft_proxy_delta",
    "model_inputs_missing",
]


def load_class(season: int) -> list[dict]:
    path = OUTPUT_DIR / f"{season}_rookie_alpha_predraft_v0.csv"
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "draft_class": season,
                "class_rank": int(row["rookie_alpha_rank"]),
                "player_id": row["player_id"],
                "player_name": row["player_name"],
                "position": row["position"],
                "ras_0_100": float(row["ras_0_100"]),
                "production_0_100": float(row["production_0_100"]),
                "draft_capital_proxy_0_100": float(row["draft_capital_proxy_0_100"]),
                "talent_score_0_100": float(row["talent_score_0_100"]),
                "rookie_alpha_0_100": float(row["rookie_alpha_0_100"]),
                "consensus_delta": float(row["consensus_delta"]),
                "talent_rank": int(row["talent_rank"]),
                "draft_proxy_delta": int(row["draft_proxy_delta"]),
                "model_inputs_missing": row.get("model_inputs_missing", ""),
            })
    return rows


def main() -> None:
    all_rows: list[dict] = []
    for season in SEASONS:
        rows = load_class(season)
        if rows:
            print(f"Loaded {len(rows)} players for {season} class")
        else:
            print(f"WARNING: No data for {season} class")
        all_rows.extend(rows)

    # Sort: newest class first, then by rank within class
    all_rows.sort(key=lambda r: (-r["draft_class"], r["class_rank"]))

    # Write CSV
    csv_path = OUTPUT_DIR / "historical_class_comparison.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Written: {csv_path} ({len(all_rows)} rows)")

    # Write JSON
    json_path = OUTPUT_DIR / "historical_class_comparison.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(all_rows, f, indent=2)
        f.write("\n")
    print(f"Written: {json_path}")

    # Print summary table
    print()
    print(f"{'Class':<6} {'Pos':<4} {'Player':<28} {'Alpha':>6} {'Talent':>7} {'RAS':>6} {'Prod':>6} {'Capital':>8} {'Delta':>6}")
    print("-" * 90)
    current_class = None
    for r in all_rows:
        if r["draft_class"] != current_class:
            current_class = r["draft_class"]
            print(f"\n── {current_class} Draft Class ──")
        print(
            f"{r['class_rank']:<6} {r['position']:<4} {r['player_name']:<28} "
            f"{r['rookie_alpha_0_100']:>6.1f} {r['talent_score_0_100']:>7.1f} "
            f"{r['ras_0_100']:>6.1f} {r['production_0_100']:>6.1f} "
            f"{r['draft_capital_proxy_0_100']:>8.1f} {r['consensus_delta']:>+6.1f}"
        )


if __name__ == "__main__":
    main()
