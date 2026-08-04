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


def freeze() -> None:
    RECORDS.mkdir(parents=True, exist_ok=True)
    for player_id, stem in PILOTS:
        card = CARDS / f"{stem}_predraft_v0.json"
        landing = LANDING / f"{stem}_landing_context_v0.json"
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
        out = RECORDS / f"{stem}_expectation_record_v0.json"
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
    args = parser.parse_args()
    if args.mode == "freeze":
        freeze()
    else:
        sys.exit(1 if verify() else 0)


if __name__ == "__main__":
    main()
