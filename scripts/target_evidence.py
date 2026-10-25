#!/usr/bin/env python3
"""Target-evidence qualification for WR/TE route profiles (#303).

The route-profile family stores source-reported, play-text-parsed and
catch-rate-estimated target counts in the same numeric ``targets`` field.
This module exposes *what kind* of evidence each value is, without changing
any stored number.

Target statuses:
  source_reported  — a source returned a target count directly (e.g. CFBD TGT).
  parsed_partial   — counted from play text by name matching; may undercount.
  estimated        — computed from an assumption (e.g. receptions / 0.70).
  unavailable      — no target evidence (null value or player lookup failed).
  unknown          — legacy row whose derivation cannot be determined.

Scheme fields (screen/depth) are ``unsupported`` when the generating path
carries no route/scheme descriptors: a stored 0 there is not an observed
absence. ``parsed_partial`` marks scheme values genuinely parsed from play
text.

New producer output carries a ``target_evidence`` block. A stored block is
trusted only when it passes ``validate_target_evidence``; an invalid block is
degraded to ``unknown`` (``unavailable`` when ``targets`` is null), never
promoted to observed evidence. Legacy files are qualified from the per-row
``source_name`` label; conditional methodology prose ("if CFBD does not
supply TGT ...") is not read as a claim that the fallback was used.
Raw values are never rewritten.
"""

from __future__ import annotations

import re
from typing import Any

CONTRACT_VERSION = "wr_te_target_evidence_v0"

SOURCE_REPORTED = "source_reported"
PARSED_PARTIAL = "parsed_partial"
ESTIMATED = "estimated"
UNAVAILABLE = "unavailable"
UNKNOWN = "unknown"
UNSUPPORTED = "unsupported"

TARGET_STATUSES = frozenset({SOURCE_REPORTED, PARSED_PARTIAL, ESTIMATED, UNAVAILABLE, UNKNOWN})
OBSERVED_STATUSES = frozenset({SOURCE_REPORTED, PARSED_PARTIAL})
SCHEME_STATUSES = frozenset({PARSED_PARTIAL, UNSUPPORTED, UNKNOWN})
ORIGINS = frozenset({"producer", "legacy_inferred"})
SCHEME_FIELDS = ("screen_targets", "screen_target_rate", "deep_target_rate", "depth_tag_coverage_rate")

_CATCH_RATE_RE = re.compile(r"(?:rec|receptions)\s*/\s*(0?\.\d+)", re.IGNORECASE)
_NO_SCHEME_MARKERS = ("no route/scheme descriptors", "carry no signal")


def _qualify_scheme(profile: dict[str, Any], text: str) -> dict[str, Any]:
    if any(marker in text for marker in _NO_SCHEME_MARKERS):
        return {"status": UNSUPPORTED, "fields": list(SCHEME_FIELDS)}
    if profile.get("screen_targets") in (None, 0) and profile.get("screen_target_rate") is None:
        return {"status": UNSUPPORTED, "fields": list(SCHEME_FIELDS)}
    return {"status": UNKNOWN, "fields": list(SCHEME_FIELDS)}


def _ypt_qualification(target_status: str) -> dict[str, Any]:
    return {
        "status": "derived",
        "denominator_status": target_status,
        "observed_denominator": target_status in OBSERVED_STATUSES,
    }


