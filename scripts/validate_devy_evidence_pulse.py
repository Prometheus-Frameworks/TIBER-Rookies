#!/usr/bin/env python3
"""Validate Devy evidence pulse v2 checkpoints (S3 candidate, synthetic-only).

Contract reference: ``docs/reports/2026-09-30-devy-pulse-2026-audit-design.md``
(§3, §5, §6.2) as refined by the independent review of PR #299. This module is
the fail-closed validator for ``devy_evidence_pulse_checkpoint`` artifacts. It
recomputes every derived field of a checkpoint from the checkpoint's own pinned
inputs (TIBER-Data college player/game observation envelopes, the Devy seed
watchlist, the Devy identity crosswalk and the prior checkpoint) and rejects any
difference.

Boundaries, deliberately:

* Discovery-only. A checkpoint copies observed cells, enumerated change states
  and integer differences of copied cells. It carries no score, rank, grade,
  probability, projection or ordering field, and any such field fails validation.
* Identity is bound, never inferred. Binding status and every decision-derived
  binding field are recomputed from the *effective* crosswalk decision at the
  checkpoint's ``as_known_at`` (latest reviewed decision following the
  supersession chain). Stale, premature or absent citations are rejected, and a
  crosswalk fork fails the checkpoint outright.
* Non-``MATCHED`` rows make no evidence or coverage assertion about a player.
* Coverage is recomputed at checkpoint level from every pinned envelope, even when
  every row is unresolved, and derived per ``MATCHED`` row by strict precedence.
* The validator consumes only the envelope fields the pulse needs. Passing here
  does **not** mean the envelope satisfied TIBER-Data's own contract validator,
  whose post-merge findings (Data PR #275) remain open, and does not qualify any
  provider or establish real-player coverage. Fixtures shipped with this
  candidate are unmistakably synthetic.
* No seed-watchlist mutation: ``auto_seed_watchlist_mutation`` must be ``"none"``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

CHECKPOINT_ARTIFACT_TYPE = "devy_evidence_pulse_checkpoint"
CHECKPOINT_SCHEMA_VERSION = "devy-evidence-pulse-v0.1.0"
CROSSWALK_ARTIFACT_TYPE = "devy_identity_crosswalk"
CROSSWALK_SCHEMA_VERSION = "devy-identity-crosswalk-v0.1.0"
ENVELOPE_ARTIFACT_TYPE = "college_player_game_observations"
ENVELOPE_SCHEMA_VERSION = "college-player-game-observations-v0.1.0"
SEED_ARTIFACT_TYPES = frozenset({"devy_seed_watchlist", "fixture_only_devy_signal_discovery_registry"})

EVIDENCE_MODES = frozenset({"synthetic_fixture", "source_observation"})
POPULATION_STATUSES = frozenset({"complete", "partial", "unknown"})

MATCHED = "MATCHED"
MATCH_CANDIDATE = "MATCH_CANDIDATE"
UNBOUND_SEED = "UNBOUND_SEED"
BINDING_STATUSES = frozenset({MATCHED, MATCH_CANDIDATE, UNBOUND_SEED})

CROSSWALK_STATUSES = frozenset({
    "READY",
    "ALIAS_RESOLVED",
    "AMBIGUOUS",
    "POSSIBLE_DUPLICATE",
    "TRANSFER_VERIFY",
    "UNAVAILABLE",
})

NEW_EVIDENCE = "NEW_EVIDENCE"
NO_NEW_EVIDENCE = "NO_NEW_EVIDENCE"
NO_OBSERVED_ROWS = "NO_OBSERVED_ROWS"
CORRECTED_EVIDENCE = "CORRECTED_EVIDENCE"
CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
EVIDENCE_CHANGE_STATES = frozenset({
    NEW_EVIDENCE,
    NO_NEW_EVIDENCE,
    NO_OBSERVED_ROWS,
    CORRECTED_EVIDENCE,
    CONFLICTING_EVIDENCE,
    IDENTITY_UNRESOLVED,
    INSUFFICIENT_EVIDENCE,
})
# States in which no delta exists at all (delta == {} and no difference anywhere).
NO_DELTA_STATES = frozenset({CONFLICTING_EVIDENCE, INSUFFICIENT_EVIDENCE, NO_OBSERVED_ROWS})

COVERAGE_COMPLETE = "COMPLETE"
COVERAGE_INCOMPLETE = "INCOMPLETE"
COVERAGE_UNKNOWN = "UNKNOWN"
COVERAGE_STATES = frozenset({COVERAGE_COMPLETE, COVERAGE_INCOMPLETE, COVERAGE_UNKNOWN})
FLAG_POPULATION_UNKNOWN = "population_unknown"
FLAG_EXPECTED_GAMES_UNKNOWN = "expected_games_unknown"
FLAG_POPULATION_PARTIAL = "population_partial"
FLAG_EXPECTED_GAME_MISSING = "expected_game_missing"
FLAG_ENVELOPE_SYNTHETIC = "envelope_synthetic"
COVERAGE_FLAGS = (
    FLAG_POPULATION_UNKNOWN,
    FLAG_EXPECTED_GAMES_UNKNOWN,
    FLAG_POPULATION_PARTIAL,
    FLAG_EXPECTED_GAME_MISSING,
    FLAG_ENVELOPE_SYNTHETIC,
)
UNKNOWN_FLAGS = frozenset({FLAG_POPULATION_UNKNOWN, FLAG_EXPECTED_GAMES_UNKNOWN})
INCOMPLETE_FLAGS = frozenset({FLAG_POPULATION_PARTIAL, FLAG_EXPECTED_GAME_MISSING})

CONTEXT_CHANGE_STATES = frozenset({
    "UNCHANGED",
    "PROGRAM_CHANGED",
    "ROSTER_STATUS_CHANGED",
    "CLASS_CONTEXT_CHANGED",
    "UNKNOWN",
})
CONTEXT_SOURCES = frozenset({"none", "seed_watchlist", "devy_roster_pulse_v1", "manual"})
ROSTER_STATUSES = frozenset({
    "new_on_roster",
    "still_present",
    "missing_from_roster",
    "program_changed",
    "unresolved",
})

DELTA_BASES = frozenset({"same_revision", "corrected", "new_rows", "not_comparable"})
OBSERVED_AVAILABILITIES = frozenset({"observed_zero", "observed_value"})
ALL_AVAILABILITIES = frozenset({
    "observed_zero",
    "observed_value",
    "unavailable_from_source",
    "not_applicable",
    "unresolved_identity",
    "incomplete_coverage",
    "source_conflict",
    "excluded_by_contract",
})
CATEGORY_FIELDS: dict[str, tuple[str, ...]] = {
    "passing": ("attempts", "completions", "yards", "touchdowns", "interceptions"),
    "rushing": ("carries", "yards", "touchdowns"),
    "receiving": ("targets", "receptions", "yards", "touchdowns"),
}
GAME_STATUSES = frozenset({"scheduled", "in_progress", "final", "suspended", "cancelled", "unknown"})
SOURCE_RELATIONSHIP_STATUSES = frozenset({
    "initial",
    "established_supersession",
    "unresolved",
    "older_discovered_later",
})
CONFLICTING_RELATIONSHIPS = frozenset({"unresolved", "older_discovered_later"})

PROPOSAL_KINDS = frozenset({
    "add_candidate",
    "re_verify_identity",
    "transition_review",
    "school_update_candidate",
})
OPPORTUNITY_UNAVAILABLE = {"status": "unavailable", "reason": "no_denominator_contract"}
REQUIRED_DISCLAIMER_PHRASES = ("discovery", "not rankings", "not rookie alpha inputs")
PROHIBITED_KEY_TOKENS = ("score", "rank", "grade", "probab", "projection", "forecast", "tier")

TOP_KEYS = frozenset({
    "artifact_type",
    "schema_version",
    "artifact_position",
    "evidence_mode",
    "checkpoint_id",
    "as_known_at",
    "generated_at",
    "disclaimer",
    "prior_checkpoint",
    "inputs",
    "window",
    "insufficient_evidence_min_games",
    "coverage_warnings",
    "rows",
    "seed_review_proposals",
    "intake_audit",
})
INPUT_KEYS = frozenset({"data_envelopes", "seed_watchlist", "identity_crosswalk"})
ENVELOPE_REF_KEYS = frozenset({
    "path",
    "sha256",
    "generated_at",
    "evidence_mode",
    "population_status",
    "competition_scope",
})
SEED_REF_KEYS = frozenset({"path", "sha256", "as_of_year"})
CROSSWALK_REF_KEYS = frozenset({"path", "sha256"})
PRIOR_REF_KEYS = frozenset({"checkpoint_id", "path", "sha256"})
WINDOW_KEYS = frozenset({"season", "game_scope_source", "expected_game_ids", "observed_game_ids"})
WARNING_KEYS = frozenset({"flag", "scope"})
ROW_KEYS = frozenset({
    "seed_player_id",
    "identity_binding",
    "coverage_state",
    "coverage_flags",
    "evidence_window",
    "observed",
    "prior_observed",
    "delta",
    "opportunity",
    "context",
    "evidence_change_state",
    "context_change_state",
    "auto_seed_watchlist_mutation",
    "needs_manual_review",
})
BINDING_KEYS = frozenset({
    "status",
    "crosswalk_row_ref",
    "crosswalk_status",
    "canonical_college_player_id",
    "decision_known_at",
    "evidence_refs",
})
EVIDENCE_WINDOW_KEYS = frozenset({"games_with_observed_rows", "games_expected", "finality_by_game"})
OBSERVED_CELL_KEYS = frozenset({"value", "availability", "observation_id", "source_revision_id"})
DELTA_CELL_KEYS = frozenset({"prior_value", "current_value", "difference", "basis", "note"})
CONTEXT_KEYS = frozenset({"source", "program_state", "roster_status", "class_context"})
INTAKE_KEYS = frozenset({"intake_method", "promotion_status", "validation_command", "downstream_block"})
PROPOSAL_KEYS = frozenset({
    "proposal_kind",
    "seed_player_id",
    "evidence_refs",
    "auto_seed_watchlist_mutation",
    "note",
})
GAME_ID_KEYS = frozenset({"season", "source_game_id"})

# Every numeric leaf in a checkpoint must sit at one of these paths. Anything else
# is a prohibited numeric output (a score, a share, a rate, a ranking...).
_ALLOWED_NUMERIC_PATHS = tuple(
    re.compile(p)
    for p in (
        r"^window\.season$",
        r"^window\.expected_game_ids\[\d+\]\.season$",
        r"^window\.observed_game_ids\[\d+\]\.season$",
        r"^inputs\.seed_watchlist\.as_of_year$",
        r"^insufficient_evidence_min_games$",
        r"^rows\[\d+\]\.evidence_window\.games_with_observed_rows$",
        r"^rows\[\d+\]\.evidence_window\.games_expected$",
        r"^rows\[\d+\]\.(observed|prior_observed)\[[^\]]+\]\.(passing|rushing|receiving)\.[a-z]+\.value$",
        r"^rows\[\d+\]\.delta\[[^\]]+\]\.(passing|rushing|receiving)\.[a-z]+\.(prior_value|current_value|difference)$",
    )
)

_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


def _instant(value: Any) -> datetime | None:
    """Parse a timezone-aware ISO-8601 timestamp; None when malformed."""
    if not isinstance(value, str) or not _TS_RE.match(value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def game_key(season: Any, source_game_id: Any) -> str:
    return f"{season}:{source_game_id}"


class _Findings:
    def __init__(self) -> None:
        self.items: list[str] = []

    def fail(self, code: str, path: str, message: str) -> None:
        self.items.append(f"{code} {path}: {message}")

    def sorted(self) -> list[str]:
        return sorted(set(self.items))


def _check_keys(f: _Findings, obj: Any, allowed: frozenset[str], path: str) -> bool:
    if not isinstance(obj, dict):
        f.fail("SHAPE", path, "must be an object")
        return False
    unknown = sorted(set(obj) - allowed)
    missing = sorted(allowed - set(obj))
    for key in unknown:
        f.fail("UNKNOWN_FIELD", f"{path}.{key}", "field is not part of the contract")
    for key in missing:
        f.fail("MISSING_FIELD", f"{path}.{key}", "required field is missing")
    return not unknown and not missing


def _walk_numeric(f: _Findings, node: Any, path: str) -> None:
    if isinstance(node, bool) or node is None or isinstance(node, str):
        return
    if isinstance(node, (int, float)):
        if not any(p.match(path) for p in _ALLOWED_NUMERIC_PATHS):
            f.fail("PROHIBITED_NUMERIC", path, "numeric value outside the permitted contract paths")
        return
    if isinstance(node, list):
        for i, item in enumerate(node):
            _walk_numeric(f, item, f"{path}[{i}]")
        return
    if isinstance(node, dict):
        for key, item in node.items():
            lowered = str(key).lower()
            if any(tok in lowered for tok in PROHIBITED_KEY_TOKENS):
                f.fail("PROHIBITED_FIELD", f"{path}.{key}", "score/rank/grade/probability/projection fields are prohibited")
            if re.match(r"^rows\[\d+\]\.(observed|prior_observed|delta)$", path):
                child = f"{path}[{key}]"
            elif path == "":
                child = str(key)
            else:
                child = f"{path}.{key}"
            _walk_numeric(f, item, child)


# --------------------------------------------------------------------------------------
# Input loading
# --------------------------------------------------------------------------------------


Resolver = Callable[[str], bytes]


def _load_json_input(f: _Findings, resolve: Resolver, ref: dict[str, Any], path: str) -> Any | None:
    rel = ref.get("path")
    expected = ref.get("sha256")
    if not _is_str(rel):
        f.fail("INPUT_PATH", f"{path}.path", "must be a non-empty string")
        return None
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        f.fail("INPUT_DIGEST", f"{path}.sha256", "must be 64 lowercase hex characters")
        return None
    try:
        raw = resolve(rel)
    except (OSError, KeyError, ValueError) as exc:
        f.fail("INPUT_UNREADABLE", f"{path}.path", f"cannot read {rel!r}: {exc}")
        return None
    actual = sha256_bytes(raw)
    if actual != expected:
        f.fail("INPUT_DIGEST", f"{path}.sha256", f"pinned digest {expected} does not match {actual}")
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        f.fail("INPUT_JSON", f"{path}.path", f"{rel!r} is not valid JSON: {exc}")
        return None


def _validate_envelope(f: _Findings, env: Any, ref: dict[str, Any], path: str, season: Any, as_known_at: datetime | None) -> dict[str, Any] | None:
    """Check the subset of a Data envelope the pulse consumes; return a summary."""
    if not isinstance(env, dict):
        f.fail("ENVELOPE_SHAPE", path, "envelope must be an object")
        return None
    if env.get("artifact_type") != ENVELOPE_ARTIFACT_TYPE:
        f.fail("ENVELOPE_TYPE", path, f"artifact_type must be {ENVELOPE_ARTIFACT_TYPE!r}")
    if env.get("schema_version") != ENVELOPE_SCHEMA_VERSION:
        f.fail("ENVELOPE_SCHEMA", path, f"schema_version must be {ENVELOPE_SCHEMA_VERSION!r}")
    mode = env.get("evidence_mode")
    if mode not in EVIDENCE_MODES:
        f.fail("ENVELOPE_MODE", path, "evidence_mode must be synthetic_fixture or source_observation")
    coverage = env.get("coverage")
    if not isinstance(coverage, dict):
        f.fail("ENVELOPE_COVERAGE", path, "coverage must be an object")
        return None
    population = coverage.get("population_status")
    if population not in POPULATION_STATUSES:
        f.fail("ENVELOPE_COVERAGE", f"{path}.coverage.population_status", "must be complete, partial or unknown")
    scope = coverage.get("game_scope")
    if not isinstance(scope, dict):
        f.fail("ENVELOPE_COVERAGE", f"{path}.coverage.game_scope", "must be an object")
        return None
    expected = scope.get("expected_game_ids")
    observed = scope.get("observed_game_ids")
    if expected is not None and not isinstance(expected, list):
        f.fail("ENVELOPE_COVERAGE", f"{path}.coverage.game_scope.expected_game_ids", "must be a list or null")
        expected = None
    if not isinstance(observed, list):
        f.fail("ENVELOPE_COVERAGE", f"{path}.coverage.game_scope.observed_game_ids", "must be a list")
        observed = []

    def keys(items: list[Any], label: str) -> set[tuple[int, str]]:
        out: set[tuple[int, str]] = set()
        for i, item in enumerate(items):
            if not isinstance(item, dict) or not _is_int(item.get("season")) or not _is_str(item.get("source_game_id")):
                f.fail("ENVELOPE_COVERAGE", f"{path}.coverage.game_scope.{label}[{i}]", "must be {season:int, source_game_id:str}")
                continue
            out.add((item["season"], item["source_game_id"]))
        return out

    expected_keys = None if expected is None else {k for k in keys(expected, "expected_game_ids") if k[0] == season}
    observed_keys = {k for k in keys(observed, "observed_game_ids") if k[0] == season}

    # Pinned header fields must match the envelope itself.
    for key, env_value in (
        ("generated_at", env.get("generated_at")),
        ("evidence_mode", mode),
        ("population_status", population),
        ("competition_scope", coverage.get("competition_scope")),
    ):
        if ref.get(key) != env_value:
            f.fail("INPUT_HEADER", f"{path}.{key}", f"pinned value {ref.get(key)!r} differs from envelope value {env_value!r}")
    generated_at = _instant(env.get("generated_at"))
    if generated_at is None:
        f.fail("ENVELOPE_CLOCK", f"{path}.generated_at", "must be a timezone-aware ISO-8601 timestamp")
    elif as_known_at is not None and generated_at > as_known_at:
        f.fail("ENVELOPE_CLOCK", f"{path}.generated_at", "envelope generation must be at or before the checkpoint cutoff")

    observations = env.get("observations")
    if not isinstance(observations, list):
        f.fail("ENVELOPE_OBSERVATIONS", f"{path}.observations", "must be a list")
        observations = []
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for i, obs in enumerate(observations):
        opath = f"{path}.observations[{i}]"
        if not isinstance(obs, dict):
            f.fail("OBSERVATION_SHAPE", opath, "must be an object")
            continue
        oid = obs.get("observation_id")
        if not _is_str(oid):
            f.fail("OBSERVATION_ID", opath, "observation_id must be a non-empty string")
            continue
        if oid in seen_ids:
            f.fail("OBSERVATION_ID", opath, f"duplicate observation_id {oid!r}")
        seen_ids.add(oid)
        if not _is_str(obs.get("source_revision_id")):
            f.fail("OBSERVATION_REVISION", f"{opath}.source_revision_id", "must be a non-empty string")
            continue
        supersedes = obs.get("supersedes")
        relationship = obs.get("source_relationship")
        established = isinstance(relationship, dict) and relationship.get("status") == "established_supersession"
        if (established or supersedes is not None) and not _is_str(supersedes):
            f.fail("OBSERVATION_RELATIONSHIP", f"{opath}.supersedes", "must be a non-empty string for established supersession, otherwise a non-empty string or null")
            continue
        identity = obs.get("identity") if isinstance(obs.get("identity"), dict) else {}
        game = obs.get("game") if isinstance(obs.get("game"), dict) else {}
        rel = obs.get("source_relationship") if isinstance(obs.get("source_relationship"), dict) else {}
        if rel.get("status") not in SOURCE_RELATIONSHIP_STATUSES:
            f.fail("OBSERVATION_RELATIONSHIP", f"{opath}.source_relationship.status", "unknown source relationship status")
        if game.get("status") not in GAME_STATUSES:
            f.fail("OBSERVATION_GAME", f"{opath}.game.status", "unknown game status")
        if _instant(obs.get("retrieved_at")) is None:
            f.fail("OBSERVATION_CLOCK", f"{opath}.retrieved_at", "must be a timezone-aware ISO-8601 timestamp")
        if mode == "synthetic_fixture" and "synthetic" not in oid.lower():
            f.fail("SYNTHETIC_PROVENANCE", opath, "synthetic envelopes must use unmistakably synthetic observation ids")
        observed_cells = obs.get("observed") if isinstance(obs.get("observed"), dict) else {}
        for cat, fields in CATEGORY_FIELDS.items():
            cat_cells = observed_cells.get(cat)
            if not isinstance(cat_cells, dict):
                f.fail("OBSERVATION_CELLS", f"{opath}.observed.{cat}", "category block missing")
                continue
            for field in fields:
                cell = cat_cells.get(field)
                if not isinstance(cell, dict) or cell.get("availability") not in ALL_AVAILABILITIES:
                    f.fail("OBSERVATION_CELLS", f"{opath}.observed.{cat}.{field}", "cell missing or has unknown availability")
                    continue
                value = cell.get("value")
                if cell["availability"] in OBSERVED_AVAILABILITIES:
                    if not _is_int(value):
                        f.fail("OBSERVATION_CELLS", f"{opath}.observed.{cat}.{field}", "observed cell must carry an integer value")
                    elif cell["availability"] == "observed_zero" and value != 0:
                        f.fail("OBSERVATION_CELLS", f"{opath}.observed.{cat}.{field}", "observed_zero must carry exactly 0")
                elif value is not None:
                    f.fail("OBSERVATION_CELLS", f"{opath}.observed.{cat}.{field}", "non-observed cell must carry null (missing is not zero)")
        rows.append({
            "envelope_path": path,
            "raw": obs,
            "observation_id": oid,
            "canonical": identity.get("canonical_college_player_id"),
            "identity_status": identity.get("status"),
            "aggregation_status": identity.get("aggregation_status"),
            "season": game.get("season"),
            "source_game_id": game.get("source_game_id"),
            "game_status": game.get("status"),
            "source_revision_id": obs.get("source_revision_id"),
            "supersedes": obs.get("supersedes"),
            "relationship": rel.get("status"),
            "retrieved_at": _instant(obs.get("retrieved_at")),
            "observed": observed_cells,
        })
    return {
        "mode": mode,
        "population": population,
        "expected": expected_keys,
        "observed": observed_keys,
        "rows": rows,
    }


def _validate_crosswalk(f: _Findings, xw: Any, path: str, synthetic: bool) -> dict[str, dict[str, Any]] | None:
    if not isinstance(xw, dict):
        f.fail("CROSSWALK_SHAPE", path, "crosswalk must be an object")
        return None
    if xw.get("artifact_type") != CROSSWALK_ARTIFACT_TYPE:
        f.fail("CROSSWALK_TYPE", path, f"artifact_type must be {CROSSWALK_ARTIFACT_TYPE!r}")
    if xw.get("schema_version") != CROSSWALK_SCHEMA_VERSION:
        f.fail("CROSSWALK_SCHEMA", path, f"schema_version must be {CROSSWALK_SCHEMA_VERSION!r}")
    if xw.get("evidence_mode") not in EVIDENCE_MODES:
        f.fail("CROSSWALK_MODE", path, "evidence_mode must be synthetic_fixture or source_observation")
    if synthetic and xw.get("evidence_mode") != "synthetic_fixture":
        f.fail("SYNTHETIC_PROVENANCE", path, "a synthetic checkpoint must pin a synthetic crosswalk")
    rows = xw.get("rows")
    if not isinstance(rows, list):
        f.fail("CROSSWALK_ROWS", f"{path}.rows", "must be a list")
        return None
    by_id: dict[str, dict[str, Any]] = {}
    for i, row in enumerate(rows):
        rpath = f"{path}.rows[{i}]"
        if not isinstance(row, dict):
            f.fail("CROSSWALK_ROW", rpath, "must be an object")
            continue
        rid = row.get("row_id")
        if not _is_str(rid):
            f.fail("CROSSWALK_ROW", rpath, "row_id must be a non-empty string")
            continue
        if rid in by_id:
            f.fail("CROSSWALK_ROW", rpath, f"duplicate row_id {rid!r}")
            continue
        if not _is_str(row.get("seed_player_id")):
            f.fail("CROSSWALK_ROW", f"{rpath}.seed_player_id", "must be a non-empty string")
        if row.get("status") not in CROSSWALK_STATUSES:
            f.fail("CROSSWALK_ROW", f"{rpath}.status", "unknown crosswalk status")
        canonical = row.get("canonical_college_player_id")
        if canonical is not None and not _is_str(canonical):
            f.fail("CROSSWALK_ROW", f"{rpath}.canonical_college_player_id", "must be a string or null")
        if synthetic and isinstance(canonical, str) and "synthetic" not in canonical.lower():
            f.fail("SYNTHETIC_PROVENANCE", f"{rpath}.canonical_college_player_id", "synthetic crosswalk ids must be unmistakably synthetic")
        decided = _instant(row.get("decision_known_at"))
        if decided is None:
            f.fail("CROSSWALK_ROW", f"{rpath}.decision_known_at", "must be a timezone-aware ISO-8601 timestamp")
        sup = row.get("supersedes")
        if sup is not None and not _is_str(sup):
            f.fail("CROSSWALK_ROW", f"{rpath}.supersedes", "must be a row_id string or null")
        refs = row.get("evidence_refs")
        parsed_refs: list[dict[str, Any]] = []
        if not isinstance(refs, list):
            f.fail("CROSSWALK_ROW", f"{rpath}.evidence_refs", "must be a list")
        else:
            for j, ref in enumerate(refs):
                if (
                    not isinstance(ref, dict)
                    or not _is_str(ref.get("kind"))
                    or not _is_str(ref.get("locator"))
                    or _instant(ref.get("known_at")) is None
                ):
                    f.fail("CROSSWALK_ROW", f"{rpath}.evidence_refs[{j}]", "must be {kind, locator, known_at}")
                    continue
                known = _instant(ref["known_at"])
                if decided is not None and known is not None and known > decided:
                    f.fail("CROSSWALK_ROW", f"{rpath}.evidence_refs[{j}]", "a decision cannot cite evidence first known after the decision itself")
                parsed_refs.append({"kind": ref["kind"], "locator": ref["locator"], "known_at": known})
        decision = row.get("reviewer_decision")
        if decision is not None and (not isinstance(decision, dict) or not _is_str(decision.get("decided_by")) or not _is_str(decision.get("decision"))):
            f.fail("CROSSWALK_ROW", f"{rpath}.reviewer_decision", "must be null or {decided_by, decision}")
        alias = row.get("alias_claim")
        if alias is not None and (
            not isinstance(alias, dict)
            or set(alias) != {"representative_observation_id"}
            or not _is_str(alias.get("representative_observation_id"))
        ):
            f.fail("CROSSWALK_ROW", f"{rpath}.alias_claim", "must be null or exactly {representative_observation_id}; currency is recomputed from the pinned envelopes, never self-declared")
        if row.get("status") == "ALIAS_RESOLVED" and alias is None:
            f.fail("CROSSWALK_ROW", f"{rpath}.alias_claim", "ALIAS_RESOLVED requires an alias_claim")
        by_id[rid] = {
            "row_id": rid,
            "path": rpath,
            "seed_player_id": row.get("seed_player_id"),
            "status": row.get("status"),
            "canonical": canonical,
            "decision_known_at": decided,
            "decision_known_at_raw": row.get("decision_known_at"),
            "supersedes": sup,
            "evidence_refs": parsed_refs,
            "reviewer_decision": decision,
            "alias_claim": alias,
        }
    for row in by_id.values():
        sup = row["supersedes"]
        if sup is None:
            continue
        target = by_id.get(sup)
        if target is None:
            f.fail("CROSSWALK_SUPERSESSION", f"{row['path']}.supersedes", f"unknown row_id {sup!r}")
        elif target["seed_player_id"] != row["seed_player_id"]:
            f.fail("CROSSWALK_SUPERSESSION", f"{row['path']}.supersedes", "cannot supersede a decision for a different seed")
        elif row["decision_known_at"] and target["decision_known_at"] and row["decision_known_at"] <= target["decision_known_at"]:
            f.fail("CROSSWALK_SUPERSESSION", f"{row['path']}.supersedes", "a superseding decision must be known later than the one it supersedes")
    return by_id


def effective_decision(rows: dict[str, dict[str, Any]], seed_player_id: str, as_known_at: datetime) -> tuple[str, dict[str, Any] | None, list[str]]:
    """Return ("none"|"one"|"fork", row|None, surviving_row_ids) at the cutoff.

    The decision is computed from the complete crosswalk, never from a cited row:
    every row for the seed known by the cutoff is a candidate, every candidate
    superseded by another candidate is discarded, and exactly one survivor is the
    effective decision. More than one survivor is a fork, which fails the
    checkpoint outright (review 5373933939, finding 3).
    """
    candidates = [
        r for r in rows.values()
        if r["seed_player_id"] == seed_player_id and r["decision_known_at"] is not None and r["decision_known_at"] <= as_known_at
    ]
    superseded = {r["supersedes"] for r in candidates if r["supersedes"]}
    survivors = sorted((r for r in candidates if r["row_id"] not in superseded), key=lambda r: r["row_id"])
    if not survivors:
        return "none", None, []
    if len(survivors) > 1:
        return "fork", None, [r["row_id"] for r in survivors]
    return "one", survivors[0], [survivors[0]["row_id"]]


def alias_is_current(decision: dict[str, Any], envelopes: list[dict[str, Any]], as_known_at: datetime) -> bool:
    """Recompute alias currency from the pinned envelopes (never from a self-declared flag).

    The representative observation must exist in a pinned envelope, be known by the
    cutoff, resolve to the decision's canonical ID, and not be superseded by any
    established source correction known by the cutoff (the Data contract's
    corrected-alias rule).
    """
    alias = decision.get("alias_claim") or {}
    rep_id = alias.get("representative_observation_id")
    if not rep_id:
        return False
    representative = None
    superseded = False
    for env in envelopes:
        for row in env["rows"]:
            if row["retrieved_at"] is None or row["retrieved_at"] > as_known_at:
                continue
            if row["observation_id"] == rep_id:
                representative = row
            if row["supersedes"] == rep_id and row["relationship"] == "established_supersession":
                superseded = True
    if representative is None or superseded:
        return False
    return (
        representative["identity_status"] == "resolved"
        and representative["canonical"] == decision["canonical"]
        and representative["aggregation_status"] == "eligible"
    )


def expected_binding(decision: dict[str, Any] | None, as_known_at: datetime, envelopes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Map the effective crosswalk decision to every decision-derived binding field."""
    envelopes = envelopes or []
    if decision is None:
        return {
            "status": UNBOUND_SEED,
            "crosswalk_row_ref": None,
            "crosswalk_status": None,
            "canonical_college_player_id": None,
            "decision_known_at": None,
            "evidence_refs": [],
        }
    status = decision["status"]
    # Only evidence known by the cutoff exists for this checkpoint; later knowledge is
    # neither copied nor allowed to qualify the decision.
    known_refs = [ref for ref in decision["evidence_refs"] if ref["known_at"] is not None and ref["known_at"] <= as_known_at]
    identity_evidence = any(ref["kind"] == "identity" for ref in known_refs)
    qualified = (
        decision["canonical"] is not None
        and decision["reviewer_decision"] is not None
        and identity_evidence
    )
    if status == "ALIAS_RESOLVED":
        qualified = qualified and alias_is_current(decision, envelopes, as_known_at)
    if status in {"READY", "ALIAS_RESOLVED"}:
        binding = MATCHED if qualified else MATCH_CANDIDATE
    elif status == "UNAVAILABLE":
        binding = UNBOUND_SEED
    else:
        binding = MATCH_CANDIDATE
    return {
        "status": binding,
        "crosswalk_row_ref": decision["row_id"],
        "crosswalk_status": status,
        "canonical_college_player_id": decision["canonical"] if binding == MATCHED else None,
        "decision_known_at": decision["decision_known_at_raw"],
        "evidence_refs": sorted(ref["locator"] for ref in known_refs),
    }


