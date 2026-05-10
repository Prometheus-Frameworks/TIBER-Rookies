"""Audit athletic-score normalization across promoted Rookie Alpha exports.

Investigation-only utility for issue #205. Does NOT modify model logic.

Reads each `exports/promoted/rookie-alpha/<year>_rookie_alpha_predraft_v0.json`
and the historical SPORQ table at `data/historical/sporq_historical.json`,
then reports:

  1. Per-class athletic_score distribution (mean / median / IQR / share <50 / <40)
  2. Combine cohort sizes per year (drives z-score noise floor)
  3. Players whose athletic_score looks suspiciously low relative to draft
     capital / production (likely candidates for normalization review)
  4. Players whose computed athletic_score diverges sharply from the
     SPORQ percentile already on file (when SPORQ is present)

Usage:
    python3 scripts/audit_athletic_score_normalization.py
    python3 scripts/audit_athletic_score_normalization.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

EXPORT_DIR = Path("exports/promoted/rookie-alpha")
COMBINE_DIR = Path("data/raw")
SPORQ_PATH = Path("data/historical/sporq_historical.json")

SUSPICIOUS_ATH_BELOW = 50.0
SUSPICIOUS_DC_AT_LEAST = 75.0
SUSPICIOUS_PROD_AT_LEAST = 75.0
SPORQ_DIVERGENCE_POINTS = 20.0
SPORQ_HIGH = 65.0


def load_json(path: Path) -> Any:
    with path.open() as fh:
        return json.load(fh)


def class_distribution(players: list[dict[str, Any]]) -> dict[str, Any]:
    vals = [p["scores"].get("athletic_score_0_100") for p in players]
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0}
    n = len(vals)
    quartiles = statistics.quantiles(vals, n=4) if n >= 4 else [min(vals), statistics.median(vals), max(vals)]
    return {
        "n": n,
        "mean": round(statistics.mean(vals), 2),
        "median": round(statistics.median(vals), 2),
        "p25": round(quartiles[0], 2),
        "p75": round(quartiles[2], 2),
        "share_below_50_pct": round(sum(1 for v in vals if v < 50) / n * 100, 1),
        "share_below_40_pct": round(sum(1 for v in vals if v < 40) / n * 100, 1),
    }


def combine_cohort_sizes(year: int) -> dict[str, int]:
    path = COMBINE_DIR / f"{year}_combine_results.json"
    if not path.exists():
        return {}
    rows = load_json(path)
    counts: dict[str, int] = {"_total": len(rows)}
    for row in rows:
        pos = row.get("position", "?")
        counts[pos] = counts.get(pos, 0) + 1
    return counts


def sporq_lookup(sporq: dict[str, Any]) -> dict[tuple[str, int], float]:
    out: dict[tuple[str, int], float] = {}
    for player in sporq.get("players", []):
        name = player.get("name")
        year = player.get("year")
        pctile = player.get("sporq_percentile")
        if name and year and pctile is not None:
            out[(name, int(year))] = float(pctile)
    return out


def find_suspicious(
    year: int,
    players: list[dict[str, Any]],
    sporq_by_key: dict[tuple[str, int], float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    low_ath_high_capital: list[dict[str, Any]] = []
    sporq_divergence: list[dict[str, Any]] = []
    for p in players:
        scores = p["scores"]
        ath = scores.get("athletic_score_0_100")
        prod = scores.get("production_0_100")
        dc = scores.get("draft_capital_proxy_0_100")
        src = scores.get("athletic_source")
        name = p.get("player_name", "")
        pos = p.get("position", "")

        if (
            ath is not None
            and dc is not None
            and prod is not None
            and ath < SUSPICIOUS_ATH_BELOW
            and dc >= SUSPICIOUS_DC_AT_LEAST
            and prod >= SUSPICIOUS_PROD_AT_LEAST
        ):
            low_ath_high_capital.append(
                {
                    "class_year": year,
                    "player_name": name,
                    "position": pos,
                    "athletic_score": ath,
                    "athletic_source": src,
                    "production_score": prod,
                    "draft_capital_score": dc,
                    "rookie_alpha": scores.get("rookie_alpha_0_100"),
                }
            )

        sporq = sporq_by_key.get((name, year))
        if sporq is not None and ath is not None and sporq >= SPORQ_HIGH and (sporq - ath) >= SPORQ_DIVERGENCE_POINTS:
            sporq_divergence.append(
                {
                    "class_year": year,
                    "player_name": name,
                    "position": pos,
                    "athletic_score": ath,
                    "athletic_source": src,
                    "sporq_percentile": sporq,
                    "delta_sporq_minus_ath": round(sporq - ath, 1),
                }
            )

    return low_ath_high_capital, sporq_divergence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Optional path to write the audit as JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    sporq = load_json(SPORQ_PATH) if SPORQ_PATH.exists() else {"players": []}
    sporq_by_key = sporq_lookup(sporq)

    report: dict[str, Any] = {
        "generated_for": "issue #205 — historical athletic score normalization audit",
        "investigation_only": True,
        "thresholds": {
            "suspicious_athletic_below": SUSPICIOUS_ATH_BELOW,
            "suspicious_draft_capital_at_least": SUSPICIOUS_DC_AT_LEAST,
            "suspicious_production_at_least": SUSPICIOUS_PROD_AT_LEAST,
            "sporq_divergence_points": SPORQ_DIVERGENCE_POINTS,
            "sporq_high_threshold": SPORQ_HIGH,
        },
        "by_class": {},
    }

    print("Athletic score audit — promoted predraft exports")
    print("=" * 64)

    for path in sorted(EXPORT_DIR.glob("*_rookie_alpha_predraft_v0.json")):
        try:
            year = int(path.name.split("_")[0])
        except ValueError:
            continue
        export = load_json(path)
        players = export.get("players", [])
        dist = class_distribution(players)
        cohort = combine_cohort_sizes(year)
        low_high, divergence = find_suspicious(year, players, sporq_by_key)

        report["by_class"][year] = {
            "athletic_distribution": dist,
            "combine_cohort_sizes": cohort,
            "low_athletic_high_capital": low_high,
            "sporq_divergence": divergence,
        }

        print(f"\n[{year}] athletic_score: n={dist.get('n')} mean={dist.get('mean')} "
              f"median={dist.get('median')} p25={dist.get('p25')} p75={dist.get('p75')} "
              f"<50={dist.get('share_below_50_pct')}% <40={dist.get('share_below_40_pct')}%")
        if cohort:
            print(f"        combine cohort sizes: {cohort}")
        if low_high:
            print(f"        suspicious (low ath, high prod & dc): {len(low_high)}")
            for r in low_high:
                print(f"          - {r['player_name']:<28s} {r['position']:>3s} "
                      f"ath={r['athletic_score']:>5.1f} ({r['athletic_source']})  "
                      f"prod={r['production_score']:>5.1f}  dc={r['draft_capital_score']:>5.1f}")
        if divergence:
            print(f"        SPORQ divergence (sporq>={SPORQ_HIGH}, gap>={SPORQ_DIVERGENCE_POINTS}): {len(divergence)}")
            for r in divergence:
                print(f"          - {r['player_name']:<28s} {r['position']:>3s} "
                      f"ath={r['athletic_score']:>5.1f}  sporq={r['sporq_percentile']:>5.1f}  "
                      f"delta=+{r['delta_sporq_minus_ath']}")

    if args.json:
        args.json.write_text(json.dumps(report, indent=2))
        print(f"\nWrote JSON audit to {args.json}")


if __name__ == "__main__":
    main()
