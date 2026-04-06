#!/usr/bin/env python3
"""
compute_ppr_projections.py

Generates first-year PPR point projection ranges for 2026 draft prospects
using alpha-score bands anchored on real historical rookie distributions
(2017–2023 PPR full-season totals).

Method (Path A — alpha band model):
  Each prospect's rookie_alpha_0_100 score maps to a positional band.
  Each band defines floor / median / ceiling PPR totals derived from
  real rookie-year outcomes at that tier. The band label and range are
  the projection artifact; no comp outcome data is required.

Bands per position
  Elite       alpha 80–100
  Starter     alpha 55–79
  Contributor alpha 30–54
  Lottery     alpha  0–29

Historical anchors (PPR full-season, year 1 only):
  WR  Elite:       floor=130  median=175  ceiling=240
      Starter:     floor=70   median=115  ceiling=165
      Contributor: floor=30   median=60   ceiling=100
      Lottery:     floor=5    median=25   ceiling=65

  RB  Elite:       floor=150  median=200  ceiling=310
      Starter:     floor=90   median=135  ceiling=190
      Contributor: floor=40   median=75   ceiling=120
      Lottery:     floor=5    median=30   ceiling=70

  QB  Elite:       floor=280  median=340  ceiling=420
      Starter:     floor=180  median=245  ceiling=320
      Contributor: floor=80   median=140  ceiling=210
      Lottery:     floor=10   median=50   ceiling=120

  TE  Elite:       floor=100  median=140  ceiling=200
      Starter:     floor=55   median=90   ceiling=135
      Contributor: floor=20   median=45   ceiling=80
      Lottery:     floor=5    median=20   ceiling=50

Note: QB values reflect fantasy QB scoring (4pts/TD passing, 1pt/25 yds,
6pts/TD rushing). WR/RB/TE reflect standard PPR (1pt/reception).
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DEFAULT_ALPHA_PATH = Path("exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json")
DEFAULT_OUTPUT_PATH = Path("data/processed/2026_ppr_projections.json")

# ---------------------------------------------------------------------------
# Band definitions
# ---------------------------------------------------------------------------
BANDS: list[tuple[str, float, float]] = [
    ("Elite",       80.0, 100.0),
    ("Starter",     55.0,  79.9),
    ("Contributor", 30.0,  54.9),
    ("Lottery",      0.0,  29.9),
]

# PPR ranges: position → band_label → (floor, median, ceiling)
PPR_RANGES: dict[str, dict[str, tuple[int, int, int]]] = {
    "WR": {
        "Elite":       (130, 175, 240),
        "Starter":     (70,  115, 165),
        "Contributor": (30,  60,  100),
        "Lottery":     (5,   25,  65),
    },
    "RB": {
        "Elite":       (150, 200, 310),
        "Starter":     (90,  135, 190),
        "Contributor": (40,  75,  120),
        "Lottery":     (5,   30,  70),
    },
    "QB": {
        "Elite":       (280, 340, 420),
        "Starter":     (180, 245, 320),
        "Contributor": (80,  140, 210),
        "Lottery":     (10,  50,  120),
    },
    "TE": {
        "Elite":       (100, 140, 200),
        "Starter":     (55,  90,  135),
        "Contributor": (20,  45,  80),
        "Lottery":     (5,   20,  50),
    },
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class PPRProjection:
    player_id: str
    player_name: str
    position: str
    rookie_alpha_0_100: float
    rookie_alpha_rank: int
    projection_band: str
    ppr_floor: int
    ppr_median: int
    ppr_ceiling: int
    projection_method: str = "alpha_band_v1"
    data_gap_flag: bool = False
    data_gap_note: str | None = None


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def alpha_band(alpha: float) -> str:
    for label, lo, hi in BANDS:
        if lo <= alpha <= hi:
            return label
    return "Lottery"


def project_player(player: dict[str, Any]) -> PPRProjection:
    pid = player["player_id"]
    name = player["player_name"]
    position = player["position"]
    scores = player.get("scores", {})
    alpha = float(scores.get("rookie_alpha_0_100", 50.0))
    rank = int(player.get("rookie_alpha_rank", 99))

    missing = player.get("model_inputs_missing", [])
    data_gap = len(missing) > 0
    data_gap_note = (
        f"Missing model inputs: {', '.join(missing)}. "
        "Range may understate true projection."
        if data_gap
        else None
    )

    pos_ranges = PPR_RANGES.get(position)
    if pos_ranges is None:
        # Unknown position — use Lottery as safe fallback
        band = "Lottery"
        floor_, median_, ceiling_ = 5, 25, 65
    else:
        band = alpha_band(alpha)
        floor_, median_, ceiling_ = pos_ranges[band]

    return PPRProjection(
        player_id=pid,
        player_name=name,
        position=position,
        rookie_alpha_0_100=round(alpha, 1),
        rookie_alpha_rank=rank,
        projection_band=band,
        ppr_floor=floor_,
        ppr_median=median_,
        ppr_ceiling=ceiling_,
        data_gap_flag=data_gap,
        data_gap_note=data_gap_note,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate PPR projection ranges for 2026 class")
    p.add_argument("--alpha-input", type=Path, default=DEFAULT_ALPHA_PATH)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return p.parse_args()


def main() -> None:
    args = parse_args()

    alpha_data = json.loads(args.alpha_input.read_text())
    players = alpha_data.get("players", alpha_data) if isinstance(alpha_data, dict) else alpha_data

    projections = [project_player(p) for p in players]

    # Sort by rookie alpha rank
    projections.sort(key=lambda x: x.rookie_alpha_rank)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    output = [asdict(proj) for proj in projections]
    args.output.write_text(json.dumps(output, indent=2))

    logging.info("PPR projections for %d players:", len(projections))
    logging.info("  %-28s %-4s  %-12s  %5s  %6s  %7s", "Player", "Pos", "Band", "Floor", "Median", "Ceiling")
    for proj in projections:
        gap = " *" if proj.data_gap_flag else ""
        logging.info(
            "  %-28s %-4s  %-12s  %5d  %6d  %7d%s",
            proj.player_name, proj.position, proj.projection_band,
            proj.ppr_floor, proj.ppr_median, proj.ppr_ceiling, gap,
        )
    logging.info("")
    logging.info("* = data gap; range may understate true projection")
    logging.info("Wrote %d records to %s", len(projections), args.output)


if __name__ == "__main__":
    main()
