#!/usr/bin/env python3
"""
compute_age_adjusted_production.py

Computes an age-adjusted production score for each 2026 draft prospect by
combining weighted season volume with a non-linear age multiplier.

Volume metric per position
  WR / TE  — targets
  QB       — pass_attempts
  RB       — rush_attempts

Volume weighting
  weighted_volume = 0.70 × best_season_volume + 0.30 × most_recent_season_volume
  If only one season has data, that season is used at 100%.

Age multiplier (non-linear)
  multiplier = max(0.85, 1.0 + 0.5 × (21 - breakout_age))
  breakout_age = null  →  multiplier = 1.0 (neutral)

  Breakout age 19 → 2.0×  (elite ceiling signal)
  Breakout age 20 → 1.5×
  Breakout age 21 → 1.0×  (baseline)
  Breakout age 22 → 0.85×

Final score
  raw_score = weighted_volume × age_multiplier
  age_adjusted_production_score = normalized 0–100 within position group
  Null breakout ages are scored neutrally; players with zero volume in both
  seasons receive a score of 0.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DEFAULT_CONTEXT_PATH = Path("data/processed/2026_prospect_context.json")
DEFAULT_WR_DIR = Path("data/processed/wr_route_profiles")
DEFAULT_QB_DIR = Path("data/processed/qb_play_profiles")
DEFAULT_RB_DIR = Path("data/processed/rb_play_profiles")
DEFAULT_OUTPUT_PATH = Path("data/processed/2026_age_adjusted_production.json")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VOLUME_FIELD: dict[str, str] = {
    "WR": "targets",
    "TE": "targets",
    "QB": "pass_attempts",
    "RB": "rush_attempts",
}

AGE_BASELINE = 21
AGE_MULTIPLIER_STEP = 0.5   # per year younger than baseline
AGE_MULTIPLIER_FLOOR = 0.85  # penalty cap for late breakouts

BEST_WEIGHT = 0.70
RECENT_WEIGHT = 0.30

# ---------------------------------------------------------------------------
# School competition classification (BOA adjustment)
# ---------------------------------------------------------------------------
# Any school not in P4_SCHOOLS receives a +0.5 non-P4 penalty on effective BOA.
# Schools in NON_FBS_MARKERS receive a +1.0 penalty instead.
P4_SCHOOLS: frozenset[str] = frozenset({
    # Big Ten
    "Ohio State", "Michigan", "Penn State", "Wisconsin", "Iowa",
    "Michigan State", "Indiana", "Purdue", "Illinois", "Minnesota",
    "Nebraska", "Northwestern", "Maryland", "Rutgers", "UCLA", "USC",
    "Washington", "Oregon",
    # SEC
    "Alabama", "Georgia", "LSU", "Florida", "Tennessee", "Texas A&M",
    "Ole Miss", "Mississippi", "Mississippi State", "Auburn",
    "South Carolina", "Vanderbilt", "Arkansas", "Missouri", "Kentucky",
    "Texas", "Oklahoma",
    # ACC
    "Clemson", "Florida State", "NC State", "North Carolina", "Duke",
    "Wake Forest", "Louisville", "Pittsburgh", "Virginia Tech", "Virginia",
    "Boston College", "Georgia Tech", "Miami", "Miami (FL)", "Syracuse",
    "California", "Stanford", "SMU",
    # Big 12
    "Texas Tech", "TCU", "Oklahoma State", "Baylor", "Kansas State",
    "Kansas", "Iowa State", "West Virginia", "Cincinnati", "Houston",
    "BYU", "UCF", "Arizona", "Arizona State", "Colorado", "Utah",
    # P4-adjacent independents
    "Notre Dame",
})

# Substrings that identify non-FBS programs (FCS/D2/D3)
NON_FBS_MARKERS: tuple[str, ...] = (
    "Indiana State", "Samford", "Eastern Washington", "Montana",
    "North Dakota", "South Dakota", "Sacramento State", "Weber State",
    "Murray State", "Villanova", "Maine", "Delaware", "James Madison",
)

NON_P4_BOA_PENALTY: float = 0.5   # added to effective BOA for G5/FBS non-P4
NON_FBS_BOA_PENALTY: float = 1.0  # added to effective BOA for FCS/non-FBS
WR_R1R3_TEAMMATE_BONUS: float = 0.5  # subtracted from effective BOA


def _primary_school(school_str: str) -> str:
    """Return the most recent school from strings like 'NMSU (2024) / Arkansas (2025)'."""
    parts = [p.strip() for p in str(school_str or "").split("/")]
    last = parts[-1]
    # Strip year annotations like " (2025)"
    return re.sub(r"\s*\(\d{4}\)\s*$", "", last).strip()


def school_boa_adjustment(school_str: str) -> tuple[float, str]:
    """
    Returns (boa_adjustment, classification_label) for competition level.
    Positive adjustment = makes effective BOA older (penalty). Zero = P4, no change.
    """
    school = _primary_school(school_str)
    for marker in NON_FBS_MARKERS:
        if marker.lower() in school.lower():
            return NON_FBS_BOA_PENALTY, "non-FBS"
    if school in P4_SCHOOLS:
        return 0.0, "P4"
    # G5 / non-P4 FBS
    return NON_P4_BOA_PENALTY, "G5"


# ---------------------------------------------------------------------------
# Age multiplier
# ---------------------------------------------------------------------------
def age_multiplier(breakout_age: int | None) -> float:
    """
    Non-linear age multiplier:
      null  → 1.0  (neutral — no age signal available)
      19    → 2.0
      20    → 1.5
      21    → 1.0
      22+   → 0.85
    """
    if breakout_age is None:
        return 1.0
    raw = 1.0 + AGE_MULTIPLIER_STEP * (AGE_BASELINE - breakout_age)
    return max(AGE_MULTIPLIER_FLOOR, raw)


# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------
def profile_dir(position: str, args: argparse.Namespace) -> Path:
    if position == "QB":
        return args.qb_dir
    if position == "RB":
        return args.rb_dir
    return args.wr_dir  # WR and TE


def load_profile(player_id: str, season: int, directory: Path) -> dict[str, Any] | None:
    path = directory / f"{player_id}_{season}.json"
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def season_volume(player_id: str, season: int, field: str, directory: Path) -> float:
    profile = load_profile(player_id, season, directory)
    if profile is None:
        return 0.0
    return float(profile.get(field) or 0.0)


# ---------------------------------------------------------------------------
# Weighted volume
# ---------------------------------------------------------------------------
def weighted_volume(
    player_id: str,
    class_year: int,
    field: str,
    directory: Path,
) -> tuple[float, float, float]:
    """
    Returns (weighted_volume, best_season_vol, recent_season_vol).
    recent = class_year - 1, prior = class_year - 2.
    Weight: 70% best season, 30% most recent season.
    If only one season has data, use it at 100%.
    """
    recent_season = class_year - 1
    prior_season = class_year - 2

    recent_vol = season_volume(player_id, recent_season, field, directory)
    prior_vol = season_volume(player_id, prior_season, field, directory)

    best_vol = max(recent_vol, prior_vol)

    if best_vol == 0.0:
        return 0.0, 0.0, recent_vol

    has_both = recent_vol > 0.0 and prior_vol > 0.0
    if has_both:
        wvol = BEST_WEIGHT * best_vol + RECENT_WEIGHT * recent_vol
    else:
        # Only one season available — use it entirely
        wvol = best_vol

    return wvol, best_vol, recent_vol


# ---------------------------------------------------------------------------
# Normalisation (0–100 within position group)
# ---------------------------------------------------------------------------
def normalize_scores(raw_scores: list[float]) -> list[float]:
    """Min-max normalise a list of raw scores to 0–100."""
    if not raw_scores:
        return []
    lo = min(raw_scores)
    hi = max(raw_scores)
    if hi == lo:
        return [50.0] * len(raw_scores)
    return [round(100.0 * (s - lo) / (hi - lo), 1) for s in raw_scores]


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------
def compute(args: argparse.Namespace) -> list[dict[str, Any]]:
    context: list[dict] = json.loads(args.context_path.read_text())

    # Group players by position for within-position normalisation
    by_position: dict[str, list[dict]] = {}
    for player in context:
        pos = player.get("position", "")
        by_position.setdefault(pos, []).append(player)

    results: list[dict[str, Any]] = []

    for pos, players in by_position.items():
        field = VOLUME_FIELD.get(pos)
        if field is None:
            logging.warning("Unknown position %s — skipping", pos)
            continue

        directory = profile_dir(pos, args)

        records: list[dict[str, Any]] = []
        raw_scores: list[float] = []

        for player in players:
            pid = player["player_id"]
            class_year = int(player.get("class_year") or 0)
            breakout_age_val = player.get("breakout_age")

            # --- BOA context adjustment ---
            school_adj, school_class = school_boa_adjustment(player.get("school", ""))
            teammate_flag = bool(player.get("wr_r1r3_teammate_flag"))
            teammate_adj = -WR_R1R3_TEAMMATE_BONUS if teammate_flag else 0.0
            total_boa_adj = school_adj + teammate_adj

            effective_boa: int | float | None
            if breakout_age_val is not None:
                effective_boa = breakout_age_val + total_boa_adj if total_boa_adj != 0.0 else breakout_age_val
            else:
                effective_boa = None

            # Full BOA audit log for every player
            eff_str = f"{effective_boa:.1f}" if effective_boa is not None else "null"
            raw_str = str(breakout_age_val) if breakout_age_val is not None else "null"
            teammate_str = " +r1r3teammate(-0.5)" if teammate_flag else ""
            adj_str = f"{total_boa_adj:+.1f}" if total_boa_adj != 0.0 else " 0.0"
            logging.info(
                "  BOA  %-26s  school=%-10s  raw=%-4s  adj=%s%s  eff=%s",
                player["player_name"],
                school_class,
                raw_str,
                adj_str,
                teammate_str,
                eff_str,
            )

            wvol, best_vol, recent_vol = weighted_volume(
                pid, class_year, field, directory
            )
            multiplier = age_multiplier(effective_boa)
            raw = wvol * multiplier

            records.append(
                {
                    "player_id": pid,
                    "player_name": player["player_name"],
                    "position": pos,
                    "breakout_age": breakout_age_val,
                    "effective_breakout_age": effective_boa,
                    "boa_adjustment": round(total_boa_adj, 2) if total_boa_adj != 0.0 else None,
                    "young_breakout_flag": player.get("young_breakout_flag", False),
                    "best_season_volume": best_vol,
                    "recent_season_volume": recent_vol,
                    "weighted_volume": round(wvol, 2),
                    "age_multiplier": round(multiplier, 3),
                    "raw_score": round(raw, 2),
                    "age_adjusted_production_score": None,  # filled after normalisation
                }
            )
            raw_scores.append(raw)

        normalised = normalize_scores(raw_scores)
        for rec, score in zip(records, normalised):
            rec["age_adjusted_production_score"] = score

        # Sort descending within position
        records.sort(key=lambda r: r["age_adjusted_production_score"], reverse=True)
        results.extend(records)

        logging.info("Position %s (%d players):", pos, len(records))
        for r in records:
            flag = " (young ✓)" if r["young_breakout_flag"] else ""
            logging.info(
                "  %-28s age=%s  mult=%.2f  wvol=%5.1f  score=%5.1f%s",
                r["player_name"],
                r["breakout_age"] if r["breakout_age"] is not None else "null",
                r["age_multiplier"],
                r["weighted_volume"],
                r["age_adjusted_production_score"],
                flag,
            )

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compute age-adjusted production scores")
    p.add_argument("--context-path", type=Path, default=DEFAULT_CONTEXT_PATH)
    p.add_argument("--wr-dir", type=Path, default=DEFAULT_WR_DIR)
    p.add_argument("--qb-dir", type=Path, default=DEFAULT_QB_DIR)
    p.add_argument("--rb-dir", type=Path, default=DEFAULT_RB_DIR)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    results = compute(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2))
    logging.info("Wrote %d records to %s", len(results), args.output)


if __name__ == "__main__":
    main()
