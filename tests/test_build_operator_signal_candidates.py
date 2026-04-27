import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_operator_signal_candidates import (
    UnmappedJournalEntriesError,
    build_candidates,
    write_candidates,
)


class BuildOperatorSignalCandidatesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.input_path = Path("data/operator-journal/raw/2026_rookie_journal_entries.json")

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
        heavy_te = next(c for c in self.candidates if c["entity_type"] == "team_meta")
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

    def test_nick_singleton_includes_missing_data_audit_tags(self) -> None:
        nick = next(c for c in self.candidates if c["player_name"] == "Nick Singleton")
        self.assertIn("missing_data_audit", nick["context_tags"])
        self.assertIn("incomplete_profile_data_risk", nick["risk_tags"])

    def test_emmett_johnson_includes_predraft_alpha_and_passing_down_role(self) -> None:
        emmett = next(c for c in self.candidates if c["player_name"] == "Emmett Johnson")
        self.assertIn("predraft_alpha_36_4", emmett["context_tags"])
        self.assertIn("passing_down_role_path", emmett["positive_signal_tags"])

    def test_skyler_bell_includes_model_edge_and_urgency_risk(self) -> None:
        skyler = next(c for c in self.candidates if c["player_name"] == "Skyler Bell")
        self.assertIn("tiber_edge_plus_18", skyler["context_tags"])
        self.assertIn("late_selection_urgency_concern", skyler["risk_tags"])

    def test_germie_bernard_includes_slot_context_and_trade_up(self) -> None:
        germie = next(c for c in self.candidates if c["player_name"] == "Germie Bernard")
        self.assertIn("mccarthy_slot_fpg_signal", germie["context_tags"])
        self.assertIn("early_round2_trade_up", germie["positive_signal_tags"])

    def test_malachi_fields_includes_profile_risk_and_year1_route_path(self) -> None:
        fields = next(c for c in self.candidates if c["player_name"] == "Malachi Fields")
        self.assertIn("man_coverage_struggle", fields["risk_tags"])
        self.assertIn("year1_route_path", fields["positive_signal_tags"])

    def test_brenen_thompson_vertical_role_candidate_exists_with_key_tags(self) -> None:
        brenen_vertical = next(
            c
            for c in self.candidates
            if c["player_name"] == "Brenen Thompson"
            and c.get("candidate_theme") == "vertical_field_stretcher_role_watch"
        )
        self.assertIn("elite_speed_archetype", brenen_vertical["positive_signal_tags"])
        self.assertIn("vertical_field_stretcher", brenen_vertical["positive_signal_tags"])
        self.assertIn("rotational_wr4_path", brenen_vertical["risk_tags"])
        self.assertIn("undersized_frame_risk", brenen_vertical["risk_tags"])

    def test_brenen_thompson_profile_audit_candidate_exists_with_key_tags(self) -> None:
        brenen_audit = next(
            c
            for c in self.candidates
            if c["player_name"] == "Brenen Thompson" and c.get("candidate_theme") == "profile_completeness_audit"
        )
        self.assertIn("missing_data_audit", brenen_audit["context_tags"])
        self.assertIn("stale_profile_writeup", brenen_audit["risk_tags"])
        self.assertIn("missing_translation_evidence_tags", brenen_audit["risk_tags"])

    def test_brenen_thompson_candidates_are_operator_journal_needs_review(self) -> None:
        brenen_candidates = [c for c in self.candidates if c["player_name"] == "Brenen Thompson"]
        self.assertEqual(len(brenen_candidates), 2)
        for candidate in brenen_candidates:
            self.assertEqual(candidate["source_type"], "operator_journal")
            self.assertEqual(candidate["review_status"], "needs_human_review")

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

    def test_candidate_ids_are_unique_and_derived_from_entry(self) -> None:
        candidate_ids = [candidate["candidate_id"] for candidate in self.candidates]
        self.assertEqual(len(candidate_ids), len(set(candidate_ids)))
        for candidate in self.candidates:
            self.assertTrue(candidate["candidate_id"].startswith(f"cand_{candidate['source_entry_id']}_"))

    def test_second_ty_simpson_entry_gets_unique_candidate_id(self) -> None:
        entries = json.loads(self.input_path.read_text(encoding="utf-8"))
        entries.append(
            {
                "entry_id": "oj_2026_006_ty_simpson_followup",
                "entry_date": "2026-04-25",
                "entry_title": "Ty Simpson historical context follow-up",
                "entry_text": "Follow-up Ty Simpson note in same thematic lane.",
                "source_type": "operator_journal",
                "operator": "local",
                "review_status": "raw",
            }
        )

        candidates = build_candidates(entries)
        ty_candidates = [candidate for candidate in candidates if candidate["player_name"] == "Ty Simpson"]
        self.assertEqual(len(ty_candidates), 2)
        self.assertEqual(len({candidate["candidate_id"] for candidate in ty_candidates}), 2)

    def test_unmapped_entries_fail_loudly_by_default(self) -> None:
        entries = json.loads(self.input_path.read_text(encoding="utf-8"))
        entries.append(
            {
                "entry_id": "oj_2026_999_unmapped",
                "entry_date": "2026-04-25",
                "entry_title": "Unknown note",
                "entry_text": "A note with no mapping rule.",
                "source_type": "operator_journal",
                "operator": "local",
                "review_status": "raw",
            }
        )

        with self.assertRaises(UnmappedJournalEntriesError):
            build_candidates(entries)

    def test_allow_unmapped_skips_unknown_entries(self) -> None:
        entries = json.loads(self.input_path.read_text(encoding="utf-8"))
        entries.append(
            {
                "entry_id": "oj_2026_999_unmapped",
                "entry_date": "2026-04-25",
                "entry_title": "Unknown note",
                "entry_text": "A note with no mapping rule.",
                "source_type": "operator_journal",
                "operator": "local",
                "review_status": "raw",
            }
        )

        candidates = build_candidates(entries, allow_unmapped=True)
        self.assertTrue(candidates)
        self.assertFalse(any(c["source_entry_id"] == "oj_2026_999_unmapped" for c in candidates))


if __name__ == "__main__":
    unittest.main()
