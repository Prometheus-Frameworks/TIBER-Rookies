#!/usr/bin/env python3
"""Freeze or verify 2023 historical expectation records (issue #283).

freeze: writes one historical_expectation_record_v0 per pilot player binding
the pre-draft card and landing-context artifact by sha256.
verify: recomputes hashes and fails if any frozen layer has been edited.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("data/historical/reconstruction_2023")
CARDS = BASE / "predraft_cards"
LANDING = BASE / "landing_context"
RECORDS = BASE / "expectation_records"

PILOTS = [
    ("wr-puka-nacua", "2023_wr_puka_nacua"),
    ("wr-zay-flowers", "2023_wr_zay_flowers"),
    ("wr-josh-downs", "2023_wr_josh_downs"),
]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(refreeze_reason: str | None = None) -> None:
    RECORDS.mkdir(parents=True, exist_ok=True)
    for player_id, stem in PILOTS:
        card = CARDS / f"{stem}_predraft_v0.json"
        landing = LANDING / f"{stem}_landing_context_v0.json"
        out = RECORDS / f"{stem}_expectation_record_v0.json"

        refreeze_log: list[dict] = []
        if out.exists():
            existing = json.loads(out.read_text())
            unchanged = (
                existing.get("predraft_card", {}).get("sha256") == sha256_of(card)
                and existing.get("landing_context", {}).get("sha256") == sha256_of(landing)
            )
            if unchanged:
                print(f"unchanged {out} (hashes already match; record kept)")
                continue
            if not refreeze_reason:
                raise SystemExit(
                    f"Refusing to overwrite {out}: frozen layers changed. "
                    "Re-freezing requires an explicit logged reason "
                    "(--refreeze-reason), per docs/historical-reconstruction-contract.md."
                )
            refreeze_log = list(existing.get("refreeze_log", []))
            refreeze_log.append({
                "refrozen_at": datetime.now(tz=timezone.utc).isoformat(),
                "reason": refreeze_reason,
                "previous_predraft_card_sha256": existing.get("predraft_card", {}).get("sha256"),
                "previous_landing_context_sha256": existing.get("landing_context", {}).get("sha256"),
            })

        record = {
            "artifact": "historical_expectation_record_v0",
            "issue": "Prometheus-Frameworks/TIBER-Rookies#283",
            "canonical_player_id": player_id,
            "class_year": 2023,
            "frozen_at": datetime.now(tz=timezone.utc).isoformat(),
            "predraft_card": {"path": str(card), "sha256": sha256_of(card)},
            "landing_context": {"path": str(landing), "sha256": sha256_of(landing)},
            "nfl_outcomes_included": False,
            "freeze_note": (
                "Frozen before any outcome layer was written. Any edit to the "
                "referenced files invalidates this record and requires an "
                "explicit logged re-freeze (see docs/historical-reconstruction-contract.md)."
            ),
        }
        if refreeze_log:
            record["refreeze_log"] = refreeze_log
        out.write_text(json.dumps(record, indent=2) + "\n")
        print(f"froze {out}")


def verify() -> int:
    failures = 0
    for _, stem in PILOTS:
        record_path = RECORDS / f"{stem}_expectation_record_v0.json"
        record = json.loads(record_path.read_text())
        for layer in ("predraft_card", "landing_context"):
            path = Path(record[layer]["path"])
            actual = sha256_of(path)
            if actual != record[layer]["sha256"]:
                print(f"FROZEN LAYER MODIFIED: {path} (record {record_path.name})")
                failures += 1
    if failures == 0:
        print("All frozen layers verified intact.")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["freeze", "verify"])
    parser.add_argument(
        "--refreeze-reason",
        default=None,
        help="Required to overwrite an existing record whose layers changed; logged into the record.",
    )
    args = parser.parse_args()
    if args.mode == "freeze":
        freeze(refreeze_reason=args.refreeze_reason)
    else:
        sys.exit(1 if verify() else 0)


if __name__ == "__main__":
    main()
