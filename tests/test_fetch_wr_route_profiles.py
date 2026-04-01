import unittest

from scripts.fetch_wr_route_profiles import (
    parse_depth_tag,
    parse_screen_flag,
    summarize_player,
    is_targeted_player,
)


class FetchWrRouteProfilesTests(unittest.TestCase):
    def test_parse_screen_flag(self) -> None:
        self.assertTrue(parse_screen_flag("Pass complete for a WR screen to X"))
        self.assertFalse(parse_screen_flag("Pass complete to X for 12 yards"))

    def test_parse_depth_tag(self) -> None:
        self.assertEqual(parse_depth_tag("deep middle to X for 22 yards"), "deep")
        self.assertEqual(parse_depth_tag("short left to X for 8 yards"), "short")
        self.assertIsNone(parse_depth_tag("pass complete to X for 8 yards"))

    def test_target_attribution_with_normalized_name(self) -> None:
        self.assertTrue(is_targeted_player("Pass complete to J.J. McCarthy for 8 yards", "JJ McCarthy"))
        self.assertFalse(is_targeted_player("Pass complete to Other Player for 8 yards", "JJ McCarthy"))

    def test_metric_computation_fixture(self) -> None:
        plays = [
            {"play_type": "Pass Completion", "play_text": "Short left pass complete to Jane Doe for 6 yards", "yards_gained": 6},
            {"play_type": "Pass Incompletion", "play_text": "Deep middle intended for Jane Doe", "yards_gained": 0},
            {"play_type": "Pass Completion", "play_text": "WR screen pass complete to Jane Doe for 10 yards", "yards_gained": 10},
            {"play_type": "Pass Completion", "play_text": "Pass complete to Jane Doe for 4 yards", "yards_gained": 4},
            {"play_type": "Pass Touchdown", "play_text": "Deep right pass to Jane Doe for 20 yards touchdown", "yards_gained": 20},
            {"play_type": "Pass Completion", "play_text": "Short middle pass complete to Teammate for 9 yards", "yards_gained": 9},
            {"play_type": "Pass Incompletion", "play_text": "Pass incomplete to Teammate", "yards_gained": 0},
            {"play_type": "Passing Touchdown", "play_text": "Screen pass to Teammate for 15 yards touchdown", "yards_gained": 15},
            {"play_type": "Rush", "play_text": "Rush up middle for 4 yards", "yards_gained": 4},
            {"play_type": "Pass Completion", "play_text": "Deep left pass complete to Teammate for 25 yards", "yards_gained": 25},
        ]

        player = {
            "player_id": "wr-jane-doe-2024",
            "player_name": "Jane Doe",
            "school": "Colorado",
            "source_season": 2024,
        }

        summary = summarize_player(player, plays, "regular")

        self.assertEqual(summary["targets"], 5)
        self.assertEqual(summary["receptions"], 4)
        self.assertEqual(summary["screen_targets"], 1)
        self.assertAlmostEqual(summary["screen_target_rate"], 0.2)
        self.assertAlmostEqual(summary["yards_per_target"], 8.0)
        self.assertAlmostEqual(summary["deep_target_rate"], 2/3)
        self.assertAlmostEqual(summary["depth_tag_coverage_rate"], 0.6)


if __name__ == "__main__":
    unittest.main()
