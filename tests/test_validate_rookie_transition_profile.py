import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_rookie_transition_profile import (
    CURRENT_SCHEMA_VERSION,
    confidence_to_band,
    validate_artifact_shape,
    validate_export_manifest,
    validate_field,
    validate_official_postdraft_outcome_value,
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


def _valid_postdraft_outcome_value(**overrides):
    base = {
        "status": "drafted",
        "nfl_team": "LV",
        "draft_round": 1,
        "overall_pick": 1,
        "is_udfa": False,
        "source_status": "external_verified",
        "upstream_provenance_status": "source_verified",
    }
    base.update(overrides)
    return base


class ValidateOfficialPostdraftOutcomeValueTests(unittest.TestCase):
    """Regression coverage for issue #267's drafted/udfa_signed semantics."""

    def test_valid_drafted_value_passes(self) -> None:
        self.assertEqual(
            validate_official_postdraft_outcome_value(_valid_postdraft_outcome_value(), prefix="p"), []
        )

    def test_valid_udfa_signed_value_passes(self) -> None:
        value = _valid_postdraft_outcome_value(
            status="udfa_signed", is_udfa=True, draft_round=None, overall_pick=None,
            upstream_provenance_status=None,
        )
        self.assertEqual(validate_official_postdraft_outcome_value(value, prefix="p"), [])

    def test_invalid_status_rejected(self) -> None:
        errors = validate_official_postdraft_outcome_value(
            _valid_postdraft_outcome_value(status="mock_drafted"), prefix="p"
        )
        self.assertTrue(any("status" in e for e in errors))

    def test_is_udfa_status_mismatch_rejected(self) -> None:
        errors = validate_official_postdraft_outcome_value(
            _valid_postdraft_outcome_value(is_udfa=True), prefix="p"
        )
        self.assertTrue(any("is_udfa" in e for e in errors))

    def test_drafted_without_round_or_pick_rejected(self) -> None:
        errors = validate_official_postdraft_outcome_value(
            _valid_postdraft_outcome_value(draft_round=None, overall_pick=None), prefix="p"
        )
        self.assertTrue(any("draft_round" in e for e in errors))
        self.assertTrue(any("overall_pick" in e for e in errors))

    def test_udfa_signed_with_nonnull_round_rejected(self) -> None:
        errors = validate_official_postdraft_outcome_value(
            _valid_postdraft_outcome_value(status="udfa_signed", is_udfa=True, overall_pick=None), prefix="p"
        )
        self.assertTrue(any("draft_round" in e for e in errors))

    def test_missing_nfl_team_rejected(self) -> None:
        errors = validate_official_postdraft_outcome_value(
            _valid_postdraft_outcome_value(nfl_team=""), prefix="p"
        )
        self.assertTrue(any("nfl_team" in e for e in errors))

    def test_null_upstream_provenance_status_allowed(self) -> None:
        errors = validate_official_postdraft_outcome_value(
            _valid_postdraft_outcome_value(upstream_provenance_status=None), prefix="p"
        )
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
    """Guards the actual committed 2026 candidate artifact. This lives under
    exports/candidate/, not exports/promoted/ — per issue #263, implementation
    and validation happen here, but promotion itself requires a separate,
    future promotion-review issue."""

    def test_2026_artifact_passes_shape_validation(self) -> None:
        path = Path("exports/candidate/rookie-transition-profile/2026_rookie_transition_profile_v0.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(validate_artifact_shape(payload), [])

    def test_2026_artifact_and_manifest_pass_full_validation(self) -> None:
        errors = validate_export_manifest(
            export_path=Path("exports/candidate/rookie-transition-profile/2026_rookie_transition_profile_v0.json"),
            manifest_path=Path("exports/candidate/rookie-transition-profile/2026_manifest.json"),
        )
        self.assertEqual(errors, [])

    def test_2026_artifact_has_48_of_48_official_postdraft_outcome_coverage(self) -> None:
        """Regression guard for the #265/#266 finding: every player must have
        a known post-draft outcome (drafted or udfa_signed), not silently
        fall back to being 'unresolved'."""
        path = Path("exports/candidate/rookie-transition-profile/2026_rookie_transition_profile_v0.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload["rows"]
        self.assertEqual(len(rows), 48)
        statuses = [r["official_postdraft_outcome"]["value"]["status"] for r in rows]
        self.assertEqual(statuses.count("drafted"), 47)
        self.assertEqual(statuses.count("udfa_signed"), 1)
        self.assertEqual(len([s for s in statuses if s is None]), 0)

    def test_2026_artifact_draft_capital_never_leaks_official_outcome_text(self) -> None:
        """Regression guard for the exact #266 defect: draft_capital must
        always remain the pre-draft proxy and never reference a real,
        realized draft outcome in its provenance text."""
        path = Path("exports/candidate/rookie-transition-profile/2026_rookie_transition_profile_v0.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload["rows"]:
            draft_capital = row["draft_capital"]
            self.assertEqual(draft_capital["provenance"]["source_type"], "market_derived_proxy")
            source_name = (draft_capital["provenance"]["source_name"] or "").lower()
            self.assertNotIn("actual pick", source_name, msg=row["player_id"])
            notes = (draft_capital["provenance"]["notes"] or "").lower()
            self.assertIn("not equivalent to realized", notes, msg=row["player_id"])


class ValidateExportManifestConsistencyTests(unittest.TestCase):
    """Regression coverage for a gap flagged in PR #264 review: export_metadata
    matching the export JSON is not sufficient — the manifest's own top-level
    fields must also agree with its export_metadata block, or a manifest could
    advertise a different season/hash list internally while still passing."""

    def _write_valid_pair(self, temp_dir: Path) -> tuple[Path, Path]:
        export_payload = {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "artifact_type": "rookie_transition_profile",
            "season": 2026,
            "generated_at": "2026-07-10T00:00:00+00:00",
            "run_id": "rookie-transition-profile-2026-test",
            "disclaimer": "This artifact is an evidence consolidation layer.",
            "source_files_used": ["a.json"],
            "coverage_summary": {"players_total": 0},
            "rows": [],
        }
        export_path = temp_dir / "profile.json"
        csv_path = temp_dir / "profile.csv"
        manifest_path = temp_dir / "manifest.json"
        export_path.write_text(json.dumps(export_payload), encoding="utf-8")
        csv_path.write_text("player_id\n", encoding="utf-8")

        export_metadata = {
            "season": export_payload["season"],
            "schema_version": export_payload["schema_version"],
            "generated_at": export_payload["generated_at"],
            "run_id": export_payload["run_id"],
            "coverage_summary": export_payload["coverage_summary"],
            "source_files_used": export_payload["source_files_used"],
        }
        manifest_payload = {
            "season": 2026,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "generated_at": export_payload["generated_at"],
            "run_id": export_payload["run_id"],
            "input_files": [{"path": "a.json", "sha256": "x"}],
            "coverage_summary": export_payload["coverage_summary"],
            "output_files": [],
            "export_metadata": export_metadata,
        }
        manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
        return export_path, manifest_path

    def test_manifest_top_level_season_mismatch_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            export_path, manifest_path = self._write_valid_pair(temp_dir)

            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            # export_metadata still matches the export JSON exactly, but the
            # manifest's own top-level season now silently disagrees with it.
            manifest_payload["season"] = 2027
            manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")

            errors = validate_export_manifest(
                export_path=export_path,
                manifest_path=manifest_path,
                check_input_hashes=False,
                check_output_hashes=False,
            )
            self.assertTrue(
                any("does not match top-level manifest metadata fields" in e for e in errors),
                msg=errors,
            )

    def test_consistent_manifest_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            export_path, manifest_path = self._write_valid_pair(temp_dir)
            errors = validate_export_manifest(
                export_path=export_path,
                manifest_path=manifest_path,
                check_input_hashes=False,
                check_output_hashes=False,
            )
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
