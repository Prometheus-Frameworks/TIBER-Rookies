import unittest
from datetime import datetime, timezone

from scripts.build_devy_roster_pulse import build_pulse
from scripts.validate_devy_roster_pulse import validate_devy_roster_pulse

WATCHLIST = {
    "prospects": [
        {"player_id": "wr-tracked", "player_name": "Tracked Receiver", "school": "State U", "position": "WR", "projected_draft_class": 2027},
        {"player_id": "rb-gone", "player_name": "Gone Back", "school": "State U", "position": "RB", "projected_draft_class": 2027},
        {"player_id": "qb-moved", "player_name": "Moved Passer", "school": "Old U", "position": "QB", "projected_draft_class": 2027},
        {"player_id": "wr-later", "player_name": "Later Receiver", "school": "State U", "position": "WR", "projected_draft_class": 2029},
    ]
}

ROSTER = [
    {"id": 1, "firstName": "Tracked", "lastName": "Receiver", "team": "State U", "position": "WR", "year": 3},
    {"id": 2, "firstName": "Breakout", "lastName": "Receiver", "team": "Small U", "position": "WR", "year": 3},
    {"id": 3, "firstName": "Young", "lastName": "Receiver", "team": "Small U", "position": "WR", "year": 2},
    {"id": 4, "firstName": "Walkon", "lastName": "Receiver", "team": "Small U", "position": "WR", "year": 4},
    {"id": 5, "firstName": "Moved", "lastName": "Passer", "team": "New U", "position": "QB", "year": 4},
]

RECRUITS = [
    {"athleteId": "1", "year": 2024, "position": "WR", "stars": 5},
    {"athleteId": "2", "year": 2023, "position": "WR", "stars": 3},
    {"athleteId": "3", "year": 2025, "position": "WR", "stars": 5},
    {"athleteId": "5", "year": 2022, "position": "PRO", "stars": 4},
]


def stat(pid, player, team, category, stat_type, value):
    return {"playerId": pid, "player": player, "team": team, "category": category, "statType": stat_type, "stat": str(value)}


STATS = [
    stat(1, "Tracked Receiver", "State U", "receiving", "YDS", 400),
    stat(2, "Breakout Receiver", "Small U", "receiving", "YDS", 900),
    stat(3, "Young Receiver", "Small U", "receiving", "YDS", 1000),
    stat(4, "Walkon Receiver", "Small U", "receiving", "YDS", 500),
    stat(5, "Moved Passer", "New U", "passing", "YDS", 2000),
    stat(99, "No Record", "Nowhere", "receiving", "YDS", 1200),
]


def build(top_n=15):
    return build_pulse(
        roster=ROSTER, recruits=RECRUITS, stats=STATS, watchlist=WATCHLIST,
        season=2026, draft_class=2027, top_n=top_n,
        source_urls=["https://api.collegefootballdata.com/roster?year=2026"],
        generated_at=datetime(2026, 11, 2, tzinfo=timezone.utc),
    )


class BuildDevyRosterPulseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = build()
        self.by_name = {c["player_name"]: c for c in self.payload["candidates"]}

    def test_output_passes_validator(self) -> None:
        self.assertEqual(validate_devy_roster_pulse(self.payload), [])
        self.assertEqual(self.payload["pulse_month"], "2026-11")

    def test_ineligible_and_unlinked_players_excluded(self) -> None:
        self.assertNotIn("Young Receiver", self.by_name)  # 2025 recruit -> not 2027 eligible
        self.assertNotIn("No Record", self.by_name)
        self.assertIn("1 stat-feed players had no roster or recruiting record", " ".join(self.payload["warnings"]))

    def test_new_production_leader_surfaces_unmatched(self) -> None:
        breakout = self.by_name["Breakout Receiver"]
        self.assertFalse(breakout["existing_seed_watchlist_match"])
        self.assertEqual(breakout["class_year_source"], "recruiting_profile")
        self.assertEqual(breakout["production_evidence"]["position_rank_among_eligible"], 1)
        self.assertEqual(breakout["auto_seed_watchlist_mutation"], "none")

    def test_roster_only_eligibility_is_low_confidence(self) -> None:
        walkon = self.by_name["Walkon Receiver"]
        self.assertEqual(walkon["class_year_source"], "roster")
        self.assertEqual(walkon["confidence_band"], "LOW")
        self.assertIn("needs_class_year_verification", walkon["candidate_tags"])

    def test_watchlist_rows_get_roster_status(self) -> None:
        self.assertEqual(self.by_name["Tracked Receiver"]["roster_status"], "still_present")
        self.assertTrue(self.by_name["Tracked Receiver"]["existing_seed_watchlist_match"])
        self.assertEqual(self.by_name["Gone Back"]["roster_status"], "missing_from_roster")
        self.assertEqual(self.by_name["Moved Passer"]["roster_status"], "program_changed")
        self.assertNotIn("Later Receiver", self.by_name)
        tracked = [c for c in self.payload["candidates"] if c["player_name"] == "Tracked Receiver"]
        self.assertEqual(len(tracked), 1)

    def test_top_n_limits_new_candidates(self) -> None:
        names = {c["player_name"] for c in build(top_n=1)["candidates"]}
        self.assertIn("Breakout Receiver", names)
        self.assertNotIn("Walkon Receiver", names)


if __name__ == "__main__":
    unittest.main()
