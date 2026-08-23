"""Mutation corpus for promoted-export integrity enforcement (issue #274, Finding 1).

Every declared promoted artifact family must fail closed on a tampered,
missing, or undeclared artifact. Mutations are applied to a throwaway mirror of
the promoted tree; the canonical artifacts in the repository are never written
to by these tests.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from unittest import mock

from scripts.validate_promoted_integrity import (
    DECLARED_FAMILIES,
    EXPECTED_MANIFEST_CHECKS,
    REGISTRY_SCHEMA_VERSION,
    iter_promoted_files,
    sha256_file,
    validate_promoted_integrity,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PROMOTED = REPO_ROOT / "exports/promoted"
CANONICAL_REGISTRY = REPO_ROOT / "exports/promoted_integrity_registry_v0.json"

# One representative artifact per family, so the corpus proves rejection for
# every declared family rather than only the manifest-bearing ones.
FAMILY_MUTATION_TARGETS = {
    "historical-comps": "2026_historical_comps_v0.json",
    "nfl-fantasy-outcomes": "player_year_ppr_outcomes_v1.csv",
    # Deliberately a postdraft variant: predraft was the only file CI covered
    # before this change.
    "rookie-alpha": "2026_rookie_alpha_postdraft_v0.json",
    "rookie-transition-profile": "2026_rookie_transition_profile_v0.csv",
}


class PromotedIntegrityCanonicalTests(unittest.TestCase):
    """Checks against the real repository artifacts."""

    def test_canonical_promoted_tree_passes(self) -> None:
        errors, coverage = validate_promoted_integrity(CANONICAL_PROMOTED, CANONICAL_REGISTRY)
        self.assertEqual(errors, [])
        self.assertEqual(set(coverage), set(DECLARED_FAMILIES))

    def test_registry_covers_every_promoted_artifact(self) -> None:
        registry = json.loads(CANONICAL_REGISTRY.read_text(encoding="utf-8"))
        registered = {
            f"{family['family']}/{artifact['path']}"
            for family in registry["families"]
            for artifact in family["artifacts"]
        }
        self.assertEqual(registered, set(iter_promoted_files(CANONICAL_PROMOTED)))

    def test_every_declared_family_is_registered_and_non_empty(self) -> None:
        registry = json.loads(CANONICAL_REGISTRY.read_text(encoding="utf-8"))
        by_name = {family["family"]: family for family in registry["families"]}
        self.assertEqual(set(by_name), set(DECLARED_FAMILIES))
        for name, family in by_name.items():
            with self.subTest(family=name):
                self.assertGreater(len(family["artifacts"]), 0)

    def test_manifest_contracts_are_enforced_where_declared(self) -> None:
        _, coverage = validate_promoted_integrity(CANONICAL_PROMOTED, CANONICAL_REGISTRY)
        self.assertEqual(coverage["rookie-alpha"]["manifest_checks"], 5)
        self.assertEqual(coverage["rookie-transition-profile"]["manifest_checks"], 1)

    def test_pinned_manifest_contract_is_exact_and_duplicate_free(self) -> None:
        """A count assertion alone would let duplicates stand in for real checks."""
        expected = {
            "rookie-alpha": {
                ("rookie-alpha-manifest-v0", f"{year}_rookie_alpha_predraft_v0.json", f"{year}_manifest.json")
                for year in (2022, 2023, 2024, 2025, 2026)
            },
            "rookie-transition-profile": {
                (
                    "rookie-transition-profile-v0",
                    "2026_rookie_transition_profile_v0.json",
                    "2026_manifest.json",
                )
            },
        }
        self.assertEqual(set(EXPECTED_MANIFEST_CHECKS), set(expected))
        for family, tuples in EXPECTED_MANIFEST_CHECKS.items():
            with self.subTest(family=family):
                self.assertEqual(len(set(tuples)), len(tuples), "duplicate checks in pinned contract")
                self.assertEqual(set(tuples), expected[family])

    def test_every_manifest_check_member_is_digest_registered(self) -> None:
        registry = json.loads(CANONICAL_REGISTRY.read_text(encoding="utf-8"))
        registered = {
            f"{family['family']}/{artifact['path']}"
            for family in registry["families"]
            for artifact in family["artifacts"]
        }
        for family, tuples in EXPECTED_MANIFEST_CHECKS.items():
            for _, export_rel, manifest_rel in tuples:
                with self.subTest(family=family, export=export_rel):
                    self.assertIn(f"{family}/{export_rel}", registered)
                    self.assertIn(f"{family}/{manifest_rel}", registered)


class RookieMlLaneDemotionTests(unittest.TestCase):
    """The ML lane must no longer be reachable as a promoted family (#286 WP-2)."""

    def test_rookie_ml_lane_is_not_a_declared_promoted_family(self) -> None:
        self.assertNotIn("rookie-ml-lane", DECLARED_FAMILIES)
        self.assertEqual(len(DECLARED_FAMILIES), 4)

    def test_rookie_ml_lane_has_no_promoted_manifest_contract(self) -> None:
        self.assertNotIn("rookie-ml-lane", EXPECTED_MANIFEST_CHECKS)

    def test_promoted_tree_contains_no_ml_lane_directory(self) -> None:
        self.assertFalse((CANONICAL_PROMOTED / "rookie-ml-lane").exists())

    def test_promoted_registry_declares_no_ml_lane_family(self) -> None:
        registry = json.loads(CANONICAL_REGISTRY.read_text(encoding="utf-8"))
        self.assertNotIn("rookie-ml-lane", {f["family"] for f in registry["families"]})


class PromotedIntegrityMutationTests(unittest.TestCase):
    """Deterministic mutation corpus applied to a mirror of the promoted tree."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.mirror = Path(self._tmp.name)
        # Mirror the repository layout so the delegated manifest validators
        # resolve their declared input paths exactly as they do in CI.
        (self.mirror / ".git").mkdir()
        os.symlink(REPO_ROOT / "data", self.mirror / "data")
        (self.mirror / "exports").mkdir()
        self.promoted = self.mirror / "exports/promoted"
        shutil.copytree(CANONICAL_PROMOTED, self.promoted)
        self.registry = self.mirror / "exports/promoted_integrity_registry_v0.json"
        shutil.copyfile(CANONICAL_REGISTRY, self.registry)
        self.addCleanup(self._tmp.cleanup)

    def run_validator(self) -> list[str]:
        errors, _ = validate_promoted_integrity(self.promoted, self.registry)
        return errors

    def read_registry(self) -> dict:
        return json.loads(self.registry.read_text(encoding="utf-8"))

    def write_registry(self, registry: dict) -> None:
        self.registry.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    def reregister(self, family: str, rel_path: str) -> None:
        """Re-derive the digest for a mutated file.

        Used to isolate manifest-tier failures: without this the digest tier
        would fire first and the test would not prove the manifest contract is
        actually wired up.
        """
        target = self.promoted / family / rel_path
        registry = self.read_registry()
        for entry in registry["families"]:
            if entry["family"] != family:
                continue
            for artifact in entry["artifacts"]:
                if artifact["path"] == rel_path:
                    artifact["sha256"] = sha256_file(target)
                    artifact["bytes"] = target.stat().st_size
        self.write_registry(registry)

    def patched_contract(self, family: str, tuples: tuple) -> mock._patch:
        """Temporarily replace the pinned contract for one family."""
        patched = dict(EXPECTED_MANIFEST_CHECKS)
        patched[family] = tuples
        return mock.patch(
            "scripts.validate_promoted_integrity.EXPECTED_MANIFEST_CHECKS", patched
        )

    def assert_baseline_clean(self) -> None:
        self.assertEqual(self.run_validator(), [], "mirror should validate before mutation")

    # --- Mutation class 1: modified artifact bytes / digest mismatch --------

    def test_appended_byte_is_rejected_for_every_family(self) -> None:
        self.assert_baseline_clean()
        for family, rel_path in FAMILY_MUTATION_TARGETS.items():
            with self.subTest(family=family):
                target = self.promoted / family / rel_path
                original = target.read_bytes()
                target.write_bytes(original + b" ")
                errors = self.run_validator()
                self.assertTrue(
                    any(f"sha256 mismatch for {rel_path}" in err and family in err for err in errors),
                    f"{family}: appended byte not rejected; errors={errors}",
                )
                target.write_bytes(original)

    def test_same_length_byte_flip_is_rejected_for_every_family(self) -> None:
        """Proves the digest, not just the recorded size, is doing the work."""
        self.assert_baseline_clean()
        for family, rel_path in FAMILY_MUTATION_TARGETS.items():
            with self.subTest(family=family):
                target = self.promoted / family / rel_path
                original = target.read_bytes()
                flipped = bytes([original[0] ^ 0x20]) + original[1:]
                self.assertNotEqual(flipped, original)
                self.assertEqual(len(flipped), len(original))
                target.write_bytes(flipped)
                errors = self.run_validator()
                self.assertTrue(
                    any(f"sha256 mismatch for {rel_path}" in err and family in err for err in errors),
                    f"{family}: same-length mutation not rejected; errors={errors}",
                )
                self.assertFalse(
                    any(f"size mismatch for {rel_path}" in err for err in errors),
                    f"{family}: size check should not fire on a same-length mutation",
                )
                target.write_bytes(original)

    # --- Mutation class 2: missing required companion ----------------------

    def test_deleted_artifact_is_rejected_for_every_family(self) -> None:
        self.assert_baseline_clean()
        for family, rel_path in FAMILY_MUTATION_TARGETS.items():
            with self.subTest(family=family):
                target = self.promoted / family / rel_path
                original = target.read_bytes()
                target.unlink()
                errors = self.run_validator()
                self.assertTrue(
                    any(
                        f"registered artifact is missing from disk: {rel_path}" in err
                        and family in err
                        for err in errors
                    ),
                    f"{family}: deleted artifact not rejected; errors={errors}",
                )
                target.write_bytes(original)

    def test_missing_manifest_is_rejected(self) -> None:
        """Deleting a manifest must fail even though its digest entry remains."""
        self.assert_baseline_clean()
        for family, manifest_name in (
            ("rookie-alpha", "2026_manifest.json"),
            ("rookie-transition-profile", "2026_manifest.json"),
        ):
            with self.subTest(family=family):
                manifest = self.promoted / family / manifest_name
                original = manifest.read_bytes()
                manifest.unlink()
                errors = self.run_validator()
                self.assertTrue(
                    any("Required companion file not found" in err and family in err for err in errors),
                    f"{family}: missing manifest not rejected by the manifest tier; errors={errors}",
                )
                manifest.write_bytes(original)

    def test_deregistering_a_manifest_check_member_is_rejected(self) -> None:
        """A check member must stay digest-pinned; dropping its entry fails closed."""
        self.assert_baseline_clean()
        for family, manifest_name in (
            ("rookie-alpha", "2026_manifest.json"),
            ("rookie-transition-profile", "2026_manifest.json"),
        ):
            with self.subTest(family=family):
                manifest = self.promoted / family / manifest_name
                original = manifest.read_bytes()
                manifest.unlink()
                registry = self.read_registry()
                for entry in registry["families"]:
                    if entry["family"] == family:
                        entry["artifacts"] = [
                            a for a in entry["artifacts"] if a["path"] != manifest_name
                        ]
                self.write_registry(registry)
                errors = self.run_validator()
                self.assertTrue(
                    any("is not digest-registered in this family" in err and family in err for err in errors),
                    f"{family}: deregistered manifest not rejected; errors={errors}",
                )
                manifest.write_bytes(original)
                shutil.copyfile(CANONICAL_REGISTRY, self.registry)

    # --- Mutation class 3: incompatible manifest / schema identity ---------

    def test_manifest_metadata_mismatch_is_rejected_for_rookie_alpha(self) -> None:
        self.assert_baseline_clean()
        manifest = self.promoted / "rookie-alpha/2026_manifest.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["export_metadata"]["run_id"] = "tampered-run-id"
        manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        self.reregister("rookie-alpha", "2026_manifest.json")

        errors = self.run_validator()
        self.assertTrue(
            any("export_metadata does not exactly match export JSON metadata" in err for err in errors),
            f"rookie-alpha manifest identity mismatch not rejected; errors={errors}",
        )

    def test_manifest_output_hash_mismatch_is_rejected_for_rookie_alpha(self) -> None:
        """A tampered export plus a matching registry digest must still fail."""
        self.assert_baseline_clean()
        export = self.promoted / "rookie-alpha/2026_rookie_alpha_predraft_v0.json"
        export.write_text("{}\n", encoding="utf-8")
        self.reregister("rookie-alpha", "2026_rookie_alpha_predraft_v0.json")

        errors = self.run_validator()
        self.assertTrue(
            any("Output hash mismatch" in err for err in errors),
            f"rookie-alpha manifest output hash mismatch not rejected; errors={errors}",
        )

    def test_schema_identity_mismatch_is_rejected_for_transition_profile(self) -> None:
        self.assert_baseline_clean()
        artifact = self.promoted / "rookie-transition-profile/2026_rookie_transition_profile_v0.json"
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        payload["schema_version"] = "rookie-transition-profile-v99.0.0"
        artifact.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        self.reregister("rookie-transition-profile", "2026_rookie_transition_profile_v0.json")

        errors = self.run_validator()
        self.assertTrue(
            any("schema_version must be" in err for err in errors),
            f"transition-profile schema identity mismatch not rejected; errors={errors}",
        )

    def test_every_rookie_alpha_year_contract_is_individually_enforced(self) -> None:
        """The exact regression from review: four years could go unenforced.

        Tampering with each year's manifest in turn must surface that year's
        contract failure, so no year can be silently substituted by another.
        """
        self.assert_baseline_clean()
        for year in (2022, 2023, 2024, 2025, 2026):
            with self.subTest(year=year):
                manifest = self.promoted / f"rookie-alpha/{year}_manifest.json"
                original = manifest.read_bytes()
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                payload["export_metadata"]["run_id"] = f"tampered-{year}"
                manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                self.reregister("rookie-alpha", f"{year}_manifest.json")

                errors = self.run_validator()
                self.assertTrue(
                    any(
                        "export_metadata does not exactly match export JSON metadata" in err
                        and f"{year}_rookie_alpha_predraft_v0.json" in err
                        for err in errors
                    ),
                    f"{year}: manifest contract not enforced; errors={errors}",
                )
                manifest.write_bytes(original)
                shutil.copyfile(CANONICAL_REGISTRY, self.registry)

    def test_registry_redeclaring_manifest_checks_is_rejected(self) -> None:
        """The registry must not be able to supply or weaken the manifest contract."""
        self.assert_baseline_clean()
        good = {
            "validator": "rookie-alpha-manifest-v0",
            "export_json": "2026_rookie_alpha_predraft_v0.json",
            "manifest": "2026_manifest.json",
        }
        registry = self.read_registry()
        for entry in registry["families"]:
            if entry["family"] == "rookie-alpha":
                # Five copies of one valid tuple: the exact substitution that
                # previously kept the count at five while disabling 2022-2025.
                entry["manifest_checks"] = [dict(good) for _ in range(5)]
        self.write_registry(registry)
        errors = self.run_validator()
        self.assertTrue(
            any("unexpected registry keys" in err and "manifest_checks" in err for err in errors),
            f"registry-supplied manifest_checks not rejected; errors={errors}",
        )

    def test_duplicate_checks_in_the_pinned_contract_are_rejected(self) -> None:
        self.assert_baseline_clean()
        duplicated = tuple(
            [("rookie-alpha-manifest-v0", "2026_rookie_alpha_predraft_v0.json", "2026_manifest.json")] * 5
        )
        with self.patched_contract("rookie-alpha", duplicated):
            errors = self.run_validator()
        self.assertTrue(
            any("duplicate checks" in err for err in errors),
            f"duplicate pinned checks not rejected; errors={errors}",
        )

    def test_escaping_manifest_check_path_is_rejected(self) -> None:
        self.assert_baseline_clean()
        with self.patched_contract(
            "rookie-alpha",
            (("rookie-alpha-manifest-v0", "../../../etc/passwd", "2026_manifest.json"),),
        ):
            errors = self.run_validator()
        self.assertTrue(
            any("must be a relative in-family path" in err or "escapes the family directory" in err
                for err in errors),
            f"escaping check path not rejected; errors={errors}",
        )

    def test_cross_family_manifest_check_path_is_rejected(self) -> None:
        self.assert_baseline_clean()
        with self.patched_contract(
            "rookie-transition-profile",
            (
                (
                    "rookie-transition-profile-v0",
                    "../rookie-alpha/2026_rookie_alpha_predraft_v0.json",
                    "2026_manifest.json",
                ),
            ),
        ):
            errors = self.run_validator()
        self.assertTrue(
            any("must be a relative in-family path" in err or "escapes the family directory" in err
                for err in errors),
            f"cross-family check path not rejected; errors={errors}",
        )

    def test_unregistered_manifest_check_member_is_rejected(self) -> None:
        self.assert_baseline_clean()
        with self.patched_contract(
            "rookie-alpha",
            (("rookie-alpha-manifest-v0", "not_registered_v0.json", "2026_manifest.json"),),
        ):
            errors = self.run_validator()
        self.assertTrue(
            any("is not digest-registered in this family" in err for err in errors),
            f"unregistered check member not rejected; errors={errors}",
        )

    # --- Mutation class 4: undeclared / shrunken artifact universe ---------

    def test_unregistered_artifact_is_rejected_for_every_family(self) -> None:
        self.assert_baseline_clean()
        for family in DECLARED_FAMILIES:
            with self.subTest(family=family):
                smuggled = self.promoted / family / "smuggled_artifact_v0.json"
                smuggled.write_text('{"smuggled": true}\n', encoding="utf-8")
                errors = self.run_validator()
                self.assertTrue(
                    any(
                        "not registered in the integrity registry" in err
                        and f"{family}/smuggled_artifact_v0.json" in err
                        for err in errors
                    ),
                    f"{family}: unregistered artifact not rejected; errors={errors}",
                )
                smuggled.unlink()

    def test_readding_an_ml_artifact_under_the_promoted_namespace_is_rejected(self) -> None:
        """Negative control: the demoted family must not be smuggled back in.

        Restoring the ML lane under `exports/promoted/` leaves its files
        unregistered, so the bijection rejects them without the promoted
        validator needing to know anything about the ML lane specifically.
        """
        self.assert_baseline_clean()
        restored = self.promoted / "rookie-ml-lane"
        restored.mkdir()
        smuggled = restored / "heldout_probabilities.json"
        shutil.copyfile(
            REPO_ROOT / "exports/experimental/rookie-ml-lane/heldout_probabilities.json",
            smuggled,
        )
        errors = self.run_validator()
        self.assertTrue(
            any(
                "not registered in the integrity registry" in err
                and "rookie-ml-lane/heldout_probabilities.json" in err
                for err in errors
            ),
            f"re-promoted ML artifact not rejected; errors={errors}",
        )

    def test_declaring_ml_lane_in_the_promoted_registry_is_rejected(self) -> None:
        """Negative control: the registry cannot re-declare the demoted family."""
        self.assert_baseline_clean()
        registry = self.read_registry()
        registry["families"].append({"family": "rookie-ml-lane", "artifacts": []})
        self.write_registry(registry)
        errors = self.run_validator()
        self.assertTrue(
            any("declares unknown families" in err and "rookie-ml-lane" in err for err in errors),
            f"re-declared ML lane family not rejected; errors={errors}",
        )

    def test_dropping_a_family_from_the_registry_is_rejected(self) -> None:
        self.assert_baseline_clean()
        for family in DECLARED_FAMILIES:
            with self.subTest(family=family):
                registry = self.read_registry()
                registry["families"] = [f for f in registry["families"] if f["family"] != family]
                self.write_registry(registry)
                errors = self.run_validator()
                self.assertTrue(
                    any("does not declare required families" in err and family in err for err in errors),
                    f"{family}: family removal not rejected; errors={errors}",
                )
                shutil.copyfile(CANONICAL_REGISTRY, self.registry)

    def test_emptying_a_family_is_rejected(self) -> None:
        self.assert_baseline_clean()
        registry = self.read_registry()
        for entry in registry["families"]:
            if entry["family"] == "nfl-fantasy-outcomes":
                entry["artifacts"] = []
        self.write_registry(registry)
        errors = self.run_validator()
        self.assertTrue(
            any("declares no artifacts" in err for err in errors),
            f"emptied family not rejected; errors={errors}",
        )

    # --- Mutation class 5: registry integrity itself -----------------------

    def test_registry_schema_version_mismatch_is_rejected(self) -> None:
        self.assert_baseline_clean()
        registry = self.read_registry()
        registry["schema_version"] = "promoted-integrity-registry-v99.0.0"
        self.write_registry(registry)
        errors = self.run_validator()
        self.assertTrue(
            any("schema_version mismatch" in err for err in errors),
            f"registry schema mismatch not rejected; errors={errors}",
        )

    def test_unknown_manifest_validator_is_rejected(self) -> None:
        self.assert_baseline_clean()
        with self.patched_contract(
            "rookie-alpha",
            (("not-a-real-validator", "2026_rookie_alpha_predraft_v0.json", "2026_manifest.json"),),
        ):
            errors = self.run_validator()
        self.assertTrue(
            any("unknown manifest validator" in err for err in errors),
            f"unknown validator not rejected; errors={errors}",
        )

    def test_registry_path_escaping_its_family_is_rejected(self) -> None:
        self.assert_baseline_clean()
        registry = self.read_registry()
        for entry in registry["families"]:
            if entry["family"] == "nfl-fantasy-outcomes":
                entry["artifacts"][0]["path"] = "../rookie-alpha/2026_manifest.json"
        self.write_registry(registry)
        errors = self.run_validator()
        self.assertTrue(
            any("escapes the family directory" in err for err in errors),
            f"registry path traversal not rejected; errors={errors}",
        )

    def test_missing_registry_is_rejected(self) -> None:
        self.assert_baseline_clean()
        self.registry.unlink()
        errors = self.run_validator()
        self.assertTrue(
            any("Integrity registry not found" in err for err in errors),
            f"missing registry not rejected; errors={errors}",
        )
        self.assertEqual(REGISTRY_SCHEMA_VERSION, "promoted-integrity-registry-v0.2.0")


if __name__ == "__main__":
    unittest.main()
