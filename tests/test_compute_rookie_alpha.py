import tempfile
import unittest
from pathlib import Path

from scripts.compute_rookie_alpha import (
    PlayerInputs,
    compute_ras_scores,
    load_json,
    merge_inputs,
    rookie_alpha_score,
    write_outputs,
)


class RookieAlphaTests(unittest.TestCase):
    def test_ras_scoring_behavior(self) -> None:
        combine_rows = [
            {
                "player_id": "rb_fast",
                "player_name": "Fast Back",
                "position": "RB",
                "forty": 4.4,
                "vertical": 38,
                "broad": 125,
                "height_in": 71,
                "weight_lb": 210,
            },
            {
                "player_id": "rb_slow",
                "player_name": "Slow Back",
                "position": "RB",
                "forty": 4.65,
                "vertical": 31,
                "broad": 113,
                "height_in": 70,
                "weight_lb": 208,
            },
        ]

        scores = compute_ras_scores(combine_rows)
        self.assertIn("rb_fast", scores)
        self.assertIn("rb_slow", scores)
        self.assertGreater(scores["rb_fast"], scores["rb_slow"])

    def test_rookie_alpha_score(self) -> None:
        player = PlayerInputs(
            player_id="p1",
            player_name="Player 1",
            position="WR",
            ras_score_0_100=80.0,
            production_score_0_100=60.0,
            draft_capital_proxy_0_100=70.0,
        )
        self.assertAlmostEqual(rookie_alpha_score(player), 69.0)

    def test_merge_inputs(self) -> None:
        combine_rows = [
            {
                "player_id": "p1",
                "player_name": "One",
                "position": "WR",
                "forty": 4.4,
            }
        ]
        production_rows = [
            {
                "player_id": "p2",
                "player_name": "Two",
                "position": "RB",
                "production_score_0_100": 75,
            }
        ]
        draft_rows = [
            {
                "player_id": "p3",
                "player_name": "Three",
                "position": "TE",
                "draft_capital_proxy_0_100": 85,
            }
        ]

        players = merge_inputs(combine_rows, production_rows, draft_rows)
        self.assertEqual([p.player_id for p in players], ["p1", "p2", "p3"])

    def test_draft_capital_proxy_handling(self) -> None:
        players = [
            PlayerInputs("p1", "One", "WR", 80, 80, None),
            PlayerInputs("p2", "Two", "WR", 80, 80, 100),
        ]
        self.assertLess(rookie_alpha_score(players[0]), rookie_alpha_score(players[1]))

    def test_missing_input_behavior_and_logging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_json = Path(tmp) / "out.json"
            out_csv = Path(tmp) / "out.csv"
            player = PlayerInputs(
                player_id="p_missing",
                player_name="Missing Inputs",
                position="QB",
                ras_score_0_100=None,
                production_score_0_100=60.0,
                draft_capital_proxy_0_100=None,
            )
            with self.assertLogs(level="WARNING") as cm:
                write_outputs(
                    players=[player],
                    season=2026,
                    combine_path=Path("combine.json"),
                    production_path=Path("production.json"),
                    draft_proxy_path=Path("draft.json"),
                    output_json=out_json,
                    output_csv=out_csv,
                )
            self.assertTrue(any("Defaulting missing inputs to 50.0" in line for line in cm.output))

    def test_missing_required_player_fields_are_skipped(self) -> None:
        players = merge_inputs(
            combine_rows=[{"player_name": "No Id", "position": "WR", "forty": 4.5}],
            production_rows=[],
            draft_proxy_rows=[],
        )
        self.assertEqual(players, [])

    def test_load_json_errors_are_friendly(self) -> None:
        with self.assertRaises(SystemExit) as missing_file_error:
            load_json(Path("/tmp/does-not-exist.json"))
        self.assertIn("Input file not found", str(missing_file_error.exception))

        with tempfile.TemporaryDirectory() as tmp:
            invalid_json = Path(tmp) / "bad.json"
            invalid_json.write_text("{not-json", encoding="utf-8")
            with self.assertRaises(SystemExit) as invalid_json_error:
                load_json(invalid_json)
            self.assertIn("Invalid JSON", str(invalid_json_error.exception))


if __name__ == "__main__":
    unittest.main()
