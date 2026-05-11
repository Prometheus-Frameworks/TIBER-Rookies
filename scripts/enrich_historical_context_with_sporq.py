"""Inject SPORQ percentiles from sporq_historical.json into historical prospect context files.

Reads data/historical/sporq_historical.json and, for each RB player with a valid
sporq_percentile, checks the corresponding <year>_prospect_context.json file. If the
player's exceptional_metrics list does not already contain a sporq_percentile entry,
one is injected.

Years covered: 2022-2025 (2026 context is managed manually via notes files).

Usage:
    python3 scripts/enrich_historical_context_with_sporq.py
    python3 scripts/enrich_historical_context_with_sporq.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path
from typing import Any

SPORQ_PATH = Path("data/historical/sporq_historical.json")
CONTEXT_DIR = Path("data/processed")
HISTORICAL_YEARS = [2022, 2023, 2024, 2025]
ELIGIBLE_POSITIONS = {"RB"}


def _normalize_name(name: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(ascii_name.lower().split())


def _sporq_tier(pctile: float) -> str:
    if pctile >= 95:
        return "historic"
    if pctile >= 85:
        return "elite"
    if pctile >= 70:
        return "above_average"
    if pctile >= 50:
        return "average"
    return "below_average"


def _build_sporq_lookup(sporq_data: dict[str, Any]) -> dict[tuple[str, int], float]:
    """Return {(normalized_name, year): sporq_percentile} for eligible positions."""
    lookup: dict[tuple[str, int], float] = {}
    for p in sporq_data.get("players", []):
        pos = p.get("pos", "")
        if pos not in ELIGIBLE_POSITIONS:
            continue
        name = p.get("name")
        year = p.get("year")
        pctile = p.get("sporq_percentile")
        if name and year and pctile is not None:
            lookup[(_normalize_name(name), int(year))] = float(pctile)
    return lookup


def _has_sporq_entry(exceptional_metrics: list[dict[str, Any]]) -> bool:
    return any(em.get("metric") == "sporq_percentile" for em in exceptional_metrics)


def _make_sporq_entry(pctile: float, player_name: str, position: str, year: int) -> dict[str, Any]:
    tier = _sporq_tier(pctile)
    tier_label = {
        "historic": f"Historic outlier — top-5% athleticism historically at {position}.",
        "elite": f"Elite athletic profile — top-15% historically at {position}.",
        "above_average": f"Above-average athleticism — top-30% historically at {position}.",
        "average": f"Average athletic profile historically at {position}.",
        "below_average": f"Below-average athleticism historically at {position}.",
    }[tier]
    return {
        "metric": "sporq_percentile",
        "value": round(pctile, 1),
        "context": (
            f"{pctile:.1f}th percentile SPORQ ({year} class, {position}). "
            f"{tier_label} "
            f"Auto-enriched from sporq_historical.json; historically-comparable position-aware composite."
        ),
        "percentile_tier": tier,
        "alpha_bonus_eligible": False,
        "source": "sporq_historical",
    }


def enrich_year(
    year: int,
    sporq_lookup: dict[tuple[str, int], float],
    dry_run: bool,
) -> tuple[int, int]:
    """Enrich one year's context file. Returns (injected_count, skipped_count)."""
    context_path = CONTEXT_DIR / f"{year}_prospect_context.json"
    if not context_path.exists():
        print(f"  [{year}] context file not found — skipping")
        return 0, 0

    context_data = json.loads(context_path.read_text())
    players: list[dict[str, Any]] = context_data if isinstance(context_data, list) else context_data.get("players", [])

    injected = 0
    skipped = 0

    for player in players:
        pos = player.get("position", "")
        if pos not in ELIGIBLE_POSITIONS:
            continue

        name = player.get("player_name", "")
        class_year = player.get("class_year") or year
        norm_name = _normalize_name(name)

        pctile = sporq_lookup.get((norm_name, int(class_year)))
        if pctile is None:
            skipped += 1
            continue

        ems: list[dict[str, Any]] = player.setdefault("exceptional_metrics", [])
        if _has_sporq_entry(ems):
            skipped += 1
            continue

        entry = _make_sporq_entry(pctile, name, pos, int(class_year))
        ems.append(entry)
        injected += 1
        print(f"  [{year}] INJECT  {name:<30s} {pos}  SPORQ={pctile:.1f}")

    if injected > 0 and not dry_run:
        if isinstance(context_data, list):
            context_path.write_text(json.dumps(players, indent=2))
        else:
            context_data["players"] = players
            context_path.write_text(json.dumps(context_data, indent=2))

    return injected, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing files.")
    args = parser.parse_args()

    if not SPORQ_PATH.exists():
        raise FileNotFoundError(f"SPORQ data not found: {SPORQ_PATH}")

    sporq_data = json.loads(SPORQ_PATH.read_text())
    sporq_lookup = _build_sporq_lookup(sporq_data)
    print(f"Loaded SPORQ lookup: {len(sporq_lookup)} RB entries")

    total_injected = 0
    total_skipped = 0

    for year in HISTORICAL_YEARS:
        injected, skipped = enrich_year(year, sporq_lookup, dry_run=args.dry_run)
        total_injected += injected
        total_skipped += skipped

    print(f"\nDone. Injected={total_injected}  Skipped/no-match={total_skipped}")
    if args.dry_run:
        print("(dry-run — no files written)")


if __name__ == "__main__":
    main()
