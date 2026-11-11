import copy
import unittest

from scripts.compute_production_scores import pivot_stats
from scripts.discover_shadow_pool import (
    build_candidates,
    evaluate_breakout,
    fetch_rosters,
    make_player_id,
    merge_players,
)

RUN_DATE = "2026-11-11"


def _rows(team, player, **stats):
    return [{"player": player, "team": team, "statType": k, "stat": str(v)} for k, v in stats.items()]


def _fixture():
    rosters = {
        "Ohio State": [
            {"id": 1, "firstName": "Jeremiah", "lastName": "Smith", "position": "WR", "year": 3},
            {"id": 2, "firstName": "Young", "lastName": "Star", "position": "WR", "year": 2},
            {"id": 3, "firstName": "Quiet", "lastName": "Soph", "position": "WR", "year": 2},
            {"id": 4, "firstName": "Big", "lastName": "Lineman", "position": "OL", "year": 4},
            {"id": 5, "firstName": "True", "lastName": "Freshman", "position": "RB", "year": 1},
            {"id": 6, "firstName": "No", "lastName": "Year", "position": "TE", "year": None},
            {"id": 7, "firstName": "Unseen", "lastName": "Soph", "position": "RB", "year": 2},
        ],
        "Miami (FL)": [
            {"id": 8, "firstName": "Senior", "lastName": "Back", "position": "RB", "year": 4},
        ],
    }
    receiving = pivot_stats(
        _rows("Ohio State", "Jeremiah Smith", REC=60, YDS=900)
        + _rows("Ohio State", "Young Star", REC=40, YDS=700)   # 700/2000 = 0.35 share
        + _rows("Ohio State", "Quiet Soph", REC=10, YDS=100)   # 0.05 share
        + _rows("Ohio State", "Other Guy", REC=20, YDS=300)
    )
    rushing = pivot_stats(_rows("Miami (FL)", "Senior Back", CAR=150, YDS=800))
    passing = pivot_stats([])
    return rosters, passing, rushing, receiving


# Smith (1) and Senior Back (8) were on FBS rosters two seasons back; the
# sophomores (2, 3, 7) first appeared one season back; 5 and 6 on neither.
TENURE = {"ids_two_back": {"1", "4", "8"}, "ids_one_back": {"1", "2", "3", "4", "7", "8"}}


class EvaluateBreakoutTests(unittest.TestCase):
    def test_share_criterion_met(self):
        self.assertTrue(evaluate_breakout("WR", {"receiving_yard_share": 0.30}))

    def test_volume_fallback(self):
        self.assertTrue(evaluate_breakout("RB", {"rush_share": 0.1, "rush_attempts": 90}))

    def test_observed_but_below(self):
        self.assertFalse(evaluate_breakout("WR", {"receiving_yard_share": 0.05}))

    def test_nothing_observable_is_null(self):
        self.assertIsNone(evaluate_breakout("WR", {"target_share": None, "targets": None}))

    def test_qb_volume_only(self):
        self.assertTrue(evaluate_breakout("QB", {"pass_attempts": 200}))
        self.assertFalse(evaluate_breakout("QB", {"pass_attempts": 100}))


class BuildCandidatesTests(unittest.TestCase):
    def setUp(self):
        self.candidates, self.unknown = build_candidates(*_fixture(), class_year=2027, run_date=RUN_DATE, **TENURE)
        self.by_name = {c["player_name"]: c for c in self.candidates}

    def test_eligibility_filter(self):
        self.assertEqual(set(self.by_name), {"Jeremiah Smith", "Young Star", "Senior Back"})

    def test_unknown_tenure_counted_not_admitted(self):
        self.assertEqual(self.unknown, 2)  # true freshman RB + TE with no prior roster

    def test_sophomore_breakout_flags(self):
        star = self.by_name["Young Star"]
        self.assertTrue(star["breakout_flagged"])
        self.assertTrue(star["young_breakout"])
        self.assertEqual(star["observed_production"]["receiving_yard_share"], 0.35)

    def test_null_honesty(self):
        smith = self.by_name["Jeremiah Smith"]["observed_production"]
        self.assertIsNone(smith["target_share"])
        self.assertIsNone(smith["targets"])
        self.assertIsNone(smith["rush_attempts"])  # no rushing row → null, not zero
        self.assertIsNone(smith["pass_attempts"])

    def test_entry_shape(self):
        back = self.by_name["Senior Back"]
        self.assertEqual(back["player_id"], "rb-senior-back-miami-fl")
        self.assertEqual(back["discovery_season"], 2026)
        self.assertEqual(back["status"], "watchlist")
        self.assertEqual(back["status_history"][0]["date"], RUN_DATE)
        self.assertEqual(back["observed_production"]["rush_share"], 1.0)
        self.assertFalse(back["young_breakout"])


