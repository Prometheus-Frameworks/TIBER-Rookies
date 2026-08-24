#!/usr/bin/env python3
"""Fail-closed integrity validation for every promoted export artifact family.

`validate_promoted_export.py` and `validate_rookie_transition_profile.py` each
enforce a rich manifest contract, but only for the families that declare a
manifest. This script closes the gap identified in issue #274 Finding 1: it
holds a byte-level digest for *every* file under `exports/promoted/`, so a
directly-edited promoted artifact is rejected in CI regardless of which family
it belongs to.

Enforcement has two tiers, and they deliberately have **separate sources of
truth**:

* ``digest``   - driven by the integrity registry, which is digest-only: it
                 records nothing but path, sha256, and size. Enforced as a
                 registry <-> disk bijection, so a modified, deleted, or
                 undeclared artifact all fail. Applies to every promoted
                 artifact without exception.
* ``manifest`` - driven by EXPECTED_MANIFEST_CHECKS below, pinned in this
                 module rather than in the registry. Each entry names an
                 export/manifest pair delegated to that family's existing
                 validator, on top of the digest tier.

The split is the point. The registry legitimately changes whenever an artifact
is regenerated; *which* export/manifest pairs must be enforced is a contract
fact that must not be editable alongside it. When delegation was driven by
registry data, a tampered registry could swap four of the five rookie-alpha
entries for duplicates of the fifth and stay green. The registry therefore
carries no manifest contract at all, and a family entry bearing any key beyond
`family` and `artifacts` is rejected rather than ignored.

The experimental Rookie ML lane is deliberately absent from DECLARED_FAMILIES.
It was demoted out of the promoted namespace in issue #286 (WP-2) and is now
covered by `validate_experimental_integrity.py`, which enforces the same
fail-closed digest bijection plus a pinned frozen inventory and a non-promotable
status contract. Demotion moved it to a different validator, not out of
validation: an ML artifact reappearing under `exports/promoted/` fails the
bijection below *and* the demotion tier there.

A family absent from EXPECTED_MANIFEST_CHECKS receives digest enforcement only.
That is a property of the repository, not a skipped check: those families
declare no manifest or schema contract anywhere in the repo, and this validator
does not invent one. It fabricates no schema identity, run id, or provenance
for artifacts that do not carry one, and every value in the registry is
mechanically derived from bytes already committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_promoted_export import (  # noqa: E402
    validate_export_manifest as validate_rookie_alpha_manifest,
)
from scripts.validate_rookie_transition_profile import (  # noqa: E402
    validate_export_manifest as validate_rookie_transition_profile_manifest,
)

REGISTRY_SCHEMA_VERSION = "promoted-integrity-registry-v0.2.0"

DEFAULT_PROMOTED_ROOT = REPO_ROOT / "exports/promoted"
DEFAULT_REGISTRY = REPO_ROOT / "exports/promoted_integrity_registry_v0.json"

# The declared promoted artifact universe. Shrinking this set is a contract
# change, not a validator change: an unexpected or absent family fails closed.
DECLARED_FAMILIES = (
    "historical-comps",
    "nfl-fantasy-outcomes",
    "rookie-alpha",
    "rookie-transition-profile",
)

MANIFEST_VALIDATORS: dict[str, Callable[..., list[str]]] = {
    "rookie-alpha-manifest-v0": validate_rookie_alpha_manifest,
    "rookie-transition-profile-v0": validate_rookie_transition_profile_manifest,
}

# The authoritative manifest-delegation contract, pinned here rather than in the
# registry. The registry is a digest record and is expected to change whenever a
# promoted artifact is legitimately regenerated; which export/manifest pairs must
# be enforced is a contract fact that must not be editable alongside it.
#
# Driving delegation from registry data allowed a tampered registry to swap the
# 2022-2025 rookie-alpha entries for duplicates of the valid 2026 tuple: the
# count stayed at five and CI stayed green while four manifest contracts went
# unenforced. Each tuple below is (validator, export_json, manifest), relative to
# the family directory, and the set is required to be exact and duplicate-free.
EXPECTED_MANIFEST_CHECKS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "rookie-alpha": tuple(
        ("rookie-alpha-manifest-v0", f"{year}_rookie_alpha_predraft_v0.json", f"{year}_manifest.json")
        for year in (2022, 2023, 2024, 2025, 2026)
    ),
    "rookie-transition-profile": (
        (
            "rookie-transition-profile-v0",
            "2026_rookie_transition_profile_v0.json",
            "2026_manifest.json",
        ),
    ),
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


def iter_promoted_files(promoted_root: Path) -> list[str]:
    """Every file under the promoted root, as sorted POSIX-relative paths."""
    return sorted(
        p.relative_to(promoted_root).as_posix()
        for p in promoted_root.rglob("*")
        if p.is_file()
    )


def build_registry(promoted_root: Path) -> dict[str, Any]:
    """Derive a registry from the canonical bytes currently on disk.

    Digests only. Which export/manifest pairs must be enforced is pinned in
    EXPECTED_MANIFEST_CHECKS and is deliberately not regenerable from bytes.
    """
    families = []
    for family_name in DECLARED_FAMILIES:
        family_dir = promoted_root / family_name
        artifacts = [
            {
                "path": rel,
                "sha256": sha256_file(family_dir / rel),
                "bytes": (family_dir / rel).stat().st_size,
            }
            for rel in iter_promoted_files(family_dir)
        ]
        families.append({"family": family_name, "artifacts": artifacts})
    return {"schema_version": REGISTRY_SCHEMA_VERSION, "families": families}


def _validate_family_artifacts(
    family_name: str, entries: list[Any], promoted_root: Path
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

        family_root = (promoted_root / family_name).resolve()
        resolved = promoted_root / family_name / rel_path
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


def _check_member_path(
    family_name: str, member: str, role: str, promoted_root: Path, registered: set[str]
) -> list[str]:
    """A declared check member must stay inside its own family and be digest-pinned."""
    errors: list[str] = []
    if Path(member).is_absolute() or Path(member).parts[:1] == ("..",):
        errors.append(f"[{family_name}] manifest check {role} must be a relative in-family path: {member}")
        return errors
    family_root = (promoted_root / family_name).resolve()
    resolved = (promoted_root / family_name / member).resolve()
    if not resolved.is_relative_to(family_root):
        errors.append(f"[{family_name}] manifest check {role} escapes the family directory: {member}")
        return errors
    if f"{family_name}/{member}" not in registered:
        errors.append(
            f"[{family_name}] manifest check {role} is not digest-registered in this family: {member}"
        )
    return errors


def _validate_family_manifests(
    family_name: str, promoted_root: Path, registered: set[str]
) -> tuple[list[str], int]:
    """Manifest-tier checks, driven by the pinned contract rather than the registry.

    Returns (errors, number of checks executed).
    """
    expected = EXPECTED_MANIFEST_CHECKS.get(family_name, ())
    if len(set(expected)) != len(expected):
        return ([f"[{family_name}] pinned manifest contract contains duplicate checks."], 0)

    errors: list[str] = []
    executed = 0
    for validator_name, export_rel, manifest_rel in expected:
        validator = MANIFEST_VALIDATORS.get(validator_name)
        if validator is None:
            errors.append(
                f"[{family_name}] unknown manifest validator {validator_name!r}; "
                f"declared validators: {sorted(MANIFEST_VALIDATORS)}"
            )
            continue

        member_errors = _check_member_path(
            family_name, export_rel, "export_json", promoted_root, registered
        )
        member_errors += _check_member_path(
            family_name, manifest_rel, "manifest", promoted_root, registered
        )
        if member_errors:
            errors.extend(member_errors)
            continue

        export_path = promoted_root / family_name / export_rel
        manifest_path = promoted_root / family_name / manifest_rel
        executed += 1
        for err in validator(export_path=export_path, manifest_path=manifest_path):
            errors.append(f"[{family_name}] {export_rel}: {err}")

    return errors, executed


def validate_promoted_integrity(
    promoted_root: Path, registry_path: Path
) -> tuple[list[str], dict[str, dict[str, int]]]:
    """Validate every promoted artifact. Returns (errors, per-family coverage)."""
    coverage: dict[str, dict[str, int]] = {}

    if not registry_path.is_file():
        return ([f"Integrity registry not found: {registry_path}"], coverage)
    if not promoted_root.is_dir():
        return ([f"Promoted export root not found: {promoted_root}"], coverage)

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
            family_name, entries, promoted_root
        )
        errors.extend(family_errors)
        registered_paths |= family_registered

        # The registry is a digest record only. A leftover manifest_checks key
        # would read as if it still drove delegation; reject it rather than
        # ignoring it silently.
        unexpected_keys = set(family) - {"family", "artifacts"}
        if unexpected_keys:
            errors.append(
                f"[{family_name}] unexpected registry keys {sorted(unexpected_keys)}; "
                f"the manifest-delegation contract is pinned in the validator, not the registry."
            )

        manifest_errors, executed = _validate_family_manifests(
            family_name, promoted_root, family_registered
        )
        errors.extend(manifest_errors)

        coverage[family_name] = {
            "artifacts": len(family_registered),
            "manifest_checks": executed,
        }

    # Bijection: an artifact added to the tree without a registered digest is
    # exactly the direct-edit bypass this check exists to stop.
    on_disk = set(iter_promoted_files(promoted_root))
    unregistered = on_disk - registered_paths
    for rel_path in sorted(unregistered):
        errors.append(f"Promoted artifact is not registered in the integrity registry: {rel_path}")

    return (errors, coverage)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate byte-level integrity of every promoted export artifact"
    )
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
        registry = build_registry(args.promoted_root)
        args.registry.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
        total = sum(len(f["artifacts"]) for f in registry["families"])
        print(f"Wrote {args.registry} covering {total} artifacts across {len(registry['families'])} families.")
        return

    errors, coverage = validate_promoted_integrity(args.promoted_root, args.registry)

    for family_name in DECLARED_FAMILIES:
        stats = coverage.get(family_name)
        if stats is None:
            print(f"- {family_name}: NOT COVERED")
            continue
        print(
            f"- {family_name}: {stats['artifacts']} artifacts digest-checked, "
            f"{stats['manifest_checks']} manifest contract(s) enforced"
        )

    if errors:
        print("PROMOTED INTEGRITY VALIDATION FAILED")
        for err in errors:
            print(f"- {err}")
        raise SystemExit(1)

    total = sum(stats["artifacts"] for stats in coverage.values())
    print(f"PROMOTED INTEGRITY VALIDATION PASSED ({total} artifacts across {len(coverage)} families)")


if __name__ == "__main__":
    main()
