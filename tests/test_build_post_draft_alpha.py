import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_post_draft_alpha import build_post_draft_rows, write_outputs


class BuildPostDraftAlphaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.predraft_path = Path("exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json")
        self.round1_path = Path("data/processed/2026_round1_draft_signal_profiles.json")
        self.day2_path = Path("data/processed/2026_day2_draft_signal_profiles.json")
        self.rows = build_post_draft_rows(self.predraft_path, self.round1_path, self.day2_path)

    def test_every_profile_player_gets_post_draft_row(self) -> None:
        round1 = json.loads(self.round1_path.read_text(encoding="utf-8"))
        day2 = json.loads(self.day2_path.read_text(encoding="utf-8"))
        expected_players = {p["player_name"] for p in round1 + day2}
        actual_players = {row["player_name"] for row in self.rows}
        self.assertSetEqual(actual_players, expected_players)

    def test_pre_draft_alpha_is_preserved(self) -> None:
        predraft = json.loads(self.predraft_path.read_text(encoding="utf-8"))
        predraft_index = {p["player_id"]: p for p in predraft["players"]}

        for row in self.rows:
            predraft_player = predraft_index.get(row["player_id"])
            if predraft_player is None:
                self.assertEqual(row["pre_draft_alpha"], 0.0)
                self.assertEqual(row["post_draft_delta"], 0.0)
                continue

            pre_alpha = round(float(predraft_player["scores"]["rookie_alpha_0_100"]), 1)
            self.assertEqual(row["pre_draft_alpha"], pre_alpha)

    def test_post_draft_delta_equals_difference(self) -> None:
        for row in self.rows:
            expected_delta = round(row["post_draft_alpha"] - row["pre_draft_alpha"], 1)
            self.assertEqual(row["post_draft_delta"], expected_delta)
            if row["post_draft_delta"] != 0:
                self.assertTrue(row["delta_reason_codes"])

    def test_stribling_gets_positive_near_round1_adjustment(self) -> None:
        stribling = next(row for row in self.rows if row["player_name"] == "De'Zhaun Stribling")
        self.assertGreater(stribling["post_draft_delta"], 0)
        self.assertTrue(
            any("near_round1_skill_capital" in reason for reason in stribling["delta_reason_codes"])
        )

    def test_round3_qbs_do_not_get_excessive_upgrade(self) -> None:
        round3_qbs = [
            row
            for row in self.rows
            if row["position"] == "QB" and row["draft_round"] == 3
        ]
        self.assertTrue(round3_qbs)
        for qb in round3_qbs:
            self.assertLessEqual(qb["post_draft_delta"], 2.0)

    def test_delayed_te_translation_watch_limits_bump(self) -> None:
        delayed_tes = [
            row
            for row in self.rows
            if row["position"] == "TE" and "delayed_te_translation_watch" in row["translator_tags"]
        ]
        self.assertTrue(delayed_tes)
        for te in delayed_tes:
            self.assertLessEqual(te["post_draft_delta"], 3.0)

    def test_write_outputs_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_json = Path(temp_dir) / "postdraft.json"
            output_csv = Path(temp_dir) / "postdraft.csv"
            write_outputs(self.rows, output_json, output_csv)

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["model"], "rookie-alpha-postdraft-v0")
            self.assertEqual(len(payload["rows"]), len(self.rows))
            self.assertTrue(output_csv.exists())


if __name__ == "__main__":
    unittest.main()