class TenureTests(unittest.TestCase):
    """CFBD roster `year` is unusable (live check 2026-11-11), so tenure decides."""

    def test_roster_year_field_is_ignored(self):
        rosters = {"Ohio State": [
            {"id": 10, "firstName": "Vet", "lastName": "Receiver", "position": "WR", "year": 1},
        ]}
        candidates, unknown = build_candidates(rosters, {}, {}, {}, class_year=2027, run_date=RUN_DATE,
                                               ids_two_back={"10"}, ids_one_back={"10"})
        self.assertEqual([(c["academic_year"], c["academic_year_source"]) for c in candidates],
                         [(3, "cfbd_fbs_roster_tenure")])
        self.assertEqual(unknown, 0)

    def test_transfer_tenure_follows_cfbd_id(self):
        # tenure sets are league-wide, so the 2024 school doesn't matter
        rosters = {"Texas A&M": [{"id": 20, "firstName": "Moved", "lastName": "On", "position": "RB", "year": 1}]}
        candidates, _ = build_candidates(rosters, {}, {}, {}, class_year=2027, run_date=RUN_DATE,
                                         ids_two_back={"20"}, ids_one_back=set())
        self.assertEqual(len(candidates), 1)


class MergePlayersTests(unittest.TestCase):
    def setUp(self):
        self.first, _ = build_candidates(*_fixture(), class_year=2027, run_date="2026-09-01", **TENURE)

    def test_rerun_preserves_operator_state_and_refreshes_observations(self):
        existing = copy.deepcopy(self.first)
        smith = next(p for p in existing if p["player_name"] == "Jeremiah Smith")
        smith["operator_notes"] = "WR1 for me"
        smith["status"] = "combine_invited"
        smith["status_history"].append({"status": "combine_invited", "date": "2027-02-01", "reason": "manual"})

        second, _ = build_candidates(*_fixture(), class_year=2027, run_date=RUN_DATE, **TENURE)
        merged, added, refreshed = merge_players(existing, second)

        smith = next(p for p in merged if p["player_name"] == "Jeremiah Smith")
        self.assertEqual(smith["operator_notes"], "WR1 for me")
        self.assertEqual(smith["status"], "combine_invited")
        self.assertEqual(len(smith["status_history"]), 2)
        self.assertEqual(smith["observed_production"]["through_date"], RUN_DATE)
        self.assertEqual((added, refreshed), (0, 3))

    def test_missing_players_are_never_removed(self):
        manual = {"player_id": "wr-manual-add-somewhere", "cfbd_player_id": None,
                  "player_name": "Manual Add", "manually_added": True}
        merged, added, _ = merge_players([manual] + copy.deepcopy(self.first), [])
        self.assertIn(manual, merged)
        self.assertEqual(len(merged), 4)
        self.assertEqual(added, 0)

    def test_transfer_matched_by_cfbd_id(self):
        existing = copy.deepcopy(self.first)
        moved = copy.deepcopy(next(c for c in self.first if c["player_name"] == "Senior Back"))
        moved["school"] = "Texas A&M"
        moved["player_id"] = make_player_id("RB", "Senior Back", "Texas A&M")
        merged, added, refreshed = merge_players(existing, [moved])
        back = [p for p in merged if p["player_name"] == "Senior Back"]
        self.assertEqual(len(back), 1)
        self.assertEqual(back[0]["school"], "Texas A&M")
        self.assertEqual(back[0]["player_id"], "rb-senior-back-miami-fl")  # identity preserved
        self.assertEqual(added, 0)

    def test_output_is_sorted_and_deterministic(self):
        a, _, _ = merge_players([], copy.deepcopy(self.first))
        b, _, _ = merge_players([], list(reversed(copy.deepcopy(self.first))))
        self.assertEqual(a, b)


class FetchRostersTests(unittest.TestCase):
    def test_empty_rosters_recorded(self):
        import scripts.discover_shadow_pool as mod
        orig = mod.REQUEST_DELAY_S
        mod.REQUEST_DELAY_S = 0
        try:
            rosters, failed = fetch_rosters(["A", "B"], 2026, fetch=lambda t, y: [{"id": 1}] if t == "A" else [])
        finally:
            mod.REQUEST_DELAY_S = orig
        self.assertEqual(list(rosters), ["A"])
        self.assertEqual(failed, ["B"])


if __name__ == "__main__":
    unittest.main()
