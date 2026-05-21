#!/usr/bin/env python3
"""Compare operator-supplied deep Devy draft snapshots with the seed watchlist."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def slugify(value: str) -> str:
    return "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())


def build_watchlist_map(seed_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    prospects = seed_payload.get("prospects", [])
    result: dict[str, dict[str, Any]] = {}
    for prospect in prospects:
        key = prospect.get("player_id") or slugify(prospect.get("player_name", ""))
        if key:
            result[key] = prospect
    return result


def compute_diff(snapshot_payload: dict[str, Any], seed_payload: dict[str, Any]) -> dict[str, Any]:
    watchlist = build_watchlist_map(seed_payload)
    drafted_keys: set[str] = set()

    drafted_and_known: list[dict[str, Any]] = []
    drafted_missing: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for draft in snapshot_payload.get("drafts", []):
        for pick in draft.get("picks", []):
            normalized = pick.get("player_name_normalized", "")
            key = slugify(normalized)
            drafted_keys.add(key)
            school_norm = pick.get("school_normalized", "unknown")
            position_norm = pick.get("position_normalized", "unknown")

            if school_norm.lower() == "unknown" or position_norm.lower() == "unknown":
                unresolved.append(
                    {
                        "draft_id": pick.get("draft_id"),
                        "pick": pick.get("pick"),
                        "player_name_normalized": normalized,
                        "school_normalized": school_norm,
                        "position_normalized": position_norm,
                        "issue": "missing_normalized_identity_fields",
                    }
                )

            if key in watchlist:
                seeded = watchlist[key]
                drafted_and_known.append(
                    {
                        "draft_id": pick.get("draft_id"),
                        "pick": pick.get("pick"),
                        "player_name_normalized": normalized,
                        "seed_player_id": seeded.get("player_id"),
                        "school": seeded.get("school", "unknown"),
                        "position": seeded.get("position", "unknown"),
                        "tiber_seed_watchlist_match": True,
                    }
                )
            else:
                drafted_missing.append(
                    {
                        "draft_id": pick.get("draft_id"),
                        "pick": pick.get("pick"),
                        "player_name_normalized": normalized,
                        "school_normalized": school_norm,
                        "position_normalized": position_norm,
                        "tiber_seed_watchlist_match": False,
                        "coverage_gap_candidate": True,
                        "auto_add_to_seed_watchlist": False,
                    }
                )

    available_seed = [
        {
            "player_id": prospect.get("player_id"),
            "player_name": prospect.get("player_name"),
            "school": prospect.get("school"),
            "position": prospect.get("position"),
        }
        for player_id, prospect in watchlist.items()
        if player_id not in drafted_keys
    ]

    return {
        "schema_version": "devy-league-market-coverage-diff-v0.1.0",
        "artifact_type": "devy_league_market_snapshot_coverage_diff",
        "snapshot_year": snapshot_payload.get("snapshot_year"),
        "comparison_basis": "operator_supplied_snapshot_vs_devy_seed_watchlist",
        "drafted_and_known_by_tiber": drafted_and_known,
        "drafted_missing_from_tiber": drafted_missing,
        "tiber_seed_available_at_snapshot": available_seed,
        "identity_conflicts_or_unresolved": unresolved,
        "coverage_gap_candidates": drafted_missing,
        "recommended_monthly_pulse_candidates": [
            {
                "player_name_normalized": row["player_name_normalized"],
                "draft_id": row["draft_id"],
                "pick": row["pick"],
                "reason": "drafted_in_operator_snapshot_missing_from_seed_watchlist",
                "auto_seed_watchlist_mutation": "none",
            }
            for row in drafted_missing
        ],
        "warnings": [
            "Coverage diff is discovery intelligence only and must not be treated as rankings/scouting truth.",
            "No automatic seed-watchlist mutation is allowed from this artifact.",
            "Do not route this artifact into Rookie Alpha, promoted rookie exports, or NFL scoring surfaces.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute deep Devy league market snapshot coverage diff")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--seed-watchlist", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    snapshot_payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    seed_payload = json.loads(args.seed_watchlist.read_text(encoding="utf-8"))
    diff = compute_diff(snapshot_payload, seed_payload)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(diff, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
