"""Mutation corpus for experimental-export integrity enforcement (issue #286, WP-2).

Demotion must not mean "remove them from validation and forget them". The
experimental Rookie ML lane left the promoted namespace with its fail-closed
coverage intact, and this corpus is what proves it: every mutation below must be
rejected, and the historical bytes must be exactly the bytes that existed at the
authorized base commit.

Mutations are applied to a throwaway mirror of the experimental tree; the
canonical artifacts in the repository are never written to by these tests.

`EnforcementLayerNecessityTests` at the end goes one step further. A green corpus
only proves the errors appear, not that any particular tier produced them, so
that class disables each enforcement layer in turn and asserts the corresponding
mutation stops being caught. Those tests fail if a check is load-bearing in name
only.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from unittest import mock

from scripts.validate_experimental_integrity import (
    DECLARED_FAMILIES,
    FROZEN_HISTORICAL_ARTIFACTS,
    REGISTRY_SCHEMA_VERSION,
    REQUIRED_STATUS_CLAIMS,
    STATUS_SIDECAR_NAME,
    iter_experimental_files,
    sha256_file,
    validate_experimental_integrity,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_EXPERIMENTAL = REPO_ROOT / "exports/experimental"
CANONICAL_PROMOTED = REPO_ROOT / "exports/promoted"
CANONICAL_REGISTRY = REPO_ROOT / "exports/experimental_integrity_registry_v0.json"

# The exact inventory and digests the ML lane carried at the authorized base
# commit, under the old promoted path. Written out longhand rather than derived
# from the validator's own constant, so that editing the pinned table in
# `validate_experimental_integrity.py` cannot silently edit its own test.
AUTHORIZED_BASE_SHA = "54215af61e581000b7370e941dbc90a8a1a70195"
BASE_ML_LANE_DIGESTS = {
    "dataset_diagnostics.json": ("89947ec0c97e0a00defe10bbf7c5341fd1b654b4c8668fb193280f1b5d045291", 1100),
    "evaluation_report.json": ("b9c448e95ef0ce1d097eefbfffc9bd1e00612874f945f4fad7202687a6a98585", 12873),
    "feature_coverage_report.json": ("dabb3bd6039bea9ac61c5dd5873f0559a68644b9d0ccc459348ad5b6bdc1b1a4", 3673),
    "feature_importance_report.json": ("839e416cc019e3b6f0913f647bf429eb3703e3f975f6e9bb80f1717abab3a104", 1122),
    "feature_table.json": ("99dca17ae65043312a57e7ca4f8dbf39442a2d8cd41ea0c1ac51e001a67d3a8e", 14851),
    "heldout_probabilities.csv": ("3a57453506050dd20e1c497b83705e4279757c7dbfe67f7aa4ac973b11f8b4f6", 253),
    "heldout_probabilities.json": ("9fecb43979174820e8f704983025c36004d6d0e02abc74772d323057844244f6", 366),
    "historical_labeled_dataset.csv": ("0561559e00022a3a2d53a3c1fc7573f8486e196f682301f55934fcae00bf6fa8", 4321),
    "historical_labeled_dataset.json": ("279cef5ee2fa40b99c2e283feff3c894ea650ea193833a5cedb0bc1d54499356", 18524),
}


class ExperimentalIntegrityCanonicalTests(unittest.TestCase):
    """Checks against the real repository artifacts."""

    def test_canonical_experimental_tree_passes(self) -> None:
        errors, coverage = validate_experimental_integrity(
            CANONICAL_EXPERIMENTAL, CANONICAL_REGISTRY, CANONICAL_PROMOTED
        )
        self.assertEqual(errors, [])
        self.assertEqual(set(coverage), set(DECLARED_FAMILIES))

    def test_registry_covers_every_experimental_artifact(self) -> None:
        registry = json.loads(CANONICAL_REGISTRY.read_text(encoding="utf-8"))
        registered = {
            f"{family['family']}/{artifact['path']}"
            for family in registry["families"]
            for artifact in family["artifacts"]
        }
        self.assertEqual(registered, set(iter_experimental_files(CANONICAL_EXPERIMENTAL)))

    def test_historical_bytes_match_the_authorized_base_commit(self) -> None:
        """Acceptance condition 4: byte-for-byte preservation across the move.

        Compared against digests transcribed from the base commit, not against
        the validator's own pinned table.
        """
        family_dir = CANONICAL_EXPERIMENTAL / "rookie-ml-lane"
        for name, (expected_hash, expected_bytes) in sorted(BASE_ML_LANE_DIGESTS.items()):
            with self.subTest(artifact=name):
                target = family_dir / name
                self.assertTrue(target.is_file(), f"{name} missing at the new path")
                self.assertEqual(
                    sha256_file(target),
                    expected_hash,
                    f"{name} sha256 drifted from base {AUTHORIZED_BASE_SHA}",
                )
                self.assertEqual(target.stat().st_size, expected_bytes)

    def test_pinned_frozen_inventory_matches_the_authorized_base_commit(self) -> None:
        """The validator's trust anchor must not have been quietly re-pinned."""
        self.assertEqual(FROZEN_HISTORICAL_ARTIFACTS["rookie-ml-lane"], BASE_ML_LANE_DIGESTS)

    def test_no_ml_artifact_remains_under_the_promoted_namespace(self) -> None:
        """Acceptance condition 1."""
        self.assertFalse((CANONICAL_PROMOTED / "rookie-ml-lane").exists())

    def test_status_sidecar_declares_non_promotable_semantics(self) -> None:
        """Acceptance condition 9, on the artifacts that exist today."""
        sidecar = json.loads(
            (CANONICAL_EXPERIMENTAL / "rookie-ml-lane" / STATUS_SIDECAR_NAME).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(sidecar["artifact_class"], "experimental_fixture_evaluation")
        self.assertIs(sidecar["is_calibrated_probability"], False)
        self.assertIs(sidecar["eligible_for_promotion"], False)
        self.assertIn("not calibrated", sidecar["uncalibrated_probability_warning"].lower())

    def test_status_sidecar_binds_old_path_to_new_path(self) -> None:
        """Acceptance condition 5: the provenance binding is committed."""
        sidecar = json.loads(
            (CANONICAL_EXPERIMENTAL / "rookie-ml-lane" / STATUS_SIDECAR_NAME).read_text(
                encoding="utf-8"
            )
        )
        migration = sidecar["migration"]
        self.assertEqual(migration["previous_path"], "exports/promoted/rookie-ml-lane")
        self.assertEqual(migration["current_path"], "exports/experimental/rookie-ml-lane")
        self.assertEqual(migration["authorized_base_sha"], AUTHORIZED_BASE_SHA)
        recorded = {
            item["path"]: (item["sha256"], item["bytes"])
            for item in sidecar["frozen_historical_artifacts"]
        }
        self.assertEqual(recorded, BASE_ML_LANE_DIGESTS)

    def test_migration_record_is_committed_and_records_both_paths(self) -> None:
        record = REPO_ROOT / "docs/migrations/2026-08-23-rookie-ml-lane-demotion.md"
        self.assertTrue(record.is_file(), "migration/provenance record is missing")
        text = record.read_text(encoding="utf-8")
        self.assertIn("exports/promoted/rookie-ml-lane", text)
        self.assertIn("exports/experimental/rookie-ml-lane", text)
        self.assertIn(AUTHORIZED_BASE_SHA, text)
        for name, (digest, _) in BASE_ML_LANE_DIGESTS.items():
            with self.subTest(artifact=name):
                self.assertIn(digest, text, f"{name} digest absent from migration record")


class ExperimentalMirrorTestCase(unittest.TestCase):
    """Shared mirror fixture and helpers. Declares no tests of its own."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.mirror = Path(self._tmp.name)
        (self.mirror / "exports").mkdir()
        self.experimental = self.mirror / "exports/experimental"
        shutil.copytree(CANONICAL_EXPERIMENTAL, self.experimental)
        self.promoted = self.mirror / "exports/promoted"
        self.promoted.mkdir()
        self.registry = self.mirror / "exports/experimental_integrity_registry_v0.json"
        shutil.copyfile(CANONICAL_REGISTRY, self.registry)
        self.addCleanup(self._tmp.cleanup)

    def run_validator(self) -> list[str]:
        errors, _ = validate_experimental_integrity(
            self.experimental, self.registry, self.promoted
        )
        return errors

    def read_registry(self) -> dict:
        return json.loads(self.registry.read_text(encoding="utf-8"))

    def write_registry(self, registry: dict) -> None:
        self.registry.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    def reregister(self, family: str, rel_path: str) -> None:
        """Re-derive the digest for a mutated file.

        Used to isolate the frozen and status tiers: without this the digest
        tier fires first and the test would not prove the pinned contract is
        actually doing the work.
        """
        target = self.experimental / family / rel_path
        registry = self.read_registry()
        for entry in registry["families"]:
            if entry["family"] != family:
                continue
            for artifact in entry["artifacts"]:
                if artifact["path"] == rel_path:
                    artifact["sha256"] = sha256_file(target)
                    artifact["bytes"] = target.stat().st_size
        self.write_registry(registry)

    def write_sidecar(self, payload: dict, *, reregister: bool = True) -> None:
        path = self.experimental / "rookie-ml-lane" / STATUS_SIDECAR_NAME
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        if reregister:
            self.reregister("rookie-ml-lane", STATUS_SIDECAR_NAME)

    def read_sidecar(self) -> dict:
        return json.loads(
            (self.experimental / "rookie-ml-lane" / STATUS_SIDECAR_NAME).read_text(
                encoding="utf-8"
            )
        )

    def assert_baseline_clean(self) -> None:
        self.assertEqual(self.run_validator(), [], "mirror should validate before mutation")


class ExperimentalIntegrityMutationTests(ExperimentalMirrorTestCase):
    """Deterministic mutation corpus applied to a mirror of the experimental tree."""

    # --- Negative control: byte-edited experimental artifact ----------------

    def test_appended_byte_is_rejected(self) -> None:
        self.assert_baseline_clean()
        for rel_path in sorted(BASE_ML_LANE_DIGESTS):
            with self.subTest(artifact=rel_path):
                target = self.experimental / "rookie-ml-lane" / rel_path
                original = target.read_bytes()
                target.write_bytes(original + b" ")
                errors = self.run_validator()
                self.assertTrue(
                    any(f"sha256 mismatch for {rel_path}" in err for err in errors),
                    f"{rel_path}: appended byte not rejected; errors={errors}",
                )
                target.write_bytes(original)

    def test_same_length_byte_flip_is_rejected(self) -> None:
        """Proves the digest, not just the recorded size, is doing the work."""
        self.assert_baseline_clean()
        for rel_path in sorted(BASE_ML_LANE_DIGESTS):
            with self.subTest(artifact=rel_path):
                target = self.experimental / "rookie-ml-lane" / rel_path
                original = target.read_bytes()
                flipped = bytes([original[0] ^ 0x20]) + original[1:]
                self.assertNotEqual(flipped, original)
                self.assertEqual(len(flipped), len(original))
                target.write_bytes(flipped)
                errors = self.run_validator()
                self.assertTrue(
                    any(f"sha256 mismatch for {rel_path}" in err for err in errors),
                    f"{rel_path}: same-length mutation not rejected; errors={errors}",
                )
                target.write_bytes(original)

    def test_consistently_tampered_artifact_is_still_rejected(self) -> None:
        """The core anti-#290 property.

        Editing a historical artifact *and* updating the registry to agree
        defeats the digest tier entirely. The pinned frozen inventory is what
        keeps this failing, because it does not live in the editable registry.
        """
        self.assert_baseline_clean()
        target = self.experimental / "rookie-ml-lane" / "heldout_probabilities.json"
        target.write_text('[{"hit_probability": 0.99}]\n', encoding="utf-8")
        self.reregister("rookie-ml-lane", "heldout_probabilities.json")

        errors = self.run_validator()
        self.assertTrue(
            any(
                "frozen historical artifact was modified" in err
                and "heldout_probabilities.json" in err
                for err in errors
            ),
            f"consistently tampered artifact not rejected; errors={errors}",
        )

    # --- Negative control: deleted expected artifact ------------------------

    def test_deleted_artifact_is_rejected(self) -> None:
        self.assert_baseline_clean()
        for rel_path in sorted(BASE_ML_LANE_DIGESTS):
            with self.subTest(artifact=rel_path):
                target = self.experimental / "rookie-ml-lane" / rel_path
                original = target.read_bytes()
                target.unlink()
                errors = self.run_validator()
                self.assertTrue(
                    any(
                        f"registered artifact is missing from disk: {rel_path}" in err
                        for err in errors
                    ),
                    f"{rel_path}: deleted artifact not rejected; errors={errors}",
                )
                target.write_bytes(original)

    def test_deleted_and_deregistered_artifact_is_still_rejected(self) -> None:
        """Deleting a file and its registry entry together must still fail."""
        self.assert_baseline_clean()
        target = self.experimental / "rookie-ml-lane" / "feature_table.json"
        target.unlink()
        registry = self.read_registry()
        for entry in registry["families"]:
            if entry["family"] == "rookie-ml-lane":
                entry["artifacts"] = [
                    a for a in entry["artifacts"] if a["path"] != "feature_table.json"
                ]
        self.write_registry(registry)

        errors = self.run_validator()
        self.assertTrue(
            any(
                "frozen historical artifact is missing from disk" in err
                and "feature_table.json" in err
                for err in errors
            ),
            f"deleted+deregistered artifact not rejected; errors={errors}",
        )

    def test_deleted_status_sidecar_is_rejected(self) -> None:
        self.assert_baseline_clean()
        sidecar = self.experimental / "rookie-ml-lane" / STATUS_SIDECAR_NAME
        sidecar.unlink()
        errors = self.run_validator()
        self.assertTrue(
            any("registered artifact is missing from disk" in err for err in errors),
            f"deleted sidecar not rejected; errors={errors}",
        )

    # --- Negative control: undeclared artifact ------------------------------

    def test_unregistered_artifact_is_rejected(self) -> None:
        self.assert_baseline_clean()
        smuggled = self.experimental / "rookie-ml-lane" / "smuggled_artifact_v0.json"
        smuggled.write_text('{"smuggled": true}\n', encoding="utf-8")
        errors = self.run_validator()
        self.assertTrue(
            any(
                "not registered in the integrity registry" in err
                and "rookie-ml-lane/smuggled_artifact_v0.json" in err
                for err in errors
            ),
            f"unregistered artifact not rejected; errors={errors}",
        )

    # --- Negative control: registry / disk divergence -----------------------

    def test_registry_declaring_a_nonexistent_artifact_is_rejected(self) -> None:
        self.assert_baseline_clean()
        registry = self.read_registry()
        for entry in registry["families"]:
            if entry["family"] == "rookie-ml-lane":
                entry["artifacts"].append(
                    {"path": "ghost_v0.json", "sha256": "0" * 64, "bytes": 1}
                )
        self.write_registry(registry)
        errors = self.run_validator()
        self.assertTrue(
            any("registered artifact is missing from disk: ghost_v0.json" in err for err in errors),
            f"registry/disk divergence not rejected; errors={errors}",
        )

    def test_swapping_a_frozen_entry_for_a_decoy_is_rejected(self) -> None:
        """The #290 attack, ported: keep the count, drop a real check.

        Deregisters one frozen artifact and registers a decoy in its place, so
        the family's artifact count is unchanged and every registry entry still
        matches its file. Only the pinned inventory notices.
        """
        self.assert_baseline_clean()
        before = len(
            next(
                e for e in self.read_registry()["families"] if e["family"] == "rookie-ml-lane"
            )["artifacts"]
        )

        decoy = self.experimental / "rookie-ml-lane" / "decoy_v0.json"
        decoy.write_text('{"decoy": true}\n', encoding="utf-8")
        registry = self.read_registry()
        for entry in registry["families"]:
            if entry["family"] == "rookie-ml-lane":
                entry["artifacts"] = [
                    a for a in entry["artifacts"] if a["path"] != "feature_table.json"
                ]
                entry["artifacts"].append(
                    {
                        "path": "decoy_v0.json",
                        "sha256": sha256_file(decoy),
                        "bytes": decoy.stat().st_size,
                    }
                )
        self.write_registry(registry)

        after = len(
            next(
                e for e in self.read_registry()["families"] if e["family"] == "rookie-ml-lane"
            )["artifacts"]
        )
        self.assertEqual(before, after, "the decoy must preserve the artifact count")

        errors = self.run_validator()
        self.assertTrue(
            any(
                "frozen historical artifact is not digest-registered" in err
                and "feature_table.json" in err
                for err in errors
            ),
            f"count-preserving check removal not rejected; errors={errors}",
        )

    def test_registry_redeclaring_the_pinned_contract_is_rejected(self) -> None:
        """The registry must not be able to supply or weaken the pinned tiers."""
        self.assert_baseline_clean()
        registry = self.read_registry()
        for entry in registry["families"]:
            if entry["family"] == "rookie-ml-lane":
                entry["frozen_historical_artifacts"] = []
                entry["status_claims"] = {"eligible_for_promotion": True}
        self.write_registry(registry)
        errors = self.run_validator()
        self.assertTrue(
            any("unexpected registry keys" in err for err in errors),
            f"registry-supplied contract not rejected; errors={errors}",
        )

    def test_registry_path_escaping_its_family_is_rejected(self) -> None:
        self.assert_baseline_clean()
        registry = self.read_registry()
        for entry in registry["families"]:
            if entry["family"] == "rookie-ml-lane":
                entry["artifacts"][0]["path"] = "../../promoted/rookie-alpha/2026_manifest.json"
        self.write_registry(registry)
        errors = self.run_validator()
        self.assertTrue(
            any("escapes the family directory" in err for err in errors),
            f"registry path traversal not rejected; errors={errors}",
        )

    def test_registry_schema_version_mismatch_is_rejected(self) -> None:
        self.assert_baseline_clean()
        registry = self.read_registry()
        registry["schema_version"] = "experimental-integrity-registry-v99.0.0"
        self.write_registry(registry)
        errors = self.run_validator()
        self.assertTrue(
            any("schema_version mismatch" in err for err in errors),
            f"registry schema mismatch not rejected; errors={errors}",
        )
        self.assertEqual(REGISTRY_SCHEMA_VERSION, "experimental-integrity-registry-v0.1.0")

    def test_dropping_the_family_from_the_registry_is_rejected(self) -> None:
        self.assert_baseline_clean()
        registry = self.read_registry()
        registry["families"] = []
        self.write_registry(registry)
        errors = self.run_validator()
        self.assertTrue(
            any("does not declare required families" in err for err in errors),
            f"family removal not rejected; errors={errors}",
        )

    def test_emptying_the_family_is_rejected(self) -> None:
        self.assert_baseline_clean()
        registry = self.read_registry()
        for entry in registry["families"]:
            if entry["family"] == "rookie-ml-lane":
                entry["artifacts"] = []
        self.write_registry(registry)
        errors = self.run_validator()
        self.assertTrue(
            any("declares no artifacts" in err for err in errors),
            f"emptied family not rejected; errors={errors}",
        )

    def test_missing_registry_is_rejected(self) -> None:
        self.assert_baseline_clean()
        self.registry.unlink()
        errors = self.run_validator()
        self.assertTrue(
            any("Integrity registry not found" in err for err in errors),
            f"missing registry not rejected; errors={errors}",
        )

    # --- Negative control: status claims promotion / calibration ------------

    def test_status_claiming_calibrated_probability_is_rejected(self) -> None:
        self.assert_baseline_clean()
        payload = self.read_sidecar()
        payload["is_calibrated_probability"] = True
        self.write_sidecar(payload)
        errors = self.run_validator()
        self.assertTrue(
            any("is_calibrated_probability must be False" in err for err in errors),
            f"calibration claim not rejected; errors={errors}",
        )

    def test_status_claiming_promotion_eligibility_is_rejected(self) -> None:
        self.assert_baseline_clean()
        payload = self.read_sidecar()
        payload["eligible_for_promotion"] = True
        self.write_sidecar(payload)
        errors = self.run_validator()
        self.assertTrue(
            any("eligible_for_promotion must be False" in err for err in errors),
            f"promotion eligibility claim not rejected; errors={errors}",
        )

    def test_status_claiming_a_promoted_artifact_class_is_rejected(self) -> None:
        self.assert_baseline_clean()
        payload = self.read_sidecar()
        payload["artifact_class"] = "promoted_model_output"
        self.write_sidecar(payload)
        errors = self.run_validator()
        self.assertTrue(
            any("artifact_class must be" in err for err in errors),
            f"promoted artifact_class not rejected; errors={errors}",
        )

    def test_status_smuggling_a_claim_through_a_non_boolean_is_rejected(self) -> None:
        """`0` equals `False` in Python; a JSON boolean is required regardless."""
        self.assert_baseline_clean()
        for value in (0, "false", None):
            with self.subTest(value=value):
                payload = self.read_sidecar()
                payload["eligible_for_promotion"] = value
                self.write_sidecar(payload)
                errors = self.run_validator()
                self.assertTrue(
                    any("eligible_for_promotion must be" in err for err in errors),
                    f"non-boolean claim {value!r} not rejected; errors={errors}",
                )

    def test_status_dropping_a_required_claim_is_rejected(self) -> None:
        self.assert_baseline_clean()
        for key in REQUIRED_STATUS_CLAIMS:
            with self.subTest(claim=key):
                payload = self.read_sidecar()
                del payload[key]
                self.write_sidecar(payload)
                errors = self.run_validator()
                self.assertTrue(
                    any(f"missing required claim: {key}" in err for err in errors),
                    f"dropped claim {key} not rejected; errors={errors}",
                )

    def test_status_dropping_the_uncalibrated_warning_is_rejected(self) -> None:
        self.assert_baseline_clean()
        for warning in ("", "   ", "see docs"):
            with self.subTest(warning=warning):
                payload = self.read_sidecar()
                payload["uncalibrated_probability_warning"] = warning
                self.write_sidecar(payload)
                errors = self.run_validator()
                self.assertTrue(
                    any("uncalibrated_probability_warning" in err for err in errors),
                    f"weak warning {warning!r} not rejected; errors={errors}",
                )

    def test_status_omitting_frozen_artifacts_is_rejected(self) -> None:
        self.assert_baseline_clean()
        payload = self.read_sidecar()
        payload["frozen_historical_artifacts"] = [
            item
            for item in payload["frozen_historical_artifacts"]
            if item["path"] != "feature_table.json"
        ]
        self.write_sidecar(payload)
        errors = self.run_validator()
        self.assertTrue(
            any("omits frozen artifacts" in err and "feature_table.json" in err for err in errors),
            f"omitted frozen artifact not rejected; errors={errors}",
        )

    def test_status_misreporting_a_frozen_digest_is_rejected(self) -> None:
        self.assert_baseline_clean()
        payload = self.read_sidecar()
        for item in payload["frozen_historical_artifacts"]:
            if item["path"] == "feature_table.json":
                item["sha256"] = "0" * 64
        self.write_sidecar(payload)
        errors = self.run_validator()
        self.assertTrue(
            any("disagrees with the pinned frozen record" in err for err in errors),
            f"misreported digest not rejected; errors={errors}",
        )

    def test_status_rewriting_the_migration_binding_is_rejected(self) -> None:
        self.assert_baseline_clean()
        payload = self.read_sidecar()
        payload["migration"]["previous_path"] = "exports/experimental/rookie-ml-lane"
        self.write_sidecar(payload)
        errors = self.run_validator()
        self.assertTrue(
            any("migration.previous_path must be" in err for err in errors),
            f"rewritten migration binding not rejected; errors={errors}",
        )

    def test_unregistered_status_sidecar_is_rejected(self) -> None:
        """A sidecar present but outside the registry is not integrity-covered."""
        self.assert_baseline_clean()
        payload = self.read_sidecar()
        self.write_sidecar(payload, reregister=False)
        registry = self.read_registry()
        for entry in registry["families"]:
            if entry["family"] == "rookie-ml-lane":
                entry["artifacts"] = [
                    a for a in entry["artifacts"] if a["path"] != STATUS_SIDECAR_NAME
                ]
        self.write_registry(registry)
        errors = self.run_validator()
        self.assertTrue(
            any("not registered in the integrity registry" in err for err in errors),
            f"unregistered sidecar not rejected; errors={errors}",
        )

    # --- Negative control: artifact back under the promoted namespace -------

    def test_ml_artifact_under_the_promoted_namespace_is_rejected(self) -> None:
        self.assert_baseline_clean()
        restored = self.promoted / "rookie-ml-lane"
        restored.mkdir()
        (restored / "heldout_probabilities.json").write_text("[]\n", encoding="utf-8")
        errors = self.run_validator()
        self.assertTrue(
            any(
                "still has artifacts under the promoted namespace" in err for err in errors
            ),
            f"re-promoted artifact not rejected; errors={errors}",
        )

    def test_empty_ml_directory_under_the_promoted_namespace_is_rejected(self) -> None:
        """Even an empty promoted directory re-asserts the demoted classification."""
        self.assert_baseline_clean()
        (self.promoted / "rookie-ml-lane").mkdir()
        errors = self.run_validator()
        self.assertTrue(
            any("still exists under the promoted namespace" in err for err in errors),
            f"empty promoted directory not rejected; errors={errors}",
        )


class EnforcementLayerNecessityTests(ExperimentalMirrorTestCase):
    """Proves each enforcement tier is load-bearing, not decorative.

    A passing mutation corpus shows the errors appear; it does not show *which*
    check produced them, so a tier could be dead code while its tests stay green
    on another tier's error. Each test below picks a mutation that only one tier
    can catch, disables that tier, and asserts validation goes green — then
    restores it and asserts the mutation is caught again.
    """

    def assert_layer_is_necessary(
        self, layer: str, mutate, *, replacement
    ) -> None:
        """Mutate, prove it is caught, disable `layer`, prove it stops being caught."""
        self.assert_baseline_clean()
        mutate()

        caught = self.run_validator()
        self.assertNotEqual(
            caught, [], f"mutation for {layer} was not caught at all; the corpus is vacuous"
        )

        target = f"scripts.validate_experimental_integrity.{layer}"
        with mock.patch(target, replacement):
            without_layer = self.run_validator()

        self.assertEqual(
            without_layer,
            [],
            f"{layer} is not the tier catching this mutation — something else fires "
            f"({without_layer}); the necessity proof is invalid",
        )

    def test_frozen_tier_is_necessary(self) -> None:
        """Only the pinned inventory catches a consistently tampered artifact."""

        def mutate() -> None:
            # Tamper the bytes and bring the registry into agreement, defeating
            # the digest tier. The sidecar is left declaring the original
            # digests, which still match the pinned table, so the status tier
            # passes too: only the frozen tier compares disk against the pin.
            target = self.experimental / "rookie-ml-lane" / "heldout_probabilities.json"
            target.write_text('[{"hit_probability": 0.99}]\n', encoding="utf-8")
            self.reregister("rookie-ml-lane", "heldout_probabilities.json")

        self.assert_layer_is_necessary(
            "_validate_frozen_history", mutate, replacement=lambda *a, **k: ([], 0)
        )

    def test_status_tier_is_necessary(self) -> None:
        """Only the status tier catches a sidecar claiming promotion eligibility."""

        def mutate() -> None:
            payload = self.read_sidecar()
            payload["eligible_for_promotion"] = True
            payload["is_calibrated_probability"] = True
            self.write_sidecar(payload)

        self.assert_layer_is_necessary(
            "_validate_status_sidecar", mutate, replacement=lambda *a, **k: []
        )

    def test_demotion_tier_is_necessary(self) -> None:
        """Only the demotion tier catches an ML artifact back under promoted."""

        def mutate() -> None:
            restored = self.promoted / "rookie-ml-lane"
            restored.mkdir()
            (restored / "heldout_probabilities.json").write_text("[]\n", encoding="utf-8")

        self.assert_layer_is_necessary(
            "_validate_demotion", mutate, replacement=lambda *a, **k: []
        )

    def test_digest_tier_is_necessary(self) -> None:
        """Only the digest tier catches an edit to a non-frozen registered file.

        The sidecar is registered but not frozen, and a whitespace-only edit
        leaves its JSON semantics intact, so the status tier still passes.
        """

        def mutate() -> None:
            target = self.experimental / "rookie-ml-lane" / STATUS_SIDECAR_NAME
            target.write_bytes(target.read_bytes() + b"\n")

        self.assert_layer_is_necessary(
            "_validate_family_artifacts",
            mutate,
            # Return the real registered-path set so downstream tiers still see
            # their members registered; only the digest comparison is removed.
            replacement=lambda family, entries, root: (
                [],
                {f"{family}/{e['path']}" for e in entries},
            ),
        )


if __name__ == "__main__":
    unittest.main()
