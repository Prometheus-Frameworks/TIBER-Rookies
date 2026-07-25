"""Incident-specific regression for TIBER-Rookies#271.

The 2025 Travis Hunter source and promoted Rookie Alpha export carried the
unsupported claim "recovered from gunshot injury in 2023" plus an unsourced
``severe_injury_recovery`` context flag. This test prevents that exact incident
from recurring without establishing a repository-wide content policy.
"""

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAYER_ID = "wr-travis-hunter"
REJECTED_CLAIM = "recovered from gunshot injury in 2023"
REJECTED_CONTEXT_FLAG = "severe_injury_recovery"
SOURCE_PATH = REPO_ROOT / "data" / "processed" / "2025_prospect_context.json"
PROMOTED_PATH = (
    REPO_ROOT
    / "exports"
    / "promoted"
    / "rookie-alpha"
    / "2025_rookie_alpha_predraft_v0.json"
)


def _source_row() -> dict:
    rows = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    return next(row for row in rows if row.get("player_id") == PLAYER_ID)


def _promoted_player() -> dict:
    payload = json.loads(PROMOTED_PATH.read_text(encoding="utf-8"))
    return next(
        player for player in payload["players"] if player.get("player_id") == PLAYER_ID
    )


class TravisHunterClaimRegressionTests(unittest.TestCase):
    def test_source_does_not_contain_rejected_claim(self) -> None:
        summary = (_source_row().get("evidence_summary") or "").lower()
        self.assertNotIn(REJECTED_CLAIM, summary)

    def test_source_does_not_contain_rejected_context_flag(self) -> None:
        flags = _source_row().get("context_flags") or []
        self.assertNotIn(REJECTED_CONTEXT_FLAG, flags)

    def test_promoted_summary_matches_corrected_source(self) -> None:
        source_summary = _source_row().get("evidence_summary") or ""
        promoted_summary = (
            (_promoted_player().get("evidence") or {}).get("evidence_summary") or ""
        )
        self.assertNotIn(REJECTED_CLAIM, promoted_summary.lower())
        self.assertEqual(promoted_summary, source_summary)


if __name__ == "__main__":
    unittest.main()