def coverage_from_flags(flags: set[str]) -> str:
    """Strict precedence: UNKNOWN > INCOMPLETE > COMPLETE."""
    if flags & UNKNOWN_FLAGS:
        return COVERAGE_UNKNOWN
    if flags & INCOMPLETE_FLAGS:
        return COVERAGE_INCOMPLETE
    return COVERAGE_COMPLETE


# --------------------------------------------------------------------------------------
# Per-player evidence recomputation
# --------------------------------------------------------------------------------------


def _observation_fingerprint(row: dict[str, Any]) -> str:
    """Content identity of an observation, used to coalesce repeats across envelopes.

    The fingerprint covers the **complete raw observation** as it appears in the
    envelope, not only the fields the pulse consumes, so two envelopes carrying the
    same observation_id with any difference in provenance, metadata or cells are an
    input defect rather than a silent merge.
    """
    return json.dumps(row["raw"], sort_keys=True, separators=(",", ":"), default=str)


def coalesce_observations(envelopes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Return one row per observation_id across all pinned envelopes.

    Overlapping or cumulative envelope slices legitimately repeat identical
    observations; those are coalesced. The same observation_id with different
    content is an input defect and is reported, never turned into an evidence
    conflict.
    """
    by_id: dict[str, tuple[str, dict[str, Any]]] = {}
    conflicts: list[str] = []
    for env in envelopes:
        for row in env["rows"]:
            fingerprint = _observation_fingerprint(row)
            oid = row["observation_id"]
            if oid in by_id:
                if by_id[oid][0] != fingerprint:
                    conflicts.append(oid)
                continue
            by_id[oid] = (fingerprint, row)
    return [row for _, row in by_id.values()], sorted(set(conflicts))


def _player_games(envelopes: list[dict[str, Any]], canonical: str, season: int, as_known_at: datetime) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    rows, _ = coalesce_observations(envelopes)
    for env in [{"rows": rows}]:
        for row in env["rows"]:
            if (
                row["canonical"] == canonical
                and row["identity_status"] == "resolved"
                and row["aggregation_status"] == "eligible"
                and row["season"] == season
                and row["retrieved_at"] is not None
                and row["retrieved_at"] <= as_known_at
            ):
                groups.setdefault(game_key(season, row["source_game_id"]), []).append(row)
    return groups


def _leaf(group: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, set[str], bool]:
    """Return (leaf, ancestor_ids, conflict) for one player/game group."""
    ids = {r["observation_id"]: r for r in group}
    if any(r["relationship"] in CONFLICTING_RELATIONSHIPS for r in group):
        return None, set(), True
    superseded = set()
    for r in group:
        if r["relationship"] == "established_supersession":
            if r["supersedes"] not in ids:
                return None, set(), True
            superseded.add(r["supersedes"])
    leaves = [r for r in group if r["observation_id"] not in superseded]
    if len(leaves) != 1:
        return None, set(), True
    leaf = leaves[0]
    ancestors: set[str] = set()
    cursor = leaf
    while cursor.get("supersedes"):
        nxt = ids.get(cursor["supersedes"])
        if nxt is None or nxt["observation_id"] in ancestors:
            # The lineage revisits a node: a supersession cycle is contradictory
            # correction history, so no node of the group may be treated as a leaf.
            return None, set(), True
        ancestors.add(nxt["observation_id"])
        cursor = nxt
    if len(ancestors) + 1 != len(ids):
        # Every row the leaf's lineage never reaches is superseded (else it would be
        # a second leaf), so the unreached rows can only form a cycle among themselves.
        return None, set(), True
    return leaf, ancestors, False


def _copy_cells(leaf: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cat, fields in CATEGORY_FIELDS.items():
        out[cat] = {}
        for field in fields:
            cell = leaf["observed"].get(cat, {}).get(field, {})
            out[cat][field] = {
                "value": cell.get("value"),
                "availability": cell.get("availability"),
                "observation_id": leaf["observation_id"],
                "source_revision_id": leaf["source_revision_id"],
            }
    return out


def recompute_matched_row(
    envelopes: list[dict[str, Any]],
    canonical: str,
    season: int,
    as_known_at: datetime,
    expected_games: set[tuple[int, str]] | None,
    prior_observed: dict[str, Any] | None,
    min_games: int,
) -> dict[str, Any]:
    """Recompute evidence_window, observed, delta and evidence_change_state for a MATCHED row."""
    groups = _player_games(envelopes, canonical, season, as_known_at)
    leaves: dict[str, tuple[dict[str, Any], set[str]]] = {}
    conflict = False
    finality: dict[str, str] = {}
    for key in sorted(groups):
        leaf, ancestors, bad = _leaf(groups[key])
        if bad or leaf is None:
            conflict = True
            continue
        leaves[key] = (leaf, ancestors)
        finality[key] = leaf["game_status"]
    games_expected = None if expected_games is None else len(expected_games)
    window = {
        "games_with_observed_rows": len(groups),
        "games_expected": games_expected,
        "finality_by_game": {} if conflict else finality,
    }
    if conflict:
        return {"state": CONFLICTING_EVIDENCE, "evidence_window": window, "observed": {}, "delta": {}}
    prior = prior_observed or {}
    missing_prior_games = sorted(set(prior) - set(groups))
    if missing_prior_games:
        # Disappearance is a competing assertion even when no current rows remain.
        return {"state": CONFLICTING_EVIDENCE, "evidence_window": {**window, "finality_by_game": {}}, "observed": {}, "delta": {}, "missing_prior_games": missing_prior_games}
    if not groups:
        return {"state": NO_OBSERVED_ROWS, "evidence_window": window, "observed": {}, "delta": {}}
    observed = {key: _copy_cells(leaf) for key, (leaf, _) in leaves.items()}

    corrected = False
    new_rows = prior_observed is None
    foreign = False
    delta: dict[str, Any] = {}
    for key, (leaf, ancestors) in leaves.items():
        prior_game = prior.get(key)
        delta[key] = {}
        for cat, fields in CATEGORY_FIELDS.items():
            delta[key][cat] = {}
            for field in fields:
                cur = observed[key][cat][field]
                prior_cell = (prior_game or {}).get(cat, {}).get(field) if prior_game else None
                if prior_cell is None:
                    basis = "new_rows"
                    new_rows = True
                elif prior_cell.get("observation_id") == leaf["observation_id"]:
                    basis = "same_revision"
                elif prior_cell.get("observation_id") in ancestors:
                    basis = "corrected"
                    corrected = True
                else:
                    basis = "not_comparable"
                    foreign = True
                difference = None
                if basis in {"same_revision", "corrected"} and cur["availability"] in OBSERVED_AVAILABILITIES and prior_cell and prior_cell.get("availability") in OBSERVED_AVAILABILITIES:
                    difference = cur["value"] - prior_cell["value"]
                delta[key][cat][field] = {
                    "prior_value": None if prior_cell is None else prior_cell.get("value"),
                    "current_value": cur["value"],
                    "difference": difference,
                    "basis": basis,
                }
    if foreign:
        # A prior-cited revision that is neither the current leaf nor one of its
        # ancestors is a competing assertion.
        return {"state": CONFLICTING_EVIDENCE, "evidence_window": {**window, "finality_by_game": {}}, "observed": {}, "delta": {}, "missing_prior_games": missing_prior_games}
    if len(groups) < min_games:
        return {"state": INSUFFICIENT_EVIDENCE, "evidence_window": window, "observed": observed, "delta": {}}
    if corrected:
        state = CORRECTED_EVIDENCE
    elif new_rows:
        state = NEW_EVIDENCE
    else:
        state = NO_NEW_EVIDENCE
    return {"state": state, "evidence_window": window, "observed": observed, "delta": delta}


# --------------------------------------------------------------------------------------
# Checkpoint validation
# --------------------------------------------------------------------------------------


def _strip_notes(delta: Any) -> Any:
    """Remove free-text notes so computed delta content can be compared exactly."""
    if not isinstance(delta, dict):
        return delta
    out: dict[str, Any] = {}
    for key, cats in delta.items():
        out[key] = {}
        if not isinstance(cats, dict):
            out[key] = cats
            continue
        for cat, fields in cats.items():
            out[key][cat] = {}
            if not isinstance(fields, dict):
                out[key][cat] = fields
                continue
            for field, cell in fields.items():
                if isinstance(cell, dict):
                    out[key][cat][field] = {k: v for k, v in cell.items() if k != "note"}
                else:
                    out[key][cat][field] = cell
    return out


def validate_devy_evidence_pulse(checkpoint: Any, resolve: Resolver, _lineage: tuple[str, ...] = ()) -> list[str]:
    """Validate a checkpoint; ``resolve(path)`` returns the bytes of a pinned input.

    ``_lineage`` carries the checkpoint IDs already being validated up the prior
    chain, so a cyclic ``prior_checkpoint`` reference fails instead of recursing.
    """
    f = _Findings()
    if not _check_keys(f, checkpoint, TOP_KEYS, "$"):
        if isinstance(checkpoint, dict):
            _walk_numeric(f, checkpoint, "")
        return f.sorted()

    if checkpoint["artifact_type"] != CHECKPOINT_ARTIFACT_TYPE:
        f.fail("ARTIFACT_TYPE", "$.artifact_type", f"must be {CHECKPOINT_ARTIFACT_TYPE!r}")
    if checkpoint["schema_version"] != CHECKPOINT_SCHEMA_VERSION:
        f.fail("SCHEMA_VERSION", "$.schema_version", f"must be {CHECKPOINT_SCHEMA_VERSION!r}")
    if checkpoint["artifact_position"] != "unpromoted":
        f.fail("ARTIFACT_POSITION", "$.artifact_position", "candidate checkpoints are always 'unpromoted'")
    if not _is_str(checkpoint["checkpoint_id"]):
        f.fail("CHECKPOINT_ID", "$.checkpoint_id", "must be a non-empty string")
    disclaimer = checkpoint["disclaimer"]
    if not _is_str(disclaimer):
        f.fail("DISCLAIMER", "$.disclaimer", "must be a non-empty string")
    else:
        for phrase in REQUIRED_DISCLAIMER_PHRASES:
            if phrase not in disclaimer.lower():
                f.fail("DISCLAIMER", "$.disclaimer", f"must include {phrase!r}")

    as_known_at = _instant(checkpoint["as_known_at"])
    generated_at = _instant(checkpoint["generated_at"])
    if as_known_at is None:
        f.fail("CLOCK", "$.as_known_at", "must be a timezone-aware ISO-8601 timestamp")
    if generated_at is None:
        f.fail("CLOCK", "$.generated_at", "must be a timezone-aware ISO-8601 timestamp")
    if as_known_at and generated_at and as_known_at > generated_at:
        f.fail("CLOCK", "$.as_known_at", "cutoff cannot be later than generated_at")

    min_games = checkpoint["insufficient_evidence_min_games"]
    if not _is_int(min_games) or min_games < 1:
        f.fail("MIN_GAMES", "$.insufficient_evidence_min_games", "must be an integer >= 1")
        min_games = 1

    # ---- window -------------------------------------------------------------------
    window = checkpoint["window"]
    season: Any = None
    if _check_keys(f, window, WINDOW_KEYS, "$.window"):
        season = window["season"]
        if not _is_int(season):
            f.fail("WINDOW", "$.window.season", "must be an integer season")
            season = None
        if window["game_scope_source"] != "data_envelope":
            f.fail("WINDOW", "$.window.game_scope_source", "must be 'data_envelope'")

    # ---- inputs -------------------------------------------------------------------
    inputs = checkpoint["inputs"]
    envelopes: list[dict[str, Any]] = []
    env_refs: list[dict[str, Any]] = []
    seed_ids: list[str] = []
    seed_loaded = False  # True once the pinned watchlist's prospects list was read, even if empty
    seed_names: dict[str, Any] = {}
    crosswalk_rows: dict[str, dict[str, Any]] | None = None
    crosswalk_pinned = False
    synthetic = False
    if _check_keys(f, inputs, INPUT_KEYS, "$.inputs"):
        refs = inputs["data_envelopes"]
        if not isinstance(refs, list) or not refs:
            f.fail("INPUTS", "$.inputs.data_envelopes", "must be a non-empty list")
            refs = []
        for i, ref in enumerate(refs):
            rpath = f"$.inputs.data_envelopes[{i}]"
            if not _check_keys(f, ref, ENVELOPE_REF_KEYS, rpath):
                continue
            env_refs.append(ref)
            env = _load_json_input(f, resolve, ref, rpath)
            if env is None:
                continue
            summary = _validate_envelope(f, env, ref, rpath, season, as_known_at)
            if summary is not None:
                summary["path"] = ref["path"]
                envelopes.append(summary)
        synthetic = any(e["mode"] == "synthetic_fixture" for e in envelopes)
        mode = checkpoint["evidence_mode"]
        if mode not in EVIDENCE_MODES:
            f.fail("EVIDENCE_MODE", "$.evidence_mode", "must be synthetic_fixture or source_observation")
        elif envelopes and (mode == "synthetic_fixture") != synthetic:
            f.fail("EVIDENCE_MODE", "$.evidence_mode", "must be synthetic_fixture exactly when any pinned envelope is synthetic")

        seed_ref = inputs["seed_watchlist"]
        if _check_keys(f, seed_ref, SEED_REF_KEYS, "$.inputs.seed_watchlist"):
            seed = _load_json_input(f, resolve, seed_ref, "$.inputs.seed_watchlist")
            if isinstance(seed, dict):
                if seed.get("artifact_type") not in SEED_ARTIFACT_TYPES:
                    f.fail("SEED_TYPE", "$.inputs.seed_watchlist", "pinned file is not a Devy seed watchlist or fixture registry")
                if seed.get("as_of_year") != seed_ref["as_of_year"]:
                    f.fail("INPUT_HEADER", "$.inputs.seed_watchlist.as_of_year", "pinned as_of_year differs from the seed watchlist")
                prospects = seed.get("prospects")
                if not isinstance(prospects, list):
                    f.fail("SEED_SHAPE", "$.inputs.seed_watchlist", "prospects must be a list")
                else:
                    seed_loaded = True
                    for j, p in enumerate(prospects):
                        if not isinstance(p, dict) or not _is_str(p.get("player_id")):
                            f.fail("SEED_SHAPE", f"$.inputs.seed_watchlist.prospects[{j}]", "player_id must be a non-empty string")
                            continue
                        seed_ids.append(p["player_id"])
                        seed_names[p["player_id"]] = p.get("player_name")
                        if synthetic and not (isinstance(p.get("player_name"), str) and p["player_name"].upper().startswith("SYNTHETIC")):
                            f.fail("SYNTHETIC_PROVENANCE", f"$.inputs.seed_watchlist.prospects[{j}]", "synthetic checkpoints may only pin seed rows whose names start with SYNTHETIC")
                if len(set(seed_ids)) != len(seed_ids):
                    f.fail("SEED_SHAPE", "$.inputs.seed_watchlist", "duplicate seed player_id")
            elif seed is not None:
                f.fail("SEED_SHAPE", "$.inputs.seed_watchlist", "pinned file must be an object")

        xw_ref = inputs["identity_crosswalk"]
        if xw_ref is not None:
            crosswalk_pinned = True
            if _check_keys(f, xw_ref, CROSSWALK_REF_KEYS, "$.inputs.identity_crosswalk"):
                xw = _load_json_input(f, resolve, xw_ref, "$.inputs.identity_crosswalk")
                if xw is not None:
                    crosswalk_rows = _validate_crosswalk(f, xw, "$.inputs.identity_crosswalk", synthetic)

    # ---- cross-envelope observation identity ---------------------------------------
    _, duplicate_conflicts = coalesce_observations(envelopes)
    for oid in duplicate_conflicts:
        f.fail("INPUT_CONFLICT", "$.inputs.data_envelopes", f"observation_id {oid!r} appears in more than one pinned envelope with different content")

    # ---- window recomputation ------------------------------------------------------
    expected_union: set[tuple[int, str]] | None = set()
    observed_union: set[tuple[int, str]] = set()
    for env in envelopes:
        observed_union |= env["observed"]
        if env["expected"] is None:
            expected_union = None
        elif expected_union is not None:
            expected_union |= env["expected"]
    if not envelopes:
        expected_union = None
    if isinstance(window, dict) and season is not None:
        def as_list(items: set[tuple[int, str]]) -> list[dict[str, Any]]:
            return [{"season": s, "source_game_id": g} for s, g in sorted(items)]

        if window["observed_game_ids"] != as_list(observed_union):
            f.fail("WINDOW", "$.window.observed_game_ids", "must equal the sorted union of pinned envelopes' observed games for the season")
        if expected_union is None:
            if window["expected_game_ids"] is not None:
                f.fail("WINDOW", "$.window.expected_game_ids", "must be null when any pinned envelope has unknown expectations")
        elif window["expected_game_ids"] != as_list(expected_union):
            f.fail("WINDOW", "$.window.expected_game_ids", "must equal the sorted union of pinned envelopes' expected games for the season")

    # ---- checkpoint-level coverage (recomputed from every pinned envelope) -------------
    warnings_expected: list[dict[str, str]] = []
    flags: set[str] = set()
    for env in envelopes:
        if env["population"] == "unknown":
            warnings_expected.append({"flag": FLAG_POPULATION_UNKNOWN, "scope": env["path"]})
        if env["population"] == "partial":
            warnings_expected.append({"flag": FLAG_POPULATION_PARTIAL, "scope": env["path"]})
        if env["mode"] == "synthetic_fixture":
            warnings_expected.append({"flag": FLAG_ENVELOPE_SYNTHETIC, "scope": env["path"]})
    if expected_union is None:
        warnings_expected.append({"flag": FLAG_EXPECTED_GAMES_UNKNOWN, "scope": "window"})
    else:
        for s, g in sorted(expected_union - observed_union):
            warnings_expected.append({"flag": FLAG_EXPECTED_GAME_MISSING, "scope": f"window:{game_key(s, g)}"})
    warnings_expected.sort(key=lambda w: (w["flag"], w["scope"]))
    flags = {w["flag"] for w in warnings_expected}
    coverage_state = coverage_from_flags(flags)
    coverage_flags = [flag for flag in COVERAGE_FLAGS if flag in flags]

    warnings = checkpoint["coverage_warnings"]
    if not isinstance(warnings, list):
        f.fail("COVERAGE_WARNINGS", "$.coverage_warnings", "must be a list")
    else:
        for i, w in enumerate(warnings):
            _check_keys(f, w, WARNING_KEYS, f"$.coverage_warnings[{i}]")
        normalized = sorted(
            ({"flag": w.get("flag"), "scope": w.get("scope")} for w in warnings if isinstance(w, dict)),
            key=lambda w: (str(w["flag"]), str(w["scope"])),
        )
        if normalized != warnings_expected:
            f.fail(
                "COVERAGE_WARNINGS",
                "$.coverage_warnings",
                f"must exactly equal the recomputed envelope-level set {warnings_expected!r}; got {normalized!r}",
            )

    # ---- prior checkpoint ---------------------------------------------------------
    prior_rows: dict[str, dict[str, Any]] | None = None
    prior_ref = checkpoint["prior_checkpoint"]
    if prior_ref is not None and _check_keys(f, prior_ref, PRIOR_REF_KEYS, "$.prior_checkpoint"):
        prior = _load_json_input(f, resolve, prior_ref, "$.prior_checkpoint")
        if isinstance(prior, dict):
            if prior.get("artifact_type") != CHECKPOINT_ARTIFACT_TYPE:
                f.fail("PRIOR", "$.prior_checkpoint", "pinned file is not a checkpoint")
            if prior.get("checkpoint_id") != prior_ref["checkpoint_id"]:
                f.fail("PRIOR", "$.prior_checkpoint.checkpoint_id", "does not match the pinned checkpoint")
            prior_cutoff = _instant(prior.get("as_known_at"))
            if prior_cutoff is None or (as_known_at and prior_cutoff >= as_known_at):
                f.fail("PRIOR", "$.prior_checkpoint", "prior checkpoint cutoff must be earlier than this cutoff")
            if isinstance(prior.get("window"), dict) and prior["window"].get("season") != season:
                f.fail("PRIOR", "$.prior_checkpoint", "prior checkpoint must cover the same season")
            # A digest only authenticates bytes. The prior checkpoint's cells may feed
            # this checkpoint's deltas only if the prior itself validates against its
            # own pinned inputs, all the way up the chain.
            prior_id = str(prior.get("checkpoint_id"))
            if prior_id in _lineage or prior_id == str(checkpoint.get("checkpoint_id")):
                f.fail("PRIOR", "$.prior_checkpoint", "cyclic prior_checkpoint lineage")
            else:
                prior_findings = validate_devy_evidence_pulse(
                    prior, resolve, _lineage + (str(checkpoint.get("checkpoint_id")),)
                )
                if prior_findings:
                    f.fail(
                        "PRIOR_INVALID",
                        "$.prior_checkpoint",
                        f"prior checkpoint {prior_id!r} fails validation against its own pinned inputs "
                        f"({len(prior_findings)} finding(s); first: {prior_findings[0]})",
                    )
            prior_rows = {}
            for r in prior.get("rows", []) if isinstance(prior.get("rows"), list) else []:
                if isinstance(r, dict) and _is_str(r.get("seed_player_id")):
                    prior_rows[r["seed_player_id"]] = r
        elif prior is not None:
            f.fail("PRIOR", "$.prior_checkpoint", "pinned file must be an object")

    # ---- rows ---------------------------------------------------------------------
    rows = checkpoint["rows"]
    if not isinstance(rows, list):
        f.fail("ROWS", "$.rows", "must be a list")
        rows = []
    row_ids = [r.get("seed_player_id") for r in rows if isinstance(r, dict)]
    # Exact coverage also holds for an empty watchlist: then rows must be empty. The check
    # is skipped only when the watchlist itself failed to load, which is already a finding.
    if seed_loaded and sorted(seed_ids) != sorted(x for x in row_ids if isinstance(x, str)):
        f.fail("ROWS", "$.rows", "rows must cover exactly the pinned seed watchlist, one row per seed (an empty watchlist requires an empty rows list)")
    if row_ids != sorted((x for x in row_ids if isinstance(x, str))):
        f.fail("ROWS", "$.rows", "rows must be sorted by seed_player_id")

    for i, row in enumerate(rows):
        rpath = f"$.rows[{i}]"
        if not _check_keys(f, row, ROW_KEYS, rpath):
            continue
        seed_id = row["seed_player_id"]
        if not _is_str(seed_id):
            f.fail("ROW", f"{rpath}.seed_player_id", "must be a non-empty string")
            continue
        if row["auto_seed_watchlist_mutation"] != "none":
            f.fail("SEED_MUTATION", f"{rpath}.auto_seed_watchlist_mutation", "must be 'none'")
        if not isinstance(row["needs_manual_review"], bool):
            f.fail("ROW", f"{rpath}.needs_manual_review", "must be a boolean")
        if row["opportunity"] != OPPORTUNITY_UNAVAILABLE:
            f.fail("OPPORTUNITY", f"{rpath}.opportunity", "no denominator contract exists; opportunity must be exactly {status: unavailable, reason: no_denominator_contract}")
        state = row["evidence_change_state"]
        if state not in EVIDENCE_CHANGE_STATES:
            f.fail("STATE", f"{rpath}.evidence_change_state", "unknown evidence_change_state")
        if row["context_change_state"] not in CONTEXT_CHANGE_STATES:
            f.fail("STATE", f"{rpath}.context_change_state", "unknown context_change_state")
        context = row["context"]
        if _check_keys(f, context, CONTEXT_KEYS, f"{rpath}.context"):
            if context["source"] not in CONTEXT_SOURCES:
                f.fail("CONTEXT", f"{rpath}.context.source", "unknown context source")
            elif context["source"] != "none":
                # No pinned, qualified context input exists in this contract version, so
                # program/roster/class context cannot be asserted from any source yet.
                f.fail("CONTEXT_UNSUPPORTED", f"{rpath}.context.source", "no qualified context input exists in this contract version; context.source must be 'none'")
            if context["roster_status"] is not None and context["roster_status"] not in ROSTER_STATUSES:
                f.fail("CONTEXT", f"{rpath}.context.roster_status", "unknown roster status")
            for key in ("program_state", "class_context"):
                if context[key] is not None and not _is_str(context[key]):
                    f.fail("CONTEXT", f"{rpath}.context.{key}", "must be a string or null")
            if context["source"] == "none":
                if any(context[k] is not None for k in ("program_state", "roster_status", "class_context")):
                    f.fail("CONTEXT", f"{rpath}.context", "context without a source must be entirely null")
                if row["context_change_state"] != "UNKNOWN":
                    f.fail("CONTEXT", f"{rpath}.context_change_state", "must be UNKNOWN when no context source is cited")

        binding = row["identity_binding"]
        if not _check_keys(f, binding, BINDING_KEYS, f"{rpath}.identity_binding"):
            continue
        if binding["status"] not in BINDING_STATUSES:
            f.fail("BINDING", f"{rpath}.identity_binding.status", "unknown binding status")
            continue

        # Effective decision from the complete pinned crosswalk (never the cited row).
        if as_known_at is None:
            continue
        if crosswalk_rows is None:
            if crosswalk_pinned:
                continue  # crosswalk failed to load; findings already recorded
            kind, decision, survivors = "none", None, []
        else:
            kind, decision, survivors = effective_decision(crosswalk_rows, seed_id, as_known_at)
        if kind == "fork":
            f.fail(
                "CROSSWALK_FORK",
                f"{rpath}.identity_binding",
                f"crosswalk holds {len(survivors)} unsuperseded decisions for this seed at the cutoff ({', '.join(survivors)}); the checkpoint cannot bind this seed",
            )
            continue
        expected = expected_binding(decision, as_known_at, envelopes)
        for key, value in expected.items():
            if binding[key] != value:
                f.fail(
                    "BINDING",
                    f"{rpath}.identity_binding.{key}",
                    f"must equal the effective-decision value {value!r}; got {binding[key]!r}",
                )
        if synthetic and isinstance(binding["canonical_college_player_id"], str) and "synthetic" not in binding["canonical_college_player_id"].lower():
            f.fail("SYNTHETIC_PROVENANCE", f"{rpath}.identity_binding.canonical_college_player_id", "must be unmistakably synthetic")

        if expected["status"] != MATCHED:
            if state != IDENTITY_UNRESOLVED:
                f.fail("IDENTITY_INVARIANT", f"{rpath}.evidence_change_state", "non-MATCHED rows must be IDENTITY_UNRESOLVED")
            for key in ("evidence_window", "observed", "prior_observed", "delta", "coverage_state", "coverage_flags"):
                if row[key] is not None:
                    f.fail("IDENTITY_INVARIANT", f"{rpath}.{key}", "must be null on a non-MATCHED row (no evidence or coverage assertion)")
            if row["needs_manual_review"] is not True:
                f.fail("IDENTITY_INVARIANT", f"{rpath}.needs_manual_review", "non-MATCHED rows require manual review")
            continue

        # MATCHED row.
        if state == IDENTITY_UNRESOLVED:
            f.fail("IDENTITY_INVARIANT", f"{rpath}.evidence_change_state", "a MATCHED row cannot be IDENTITY_UNRESOLVED")
        if row["coverage_state"] != coverage_state:
            f.fail("COVERAGE", f"{rpath}.coverage_state", f"must equal recomputed {coverage_state!r}; got {row['coverage_state']!r}")
        if row["coverage_flags"] != coverage_flags:
            f.fail("COVERAGE", f"{rpath}.coverage_flags", f"must equal recomputed {coverage_flags!r}; got {row['coverage_flags']!r}")
        if season is None or expected["canonical_college_player_id"] is None:
            continue

        prior_observed_expected: dict[str, Any] | None = None
        if prior_rows is not None:
            prior_row = prior_rows.get(seed_id)
            if isinstance(prior_row, dict) and isinstance(prior_row.get("identity_binding"), dict) and prior_row["identity_binding"].get("status") == MATCHED:
                prior_observed_expected = prior_row.get("observed") if isinstance(prior_row.get("observed"), dict) else {}
        if row["prior_observed"] != prior_observed_expected:
            f.fail("PRIOR", f"{rpath}.prior_observed", "must equal the prior checkpoint's observed cells for this seed (null when no MATCHED prior row)")

        computed = recompute_matched_row(
            envelopes,
            expected["canonical_college_player_id"],
            season,
            as_known_at,
            expected_union,
            prior_observed_expected,
            min_games,
        )
        if state != computed["state"]:
            f.fail("STATE", f"{rpath}.evidence_change_state", f"must equal recomputed {computed['state']!r}; got {state!r}")
        if row["evidence_window"] != computed["evidence_window"]:
            f.fail("EVIDENCE_WINDOW", f"{rpath}.evidence_window", f"must equal recomputed {computed['evidence_window']!r}")
        if row["observed"] != computed["observed"]:
            f.fail("OBSERVED", f"{rpath}.observed", "must equal the copied cells of the current source leaves")
        if computed["state"] in NO_DELTA_STATES:
            if row["delta"] != {}:
                f.fail("DELTA", f"{rpath}.delta", f"must be empty in state {computed['state']}")
        else:
            if _strip_notes(row["delta"]) != computed["delta"]:
                f.fail("DELTA", f"{rpath}.delta", "must equal the recomputed per-cell delta (prior_value, current_value, difference, basis)")
            if isinstance(row["delta"], dict):
                for gkey, cats in row["delta"].items():
                    if not isinstance(cats, dict):
                        continue
                    for cat, fields in cats.items():
                        if not isinstance(fields, dict):
                            continue
                        for field, cell in fields.items():
                            cpath = f"{rpath}.delta[{gkey}].{cat}.{field}"
                            if not _check_keys(f, cell, DELTA_CELL_KEYS, cpath):
                                continue
                            if cell["basis"] not in DELTA_BASES:
                                f.fail("DELTA", f"{cpath}.basis", "unknown delta basis")
                            if not isinstance(cell["note"], str):
                                f.fail("DELTA", f"{cpath}.note", "note must be a string")
        if computed["state"] == CONFLICTING_EVIDENCE and row["needs_manual_review"] is not True:
            f.fail("ROW", f"{rpath}.needs_manual_review", "conflicting evidence requires manual review")
        if isinstance(row["observed"], dict):
            for gkey, cats in row["observed"].items():
                if isinstance(cats, dict):
                    for cat, fields in cats.items():
                        if isinstance(fields, dict):
                            for field, cell in fields.items():
                                _check_keys(f, cell, OBSERVED_CELL_KEYS, f"{rpath}.observed[{gkey}].{cat}.{field}")
        if isinstance(row["evidence_window"], dict):
            _check_keys(f, row["evidence_window"], EVIDENCE_WINDOW_KEYS, f"{rpath}.evidence_window")

    # ---- proposals ----------------------------------------------------------------
    proposals = checkpoint["seed_review_proposals"]
    if not isinstance(proposals, list):
        f.fail("PROPOSALS", "$.seed_review_proposals", "must be a list")
    else:
        for i, p in enumerate(proposals):
            ppath = f"$.seed_review_proposals[{i}]"
            if not _check_keys(f, p, PROPOSAL_KEYS, ppath):
                continue
            if p["proposal_kind"] not in PROPOSAL_KINDS:
                f.fail("PROPOSALS", f"{ppath}.proposal_kind", "unknown proposal kind")
            if p["auto_seed_watchlist_mutation"] != "none":
                f.fail("SEED_MUTATION", f"{ppath}.auto_seed_watchlist_mutation", "must be 'none'")
            if p["seed_player_id"] is not None and not _is_str(p["seed_player_id"]):
                f.fail("PROPOSALS", f"{ppath}.seed_player_id", "must be a string or null")
            if not isinstance(p["evidence_refs"], list) or not all(_is_str(x) for x in p["evidence_refs"]):
                f.fail("PROPOSALS", f"{ppath}.evidence_refs", "must be a list of strings")
            if not _is_str(p["note"]):
                f.fail("PROPOSALS", f"{ppath}.note", "must be a non-empty string")

    # ---- intake audit -------------------------------------------------------------
    intake = checkpoint["intake_audit"]
    if _check_keys(f, intake, INTAKE_KEYS, "$.intake_audit"):
        if not _is_str(intake["intake_method"]):
            f.fail("INTAKE", "$.intake_audit.intake_method", "must be a non-empty string")
        if intake["promotion_status"] != "non_promoted_discovery_only":
            f.fail("INTAKE", "$.intake_audit.promotion_status", "must be 'non_promoted_discovery_only'")
        if intake["downstream_block"] != "blocked_until_rookie_transition":
            f.fail("INTAKE", "$.intake_audit.downstream_block", "must be 'blocked_until_rookie_transition'")
        if not _is_str(intake["validation_command"]):
            f.fail("INTAKE", "$.intake_audit.validation_command", "must be a non-empty string")

    # ---- prohibited numerics and fields (whole document) ----------------------------
    _walk_numeric(f, checkpoint, "")
    return f.sorted()


def filesystem_resolver(base_dir: Path) -> Resolver:
    def resolve(rel: str) -> bytes:
        target = (base_dir / rel).resolve()
        if base_dir.resolve() not in target.parents and target != base_dir.resolve():
            raise ValueError("pinned input path escapes the checkpoint directory")
        return target.read_bytes()

    return resolve


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Devy evidence pulse v2 checkpoint against its pinned inputs.")
    parser.add_argument("--checkpoint", type=Path, required=True, help="Path to the checkpoint JSON")
    args = parser.parse_args()
    try:
        checkpoint = json.loads(args.checkpoint.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"VALIDATION FAILED\n - cannot read checkpoint: {exc}")
        return 1
    errors = validate_devy_evidence_pulse(checkpoint, filesystem_resolver(args.checkpoint.parent))
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f" - {error}")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
