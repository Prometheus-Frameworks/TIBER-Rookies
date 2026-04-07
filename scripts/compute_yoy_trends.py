#!/usr/bin/env python3
"""Compute year-over-year volume and efficiency trends from play profiles.

Reads WR/TE route profiles and RB play profiles for 2024 and 2025, pairs them
by player_id, and outputs a trend artifact used by the UI to display ↑/↓/→
indicators on the board.

Output: data/processed/2026_yoy_trends.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

VOLUME_THRESHOLD = 0.15   # ±15% = flat, outside = up/down
EFFICIENCY_THRESHOLD = 0.10  # ±10% for efficiency (tighter signal)

WR_TE_PROFILE_DIR = Path("data/processed/wr_route_profiles")
RB_PROFILE_DIR = Path("data/processed/rb_play_profiles")
OUTPUT_PATH = Path("data/processed/2026_yoy_trends.json")


def pct_change(old: float | None, new: float | None) -> float | None:
    if old is None or new is None or old == 0:
        return None
    return (new - old) / abs(old)


def trend_tag(change: float | None, threshold: float) -> str:
    if change is None:
        return "neutral"
    if change >= threshold:
        return "up"
    if change <= -threshold:
        return "down"
    return "neutral"


def load_profile(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def compute_wr_te_trend(pid: str, profile_dir: Path) -> dict | None:
    p24_path = profile_dir / f"{pid}_2024.json"
    p25_path = profile_dir / f"{pid}_2025.json"
    if not p24_path.exists() or not p25_path.exists():
        return None

    p24 = load_profile(p24_path)
    p25 = load_profile(p25_path)

    targets_24 = p24.get("targets")
    targets_25 = p25.get("targets")
    ypt_24 = p24.get("yards_per_target")
    ypt_25 = p25.get("yards_per_target")

    vol_change = pct_change(targets_24, targets_25)
    eff_change = pct_change(ypt_24, ypt_25)

    return {
        "player_id": pid,
        "player_name": p25.get("player_name", pid),
        "position_group": "WR_TE",
        "season_from": 2024,
        "season_to": 2025,
        "volume_metric": "targets",
        "volume_2024": targets_24,
        "volume_2025": targets_25,
        "volume_change_pct": round(vol_change, 4) if vol_change is not None else None,
        "volume_trend": trend_tag(vol_change, VOLUME_THRESHOLD),
        "efficiency_metric": "yards_per_target",
        "efficiency_2024": round(ypt_24, 3) if ypt_24 is not None else None,
        "efficiency_2025": round(ypt_25, 3) if ypt_25 is not None else None,
        "efficiency_change_pct": round(eff_change, 4) if eff_change is not None else None,
        "efficiency_trend": trend_tag(eff_change, EFFICIENCY_THRESHOLD),
    }


def compute_rb_trend(pid: str, profile_dir: Path) -> dict | None:
    p24_path = profile_dir / f"{pid}_2024.json"
    p25_path = profile_dir / f"{pid}_2025.json"
    if not p24_path.exists() or not p25_path.exists():
        return None

    p24 = load_profile(p24_path)
    p25 = load_profile(p25_path)

    attempts_24 = p24.get("rush_attempts")
    attempts_25 = p25.get("rush_attempts")
    ypc_24 = p24.get("yards_per_carry")
    ypc_25 = p25.get("yards_per_carry")

    vol_change = pct_change(attempts_24, attempts_25)
    eff_change = pct_change(ypc_24, ypc_25)

    return {
        "player_id": pid,
        "player_name": p25.get("player_name", pid),
        "position_group": "RB",
        "season_from": 2024,
        "season_to": 2025,
        "volume_metric": "rush_attempts",
        "volume_2024": attempts_24,
        "volume_2025": attempts_25,
        "volume_change_pct": round(vol_change, 4) if vol_change is not None else None,
        "volume_trend": trend_tag(vol_change, VOLUME_THRESHOLD),
        "efficiency_metric": "yards_per_carry",
        "efficiency_2024": round(ypc_24, 3) if ypc_24 is not None else None,
        "efficiency_2025": round(ypc_25, 3) if ypc_25 is not None else None,
        "efficiency_change_pct": round(eff_change, 4) if eff_change is not None else None,
        "efficiency_trend": trend_tag(eff_change, EFFICIENCY_THRESHOLD),
    }


def main() -> None:
    results: list[dict] = []

    # WR/TE profiles
    wr_te_pids: set[str] = set()
    for path in sorted(WR_TE_PROFILE_DIR.glob("*_2025.json")):
        if path.stem.startswith("README"):
            continue
        pid = path.stem.replace("_2025", "")
        wr_te_pids.add(pid)

    for pid in sorted(wr_te_pids):
        row = compute_wr_te_trend(pid, WR_TE_PROFILE_DIR)
        if row:
            results.append(row)
            logging.info(
                "%s: vol %s (%s→%s), eff %s (%.2f→%.2f)",
                pid,
                row["volume_trend"].upper(),
                row["volume_2024"],
                row["volume_2025"],
                row["efficiency_trend"].upper(),
                row["efficiency_2024"] or 0,
                row["efficiency_2025"] or 0,
            )
        else:
            logging.warning("%s: missing 2024 or 2025 profile, skipped", pid)

    # RB profiles
    rb_pids: set[str] = set()
    for path in sorted(RB_PROFILE_DIR.glob("*_2025.json")):
        pid = path.stem.replace("_2025", "")
        rb_pids.add(pid)

    for pid in sorted(rb_pids):
        row = compute_rb_trend(pid, RB_PROFILE_DIR)
        if row:
            results.append(row)
            logging.info(
                "%s: vol %s (%s→%s), eff %s (%.2f→%.2f)",
                pid,
                row["volume_trend"].upper(),
                row["volume_2024"],
                row["volume_2025"],
                row["efficiency_trend"].upper(),
                row["efficiency_2024"] or 0,
                row["efficiency_2025"] or 0,
            )
        else:
            logging.warning("%s: missing 2024 or 2025 profile, skipped", pid)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    logging.info("Wrote %d trend rows to %s", len(results), OUTPUT_PATH)


if __name__ == "__main__":
    main()
