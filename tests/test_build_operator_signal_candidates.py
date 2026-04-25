import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_operator_signal_candidates import build_candidates, write_candidates


class BuildOperatorSignalCandidatesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.input_path = Path("data/operator-journal/raw/2026_rookie_journal_entries.json")
        self.output_path = Path("data/operator-journal/processed/2026_operator_signal_candidates.json")

        entries = json.loads(self.input_path.read_text(encoding="utf-8"))
        self.candidates = build_candidates(entries)

    def test_script_creates_candidate_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "operator_candidates.json"
            write_candidates(self.input_path, output_path)
            self.assertTrue(output_path.exists())
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(payload)

    def test_output_includes_antonio_williams(self) -> None:
        antonio = next(c for c in self.candidates if c["player_name"] == "Antonio Williams")
        self.assertEqual(antonio["team"], "Commanders")
        self.assertIn("available_target_opportunity", antonio["positive_signal_tags"])

    def test_output_includes_heavy_te_meta(self) -> None:
        heavy_te = next(c for c in self.candidates if c["candidate_id"] == "cand_2026_heavy_te_meta")
        self.assertIn("heavy_te_personnel_meta", heavy_te["positive_signal_tags"])
        self.assertIn("two_wr_set_target_focus", heavy_te["context_tags"])

    def test_ty_simpson_includes_low_experience_risk_tags(self) -> None:
        ty = next(c for c in self.candidates if c["player_name"] == "Ty Simpson")
        self.assertIn("low_college_attempt_sample", ty["risk_tags"])
        self.assertIn("round1_qb_experience_risk", ty["risk_tags"])
        self.assertIn("developmental_qb_variance", ty["risk_tags"])

    def test_tanner_koziol_includes_model_edge_tags(self) -> None:
        tanner = next(c for c in self.candidates if c["player_name"] == "Tanner Koziol")
        self.assertIn("tiber_edge_plus_18", tanner["context_tags"])
        self.assertIn("model_edge_confirmed_by_draft_capital", tanner["positive_signal_tags"])

    def test_all_candidates_are_operator_journal_source(self) -> None:
        for candidate in self.candidates:
            self.assertEqual(candidate["source_type"], "operator_journal")

    def test_all_candidates_default_to_needs_human_review(self) -> None:
        for candidate in self.candidates:
            self.assertEqual(candidate["review_status"], "needs_human_review")

    def test_script_does_not_target_alpha_artifacts(self) -> None:
        script_text = Path("scripts/build_operator_signal_candidates.py").read_text(encoding="utf-8")
        self.assertNotIn("rookie_alpha", script_text)
        self.assertNotIn("post_draft_alpha", script_text)


if __name__ == "__main__":
    unittest.main()
