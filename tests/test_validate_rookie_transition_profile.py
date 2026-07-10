import json
import unittest
from pathlib import Path

from scripts.validate_rookie_transition_profile import (
    CURRENT_SCHEMA_VERSION,
    confidence_to_band,
    validate_artifact_shape,
    validate_export_manifest,
    validate_field,
    validate_provenance_object,
    validate_row,
)


def _valid_provenance(**overrides):
    base = {
        "source_type": "measured_identity_fact",
        "source_name": "test source",
        "source_url": None,
        "confidence": 0.9,
        "confidence_band": "HIGH",
        "last_verified_at": "2026-07-01",
        "notes": None,
    }
    base.update(overrides)
    return base


def _valid_row(**overrides):
    row = {
        "player_id": "wr-test-player",
        "player_name": "Test Player",
        "position": "WR",
        "school": "Test State",
        "class_year": 2026,
        "age_at_entry": {"value": 21, "provenance": _valid_provenance()},
    }
    row.update(overrides)
    return row


class ConfidenceToBandTests(unittest.TestCase):
    def test_low_below_0_65(self) -> None:
        self.assertEqual(confidence_to_band(0.5), "LOW")

    def test_medium_between_0_65_and_0_84(self) -> None:
        self.assertEqual(confidence_to_band(0.65), "MEDIUM")
        self.assertEqual(confidence_to_band(0.8), "MEDIUM")

    def test_high_at_or_above_0_85(self) -> None:
        self.assertEqual(confidence_to_band(0.85), "HIGH")
        self.assertEqual(confidence_to_band(1.0), "HIGH")


class ValidateProvenanceObjectTests(unittest.TestCase):
    def test_valid_provenance_passes(self) -> None:
        self.assertEqual(validate_provenance_object(_valid_provenance(), prefix="p"), [])

    def test_invalid_source_type_rejected(self) -> None:
        errors = validate_provenance_object(_valid_provenance(source_type="made_up"), prefix="p")
        self.assertTrue(any("source_type" in e for e in errors))

    def test_confidence_out_of_range_rejected(self) -> None:
        errors = validate_provenance_object(_valid_provenance(confidence=1.5), prefix="p")
        self.assertTrue(any("confidence" in e for e in errors))

    def test_confidence_band_mismatch_rejected(self) -> None:
        errors = validate_provenance_object(_valid_provenance(confidence=0.9, confidence_band="LOW"), prefix="p")
        self.assertTrue(any("confidence_band" in e for e in errors))

    def test_unavailable_requires_only_notes(self) -> None:
        errors = validate_provenance_object(
            {
                "source_type": "unavailable",
                "source_name": None,
                "source_url": None,
                "confidence": None,
                "confidence_band": None,
                "last_verified_at": None,
                "notes": "no data on file",
            },
            prefix="p",
        )
        self.assertEqual(errors, [])

    def test_unavailable_without_notes_rejected(self) -> None:
        errors = validate_provenance_object(
            {"source_type": "unavailable", "notes": ""},
            prefix="p",
        )
        self.assertTrue(any("notes" in e for e in errors))


class ValidateFieldTests(unittest.TestCase):
    def test_value_and_provenance_required(self) -> None:
        errors = validate_field({"value": 21}, prefix="p")
        self.assertTrue(errors)

    def test_available_field_with_null_value_rejected(self) -> None:
        errors = validate_field({"value": None, "provenance": _valid_provenance()}, prefix="p")
        self.assertTrue(any("must not be null" in e for e in errors))

    def test_unavailable_field_with_non_null_value_rejected(self) -> None:
        errors = validate_field(
            {
                "value": 21,
                "provenance": {
                    "source_type": "unavailable",
                    "source_name": None,
                    "source_url": None,
                    "confidence": None,
                    "confidence_band": None,
                    "last_verified_at": None,
                    "notes": "no data",
                },
            },
            prefix="p",
        )
        self.assertTrue(any("must be null" in e for e in errors))

    def test_valid_available_field_passes(self) -> None:
        errors = validate_field({"value": 21, "provenance": _valid_provenance()}, prefix="p")
        self.assertEqual(errors, [])


class ValidateRowTests(unittest.TestCase):
    def test_missing_identity_fields_rejected(self) -> None:
        errors = validate_row({}, index=0, season=2026)
        self.assertTrue(any("player_id" in e for e in errors))

    def test_governed_field_without_provenance_rejected(self) -> None:
        row = _valid_row(draft_capital={"value": {"draft_capital_proxy_0_100": 90.0}})
        errors = validate_row(row, index=0, season=2026)
        self.assertTrue(any("draft_capital" in e for e in errors))

    def test_last_verified_at_after_season_rejected(self) -> None:
        row = _valid_row(age_at_entry={"value": 21, "provenance": _valid_provenance(last_verified_at="2027-01-01")})
        errors = validate_row(row, index=0, season=2026)
        self.assertTrue(any("later than season" in e for e in errors))

    def test_valid_row_passes(self) -> None:
        self.assertEqual(validate_row(_valid_row(), index=0, season=2026), [])


class ValidateArtifactShapeTests(unittest.TestCase):
    def _valid_artifact(self, **overrides) -> dict:
        artifact = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "artifact_type": "rookie_transition_profile",
            "season": 2026,
            "generated_at": "2026-07-10T00:00:00+00:00",
            "run_id": "rookie-transition-profile-2026-test",
            "disclaimer": "This artifact is an evidence consolidation layer.",
            "source_files_used": ["a"],
            "coverage_summary": {"players_total": 1},
            "rows": [_valid_row()],
        }
        artifact.update(overrides)
        return artifact

    def test_valid_artifact_passes(self) -> None:
        self.assertEqual(validate_artifact_shape(self._valid_artifact()), [])

    def test_wrong_schema_version_rejected(self) -> None:
        errors = validate_artifact_shape(self._valid_artifact(schema_version="wrong"))
        self.assertTrue(any("schema_version" in e for e in errors))

    def test_duplicate_player_id_rejected(self) -> None:
        row = _valid_row()
        errors = validate_artifact_shape(self._valid_artifact(rows=[row, dict(row)]))
        self.assertTrue(any("duplicates" in e for e in errors))

    def test_empty_disclaimer_rejected(self) -> None:
        errors = validate_artifact_shape(self._valid_artifact(disclaimer=""))
        self.assertTrue(any("disclaimer" in e for e in errors))


class RealCommittedArtifactTests(unittest.TestCase):
    """Guards the actual promoted 2026 artifact, mirroring how other promoted
    families in this repo are checked against the real committed files."""

    def test_2026_artifact_passes_shape_validation(self) -> None:
        path = Path("exports/promoted/rookie-transition-profile/2026_rookie_transition_profile_v0.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(validate_artifact_shape(payload), [])

    def test_2026_artifact_and_manifest_pass_full_validation(self) -> None:
        errors = validate_export_manifest(
            export_path=Path("exports/promoted/rookie-transition-profile/2026_rookie_transition_profile_v0.json"),
            manifest_path=Path("exports/promoted/rookie-transition-profile/2026_manifest.json"),
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
