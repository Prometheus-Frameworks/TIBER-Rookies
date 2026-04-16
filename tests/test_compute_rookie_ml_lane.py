import unittest

from scripts.compute_rookie_ml_lane import (
    BASELINE_MODEL_FEATURES,
    _extract_hit_label,
    build_labeled_rows,
    pr_auc,
    roc_auc,
    time_split,
)


class RookieMlLaneTests(unittest.TestCase):
    def test_extract_hit_label_by_position_thresholds(self) -> None:
        self.assertEqual(_extract_hit_label({"position": "WR", "top_finish_band": "TOP-24"}), 1)
        self.assertEqual(_extract_hit_label({"position": "RB", "top_finish_band": "RB25"}), 0)
        self.assertEqual(_extract_hit_label({"position": "TE", "top_finish_band": "TE12"}), 1)
        self.assertEqual(_extract_hit_label({"position": "QB", "top_finish_band": "QB15"}), 1)
        self.assertEqual(_extract_hit_label({"position": "QB", "top_finish_band": "QB16"}), 0)


    def test_tier_labels_do_not_parse_as_literal_ranks(self) -> None:
        self.assertEqual(_extract_hit_label({"position": "WR", "top_finish_band": "WR3"}), 0)
        self.assertEqual(_extract_hit_label({"position": "RB", "top_finish_band": "RB2"}), 1)
        self.assertEqual(_extract_hit_label({"position": "QB", "top_finish_band": "QB15"}), 1)

    def test_build_labeled_rows_filters_unlabeled(self) -> None:
        features = [
            {
                "player_id": "a",
                "player_name": "A",
                "position": "WR",
                "draft_year": 2020,
                "draft_capital_proxy_0_100": 80,
                "production_0_100": 70,
                "ras_0_100": 60,
            },
            {
                "player_id": "b",
                "player_name": "B",
                "position": "WR",
                "draft_year": 2021,
                "draft_capital_proxy_0_100": 70,
                "production_0_100": 50,
                "ras_0_100": 40,
            },
        ]
        outcomes = [
            {"player_id": "a", "position": "WR", "top_finish_band": "TOP-24"},
            {"player_id": "b", "position": "WR", "top_finish_band": None},
        ]
        rows = build_labeled_rows(features, outcomes, {})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["player_id"], "a")
        self.assertEqual(rows[0]["hit_label"], 1)

    def test_time_split_uses_class_years(self) -> None:
        rows = [
            {"player_id": "a", "draft_year": 2019, "hit_label": 1},
            {"player_id": "b", "draft_year": 2020, "hit_label": 0},
            {"player_id": "c", "draft_year": 2021, "hit_label": 1},
            {"player_id": "d", "draft_year": 2022, "hit_label": 1},
        ]
        split = time_split(rows, holdout_year=2022)
        self.assertEqual(split.years["test"], [2022])
        self.assertEqual(split.years["validation"], [2021])
        self.assertEqual(split.years["train"], [2019, 2020])

    def test_time_split_does_not_reuse_validation_as_training(self) -> None:
        rows = [
            {"player_id": "a", "draft_year": 2021, "hit_label": 1},
            {"player_id": "b", "draft_year": 2022, "hit_label": 0},
        ]
        with self.assertRaises(SystemExit):
            time_split(rows, holdout_year=2022)

    def test_auc_helpers(self) -> None:
        y = [0, 0, 1, 1]
        p = [0.1, 0.4, 0.6, 0.9]
        self.assertGreater(roc_auc(y, p), 0.9)
        self.assertGreater(pr_auc(y, p), 0.8)

    def test_logistic_full_excludes_deterministic_grade_feature(self) -> None:
        self.assertNotIn("deterministic_grade_0_100", BASELINE_MODEL_FEATURES["logistic_full"])


if __name__ == "__main__":
    unittest.main()
