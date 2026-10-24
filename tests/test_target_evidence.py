"""Target-evidence qualification tests for WR/TE route profiles (#303)."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.compute_age_adjusted_production import season_volume
from scripts.compute_yoy_trends import compute_wr_te_trend, validate_wr_te_rows
from scripts.fetch_wr_route_profiles import build_profile
from scripts.target_evidence import qualify_profile, target_status

PROFILE_DIR = Path("data/processed/wr_route_profiles")
PLAYER = {"player_id": "wr-test-player", "player_name": "Test Player", "school": "Test State"}


def load(name: str) -> dict:
    return json.loads((PROFILE_DIR / name).read_text(encoding="utf-8"))


def legacy_estimated(targets: int, receptions: int, ypt: float) -> dict:
    return {
        "targets": targets,
        "receptions": receptions,
        "yards_per_target": ypt,
        "screen_targets": 0,
        "screen_target_rate": None,
        "source_name": "Grok/Sports-Reference (season=2024, team=X); targets estimated (REC / 0.70)",
        "source_url": None,
        "methodology_notes": "Targets estimated as receptions / 0.70.",
    }


class LegacyQualificationTests(unittest.TestCase):
    def test_hurst_targets_are_estimated_not_measured(self) -> None:
        profile = load("wr-ted-hurst_2025.json")
        q = qualify_profile(profile)
        self.assertEqual(q["qualification_origin"], "legacy_inferred")
        self.assertEqual(q["targets"]["status"], "estimated")
        self.assertEqual(q["targets"]["method"], "receptions_div_assumed_catch_rate")
        self.assertEqual(q["targets"]["assumed_catch_rate"], 0.70)
        self.assertEqual(q["yards_per_target"]["denominator_status"], "estimated")
        self.assertFalse(q["yards_per_target"]["observed_denominator"])
        self.assertEqual(q["scheme_fields"]["status"], "unsupported")
        self.assertIn("screen_targets", q["scheme_fields"]["fields"])
        self.assertIn("REC / 0.70", q["lineage"]["source_name"])
        # Raw legacy values are retained untouched.
        self.assertEqual((profile["targets"], profile["yards_per_target"], profile["screen_targets"]), (101, 9.9, 0))

    def test_play_by_play_row_is_parsed_partial_with_unsupported_scheme(self) -> None:
        q = qualify_profile(load("wr-carnell-tate_2024.json"))
        self.assertEqual(q["targets"]["status"], "parsed_partial")
        self.assertTrue(q["yards_per_target"]["observed_denominator"])
        self.assertEqual(q["scheme_fields"]["status"], "unsupported")

    def test_synthetic_row_is_estimated_including_receptions(self) -> None:
        q = qualify_profile(load("wr-antonio-williams_2024.json"))
        self.assertEqual(q["targets"]["status"], "estimated")
        self.assertEqual(q["receptions"]["status"], "estimated")
        self.assertEqual(q["targets"]["assumed_catch_rate"], 0.70)
        # Stored screen_target_rate 0.0 is not an observation.
        self.assertEqual(q["scheme_fields"]["status"], "unsupported")

    def test_invalidated_null_row_is_unavailable(self) -> None:
        self.assertEqual(target_status(load("te-kenyon-sadiq_2025.json")), "unavailable")

    def test_ambiguous_legacy_row_stays_unknown(self) -> None:
        profile = {"targets": 40, "receptions": 30, "source_name": "Some notes", "methodology_notes": ""}
        self.assertEqual(target_status(profile), "unknown")

    def test_parsed_scheme_observation_not_marked_unsupported(self) -> None:
        profile = {
            "targets": 50,
            "receptions": 35,
            "screen_targets": 4,
            "screen_target_rate": 0.08,
            "source_name": "CFBD play-by-play (year=2023, team=X)",
            "methodology_notes": "",
        }
        q = qualify_profile(profile)
        self.assertEqual(q["targets"]["status"], "parsed_partial")
        self.assertNotEqual(q["scheme_fields"]["status"], "unsupported")

    def test_every_committed_profile_gets_a_status(self) -> None:
        for path in sorted(PROFILE_DIR.glob("*.json")):
            with self.subTest(path=path.name):
                self.assertNotEqual(target_status(json.loads(path.read_text())), "unknown")


class ProducerEvidenceTests(unittest.TestCase):
    def test_reported_tgt(self) -> None:
        profile = build_profile(PLAYER, 2025, {"REC": 60.0, "YDS": 900.0, "TGT": 90.0})
        self.assertEqual(profile["targets"], 90)
        self.assertEqual(profile["yards_per_target"], 10.0)
        ev = profile["target_evidence"]
        self.assertEqual(ev["qualification_origin"], "producer")
        self.assertEqual(ev["targets"]["status"], "source_reported")
        self.assertTrue(ev["yards_per_target"]["observed_denominator"])
        self.assertEqual(ev["scheme_fields"]["status"], "unsupported")

    def test_reported_zero_is_observed_zero(self) -> None:
        profile = build_profile(PLAYER, 2025, {"REC": 0.0, "YDS": 0.0, "TGT": 0.0})
        self.assertEqual(profile["targets"], 0)
        self.assertEqual(profile["target_evidence"]["targets"]["status"], "source_reported")

    def test_estimated_fallback_keeps_numbers(self) -> None:
        profile = build_profile(PLAYER, 2025, {"REC": 71.0, "YDS": 1000.0})
        self.assertEqual(profile["targets"], 101)  # round(71 / 0.70), unchanged policy
        self.assertEqual(profile["yards_per_target"], round(1000.0 / 101, 1))
        ev = profile["target_evidence"]
        self.assertEqual(ev["targets"]["status"], "estimated")
        self.assertEqual(ev["targets"]["assumed_catch_rate"], 0.70)
        self.assertEqual(ev["receptions"]["status"], "source_reported")
        self.assertFalse(ev["yards_per_target"]["observed_denominator"])

    def test_player_not_found_is_unavailable_not_zero(self) -> None:
        profile = build_profile(PLAYER, 2025, None)
        self.assertEqual(profile["targets"], 0)  # legacy placeholder retained
        ev = profile["target_evidence"]
        self.assertEqual(ev["targets"]["status"], "unavailable")
        self.assertEqual(ev["receptions"]["status"], "unavailable")

    def test_qualification_survives_serialization(self) -> None:
        profile = build_profile(PLAYER, 2025, {"REC": 50.0, "YDS": 600.0})
        reloaded = json.loads(json.dumps(profile))
        self.assertEqual(qualify_profile(reloaded), profile["target_evidence"])


class DownstreamCompatibilityTests(unittest.TestCase):
    def test_yoy_mixed_source_comparison_is_qualified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            p24 = legacy_estimated(70, 49, 9.1)
            p25 = build_profile(PLAYER, 2025, {"REC": 60.0, "YDS": 900.0, "TGT": 90.0})
            (d / "wr-test-player_2024.json").write_text(json.dumps(p24))
            (d / "wr-test-player_2025.json").write_text(json.dumps(p25))
            row = compute_wr_te_trend("wr-test-player", d)
        self.assertEqual(row["target_status_2024"], "estimated")
        self.assertEqual(row["target_status_2025"], "source_reported")
        self.assertEqual(row["target_basis"], "mixed")
        self.assertFalse(row["efficiency_observed_denominators"])
        # Numeric calculation unchanged.
        self.assertEqual((row["volume_2024"], row["volume_2025"]), (70, 90))
        self.assertEqual(row["volume_change_pct"], round((90 - 70) / 70, 4))
        self.assertEqual(row["efficiency_change_pct"], round((10.0 - 9.1) / 9.1, 4))
        validate_wr_te_rows([row])

    def test_yoy_validation_rejects_lost_status(self) -> None:
        row = {"player_id": "x", "position_group": "WR_TE", "target_status_2024": "estimated"}
        with self.assertRaises(ValueError):
            validate_wr_te_rows([row])
        validate_wr_te_rows([{"player_id": "rb", "position_group": "RB"}])

    def test_age_adjusted_volume_reads_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "wr-a_2025.json").write_text(json.dumps(build_profile(PLAYER, 2025, {"REC": 71.0, "YDS": 1000.0})))
            (d / "wr-b_2025.json").write_text(json.dumps(build_profile(PLAYER, 2025, None)))
            self.assertEqual(season_volume("wr-a", 2025, "targets", d), 101.0)
            # Retained legacy behavior (deferred to migration): unavailable reads as 0.
            self.assertEqual(season_volume("wr-b", 2025, "targets", d), 0.0)
            self.assertEqual(season_volume("wr-missing", 2025, "targets", d), 0.0)


if __name__ == "__main__":
    unittest.main()
