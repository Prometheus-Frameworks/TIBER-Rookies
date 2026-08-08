#!/usr/bin/env python3
"""Build source-backed stub rows for drafted 2026 players without Alpha coverage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DRAFT_RESULTS = REPO_ROOT / "data/processed/2026_draft_results.json"
DEFAULT_ALPHA_CONTEXT = (
    REPO_ROOT
    / "exports/promoted/rookie-alpha/2026_rookie_alpha_postdraft_role_context_v0.json"
)
DEFAULT_OUTPUT = REPO_ROOT / "data/processed/2026_rookie_stubs_v0.json"

PROVENANCE_FIELDS = (
    "source_name",
    "source_url",
    "source_status",
    "upstream_provenance_status",
    "ingested_from",
    "ingested_at",
)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Required input does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Required input is not valid JSON: {path}: {exc}") from exc


def require_player_id(row: dict[str, Any], source: str, index: int) -> str:
    player_id = row.get("player_id")
    if not isinstance(player_id, str) or not player_id.strip():
        raise ValueError(f"{source} row {index} is missing player_id")
    normalized = player_id.strip().lower()
    if normalized != player_id:
        raise ValueError(f"{source} row {index} has a non-canonical player_id: {player_id}")
    return normalized


def collect_unique_ids(rows: list[Any], source: str) -> set[str]:
    ids: set[str] = set()
    for index, raw_row in enumerate(rows):
        if not isinstance(raw_row, dict):
            raise ValueError(f"{source} row {index} is not an object")
        player_id = require_player_id(raw_row, source, index)
        if player_id in ids:
            raise ValueError(f"{source} contains duplicate player_id: {player_id}")
        ids.add(player_id)
    return ids


def build_stub(row: dict[str, Any], index: int) -> dict[str, Any]:
    player_id = require_player_id(row, "draft-results", index)
    required_values = {
        "player_name": row.get("player_name"),
        "position": row.get("position"),
        "nfl_team": row.get("nfl_team"),
        "draft_round": row.get("draft_round"),
        "overall_pick": row.get("overall_pick"),
    }
    missing = [key for key, value in required_values.items() if value is None or value == ""]
    if missing:
        raise ValueError(f"draft-results row {index} ({player_id}) is missing: {', '.join(missing)}")
    for field in ("player_name", "position", "nfl_team"):
        if not isinstance(required_values[field], str):
            raise ValueError(f"draft-results row {index} ({player_id}) has invalid {field}")
    if not isinstance(required_values["draft_round"], int) or not 1 <= required_values["draft_round"] <= 7:
        raise ValueError(f"draft-results row {index} ({player_id}) has invalid draft_round")
    if not isinstance(required_values["overall_pick"], int) or required_values["overall_pick"] < 1:
        raise ValueError(f"draft-results row {index} ({player_id}) has invalid overall_pick")

    provenance: dict[str, Any] = {}
    for field in PROVENANCE_FIELDS:
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"draft-results row {index} ({player_id}) is missing {field}")
        provenance[field] = value

    return {
        "player_id": player_id,
        "name": required_values["player_name"],
        "position": required_values["position"],
        "team": required_values["nfl_team"],
        "round": required_values["draft_round"],
        "overall_pick": required_values["overall_pick"],
        "alpha_status": "not_scored",
        "reason": "below_day2_scoring_floor",
        "provenance": provenance,
    }


def build_stubs(draft_results: Any, alpha_context: Any) -> list[dict[str, Any]]:
    if not isinstance(draft_results, list):
        raise ValueError("draft-results input must be a top-level array")
    if not isinstance(alpha_context, dict) or not isinstance(alpha_context.get("rows"), list):
        raise ValueError("Alpha role-context input must be an object with a rows array")

    draft_ids = collect_unique_ids(draft_results, "draft-results")
    scored_ids = collect_unique_ids(alpha_context["rows"], "Alpha role-context")
    unknown_scored_ids = scored_ids - draft_ids
    if unknown_scored_ids:
        raise ValueError(
            "Alpha role-context contains player_ids absent from draft-results: "
            + ", ".join(sorted(unknown_scored_ids))
        )

    stubs: list[dict[str, Any]] = []
    for index, row in enumerate(draft_results):
        if row.get("draft_result_status") != "drafted":
            continue
        player_id = require_player_id(row, "draft-results", index)
        if player_id not in scored_ids:
            stubs.append(build_stub(row, index))

    return stubs


def render_stubs(stubs: list[dict[str, Any]]) -> str:
    return f"{json.dumps(stubs, indent=2, ensure_ascii=False)}\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft-results", type=Path, default=DEFAULT_DRAFT_RESULTS)
    parser.add_argument("--alpha-context", type=Path, default=DEFAULT_ALPHA_CONTEXT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the checked-in output differs from a fresh deterministic build.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stubs = build_stubs(load_json(args.draft_results), load_json(args.alpha_context))
    rendered = render_stubs(stubs)

    if args.check:
        try:
            existing = args.output.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"Stub artifact missing: {args.output}")
            return 1
        if existing != rendered:
            print(f"Stub artifact is stale: {args.output}")
            return 1
        print(f"Stub artifact is current: {len(stubs)} rows")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {len(stubs)} stub rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
