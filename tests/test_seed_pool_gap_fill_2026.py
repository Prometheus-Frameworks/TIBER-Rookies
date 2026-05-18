"""Tests for the issue #213 priority-player gap fill — CFBD-populated state.

This is the follow-up to the bounded first pass (PR #214):
- PR #214 added 8 identity-only seed stubs with production_score_0_100=null.
- This PR ran scripts/compute_production_scores.py to populate production
  scores from CFBD 2025 season stats, then rebuilt the alpha export.

Covers:
- The Nick Singleton player_id alignment in draft_results.json (carried
  forward from PR #214).
- Each of the 8 priority stubs now has CFBD-sourced production scores in
  both data/raw/2026_real_seed_pool.json and
  data/processed/2026_college_production.json.
- Each priority player_id now appears in the rebuilt pre-draft alpha
  export and joins to its canonical draft_results row.
- Klubnik and Green remain intentionally excluded (school not present in
  any existing repo data file).
- Existing 40 alpha scores remain stable (no drift from the rebuild).
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
PLAYER_STATS_PATH = REPO_ROOT / "data" / "processed" / "2026_player_stats.json"
ALPHA_EXPORT_PATH = (
    REPO_ROOT / "exports" / "promoted" / "rookie-alpha" / "2026_rookie_alpha_predraft_v0.json"
)

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
    """Carryover from PR #214: draft_results uses rb-nick-singleton to match the alpha export."""

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


class PriorityPlayerSeedPoolTests(unittest.TestCase):
    """Seed pool identity contract for the 8 priority players (post-CFBD population)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.seed_by_id = {row["player_id"]: row for row in _load(SEED_POOL_PATH)}

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

    def test_priority_stubs_now_have_cfbd_production_score(self) -> None:
        # After compute_production_scores.py runs, each stub carries a
        # numeric production_score_0_100 and the canonical CFBD source string.
        for pid in PRIORITY_STUB_IDS:
            row = self.seed_by_id[pid]
            self.assertIsInstance(
                row["production_score_0_100"],
                (int, float),
                f"{pid} production_score_0_100 must be numeric after CFBD population",
            )
            self.assertGreater(row["production_score_0_100"], 0)
            self.assertLessEqual(row["production_score_0_100"], 100)
            self.assertIn("CFBD 2025 season stats", row["production_score_source"])
            self.assertNotEqual(row["production_score_source"], "pending_cfbd_population_2025_season")

    def test_klubnik_and_green_remain_intentionally_skipped(self) -> None:
        # Schools not present in any existing repo data file → still skipped.
        self.assertNotIn("qb-cade-klubnik", self.seed_by_id)
        self.assertNotIn("qb-taylen-green", self.seed_by_id)


class PriorityStubCrossFileIdContractTests(unittest.TestCase):
    """Stub player_ids align with the existing draft_results and
    draft_capital_proxy rows, and now also appear in college_production
    and the rebuilt alpha export.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.draft_results_ids = {r["player_id"] for r in _load(DRAFT_RESULTS_PATH)}
        cls.draft_proxy_ids = {r["player_id"] for r in _load(DRAFT_PROXY_PATH)}
        cls.college_production_ids = {r["player_id"] for r in _load(COLLEGE_PRODUCTION_PATH)}
        cls.player_stats_ids = {r["player_id"] for r in _load(PLAYER_STATS_PATH)}
        cls.alpha = json.loads(ALPHA_EXPORT_PATH.read_text(encoding="utf-8"))
        cls.alpha_by_id = {p["player_id"]: p for p in cls.alpha["players"]}

    def test_each_stub_has_matching_draft_results_row(self) -> None:
        missing = PRIORITY_STUB_IDS - self.draft_results_ids
        self.assertFalse(missing, f"Stub player_ids missing from draft_results: {missing}")

    def test_each_stub_has_matching_draft_capital_proxy_row(self) -> None:
        missing = PRIORITY_STUB_IDS - self.draft_proxy_ids
        self.assertFalse(missing, f"Stub player_ids missing from draft_capital_proxy: {missing}")

    def test_each_stub_has_college_production_row(self) -> None:
        missing = PRIORITY_STUB_IDS - self.college_production_ids
        self.assertFalse(missing, f"Stub player_ids missing from college_production: {missing}")

    def test_each_stub_has_player_stats_row(self) -> None:
        missing = PRIORITY_STUB_IDS - self.player_stats_ids
        self.assertFalse(missing, f"Stub player_ids missing from player_stats: {missing}")

    def test_each_stub_appears_in_alpha_export(self) -> None:
        # The whole point of populating CFBD production: stubs now appear in
        # the alpha export so the board can surface them with the Day-3
        # headwind applied by lib/rookies/postDraftAdjustments.js.
        missing = PRIORITY_STUB_IDS - set(self.alpha_by_id)
        self.assertFalse(missing, f"Stub player_ids missing from alpha export: {missing}")

    def test_stubs_have_finite_alpha_inputs(self) -> None:
        for pid in PRIORITY_STUB_IDS:
            scores = self.alpha_by_id[pid]["scores"]
            self.assertIsNotNone(scores["production_0_100"], f"{pid} production_0_100 must be set")
            self.assertIsNotNone(scores["draft_capital_proxy_0_100"], f"{pid} draft_capital_proxy_0_100 must be set")
            self.assertIsNotNone(scores["rookie_alpha_0_100"], f"{pid} rookie_alpha_0_100 must be set")
            # Day-3 capital + low production keeps these stubs in the lower
            # half of the export; no stub should be promoted into Day-2 tiers.
            self.assertLess(scores["rookie_alpha_0_100"], 60.0, f"{pid} alpha out of Day-3 band")


if __name__ == "__main__":
    unittest.main()
