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

New producer output carries a ``target_evidence`` block; legacy files are
qualified by reading their ``source_name`` / ``methodology_notes`` text.
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
        "observed_denominator": target_status in (SOURCE_REPORTED, PARSED_PARTIAL),
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


def qualify_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Return the target-evidence qualification for a route-profile dict."""
    existing = profile.get("target_evidence")
    if isinstance(existing, dict) and existing.get("targets", {}).get("status") in TARGET_STATUSES:
        return existing

    source_name = str(profile.get("source_name") or "")
    notes = str(profile.get("methodology_notes") or "")
    text = f"{source_name} {notes}".lower()
    lineage = {"source_name": profile.get("source_name"), "source_url": profile.get("source_url")}
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

    match = _CATCH_RATE_RE.search(text)
    if "estimated" in text and match:
        return legacy(
            ESTIMATED,
            UNKNOWN,
            method="receptions_div_assumed_catch_rate",
            assumed_catch_rate=float(match.group(1)),
        )
    if "cfbd tgt stat" in text:
        return legacy(SOURCE_REPORTED, SOURCE_REPORTED)
    if "play-by-play" in text:
        return legacy(PARSED_PARTIAL, PARSED_PARTIAL)
    return legacy(UNKNOWN, UNKNOWN)


def target_status(profile: dict[str, Any]) -> str:
    return qualify_profile(profile)["targets"]["status"]
