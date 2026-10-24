#!/usr/bin/env python3
"""Compute year-over-year volume and efficiency trends from play profiles.

Reads WR/TE route profiles and RB play profiles for 2024 and 2025, pairs them
by player_id, and outputs a trend artifact used by the UI to display ↑/↓/→
indicators on the board.

WR/TE rows carry per-season target-evidence status (#303) so a comparison
mixing estimated and parsed/reported target counts stays visibly qualified.
Numeric fields are unchanged; yards_per_target trends are observed-only
efficiency evidence only when both denominators were observed.

Output: data/processed/2026_yoy_trends.json
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.target_evidence import PARSED_PARTIAL, SOURCE_REPORTED, TARGET_STATUSES, target_status

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

    status_24 = target_status(p24)
    status_25 = target_status(p25)

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
        "target_status_2024": status_24,
        "target_status_2025": status_25,
        "target_basis": status_24 if status_24 == status_25 else "mixed",
        "efficiency_observed_denominators": {status_24, status_25} <= {SOURCE_REPORTED, PARSED_PARTIAL},
    }


def validate_wr_te_rows(rows: list[dict]) -> None:
    """Fail generation if any WR/TE row lost its target-evidence status."""
    for row in rows:
        if row.get("position_group") != "WR_TE":
            continue
        for key in ("target_status_2024", "target_status_2025"):
            if row.get(key) not in TARGET_STATUSES:
                raise ValueError(f"{row.get('player_id')}: missing/invalid {key}={row.get(key)!r}")
        if "target_basis" not in row or "efficiency_observed_denominators" not in row:
            raise ValueError(f"{row.get('player_id')}: missing target qualification fields")


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

    validate_wr_te_rows(results)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    logging.info("Wrote %d trend rows to %s", len(results), OUTPUT_PATH)


if __name__ == "__main__":
    main()
