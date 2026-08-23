#!/usr/bin/env python3
"""Fail-closed integrity validation for every experimental export artifact family.

Demotion is not deregulation. When the Rookie ML lane left `exports/promoted/`
(issue #286, WP-2) it kept full byte-level integrity coverage; it simply stopped
claiming to be a promoted model. This validator is the enforcement half of that
claim, and it is deliberately *stricter* than the promoted validator in one
respect: it also enforces what the artifacts are allowed to say about themselves.

Enforcement has four tiers, with deliberately separate sources of truth:

* ``frozen``   - FROZEN_HISTORICAL_ARTIFACTS below, pinned in this module. These
                 are the exact bytes the ML lane carried at the authorized base
                 commit, and they are immutable: the historical record is not
                 improvable. Because this tier lives in code, it holds even if
                 the registry and the disk are tampered with *consistently*.
* ``digest``   - driven by the integrity registry, which is digest-only: path,
                 sha256, and size. Enforced as a registry <-> disk bijection, so
                 a modified, deleted, or undeclared artifact all fail.
* ``status``   - REQUIRED_STATUS_CLAIMS below. The family must carry a status
                 sidecar, and that sidecar must declare the artifacts to be
                 uncalibrated and ineligible for promotion. A sidecar claiming
                 otherwise is rejected, not ignored.
* ``demotion`` - the promoted namespace must not contain the demoted family.
                 Putting an ML artifact back under `exports/promoted/` fails
                 here as well as in the promoted validator's bijection.

The `frozen` tier is the point. `validate_promoted_integrity.py` learned in
PR #290 that a contract driven by editable registry data can be neutered while
its count assertion stays green: five rookie-alpha entries were swappable for
five duplicates of one valid tuple. A registry is a digest record and changes
whenever an artifact is legitimately regenerated; *which* artifacts must exist
and what they must hash to is a contract fact that must not be editable
alongside it. Removing an entry from the registry therefore does not remove the
check - the frozen tier fails independently, and no count assertion can satisfy
it.

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

STATUS_SIDECAR_NAME = "experimental_status_v0.json"
STATUS_SCHEMA_VERSION = "experimental-status-v0.1.0"

# The semantics every experimental family must publish about itself. Pinned
# here so that a family cannot self-declare its way back toward promotion:
# these are exact-value checks, and a sidecar asserting calibration or
# promotion eligibility is a validation failure.
REQUIRED_STATUS_CLAIMS: dict[str, Any] = {
    "artifact_class": "experimental_fixture_evaluation",
    "is_calibrated_probability": False,
    "eligible_for_promotion": False,
}

# Substantive warning text must be present; an empty or whitespace string does
# not discharge the obligation to say the probability-shaped fields are not
# calibrated claims.
MIN_WARNING_LENGTH = 40

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

# Where each demoted family came from, for the provenance binding the migration
# record must reproduce.
MIGRATION_ORIGIN = {"rookie-ml-lane": "exports/promoted/rookie-ml-lane"}


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
    """Status-tier checks: the family must publish non-promotable semantics."""
    errors: list[str] = []
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
        errors.append(f"[{family_name}] status sidecar is not valid JSON: {exc}")
        return errors

    if not isinstance(payload, dict):
        errors.append(f"[{family_name}] status sidecar must be a JSON object.")
        return errors

    if payload.get("schema_version") != STATUS_SCHEMA_VERSION:
        errors.append(
            f"[{family_name}] status sidecar schema_version mismatch: expected "
            f"{STATUS_SCHEMA_VERSION!r}, got {payload.get('schema_version')!r}"
        )

    # Exact-value semantics. A truthy calibration or eligibility claim is the
    # failure this tier exists to catch.
    for key, required_value in REQUIRED_STATUS_CLAIMS.items():
        if key not in payload:
            errors.append(f"[{family_name}] status sidecar is missing required claim: {key}")
            continue
        actual = payload[key]
        if actual is not required_value and actual != required_value:
            errors.append(
                f"[{family_name}] status sidecar claim {key} must be {required_value!r}, "
                f"got {actual!r}"
            )
        # `1`/`0` equal `True`/`False` in Python; an experimental status record
        # must not smuggle a claim through a non-boolean type.
        if isinstance(required_value, bool) and not isinstance(actual, bool):
            errors.append(
                f"[{family_name}] status sidecar claim {key} must be a JSON boolean, "
                f"got {type(actual).__name__}"
            )

    warning = payload.get("uncalibrated_probability_warning")
    if not isinstance(warning, str) or len(warning.strip()) < MIN_WARNING_LENGTH:
        errors.append(
            f"[{family_name}] status sidecar must carry a substantive "
            f"'uncalibrated_probability_warning' (>= {MIN_WARNING_LENGTH} chars)."
        )

    # The sidecar must account for the frozen inventory, so status cannot be
    # published for a family while quietly excluding its artifacts.
    frozen = FROZEN_HISTORICAL_ARTIFACTS.get(family_name, {})
    if frozen:
        covered = payload.get("frozen_historical_artifacts")
        if not isinstance(covered, list):
            errors.append(
                f"[{family_name}] status sidecar must list 'frozen_historical_artifacts'."
            )
        else:
            declared = {c.get("path") for c in covered if isinstance(c, dict)}
            missing = set(frozen) - declared
            if missing:
                errors.append(
                    f"[{family_name}] status sidecar omits frozen artifacts: {sorted(missing)}"
                )
            for item in covered:
                if not isinstance(item, dict):
                    continue
                path = item.get("path")
                if path not in frozen:
                    errors.append(
                        f"[{family_name}] status sidecar declares unknown frozen artifact: {path!r}"
                    )
                    continue
                expected_hash, expected_bytes = frozen[path]
                if item.get("sha256") != expected_hash or item.get("bytes") != expected_bytes:
                    errors.append(
                        f"[{family_name}] status sidecar digest disagrees with the pinned "
                        f"frozen record for {path}"
                    )

    origin = MIGRATION_ORIGIN.get(family_name)
    if origin is not None:
        migration = payload.get("migration")
        if not isinstance(migration, dict):
            errors.append(f"[{family_name}] status sidecar must carry a 'migration' object.")
        else:
            if migration.get("previous_path") != origin:
                errors.append(
                    f"[{family_name}] status sidecar migration.previous_path must be "
                    f"{origin!r}, got {migration.get('previous_path')!r}"
                )
            expected_new = f"exports/experimental/{family_name}"
            if migration.get("current_path") != expected_new:
                errors.append(
                    f"[{family_name}] status sidecar migration.current_path must be "
                    f"{expected_new!r}, got {migration.get('current_path')!r}"
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
        "--update",
        action="store_true",
        help="Rewrite the registry from the canonical bytes on disk instead of validating.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

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