def build_target_evidence(
    target_status: str,
    *,
    origin: str,
    receptions_status: str,
    scheme_status: str,
    method: str | None = None,
    assumed_catch_rate: float | None = None,
    lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a ``target_evidence`` block (shared by producer and legacy reader)."""
    targets: dict[str, Any] = {"status": target_status}
    if method is not None:
        targets["method"] = method
    if assumed_catch_rate is not None:
        targets["assumed_catch_rate"] = assumed_catch_rate
    return {
        "contract_version": CONTRACT_VERSION,
        "qualification_origin": origin,
        "targets": targets,
        "receptions": {"status": receptions_status},
        "yards_per_target": _ypt_qualification(target_status),
        "scheme_fields": {"status": scheme_status, "fields": list(SCHEME_FIELDS)},
        "lineage": lineage or {},
    }


def validate_target_evidence(block: Any, profile: dict[str, Any]) -> list[str]:
    """Return contract violations for a stored block (empty list = valid)."""
    if not isinstance(block, dict):
        return ["target_evidence is not an object"]
    errors: list[str] = []
    if block.get("contract_version") != CONTRACT_VERSION:
        errors.append(f"unrecognized contract_version {block.get('contract_version')!r}")
    origin = block.get("qualification_origin")
    if not isinstance(origin, str) or origin not in ORIGINS:
        errors.append("invalid qualification_origin")
    for key in ("targets", "receptions", "yards_per_target", "scheme_fields", "lineage"):
        if not isinstance(block.get(key), dict):
            errors.append(f"missing or non-object {key}")
    if errors:
        return errors

    status = block["targets"].get("status")
    if not isinstance(status, str) or status not in TARGET_STATUSES:
        errors.append(f"invalid targets.status {status!r}")
    receptions_status = block["receptions"].get("status")
    if not isinstance(receptions_status, str) or receptions_status not in TARGET_STATUSES:
        errors.append("invalid receptions.status")
    scheme_status = block["scheme_fields"].get("status")
    if not isinstance(scheme_status, str) or scheme_status not in SCHEME_STATUSES:
        errors.append("invalid scheme_fields.status")
    ypt = block["yards_per_target"]
    if ypt.get("status") != "derived" or ypt.get("denominator_status") != status:
        errors.append("yards_per_target qualification does not match targets.status")
    observed_denominator = isinstance(status, str) and status in OBSERVED_STATUSES
    if ypt.get("observed_denominator") is not observed_denominator:
        errors.append("yards_per_target.observed_denominator inconsistent with targets.status")
    if status == ESTIMATED:
        rate = block["targets"].get("assumed_catch_rate")
        if not block["targets"].get("method") or not isinstance(rate, (int, float)) or not 0 < rate <= 1:
            errors.append("estimated targets require method and assumed_catch_rate in (0, 1]")
    if profile.get("targets") is None and status != UNAVAILABLE:
        errors.append("null targets must be unavailable")
    return errors


def qualify_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Return the target-evidence qualification for a route-profile dict."""
    lineage = {"source_name": profile.get("source_name"), "source_url": profile.get("source_url")}
    if "target_evidence" in profile:
        existing = profile["target_evidence"]
        errors = validate_target_evidence(existing, profile)
        if not errors:
            return existing
        # Never trust or re-infer past an invalid stored block: degrade.
        degraded = UNAVAILABLE if profile.get("targets") is None else UNKNOWN
        block = build_target_evidence(
            degraded,
            origin="legacy_inferred",
            receptions_status=UNKNOWN,
            scheme_status=UNKNOWN,
            lineage=lineage,
        )
        block["invalid_stored_block"] = errors
        return block

    source_name = str(profile.get("source_name") or "")
    label = source_name.lower()
    notes = str(profile.get("methodology_notes") or "")
    text = f"{source_name} {notes}".lower()
    scheme = _qualify_scheme(profile, text)

    def legacy(target_status: str, receptions_status: str, **kwargs: Any) -> dict[str, Any]:
        # Estimated/unavailable rows have no play-level data, so any stored
        # scheme value cannot be an observation.
        no_plays = target_status in (ESTIMATED, UNAVAILABLE)
        return build_target_evidence(
            target_status,
            origin="legacy_inferred",
            receptions_status=receptions_status,
            scheme_status=UNSUPPORTED if no_plays else scheme["status"],
            lineage=lineage,
            **kwargs,
        )

    if profile.get("targets") is None:
        return legacy(UNAVAILABLE, UNAVAILABLE if profile.get("receptions") is None else UNKNOWN)
    if "player not found" in text or "not matched" in text:
        return legacy(UNAVAILABLE, UNAVAILABLE)

    # Synthetic rows whose receptions are themselves estimates (source_name
    # begins "ESTIMATED"); checked before the generic REC/x pattern.
    if source_name.strip().upper().startswith("ESTIMATED"):
        rate = 0.70 if "70% catch rate" in text else None
        return legacy(
            ESTIMATED,
            ESTIMATED,
            method="synthetic_receptions_div_assumed_catch_rate",
            assumed_catch_rate=rate,
        )

    # Per-row derivation label in source_name only; methodology_notes may
    # describe the fallback conditionally for every row.
    if "targets=cfbd tgt stat" in label:
        return legacy(SOURCE_REPORTED, UNKNOWN, method="cfbd_tgt_stat")
    match = _CATCH_RATE_RE.search(label)
    if "estimated" in label and match:
        return legacy(
            ESTIMATED,
            UNKNOWN,
            method="receptions_div_assumed_catch_rate",
            assumed_catch_rate=float(match.group(1)),
        )
    if "play-by-play" in label:
        return legacy(PARSED_PARTIAL, PARSED_PARTIAL)
    return legacy(UNKNOWN, UNKNOWN)


def target_status(profile: dict[str, Any]) -> str:
    return qualify_profile(profile)["targets"]["status"]
