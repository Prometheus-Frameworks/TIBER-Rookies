#!/usr/bin/env python3
"""Fail-closed integrity validation for every experimental export artifact family.

Demotion is not deregulation. When the Rookie ML lane left `exports/promoted/`
(issue #286, WP-2) it kept full byte-level integrity coverage; it simply stopped
claiming to be a promoted model. This validator is the enforcement half of that
claim, and it is deliberately *stricter* than the promoted validator in one
respect: it also enforces what the artifacts are allowed to say about themselves.

There are two distinct things to validate, with different lifecycles:

* the **migration archive** at `exports/experimental/rookie-ml-lane/` - nine
  artifacts whose bytes are frozen at the authorized base commit, plus a status
  sidecar that binds them to their old promoted path. Immutable. Validated by
  `validate_experimental_integrity()`.
* a **generated run** - whatever the producer writes today, into its own
  destination outside `exports/`. Mutable, uncommitted, and never allowed to
  land on top of the archive. Validated by `validate_generated_run()`.

Collapsing those two into one directory is what made the documented producer
command destructive: running it overwrote frozen artifacts, added unregistered
outputs, and replaced the migration sidecar with a run-shaped one. They are kept
apart here, and the producer refuses to write into the archive at all.

Archive enforcement has four tiers, with deliberately separate sources of truth:

* ``frozen``   - FROZEN_HISTORICAL_ARTIFACTS below, pinned in this module. These
                 are the exact bytes the ML lane carried at the authorized base
                 commit, and they are immutable: the historical record is not
                 improvable. Because this tier lives in code, it holds even if
                 the registry and the disk are tampered with *consistently*.
* ``digest``   - driven by the integrity registry, which is digest-only: path,
                 sha256, and size. Enforced as a registry <-> disk bijection, so
                 a modified, deleted, or undeclared artifact all fail.
* ``status``   - PINNED_STATUS_CLAIMS, PINNED_MIGRATION_CLAIMS and
                 GOVERNED_UNCALIBRATED_WARNING below. The family must carry a
                 status sidecar, and every governance-relevant field in it is
                 pinned to an exact value here. A sidecar is not permitted to
                 rename its own family, re-describe its lane, claim it replaces
                 deterministic Rookie Alpha, restate the authorized base commit,
                 withdraw the byte-preservation claim, or substitute its own
                 wording for the governed warning - even if the registry digest
                 is updated to agree with it.
* ``demotion`` - the promoted namespace must not contain the demoted family.

The `frozen` and `status` tiers are the point. `validate_promoted_integrity.py`
learned in PR #290 that a contract driven by editable registry data can be
neutered while its count assertion stays green. A registry is a digest record
and changes whenever an artifact is legitimately regenerated; *which* artifacts
must exist, what they must hash to, and what the family is permitted to say
about itself are contract facts that must not be editable alongside it.
Consistently updating a sidecar and its registry digest together therefore does
not buy anything: the pinned values are compared against code.

Every value in FROZEN_HISTORICAL_ARTIFACTS is mechanically derived from bytes
already committed at the authorized base. This module fabricates no schema
identity, run id, calibration claim, or provenance for artifacts that do not
carry one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REGISTRY_SCHEMA_VERSION = "experimental-integrity-registry-v0.1.0"

DEFAULT_EXPERIMENTAL_ROOT = REPO_ROOT / "exports/experimental"
DEFAULT_PROMOTED_ROOT = REPO_ROOT / "exports/promoted"
DEFAULT_REGISTRY = REPO_ROOT / "exports/experimental_integrity_registry_v0.json"

# The declared experimental artifact universe. Shrinking this set is a contract
# change, not a validator change: an unexpected or absent family fails closed.
DECLARED_FAMILIES = ("rookie-ml-lane",)

# Families that must no longer appear under `exports/promoted/`. This is the
# demotion itself, expressed as an enforced invariant rather than a claim in a
# migration note.
DEMOTED_FROM_PROMOTED = ("rookie-ml-lane",)

# The committed, immutable migration archives. The producer must refuse to write
# here; see `scripts/compute_rookie_ml_lane.py`.
FROZEN_ARCHIVE_DIRS = ("exports/experimental/rookie-ml-lane",)

STATUS_SIDECAR_NAME = "experimental_status_v0.json"
STATUS_SCHEMA_VERSION = "experimental-status-v0.1.0"

# A status record describes either the frozen migration archive or a freshly
# generated run. The two shapes are not interchangeable, and a run may not
# borrow the archive's provenance.
ARCHIVE_STATUS_KIND = "migration_archive"
RUN_STATUS_KIND = "generated_run"

# The exact governed warning. Pinned verbatim rather than by length: a long
# string is not evidence of an honest one, and "these outputs are calibrated
# probabilities" clears any length threshold.
GOVERNED_UNCALIBRATED_WARNING = (
    "The probability-shaped fields in this family (hit_probability, "
    "miss_probability, model_confidence, and the heldout_probabilities.* "
    "exports) are experimental fixture-fed evaluation outputs. They are NOT "
    "calibrated probabilities, NOT forecasts, and NOT a promoted model signal. "
    "They were produced by an interpretable baseline harness over sample "
    "fixtures for lane-comparison diagnostics only. Do not read them as the "
    "likelihood that any player will hit, do not surface them to users as "
    "probabilities, and do not consume them in any promoted, Forecast, or "
    "Fantasy contract."
)

# Identity and semantics every experimental status record must publish, archive
# or run alike. Exact-value checks: a sidecar cannot self-declare its way toward
# promotion, nor quietly redefine what lane it belongs to.
PINNED_STATUS_CLAIMS: dict[str, Any] = {
    "artifact_class": "experimental_fixture_evaluation",
    "is_calibrated_probability": False,
    "eligible_for_promotion": False,
    "lane": "parallel_ml_evaluation_only",
    "replaces_deterministic_rookie_alpha": False,
}

# Per-family identity, so a sidecar cannot rename the family it speaks for.
PINNED_FAMILY_IDENTITY: dict[str, str] = {"rookie-ml-lane": "rookie-ml-lane"}

# The migration provenance a frozen archive must reproduce exactly. Restating
# the authorized base commit or withdrawing `byte_preserving` are governance
# claims, not editorial ones.
PINNED_MIGRATION_CLAIMS: dict[str, dict[str, Any]] = {
    "rookie-ml-lane": {
        "authorized_base_sha": "54215af61e581000b7370e941dbc90a8a1a70195",
        "work_packet": "WP-2",
        "byte_preserving": True,
        "previous_path": "exports/promoted/rookie-ml-lane",
        "current_path": "exports/experimental/rookie-ml-lane",
    },
}

# The exact artifact universe a clean producer run emits, pinned here rather than
# derived from whatever happens to be in the output directory. The run sidecar is
# written by the producer and inventories its own output, which makes it a
# self-declaring record: without this anchor, a stale or injected file sitting in
# a reusable run directory is silently adopted as "generated" and validates. The
# frozen tier exists for the same reason on the archive side.
EXPECTED_RUN_ARTIFACTS: frozenset[str] = frozenset(
    {
        "dataset_diagnostics.json",
        "evaluation_report.json",
        "feature_coverage_report.json",
        "feature_importance_report.json",
        "feature_table.json",
        "heldout_probabilities.csv",
        "heldout_probabilities.json",
        "historical_class_coverage_report.json",
        "historical_feature_consistency_report.json",
        "historical_label_provenance_report.json",
        "historical_labeled_dataset.csv",
        "historical_labeled_dataset.json",
        "historical_outcomes_canonical.json",
        "historical_position_slices_report.json",
    }
)

# The immutable historical inventory, as it stood at the authorized base commit
# 54215af61e581000b7370e941dbc90a8a1a70195 under the old promoted path. These
# bytes moved namespace; they did not change. Any drift is a failure, including
# drift the registry has been updated to agree with.
FROZEN_HISTORICAL_ARTIFACTS: dict[str, dict[str, tuple[str, int]]] = {
    "rookie-ml-lane": {
        "dataset_diagnostics.json": ("89947ec0c97e0a00defe10bbf7c5341fd1b654b4c8668fb193280f1b5d045291", 1100),
        "evaluation_report.json": ("b9c448e95ef0ce1d097eefbfffc9bd1e00612874f945f4fad7202687a6a98585", 12873),
        "feature_coverage_report.json": ("dabb3bd6039bea9ac61c5dd5873f0559a68644b9d0ccc459348ad5b6bdc1b1a4", 3673),
        "feature_importance_report.json": ("839e416cc019e3b6f0913f647bf429eb3703e3f975f6e9bb80f1717abab3a104", 1122),
        "feature_table.json": ("99dca17ae65043312a57e7ca4f8dbf39442a2d8cd41ea0c1ac51e001a67d3a8e", 14851),
        "heldout_probabilities.csv": ("3a57453506050dd20e1c497b83705e4279757c7dbfe67f7aa4ac973b11f8b4f6", 253),
        "heldout_probabilities.json": ("9fecb43979174820e8f704983025c36004d6d0e02abc74772d323057844244f6", 366),
        "historical_labeled_dataset.csv": ("0561559e00022a3a2d53a3c1fc7573f8486e196f682301f55934fcae00bf6fa8", 4321),
        "historical_labeled_dataset.json": ("279cef5ee2fa40b99c2e283feff3c894ea650ea193833a5cedb0bc1d54499356", 18524),
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_experimental_files(root: Path) -> list[str]:
    """Every file under the given root, as sorted POSIX-relative paths."""
    return sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    )


def build_registry(experimental_root: Path) -> dict[str, Any]:
    """Derive a registry from the canonical bytes currently on disk.

    Digests only. Which artifacts must exist, what they must hash to, and what
    the family must claim about itself are pinned in this module and are
    deliberately not regenerable from bytes.
    """
    families = []
    for family_name in DECLARED_FAMILIES:
        family_dir = experimental_root / family_name
        artifacts = [
            {
                "path": rel,
                "sha256": sha256_file(family_dir / rel),
                "bytes": (family_dir / rel).stat().st_size,
            }
            for rel in iter_experimental_files(family_dir)
        ]
        families.append({"family": family_name, "artifacts": artifacts})
    return {"schema_version": REGISTRY_SCHEMA_VERSION, "families": families}


def _check_pinned_claims(label: str, payload: dict, pinned: dict[str, Any]) -> list[str]:
    """Exact-value comparison of governance fields against the code-pinned set."""
    errors: list[str] = []
    for key, required_value in sorted(pinned.items()):
        if key not in payload:
            errors.append(f"{label} is missing required claim: {key}")
            continue
        actual = payload[key]
        # `1`/`0` equal `True`/`False` in Python; a governance record must not
        # smuggle a claim through a non-boolean type.
        if isinstance(required_value, bool) and not isinstance(actual, bool):
            errors.append(
                f"{label} claim {key} must be a JSON boolean, got {type(actual).__name__}"
            )
            continue
        if actual != required_value:
            errors.append(f"{label} claim {key} must be {required_value!r}, got {actual!r}")
    return errors


def _check_governed_warning(label: str, payload: dict) -> list[str]:
    """The warning must be the governed text, verbatim."""
    warning = payload.get("uncalibrated_probability_warning")
    if warning == GOVERNED_UNCALIBRATED_WARNING:
        return []
    if not isinstance(warning, str):
        return [
            f"{label} must carry 'uncalibrated_probability_warning' as the governed "
            f"text; got {type(warning).__name__}"
        ]
    return [
        f"{label} 'uncalibrated_probability_warning' does not match the governed "
        f"warning pinned in validate_experimental_integrity.py. Substituting other "
        f"wording is a governance change, not an editorial one."
    ]


def _validate_family_artifacts(
    family_name: str, entries: list[Any], experimental_root: Path
) -> tuple[list[str], set[str]]:
    """Digest-tier checks for one family. Returns (errors, registered paths)."""
    errors: list[str] = []
    registered: set[str] = set()

    for entry in entries:
        if not isinstance(entry, dict):
            errors.append(f"[{family_name}] artifact entries must be objects, got: {entry!r}")
            continue
        rel_path = entry.get("path")
        expected_hash = entry.get("sha256")
        expected_bytes = entry.get("bytes")
        if not rel_path or not expected_hash or expected_bytes is None:
            errors.append(f"[{family_name}] artifact entry missing path/sha256/bytes: {entry!r}")
            continue

        registry_key = f"{family_name}/{rel_path}"
        if registry_key in registered:
            errors.append(f"[{family_name}] duplicate registry entry: {rel_path}")
            continue
        registered.add(registry_key)

        family_root = (experimental_root / family_name).resolve()
        resolved = experimental_root / family_name / rel_path
        # A registry entry must not reach outside the family it declares.
        if not resolved.resolve().is_relative_to(family_root):
            errors.append(f"[{family_name}] registry path escapes the family directory: {rel_path}")
            continue
        if not resolved.is_file():
            errors.append(f"[{family_name}] registered artifact is missing from disk: {rel_path}")
            continue

        actual_bytes = resolved.stat().st_size
        if actual_bytes != expected_bytes:
            errors.append(
                f"[{family_name}] size mismatch for {rel_path}: "
                f"expected {expected_bytes}, got {actual_bytes}"
            )
        actual_hash = sha256_file(resolved)
        if actual_hash != expected_hash:
            errors.append(
                f"[{family_name}] sha256 mismatch for {rel_path}: "
                f"expected {expected_hash}, got {actual_hash}"
            )

    return errors, registered


def _validate_frozen_history(
    family_name: str, experimental_root: Path, registered: set[str]
) -> tuple[list[str], int]:
    """Frozen-tier checks, driven by the pinned inventory rather than the registry.

    This tier is what makes registry edits insufficient to disable a check.
    Returns (errors, number of frozen artifacts verified).
    """
    frozen = FROZEN_HISTORICAL_ARTIFACTS.get(family_name, {})
    errors: list[str] = []
    verified = 0

    for rel_path, (expected_hash, expected_bytes) in sorted(frozen.items()):
        target = experimental_root / family_name / rel_path
        if not target.is_file():
            errors.append(
                f"[{family_name}] frozen historical artifact is missing from disk: {rel_path}"
            )
            continue

        actual_bytes = target.stat().st_size
        actual_hash = sha256_file(target)
        if actual_bytes != expected_bytes or actual_hash != expected_hash:
            errors.append(
                f"[{family_name}] frozen historical artifact was modified: {rel_path} "
                f"(pinned sha256={expected_hash} bytes={expected_bytes}, "
                f"got sha256={actual_hash} bytes={actual_bytes})"
            )
            continue

        # A frozen artifact that no longer appears in the registry would lose
        # its bijection coverage; the pinned tier refuses to let that pass.
        if f"{family_name}/{rel_path}" not in registered:
            errors.append(
                f"[{family_name}] frozen historical artifact is not digest-registered: {rel_path}"
            )
            continue

        verified += 1

    return errors, verified


def _validate_status_sidecar(
    family_name: str, experimental_root: Path, registered: set[str]
) -> list[str]:
    """Status-tier checks: the archive must publish pinned, non-promotable identity."""
    errors: list[str] = []
    label = f"[{family_name}] status sidecar"
    sidecar = experimental_root / family_name / STATUS_SIDECAR_NAME

    if not sidecar.is_file():
        errors.append(
            f"[{family_name}] required experimental status sidecar is missing: {STATUS_SIDECAR_NAME}"
        )
        return errors
    if f"{family_name}/{STATUS_SIDECAR_NAME}" not in registered:
        errors.append(
            f"[{family_name}] status sidecar is not digest-registered: {STATUS_SIDECAR_NAME}"
        )

    try:
        payload = load_json(sidecar)
    except Exception as exc:
        errors.append(f"{label} is not valid JSON: {exc}")
        return errors

    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object.")
        return errors

    if payload.get("schema_version") != STATUS_SCHEMA_VERSION:
        errors.append(
            f"{label} schema_version mismatch: expected "
            f"{STATUS_SCHEMA_VERSION!r}, got {payload.get('schema_version')!r}"
        )

    # The committed archive must identify itself as the archive. A run-shaped
    # record landing here means a generated run overwrote the migration record.
    if payload.get("status_kind") != ARCHIVE_STATUS_KIND:
        errors.append(
            f"{label} status_kind must be {ARCHIVE_STATUS_KIND!r}, got "
            f"{payload.get('status_kind')!r}. A generated run must not replace the "
            f"frozen migration archive."
        )

    errors.extend(_check_pinned_claims(label, payload, PINNED_STATUS_CLAIMS))
    errors.extend(_check_governed_warning(label, payload))

    expected_family = PINNED_FAMILY_IDENTITY.get(family_name)
    if expected_family is not None:
        errors.extend(_check_pinned_claims(label, payload, {"family": expected_family}))

    # The sidecar must account for the frozen inventory, so status cannot be
    # published for a family while quietly excluding its artifacts.
    frozen = FROZEN_HISTORICAL_ARTIFACTS.get(family_name, {})
    if frozen:
        covered = payload.get("frozen_historical_artifacts")
        if not isinstance(covered, list):
            errors.append(f"{label} must list 'frozen_historical_artifacts'.")
        else:
            declared = {c.get("path") for c in covered if isinstance(c, dict)}
            missing = set(frozen) - declared
            if missing:
                errors.append(f"{label} omits frozen artifacts: {sorted(missing)}")
            for item in covered:
                if not isinstance(item, dict):
                    continue
                path = item.get("path")
                if path not in frozen:
                    errors.append(f"{label} declares unknown frozen artifact: {path!r}")
                    continue
                expected_hash, expected_bytes = frozen[path]
                if item.get("sha256") != expected_hash or item.get("bytes") != expected_bytes:
                    errors.append(
                        f"{label} digest disagrees with the pinned frozen record for {path}"
                    )

    pinned_migration = PINNED_MIGRATION_CLAIMS.get(family_name)
    if pinned_migration is not None:
        migration = payload.get("migration")
        if not isinstance(migration, dict):
            errors.append(f"{label} must carry a 'migration' object.")
        else:
            errors.extend(
                _check_pinned_claims(f"{label} migration", migration, pinned_migration)
            )

    return errors


def _validate_demotion(promoted_root: Path) -> list[str]:
    """Demotion tier: the promoted namespace must not host a demoted family."""
    errors: list[str] = []
    for family_name in DEMOTED_FROM_PROMOTED:
        demoted_dir = promoted_root / family_name
        if not demoted_dir.exists():
            continue
        stragglers = [
            p.relative_to(promoted_root).as_posix()
            for p in demoted_dir.rglob("*")
            if p.is_file()
        ]
        if stragglers:
            errors.append(
                f"[{family_name}] demoted family still has artifacts under the promoted "
                f"namespace: {sorted(stragglers)}"
            )
        else:
            errors.append(
                f"[{family_name}] demoted family directory still exists under the promoted "
                f"namespace: {demoted_dir}"
            )
    return errors


def validate_generated_run(run_dir: Path) -> list[str]:
    """Validate a freshly generated producer run.

    A run is not the archive: it carries no migration provenance and is not
    committed. What it *must* do is publish the same non-promotable semantics as
    everything else in this lane, inventory itself completely, and not pass
    itself off as the frozen migration record.
    """
    errors: list[str] = []
    label = "[generated run] status sidecar"

    if not run_dir.is_dir():
        return [f"Generated run directory not found: {run_dir}"]

    sidecar = run_dir / STATUS_SIDECAR_NAME
    if not sidecar.is_file():
        return [
            f"Generated run is missing its status sidecar ({STATUS_SIDECAR_NAME}); "
            f"experimental output must never be separable from its semantics."
        ]

    try:
        payload = load_json(sidecar)
    except Exception as exc:
        return [f"{label} is not valid JSON: {exc}"]
    if not isinstance(payload, dict):
        return [f"{label} must be a JSON object."]

    if payload.get("schema_version") != STATUS_SCHEMA_VERSION:
        errors.append(
            f"{label} schema_version mismatch: expected {STATUS_SCHEMA_VERSION!r}, "
            f"got {payload.get('schema_version')!r}"
        )
    if payload.get("status_kind") != RUN_STATUS_KIND:
        errors.append(
            f"{label} status_kind must be {RUN_STATUS_KIND!r}, got "
            f"{payload.get('status_kind')!r}"
        )

    errors.extend(_check_pinned_claims(label, payload, PINNED_STATUS_CLAIMS))
    errors.extend(_check_governed_warning(label, payload))

    expected_family = PINNED_FAMILY_IDENTITY.get(payload.get("family"))
    if expected_family is None:
        errors.append(
            f"{label} declares unknown family {payload.get('family')!r}; "
            f"expected one of {sorted(PINNED_FAMILY_IDENTITY)}"
        )

    # A run must not borrow the archive's provenance. These fields assert a
    # byte-preserving migration from the promoted namespace, which a freshly
    # generated result has not performed.
    for forbidden in ("migration", "frozen_historical_artifacts"):
        if forbidden in payload:
            errors.append(
                f"{label} must not carry {forbidden!r}: a generated run has no "
                f"migration provenance and must not present itself as the frozen archive."
            )

    # Inventory checks. The declared list is not trusted on its own: it is
    # cross-checked against a recursive walk of the run directory AND against the
    # code-pinned expected universe, and every entry carries a digest.
    declared = payload.get("generated_artifacts")
    if not isinstance(declared, list):
        errors.append(f"{label} must list 'generated_artifacts'.")
        return errors

    declared_by_path: dict[str, dict] = {}
    for item in declared:
        if not isinstance(item, dict):
            errors.append(
                f"{label} generated_artifacts entries must be objects carrying "
                f"path/sha256/bytes, got: {item!r}"
            )
            continue
        rel = item.get("path")
        if not rel or item.get("sha256") is None or item.get("bytes") is None:
            errors.append(f"{label} generated_artifacts entry missing path/sha256/bytes: {item!r}")
            continue
        if rel in declared_by_path:
            errors.append(f"{label} declares {rel} more than once.")
            continue
        declared_by_path[rel] = item

    # Recursive, so a nested file cannot hide from validation.
    on_disk = {
        p.relative_to(run_dir).as_posix()
        for p in run_dir.rglob("*")
        if p.is_file() and p.relative_to(run_dir).as_posix() != STATUS_SIDECAR_NAME
    }

    for rel in sorted(on_disk - set(declared_by_path)):
        errors.append(f"{label} does not declare a file present in the run: {rel}")
    for rel in sorted(set(declared_by_path) - on_disk):
        errors.append(f"{label} declares an artifact that is absent from the run: {rel}")

    # The pinned universe is the non-self-declaring anchor: a stale or injected
    # file cannot be legitimized just by appearing in the sidecar, and a missing
    # output cannot be hidden by omitting it from both sidecar and expectations.
    for rel in sorted(on_disk - EXPECTED_RUN_ARTIFACTS):
        errors.append(
            f"{label} run contains an artifact outside the expected generated universe: "
            f"{rel}. A run directory must contain only freshly generated output."
        )
    for rel in sorted(EXPECTED_RUN_ARTIFACTS - on_disk):
        errors.append(f"{label} run is missing an expected generated artifact: {rel}")

    # Digests, so editing a declared artifact's bytes cannot pass on filename alone.
    for rel, item in sorted(declared_by_path.items()):
        target = run_dir / rel
        if not target.is_file():
            continue
        if not target.resolve().is_relative_to(run_dir.resolve()):
            errors.append(f"{label} declared path escapes the run directory: {rel}")
            continue
        actual_bytes = target.stat().st_size
        actual_hash = sha256_file(target)
        if item.get("bytes") != actual_bytes:
            errors.append(
                f"{label} size mismatch for {rel}: declared {item.get('bytes')}, "
                f"got {actual_bytes}"
            )
        if item.get("sha256") != actual_hash:
            errors.append(
                f"{label} sha256 mismatch for {rel}: declared {item.get('sha256')}, "
                f"got {actual_hash}"
            )

    return errors


def validate_experimental_integrity(
    experimental_root: Path, registry_path: Path, promoted_root: Path
) -> tuple[list[str], dict[str, dict[str, int]]]:
    """Validate every experimental artifact. Returns (errors, per-family coverage)."""
    coverage: dict[str, dict[str, int]] = {}

    if not registry_path.is_file():
        return ([f"Integrity registry not found: {registry_path}"], coverage)
    if not experimental_root.is_dir():
        return ([f"Experimental export root not found: {experimental_root}"], coverage)

    try:
        registry = load_json(registry_path)
    except Exception as exc:
        return ([f"Failed to parse integrity registry: {exc}"], coverage)

    if not isinstance(registry, dict):
        return (["Integrity registry must be a JSON object."], coverage)
    if registry.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        return (
            [
                f"Integrity registry schema_version mismatch: expected "
                f"{REGISTRY_SCHEMA_VERSION!r}, got {registry.get('schema_version')!r}"
            ],
            coverage,
        )

    families = registry.get("families")
    if not isinstance(families, list):
        return (["Integrity registry 'families' must be a list."], coverage)

    errors: list[str] = []
    registered_paths: set[str] = set()

    registered_families = [f.get("family") for f in families if isinstance(f, dict)]
    missing_families = set(DECLARED_FAMILIES) - set(registered_families)
    if missing_families:
        errors.append(
            f"Integrity registry does not declare required families: {sorted(missing_families)}"
        )
    unexpected_families = set(registered_families) - set(DECLARED_FAMILIES)
    if unexpected_families:
        errors.append(
            f"Integrity registry declares unknown families: {sorted(unexpected_families)}"
        )

    for family in families:
        if not isinstance(family, dict):
            errors.append(f"Registry family entries must be objects, got: {family!r}")
            continue
        family_name = family.get("family")
        if family_name not in DECLARED_FAMILIES:
            continue
        entries = family.get("artifacts")
        if not isinstance(entries, list):
            errors.append(f"[{family_name}] 'artifacts' must be a list.")
            continue
        if not entries:
            errors.append(f"[{family_name}] declares no artifacts; the family must not be empty.")
            continue

        family_errors, family_registered = _validate_family_artifacts(
            family_name, entries, experimental_root
        )
        errors.extend(family_errors)
        registered_paths |= family_registered

        # The registry is a digest record only. A key implying it also carries
        # the frozen inventory or the status contract would read as if it drove
        # them; reject it rather than ignoring it silently.
        unexpected_keys = set(family) - {"family", "artifacts"}
        if unexpected_keys:
            errors.append(
                f"[{family_name}] unexpected registry keys {sorted(unexpected_keys)}; "
                f"the frozen inventory and status contract are pinned in the validator, "
                f"not the registry."
            )

        frozen_errors, frozen_verified = _validate_frozen_history(
            family_name, experimental_root, family_registered
        )
        errors.extend(frozen_errors)

        errors.extend(
            _validate_status_sidecar(family_name, experimental_root, family_registered)
        )

        coverage[family_name] = {
            "artifacts": len(family_registered),
            "frozen_verified": frozen_verified,
        }

    # Bijection: an artifact added to the tree without a registered digest is
    # exactly the direct-edit bypass this check exists to stop.
    on_disk = set(iter_experimental_files(experimental_root))
    unregistered = on_disk - registered_paths
    for rel_path in sorted(unregistered):
        errors.append(
            f"Experimental artifact is not registered in the integrity registry: {rel_path}"
        )

    errors.extend(_validate_demotion(promoted_root))

    return (errors, coverage)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate byte-level integrity of every experimental export artifact"
    )
    parser.add_argument("--experimental-root", type=Path, default=DEFAULT_EXPERIMENTAL_ROOT)
    parser.add_argument("--promoted-root", type=Path, default=DEFAULT_PROMOTED_ROOT)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help=(
            "Validate a generated producer run at this path instead of the committed "
            "migration archive."
        ),
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Rewrite the registry from the canonical bytes on disk instead of validating.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.run_dir is not None:
        errors = validate_generated_run(args.run_dir)
        if errors:
            print("EXPERIMENTAL RUN VALIDATION FAILED")
            for err in errors:
                print(f"- {err}")
            raise SystemExit(1)
        print(f"EXPERIMENTAL RUN VALIDATION PASSED ({args.run_dir})")
        return

    if args.update:
        registry = build_registry(args.experimental_root)
        args.registry.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
        total = sum(len(f["artifacts"]) for f in registry["families"])
        print(
            f"Wrote {args.registry} covering {total} artifacts "
            f"across {len(registry['families'])} families."
        )
        return

    errors, coverage = validate_experimental_integrity(
        args.experimental_root, args.registry, args.promoted_root
    )

    for family_name in DECLARED_FAMILIES:
        stats = coverage.get(family_name)
        if stats is None:
            print(f"- {family_name}: NOT COVERED")
            continue
        print(
            f"- {family_name}: {stats['artifacts']} artifacts digest-checked, "
            f"{stats['frozen_verified']} frozen historical artifact(s) verified against "
            f"the pinned inventory"
        )

    if errors:
        print("EXPERIMENTAL INTEGRITY VALIDATION FAILED")
        for err in errors:
            print(f"- {err}")
        raise SystemExit(1)

    total = sum(stats["artifacts"] for stats in coverage.values())
    print(
        f"EXPERIMENTAL INTEGRITY VALIDATION PASSED "
        f"({total} artifacts across {len(coverage)} families)"
    )


if __name__ == "__main__":
    main()
