"""Tests for the issue #213 bounded gap-fill seed entries.

Covers:
- The Nick Singleton player_id alignment patch in draft_results.json so the
  alpha export's rb-nick-singleton row joins to the canonical draft pick.
- The priority-player identity stubs added to data/raw/2026_real_seed_pool.json.
- The expected fail-closed state for production: stubs do not yet appear in the
  alpha export because production_score_0_100 is intentionally null pending
  CFBD population (compute_rookie_alpha.py requires production + draft capital
  together).
- The cross-file player_id contract: each stub matches an existing
  data/processed/2026_draft_capital_proxy.json row and the matching
  data/processed/2026_draft_results.json row, so the seed will surface on the
  board once compute_production_scores.py runs with CFBD access.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SEED_POOL_PATH = REPO_ROOT / "data" / "raw" / "2026_real_seed_pool.json"
DRAFT_RESULTS_PATH = REPO_ROOT / "data" / "processed" / "2026_draft_results.json"
DRAFT_PROXY_PATH = REPO_ROOT / "data" / "processed" / "2026_draft_capital_proxy.json"
COLLEGE_PRODUCTION_PATH = REPO_ROOT / "data" / "processed" / "2026_college_production.json"
ALPHA_EXPORT_PATH = (
    REPO_ROOT / "exports" / "promoted" / "rookie-alpha" / "2026_rookie_alpha_predraft_v0.json"
)

# Priority players added as identity-only stubs in this PR. Klubnik and Green
# are explicitly excluded — their schools are not in any existing repo data
# file, so per the fail-closed hard rule they were skipped.
PRIORITY_STUB_IDS = {
    "rb-kaytron-allen",
    "rb-seth-mcgowan",
    "rb-emmett-johnson",
    "wr-barion-brown",
    "wr-deion-burks",
    "wr-kevin-coleman-jr",
    "wr-kendrick-law",
    "te-justin-joly",
}

REQUIRED_SEED_FIELDS = ("player_id", "player_name", "position", "school", "class_year")


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


class SingletonPlayerIdAlignmentTests(unittest.TestCase):
    """Patch: draft_results.json uses rb-nick-singleton to match the alpha export."""

    def test_draft_results_uses_seed_pool_player_id(self) -> None:
        draft_results = _load(DRAFT_RESULTS_PATH)
        singleton_rows = [r for r in draft_results if r["player_id"] == "rb-nick-singleton"]
        self.assertEqual(len(singleton_rows), 1)
        row = singleton_rows[0]
        self.assertEqual(row["draft_round"], 5)
        self.assertEqual(row["overall_pick"], 165)
        self.assertEqual(row["nfl_team"], "TEN")

    def test_no_stale_rb_nicholas_singleton_player_id(self) -> None:
        draft_results = _load(DRAFT_RESULTS_PATH)
        stale = [r for r in draft_results if r["player_id"] == "rb-nicholas-singleton"]
        self.assertEqual(stale, [])

    def test_alpha_export_singleton_row_joins_to_draft_results(self) -> None:
        alpha = json.loads(ALPHA_EXPORT_PATH.read_text(encoding="utf-8"))
        alpha_ids = {p["player_id"] for p in alpha["players"]}
        self.assertIn("rb-nick-singleton", alpha_ids)
        draft_ids = {r["player_id"] for r in _load(DRAFT_RESULTS_PATH)}
        self.assertIn("rb-nick-singleton", alpha_ids & draft_ids)


class PriorityPlayerSeedStubsTests(unittest.TestCase):
    """Issue #213 first pass: identity-only seed entries for 8 priority players."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.seed_rows = _load(SEED_POOL_PATH)
        cls.seed_by_id = {row["player_id"]: row for row in cls.seed_rows}

    def test_all_priority_stubs_present_in_seed_pool(self) -> None:
        missing = PRIORITY_STUB_IDS - set(self.seed_by_id)
        self.assertFalse(missing, f"Missing priority stubs in seed pool: {missing}")

    def test_priority_stubs_have_required_minimum_fields(self) -> None:
        for pid in PRIORITY_STUB_IDS:
            row = self.seed_by_id[pid]
            for field in REQUIRED_SEED_FIELDS:
                self.assertIn(field, row, f"{pid} missing required field {field}")
                self.assertIsNotNone(row[field], f"{pid} has null required field {field}")
            self.assertEqual(row["class_year"], 2026)
            self.assertIn(row["position"], {"RB", "WR", "TE"})

    def test_priority_stubs_production_score_is_null_fail_closed(self) -> None:
        # Hard rule: stubs must not invent production scores. Null here means
        # the player is intentionally excluded from the alpha rebuild until
        # CFBD-derived production is populated.
        for pid in PRIORITY_STUB_IDS:
            row = self.seed_by_id[pid]
            self.assertIsNone(
                row["production_score_0_100"],
                f"{pid} must have null production_score_0_100 until CFBD populates",
            )
            self.assertEqual(row["production_score_source"], "pending_cfbd_population_2025_season")

    def test_klubnik_and_green_intentionally_skipped(self) -> None:
        # Schools for Klubnik (Clemson) and Green (Arkansas) are not present in
        # any existing repo data file. Per fail-closed rule they were skipped.
        self.assertNotIn("qb-cade-klubnik", self.seed_by_id)
        self.assertNotIn("qb-taylen-green", self.seed_by_id)


class PriorityStubCrossFileIdContractTests(unittest.TestCase):
    """Stub player_ids must align with the existing draft_results and
    draft_capital_proxy rows so the alpha rebuild will join cleanly once
    CFBD-derived production is populated.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.draft_results_ids = {r["player_id"] for r in _load(DRAFT_RESULTS_PATH)}
        cls.draft_proxy_ids = {r["player_id"] for r in _load(DRAFT_PROXY_PATH)}

    def test_each_stub_has_matching_draft_results_row(self) -> None:
        missing = PRIORITY_STUB_IDS - self.draft_results_ids
        self.assertFalse(missing, f"Stub player_ids missing from draft_results: {missing}")

    def test_each_stub_has_matching_draft_capital_proxy_row(self) -> None:
        missing = PRIORITY_STUB_IDS - self.draft_proxy_ids
        self.assertFalse(missing, f"Stub player_ids missing from draft_capital_proxy: {missing}")

    def test_stubs_are_currently_excluded_from_alpha_export(self) -> None:
        # Confirms the fail-closed contract: until production_score_0_100 is
        # populated for these ids in 2026_college_production.json, the alpha
        # rebuild excludes them (compute_rookie_alpha.merge_inputs requires
        # production + draft_capital_proxy together).
        alpha_ids = {
            p["player_id"]
            for p in json.loads(ALPHA_EXPORT_PATH.read_text(encoding="utf-8"))["players"]
        }
        college_production_ids = {row["player_id"] for row in _load(COLLEGE_PRODUCTION_PATH)}
        for pid in PRIORITY_STUB_IDS:
            self.assertNotIn(
                pid,
                college_production_ids,
                f"{pid} should not be in 2026_college_production.json until CFBD populates",
            )
            self.assertNotIn(
                pid,
                alpha_ids,
                f"{pid} should not be in alpha export until production is populated",
            )


if __name__ == "__main__":
    unittest.main()
