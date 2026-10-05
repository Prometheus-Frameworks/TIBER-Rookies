"""Focused tests for the Devy evidence pulse v2 validator (synthetic-only S3 candidate).

Every case mutates the synthetic fixtures in memory; nothing here touches real
players, providers, seeds or TIBER-Data artifacts. A passing suite proves contract
behaviour, not 2026 coverage.
"""

import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.validate_devy_evidence_pulse import (
    CONFLICTING_EVIDENCE,
    COVERAGE_COMPLETE,
    COVERAGE_INCOMPLETE,
    COVERAGE_UNKNOWN,
    CORRECTED_EVIDENCE,
    IDENTITY_UNRESOLVED,
    INSUFFICIENT_EVIDENCE,
    MATCH_CANDIDATE,
    MATCHED,
    NO_NEW_EVIDENCE,
    UNBOUND_SEED,
    _leaf,
    coverage_from_flags,
    effective_decision,
    validate_devy_evidence_pulse,
)

FIXTURE_DIR = Path("data/fixtures/devy_evidence_pulse")
CURRENT = "synthetic_checkpoint_2026_w03.json"
PRIOR = "synthetic_checkpoint_2026_w02.json"
ENVELOPE = "synthetic_envelope_2026_w03.json"
CROSSWALK = "synthetic_identity_crosswalk.json"
SEEDS = "synthetic_seed_watchlist.json"
T = "2026-09-20T12:00:00Z"


def _dump(obj) -> bytes:
    return (json.dumps(obj, indent=2) + "\n").encode("utf-8")


class Bundle:
    """In-memory copy of a checkpoint and its pinned inputs."""

    def __init__(self, checkpoint_name: str) -> None:
        self.files = {p.name: p.read_bytes() for p in FIXTURE_DIR.iterdir()}
        self.checkpoint = json.loads(self.files[checkpoint_name].decode("utf-8"))

    def read(self, name: str):
        return json.loads(self.files[name].decode("utf-8"))

    def write(self, name: str, obj) -> None:
        self.files[name] = _dump(obj)
        digest = hashlib.sha256(self.files[name]).hexdigest()
        inputs = self.checkpoint["inputs"]
        for ref in inputs["data_envelopes"]:
            if ref["path"] == name:
                ref["sha256"] = digest
                ref["generated_at"] = obj["generated_at"]
                ref["population_status"] = obj["coverage"]["population_status"]
        if inputs["seed_watchlist"]["path"] == name:
            inputs["seed_watchlist"]["sha256"] = digest
        if inputs["identity_crosswalk"] and inputs["identity_crosswalk"]["path"] == name:
            inputs["identity_crosswalk"]["sha256"] = digest
        if self.checkpoint["prior_checkpoint"] and self.checkpoint["prior_checkpoint"]["path"] == name:
            self.checkpoint["prior_checkpoint"]["sha256"] = digest
        # The prior checkpoint pins the same inputs; a rewritten input must be re-pinned
        # there too, which in turn re-pins the prior itself in this checkpoint.
        prior_ref = self.checkpoint["prior_checkpoint"]
        if prior_ref and prior_ref["path"] != name and prior_ref["path"] in self.files:
            prior = json.loads(self.files[prior_ref["path"]].decode("utf-8"))
            touched = False
            for ref in prior["inputs"]["data_envelopes"]:
                if ref["path"] == name:
                    ref["sha256"] = digest
                    touched = True
            if prior["inputs"]["seed_watchlist"]["path"] == name:
                prior["inputs"]["seed_watchlist"]["sha256"] = digest
                touched = True
            if prior["inputs"]["identity_crosswalk"] and prior["inputs"]["identity_crosswalk"]["path"] == name:
                prior["inputs"]["identity_crosswalk"]["sha256"] = digest
                touched = True
            if touched:
                self.write(prior_ref["path"], prior)

    def row(self, seed_id: str) -> dict:
        return next(r for r in self.checkpoint["rows"] if r["seed_player_id"] == seed_id)

    def errors(self) -> list[str]:
        return validate_devy_evidence_pulse(self.checkpoint, lambda p: self.files[p])


def unresolved_row(seed_id: str) -> dict:
    return {
        "seed_player_id": seed_id,
        "identity_binding": {
            "status": UNBOUND_SEED,
            "crosswalk_row_ref": None,
            "crosswalk_status": None,
            "canonical_college_player_id": None,
            "decision_known_at": None,
            "evidence_refs": [],
        },
        "coverage_state": None,
        "coverage_flags": None,
        "evidence_window": None,
        "observed": None,
        "prior_observed": None,
        "delta": None,
        "opportunity": {"status": "unavailable", "reason": "no_denominator_contract"},
        "context": {"source": "none", "program_state": None, "roster_status": None, "class_context": None},
        "evidence_change_state": IDENTITY_UNRESOLVED,
        "context_change_state": "UNKNOWN",
        "auto_seed_watchlist_mutation": "none",
        "needs_manual_review": True,
    }


class FixtureValidity(unittest.TestCase):
    def test_current_fixture_validates(self) -> None:
        self.assertEqual(Bundle(CURRENT).errors(), [])

    def test_prior_fixture_validates(self) -> None:
        self.assertEqual(Bundle(PRIOR).errors(), [])

    def test_fixture_exercises_every_designed_state(self) -> None:
        b = Bundle(CURRENT)
        states = {r["seed_player_id"]: r["evidence_change_state"] for r in b.checkpoint["rows"]}
        self.assertEqual(states["synthetic-seed-a"], IDENTITY_UNRESOLVED)
        self.assertEqual(b.row("synthetic-seed-a")["identity_binding"]["status"], UNBOUND_SEED)
        self.assertEqual(b.row("synthetic-seed-b")["identity_binding"]["status"], MATCH_CANDIDATE)
        self.assertEqual(states["synthetic-seed-c"], CORRECTED_EVIDENCE)
        self.assertEqual(b.row("synthetic-seed-c")["delta"]["2026:syn-g1"]["passing"]["yards"]["difference"], 5)
        self.assertEqual(states["synthetic-seed-d"], NO_NEW_EVIDENCE)
        self.assertEqual(states["synthetic-seed-e"], "NO_OBSERVED_ROWS")
        for r in b.checkpoint["rows"]:
            if r["identity_binding"]["status"] == MATCHED:
                self.assertEqual(r["coverage_state"], COVERAGE_INCOMPLETE)
            else:
                self.assertIsNone(r["coverage_state"])
                self.assertIsNone(r["coverage_flags"])
                self.assertIsNone(r["evidence_window"])

    def test_cli_passes_on_fixture_and_fails_on_tampered_copy(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/validate_devy_evidence_pulse.py", "--checkpoint", str(FIXTURE_DIR / CURRENT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("VALIDATION PASSED", result.stdout)
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            for p in FIXTURE_DIR.iterdir():
                (tmp_dir / p.name).write_bytes(p.read_bytes())
            env = json.loads((tmp_dir / ENVELOPE).read_text())
            env["observations"][1]["observed"]["passing"]["yards"]["value"] = 999
            (tmp_dir / ENVELOPE).write_bytes(_dump(env))
            result = subprocess.run(
                [sys.executable, "scripts/validate_devy_evidence_pulse.py", "--checkpoint", str(tmp_dir / CURRENT)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("INPUT_DIGEST", result.stdout)


class IdentityResolution(unittest.TestCase):
    def setUp(self) -> None:
        self.b = Bundle(CURRENT)

    def test_stale_crosswalk_citation_is_rejected_not_degraded(self) -> None:
        self.b.row("synthetic-seed-b")["identity_binding"]["crosswalk_row_ref"] = "synthetic-xw-r1"
        errors = self.b.errors()
        self.assertTrue(any("identity_binding.crosswalk_row_ref" in e and "synthetic-xw-r2" in e for e in errors), errors)

    def test_every_decision_derived_binding_field_is_recomputed(self) -> None:
        binding = self.b.row("synthetic-seed-b")["identity_binding"]
        binding["crosswalk_status"] = "READY"
        binding["decision_known_at"] = "2026-09-15T09:00:00Z"
        binding["evidence_refs"] = ["synthetic:roster-b"]
        errors = self.b.errors()
        for field in ("crosswalk_status", "decision_known_at", "evidence_refs"):
            self.assertTrue(any(f"identity_binding.{field}" in e for e in errors), (field, errors))

    def test_candidate_row_cannot_carry_a_canonical_id(self) -> None:
        self.b.row("synthetic-seed-b")["identity_binding"]["canonical_college_player_id"] = "synthetic-college-b"
        self.assertTrue(any("identity_binding.canonical_college_player_id" in e for e in self.b.errors()))

    def test_unqualified_ready_decision_maps_to_candidate(self) -> None:
        xw = self.b.read(CROSSWALK)
        next(r for r in xw["rows"] if r["row_id"] == "synthetic-xw-r3")["reviewer_decision"] = None
        self.b.write(CROSSWALK, xw)
        errors = self.b.errors()
        self.assertTrue(any("rows[2].identity_binding.status" in e and MATCH_CANDIDATE in e for e in errors), errors)

    def test_missing_identity_evidence_disqualifies_ready(self) -> None:
        xw = self.b.read(CROSSWALK)
        next(r for r in xw["rows"] if r["row_id"] == "synthetic-xw-r3")["evidence_refs"][0]["kind"] = "transfer_report"
        self.b.write(CROSSWALK, xw)
        self.assertTrue(any("rows[2].identity_binding.status" in e for e in self.b.errors()))

    def test_alias_currency_is_recomputed_from_observation_lineage(self) -> None:
        # At the prior cutoff (W02) the alias representative r1 is current. By W03 a
        # source correction (r2 supersedes r1) is known, so the W02-era decision no
        # longer qualifies until a later reviewed re-binding names r2.
        xw = self.b.read(CROSSWALK)
        r3 = next(r for r in xw["rows"] if r["row_id"] == "synthetic-xw-r3")
        r3["status"] = "ALIAS_RESOLVED"
        r3["alias_claim"] = {"representative_observation_id": "synthetic-observation-c-g1-r1"}
        self.b.write(CROSSWALK, xw)
        prior = self.b.read(PRIOR)
        prior["rows"][2]["identity_binding"]["crosswalk_status"] = "ALIAS_RESOLVED"
        self.b.write(PRIOR, prior)
        self.b.row("synthetic-seed-c")["identity_binding"]["crosswalk_status"] = "ALIAS_RESOLVED"
        errors = self.b.errors()
        self.assertFalse(any(e.startswith("PRIOR_INVALID") for e in errors), errors)
        self.assertTrue(any("rows[2].identity_binding.status" in e and MATCH_CANDIDATE in e for e in errors), errors)
        # A later reviewed re-binding to the corrected revision restores MATCHED at W03 only.
        xw["rows"].append({
            "row_id": "synthetic-xw-r6",
            "seed_player_id": "synthetic-seed-c",
            "status": "ALIAS_RESOLVED",
            "canonical_college_player_id": "synthetic-college-c",
            "decision_known_at": "2026-09-16T09:00:00Z",
            "supersedes": "synthetic-xw-r3",
            "evidence_refs": [{"kind": "identity", "locator": "synthetic:roster-c", "known_at": "2026-09-09T09:00:00Z"}],
            "reviewer_decision": {"decided_by": "synthetic-reviewer", "decision": "SYNTHETIC re-bound after correction"},
            "alias_claim": {"representative_observation_id": "synthetic-observation-c-g1-r2"},
            "note": "SYNTHETIC",
        })
        self.b.write(CROSSWALK, xw)
        binding = self.b.row("synthetic-seed-c")["identity_binding"]
        binding["crosswalk_row_ref"] = "synthetic-xw-r6"
        binding["decision_known_at"] = "2026-09-16T09:00:00Z"
        self.assertEqual(self.b.errors(), [])
        # A representative absent from every pinned envelope is not current.
        xw["rows"][-1]["alias_claim"] = {"representative_observation_id": "synthetic-observation-nowhere"}
        self.b.write(CROSSWALK, xw)
        self.assertTrue(any("rows[2].identity_binding.status" in e and MATCH_CANDIDATE in e for e in self.b.errors()))

    def test_self_declared_alias_currency_is_rejected(self) -> None:
        xw = self.b.read(CROSSWALK)
        r3 = next(r for r in xw["rows"] if r["row_id"] == "synthetic-xw-r3")
        r3["status"] = "ALIAS_RESOLVED"
        r3["alias_claim"] = {"representative_observation_id": "synthetic-observation-c-g1-r1", "current": True}
        self.b.write(CROSSWALK, xw)
        self.assertTrue(any("alias_claim" in e and "never self-declared" in e for e in self.b.errors()))

    def test_evidence_known_after_the_cutoff_cannot_qualify_or_be_copied(self) -> None:
        xw = self.b.read(CROSSWALK)
        r3 = next(r for r in xw["rows"] if r["row_id"] == "synthetic-xw-r3")
        r3["evidence_refs"].append({"kind": "transfer_report", "locator": "synthetic:future-c", "known_at": "2026-09-25T09:00:00Z"})
        self.b.write(CROSSWALK, xw)
        errors = self.b.errors()
        # The crosswalk row itself is defective: it cites evidence first known after the decision.
        self.assertTrue(any(e.startswith("CROSSWALK_ROW") and "known after the decision" in e for e in errors), errors)
        # And a checkpoint that copies the premature locator is rejected on evidence_refs.
        self.b.row("synthetic-seed-c")["identity_binding"]["evidence_refs"] = ["synthetic:future-c", "synthetic:roster-c"]
        self.assertTrue(any("rows[2].identity_binding.evidence_refs" in e for e in self.b.errors()))

    def test_only_identity_evidence_known_by_the_cutoff_qualifies(self) -> None:
        # Decision known at T-10d, its only identity evidence re-dated to after the cutoff:
        # the row is defective and the decision no longer qualifies.
        xw = self.b.read(CROSSWALK)
        r3 = next(r for r in xw["rows"] if r["row_id"] == "synthetic-xw-r3")
        r3["evidence_refs"][0]["known_at"] = "2026-09-22T09:00:00Z"
        self.b.write(CROSSWALK, xw)
        errors = self.b.errors()
        self.assertTrue(any(e.startswith("CROSSWALK_ROW") for e in errors), errors)
        self.assertTrue(any("rows[2].identity_binding.status" in e and MATCH_CANDIDATE in e for e in errors), errors)

    def test_crosswalk_fork_fails_the_checkpoint_outright(self) -> None:
        xw = self.b.read(CROSSWALK)
        xw["rows"].append({
            "row_id": "synthetic-xw-r6",
            "seed_player_id": "synthetic-seed-c",
            "status": "READY",
            "canonical_college_player_id": "synthetic-college-c2",
            "decision_known_at": "2026-09-11T09:00:00Z",
            "supersedes": None,
            "evidence_refs": [{"kind": "identity", "locator": "synthetic:roster-c2", "known_at": "2026-09-10T09:00:00Z"}],
            "reviewer_decision": {"decided_by": "synthetic-reviewer", "decision": "SYNTHETIC second decision"},
            "alias_claim": None,
            "note": "SYNTHETIC fork",
        })
        self.b.write(CROSSWALK, xw)
        errors = self.b.errors()
        self.assertTrue(any(e.startswith("CROSSWALK_FORK") and "synthetic-xw-r3" in e and "synthetic-xw-r6" in e for e in errors), errors)
        kind, decision, survivors = effective_decision(
            {r["row_id"]: {"row_id": r["row_id"], "seed_player_id": r["seed_player_id"], "decision_known_at": __import__("datetime").datetime.fromisoformat(r["decision_known_at"].replace("Z", "+00:00")), "supersedes": r["supersedes"]} for r in xw["rows"]},
            "synthetic-seed-c",
            __import__("datetime").datetime.fromisoformat(T.replace("Z", "+00:00")),
        )
        self.assertEqual((kind, decision), ("fork", None))
        self.assertEqual(survivors, ["synthetic-xw-r3", "synthetic-xw-r6"])

    def test_null_crosswalk_means_every_seed_is_unbound(self) -> None:
        self.b.checkpoint["inputs"]["identity_crosswalk"] = None
        errors = self.b.errors()
        self.assertTrue(any("rows[2].identity_binding.status" in e and UNBOUND_SEED in e for e in errors), errors)
        self.b.checkpoint["rows"] = [unresolved_row(f"synthetic-seed-{k}") for k in "abcde"]
        self.assertEqual(self.b.errors(), [])

    def test_non_matched_row_cannot_assert_evidence_or_coverage(self) -> None:
        row = self.b.row("synthetic-seed-a")
        row["evidence_change_state"] = "NO_OBSERVED_ROWS"
        row["coverage_state"] = COVERAGE_INCOMPLETE
        row["evidence_window"] = {"games_with_observed_rows": 0, "games_expected": 3, "finality_by_game": {}}
        errors = self.b.errors()
        self.assertTrue(any("rows[0].evidence_change_state" in e and "IDENTITY_UNRESOLVED" in e for e in errors), errors)
        self.assertTrue(any("rows[0].coverage_state" in e for e in errors), errors)
        self.assertTrue(any("rows[0].evidence_window" in e for e in errors), errors)

    def test_matched_row_cannot_be_identity_unresolved(self) -> None:
        self.b.row("synthetic-seed-c")["evidence_change_state"] = IDENTITY_UNRESOLVED
        self.assertTrue(any("rows[2].evidence_change_state" in e and "cannot be IDENTITY_UNRESOLVED" in e for e in self.b.errors()))

    def test_synthetic_checkpoint_rejects_real_looking_seed_names(self) -> None:
        seeds = self.b.read(SEEDS)
        seeds["prospects"][0]["player_name"] = "Jordan Example"
        self.b.write(SEEDS, seeds)
        self.assertTrue(any(e.startswith("SYNTHETIC_PROVENANCE") for e in self.b.errors()))


class SupersessionAndCutoff(unittest.TestCase):
    def setUp(self) -> None:
        self.b = Bundle(CURRENT)

    def test_decision_known_after_cutoff_is_not_effective(self) -> None:
        xw = self.b.read(CROSSWALK)
        next(r for r in xw["rows"] if r["row_id"] == "synthetic-xw-r3")["decision_known_at"] = "2026-09-21T09:00:00Z"
        self.b.write(CROSSWALK, xw)
        errors = self.b.errors()
        self.assertTrue(any("rows[2].identity_binding.status" in e and UNBOUND_SEED in e for e in errors), errors)

    def test_supersession_must_be_known_later_than_its_target(self) -> None:
        xw = self.b.read(CROSSWALK)
        next(r for r in xw["rows"] if r["row_id"] == "synthetic-xw-r2")["decision_known_at"] = "2026-09-14T09:00:00Z"
        self.b.write(CROSSWALK, xw)
        self.assertTrue(any(e.startswith("CROSSWALK_SUPERSESSION") for e in self.b.errors()))

    def test_supersession_cannot_cross_seeds(self) -> None:
        xw = self.b.read(CROSSWALK)
        next(r for r in xw["rows"] if r["row_id"] == "synthetic-xw-r2")["seed_player_id"] = "synthetic-seed-a"
        self.b.write(CROSSWALK, xw)
        self.assertTrue(any("cannot supersede a decision for a different seed" in e for e in self.b.errors()))

    def test_supersession_cycle_with_one_apparent_leaf_is_conflicting(self) -> None:
        env = self.b.read(ENVELOPE)
        r1 = next(o for o in env["observations"] if o["observation_id"] == "synthetic-observation-c-g1-r1")
        r2 = next(o for o in env["observations"] if o["observation_id"] == "synthetic-observation-c-g1-r2")
        # r1 -> r2 -> r1 is a cycle; a new r3 supersedes r2 and is the only apparent leaf.
        r1["supersedes"] = r2["observation_id"]
        r1["source_relationship"] = {**r2["source_relationship"], "related_observation_id": r2["observation_id"]}
        r3 = copy.deepcopy(r2)
        r3["observation_id"] = "synthetic-observation-c-g1-r3"
        r3["source_revision_id"] = "synthetic-r3"
        r3["supersedes"] = r2["observation_id"]
        r3["source_relationship"]["related_observation_id"] = r2["observation_id"]
        r3["retrieved_at"] = "2026-09-16T12:00:00Z"
        env["observations"].append(r3)
        self.b.write(ENVELOPE, env)
        row = self.b.row("synthetic-seed-c")
        # A checkpoint that copies r3's cells, as a truncating ancestry walk would allow, must fail.
        for cat in row["observed"]["2026:syn-g1"].values():
            for cell in cat.values():
                cell["observation_id"] = "synthetic-observation-c-g1-r3"
                cell["source_revision_id"] = "synthetic-r3"
        errors = self.b.errors()
        self.assertTrue(any("rows[2].evidence_change_state" in e and CONFLICTING_EVIDENCE in e for e in errors), errors)
        self.assertTrue(any("rows[2].observed" in e for e in errors), errors)
        # Declaring the conflict, with no leaf, no cells and no delta, is the only valid outcome.
        row["evidence_change_state"] = CONFLICTING_EVIDENCE
        row["evidence_window"] = {"games_with_observed_rows": 2, "games_expected": 3, "finality_by_game": {}}
        row["observed"] = {}
        row["delta"] = {}
        row["needs_manual_review"] = True
        self.assertEqual(self.b.errors(), [])

    def test_leaf_rejects_every_cycle_shape(self) -> None:
        def obs(oid: str, supersedes: str | None) -> dict:
            return {"observation_id": oid, "relationship": "established_supersession" if supersedes else "initial", "supersedes": supersedes}

        chain = [obs("a", None), obs("b", "a"), obs("c", "b")]
        leaf, ancestors, conflict = _leaf(chain)
        self.assertEqual((leaf["observation_id"], ancestors, conflict), ("c", {"a", "b"}, False))
        one_apparent_leaf = [obs("a", "b"), obs("b", "a"), obs("c", "a")]
        self.assertEqual(_leaf(one_apparent_leaf), (None, set(), True))
        cycle_beside_a_leaf = [obs("a", "b"), obs("b", "a"), obs("d", None)]
        self.assertEqual(_leaf(cycle_beside_a_leaf), (None, set(), True))

    def test_observation_retrieved_after_cutoff_is_excluded(self) -> None:
        env = self.b.read(ENVELOPE)
        next(o for o in env["observations"] if o["observation_id"] == "synthetic-observation-c-g2-r1")["retrieved_at"] = "2026-09-21T12:00:00Z"
        self.b.write(ENVELOPE, env)
        errors = self.b.errors()
        self.assertTrue(any("rows[2].evidence_window" in e for e in errors), errors)
        self.assertTrue(any("rows[2].observed" in e for e in errors), errors)

    def test_cutoff_cannot_follow_generation(self) -> None:
        self.b.checkpoint["as_known_at"] = "2026-09-20T12:10:00Z"
        self.assertTrue(any(e.startswith("CLOCK") for e in self.b.errors()))

    def test_prior_checkpoint_is_validated_before_its_cells_are_trusted(self) -> None:
        prior = self.b.read(PRIOR)
        cell = prior["rows"][3]["observed"]["2026:syn-g1"]["rushing"]["yards"]
        self.assertEqual(cell["value"], 77)
        cell["value"] = 999
        self.b.write(PRIOR, prior)
        row = self.b.row("synthetic-seed-d")
        row["prior_observed"]["2026:syn-g1"]["rushing"]["yards"]["value"] = 999
        row["delta"]["2026:syn-g1"]["rushing"]["yards"]["prior_value"] = 999
        row["delta"]["2026:syn-g1"]["rushing"]["yards"]["difference"] = 77 - 999
        errors = self.b.errors()
        self.assertTrue(any(e.startswith("PRIOR_INVALID") and "synthetic-checkpoint-2026-w02" in e for e in errors), errors)

    def test_cyclic_prior_lineage_fails(self) -> None:
        prior = self.b.read(PRIOR)
        prior["prior_checkpoint"] = {"checkpoint_id": "synthetic-checkpoint-2026-w03", "path": CURRENT, "sha256": "0" * 64}
        self.b.write(PRIOR, prior)
        errors = self.b.errors()
        self.assertTrue(any(e.startswith("PRIOR_INVALID") for e in errors), errors)

    def test_prior_checkpoint_must_precede_this_cutoff(self) -> None:
        prior = self.b.read(PRIOR)
        prior["as_known_at"] = "2026-09-20T12:00:00Z"
        prior["generated_at"] = "2026-09-20T12:01:00Z"
        self.b.write(PRIOR, prior)
        self.assertTrue(any(e.startswith("PRIOR") and "earlier" in e for e in self.b.errors()))


class CoveragePrecedence(unittest.TestCase):
    def setUp(self) -> None:
        self.b = Bundle(CURRENT)

    def test_precedence_function(self) -> None:
        self.assertEqual(coverage_from_flags({"population_partial", "expected_games_unknown"}), COVERAGE_UNKNOWN)
        self.assertEqual(coverage_from_flags({"population_partial", "expected_game_missing"}), COVERAGE_INCOMPLETE)
        self.assertEqual(coverage_from_flags({"envelope_synthetic"}), COVERAGE_COMPLETE)
        self.assertEqual(coverage_from_flags(set()), COVERAGE_COMPLETE)

    def test_checkpoint_level_warnings_are_required_even_when_all_rows_are_unresolved(self) -> None:
        self.b.checkpoint["inputs"]["identity_crosswalk"] = None
        self.b.checkpoint["rows"] = [unresolved_row(f"synthetic-seed-{k}") for k in "abcde"]
        self.assertEqual(self.b.errors(), [])
        self.b.checkpoint["coverage_warnings"] = []
        errors = self.b.errors()
        self.assertTrue(any(e.startswith("COVERAGE_WARNINGS") for e in errors), errors)

    def test_warnings_must_match_recomputed_set_exactly(self) -> None:
        self.b.checkpoint["coverage_warnings"].pop()
        self.assertTrue(any(e.startswith("COVERAGE_WARNINGS") for e in self.b.errors()))
        self.b = Bundle(CURRENT)
        self.b.checkpoint["coverage_warnings"].append({"flag": "population_unknown", "scope": ENVELOPE})
        self.assertTrue(any(e.startswith("COVERAGE_WARNINGS") for e in self.b.errors()))

    def test_unknown_expectations_outrank_partial_population(self) -> None:
        env = self.b.read(ENVELOPE)
        env["coverage"]["game_scope"]["expected_game_ids"] = None
        self.b.write(ENVELOPE, env)
        cp = self.b.checkpoint
        cp["window"]["expected_game_ids"] = None
        cp["coverage_warnings"] = [
            {"flag": "envelope_synthetic", "scope": ENVELOPE},
            {"flag": "expected_games_unknown", "scope": "window"},
            {"flag": "population_partial", "scope": ENVELOPE},
        ]
        for row in cp["rows"]:
            if row["identity_binding"]["status"] == MATCHED:
                row["coverage_state"] = COVERAGE_INCOMPLETE  # deliberately wrong first
                row["coverage_flags"] = ["expected_games_unknown", "population_partial", "envelope_synthetic"]
                row["evidence_window"]["games_expected"] = None
        errors = self.b.errors()
        self.assertTrue(any("coverage_state" in e and COVERAGE_UNKNOWN in e for e in errors), errors)
        for row in cp["rows"]:
            if row["identity_binding"]["status"] == MATCHED:
                row["coverage_state"] = COVERAGE_UNKNOWN
        self.assertEqual(self.b.errors(), [])

    def test_complete_population_with_all_expected_games_observed_is_complete(self) -> None:
        env = self.b.read(ENVELOPE)
        env["coverage"]["population_status"] = "complete"
        env["coverage"]["game_scope"]["expected_game_ids"] = env["coverage"]["game_scope"]["observed_game_ids"]
        self.b.write(ENVELOPE, env)
        cp = self.b.checkpoint
        cp["window"]["expected_game_ids"] = cp["window"]["observed_game_ids"]
        cp["coverage_warnings"] = [{"flag": "envelope_synthetic", "scope": ENVELOPE}]
        for row in cp["rows"]:
            if row["identity_binding"]["status"] == MATCHED:
                row["coverage_state"] = COVERAGE_COMPLETE
                row["coverage_flags"] = ["envelope_synthetic"]
                row["evidence_window"]["games_expected"] = 2
        self.assertEqual(self.b.errors(), [])

    def test_row_coverage_state_must_match_recomputation(self) -> None:
        self.b.row("synthetic-seed-c")["coverage_state"] = COVERAGE_COMPLETE
        self.assertTrue(any("rows[2].coverage_state" in e for e in self.b.errors()))

    def test_identical_observations_across_envelopes_are_coalesced(self) -> None:
        copy_name = "synthetic_envelope_2026_w03_copy.json"
        env = self.b.read(ENVELOPE)
        self.b.files[copy_name] = self.b.files[ENVELOPE]
        ref = copy.deepcopy(self.b.checkpoint["inputs"]["data_envelopes"][0])
        ref["path"] = copy_name
        self.b.checkpoint["inputs"]["data_envelopes"].append(ref)
        self.b.checkpoint["coverage_warnings"] = sorted(
            self.b.checkpoint["coverage_warnings"]
            + [{"flag": "envelope_synthetic", "scope": copy_name}, {"flag": "population_partial", "scope": copy_name}],
            key=lambda w: (w["flag"], w["scope"]),
        )
        self.assertEqual(self.b.errors(), [])
        # Same observation_id with different content is an input defect, not a conflict.
        env["observations"][3]["observed"]["rushing"]["yards"]["value"] = 78
        self.b.files[copy_name] = _dump(env)
        self.b.checkpoint["inputs"]["data_envelopes"][1]["sha256"] = hashlib.sha256(self.b.files[copy_name]).hexdigest()
        errors = self.b.errors()
        self.assertTrue(any(e.startswith("INPUT_CONFLICT") and "synthetic-observation-d-g1-r1" in e for e in errors), errors)
        self.assertFalse(any("rows[3].evidence_change_state" in e and CONFLICTING_EVIDENCE in e for e in errors), errors)
        # A difference in content the pulse does not consume (provenance metadata) is
        # still a different observation and must not be coalesced silently.
        env = self.b.read(ENVELOPE)
        env["observations"][3]["provider"] = "synthetic-provider-b"
        self.b.files[copy_name] = _dump(env)
        self.b.checkpoint["inputs"]["data_envelopes"][1]["sha256"] = hashlib.sha256(self.b.files[copy_name]).hexdigest()
        errors = self.b.errors()
        self.assertTrue(any(e.startswith("INPUT_CONFLICT") and "synthetic-observation-d-g1-r1" in e for e in errors), errors)
        env = self.b.read(ENVELOPE)
        env["observations"][3]["source_snapshot_ref"] = "synthetic-snapshot-other"
        self.b.files[copy_name] = _dump(env)
        self.b.checkpoint["inputs"]["data_envelopes"][1]["sha256"] = hashlib.sha256(self.b.files[copy_name]).hexdigest()
        self.assertTrue(any(e.startswith("INPUT_CONFLICT") for e in self.b.errors()))

    def test_window_must_be_recomputed_from_envelopes(self) -> None:
        self.b.checkpoint["window"]["observed_game_ids"].append({"season": 2026, "source_game_id": "syn-g3"})
        self.assertTrue(any("window.observed_game_ids" in e for e in self.b.errors()))


class CorrectionsAndStates(unittest.TestCase):
    def setUp(self) -> None:
        self.b = Bundle(CURRENT)

    def test_every_prior_observed_game_disappearing_is_conflicting(self) -> None:
        env = self.b.read(ENVELOPE)
        env["observations"] = [o for o in env["observations"] if o["identity"]["canonical_college_player_id"] != "synthetic-college-d"]
        self.b.write(ENVELOPE, env)
        row = self.b.row("synthetic-seed-d")
        self.assertIn("2026:syn-g1", row["prior_observed"])
        row["evidence_change_state"] = "NO_OBSERVED_ROWS"
        row["evidence_window"] = {"games_with_observed_rows": 0, "games_expected": 3, "finality_by_game": {}}
        row["observed"] = {}
        row["delta"] = {}
        errors = self.b.errors()
        self.assertTrue(any("rows[3].evidence_change_state" in e and CONFLICTING_EVIDENCE in e for e in errors), errors)
        row["evidence_change_state"] = CONFLICTING_EVIDENCE
        row["needs_manual_review"] = True
        self.assertEqual(self.b.errors(), [])

    def test_no_observed_rows_without_prior_observations_remains_valid(self) -> None:
        for name, prior_observed in ((PRIOR, None), (CURRENT, {})):
            with self.subTest(checkpoint=name):
                bundle = Bundle(name)
                row = bundle.row("synthetic-seed-e")
                self.assertEqual(row["prior_observed"], prior_observed)
                self.assertEqual(row["evidence_change_state"], "NO_OBSERVED_ROWS")
                self.assertEqual(row["observed"], {})
                self.assertEqual(row["delta"], {})
                self.assertEqual(bundle.errors(), [])

    def test_correction_state_cannot_be_relabelled(self) -> None:
        self.b.row("synthetic-seed-c")["evidence_change_state"] = "NEW_EVIDENCE"
        self.assertTrue(any("rows[2].evidence_change_state" in e and CORRECTED_EVIDENCE in e for e in self.b.errors()))

    def test_difference_is_recomputed(self) -> None:
        self.b.row("synthetic-seed-c")["delta"]["2026:syn-g1"]["passing"]["yards"]["difference"] = 6
        self.assertTrue(any("rows[2].delta" in e for e in self.b.errors()))

    def test_unresolved_source_relationship_forces_conflicting_evidence(self) -> None:
        env = self.b.read(ENVELOPE)
        obs = next(o for o in env["observations"] if o["observation_id"] == "synthetic-observation-c-g1-r2")
        obs["source_relationship"]["status"] = "unresolved"
        obs["source_relationship"]["basis"] = "none"
        self.b.write(ENVELOPE, env)
        errors = self.b.errors()
        self.assertTrue(any("rows[2].evidence_change_state" in e and CONFLICTING_EVIDENCE in e for e in errors), errors)
        row = self.b.row("synthetic-seed-c")
        row["evidence_change_state"] = CONFLICTING_EVIDENCE
        row["evidence_window"] = {"games_with_observed_rows": 2, "games_expected": 3, "finality_by_game": {}}
        row["observed"] = {}
        row["delta"] = {}
        row["needs_manual_review"] = True
        self.assertEqual(self.b.errors(), [])

    def test_insufficient_evidence_has_no_delta(self) -> None:
        self.b.checkpoint["insufficient_evidence_min_games"] = 2
        errors = self.b.errors()
        self.assertTrue(any("rows[3].evidence_change_state" in e and INSUFFICIENT_EVIDENCE in e for e in errors), errors)
        row = self.b.row("synthetic-seed-d")
        row["evidence_change_state"] = INSUFFICIENT_EVIDENCE
        self.assertTrue(any("rows[3].delta" in e and "must be empty" in e for e in self.b.errors()))
        row["delta"] = {}
        self.assertEqual(self.b.errors(), [])

    def test_insufficient_games_cannot_hide_a_competing_prior_revision(self) -> None:
        env = self.b.read(ENVELOPE)
        obs = next(o for o in env["observations"] if o["observation_id"] == "synthetic-observation-d-g1-r1")
        obs["observation_id"] = "synthetic-observation-d-g1-unrelated"
        obs["source_revision_id"] = "synthetic-unrelated-revision"
        self.b.write(ENVELOPE, env)
        row = self.b.row("synthetic-seed-d")
        for cells in row["observed"]["2026:syn-g1"].values():
            for cell in cells.values():
                cell["observation_id"] = obs["observation_id"]
                cell["source_revision_id"] = obs["source_revision_id"]
        self.b.checkpoint["insufficient_evidence_min_games"] = 2
        row["evidence_change_state"] = INSUFFICIENT_EVIDENCE
        row["delta"] = {}
        row["needs_manual_review"] = False
        errors = self.b.errors()
        self.assertTrue(any("rows[3].evidence_change_state" in e and CONFLICTING_EVIDENCE in e for e in errors), errors)
        self.assertTrue(any("rows[3].observed" in e for e in errors), errors)
        self.assertTrue(any("rows[3].evidence_window" in e for e in errors), errors)
        self.assertTrue(any("rows[3].needs_manual_review" in e for e in errors), errors)
        row["evidence_change_state"] = CONFLICTING_EVIDENCE
        row["observed"] = {}
        row["evidence_window"]["finality_by_game"] = {}
        row["needs_manual_review"] = True
        self.assertEqual(self.b.errors(), [])

    def test_delta_without_corrected_lineage_is_not_comparable_and_conflicting(self) -> None:
        env = self.b.read(ENVELOPE)
        obs = next(o for o in env["observations"] if o["observation_id"] == "synthetic-observation-c-g1-r2")
        obs["supersedes"] = None
        obs["source_relationship"] = {"status": "initial", "related_observation_id": None, "basis": "none", "evidence_refs": []}
        env["observations"] = [o for o in env["observations"] if o["observation_id"] != "synthetic-observation-c-g1-r1"]
        self.b.write(ENVELOPE, env)
        errors = self.b.errors()
        # The prior cited r1, which is now neither the leaf nor an ancestor: a competing assertion.
        self.assertTrue(any("rows[2].evidence_change_state" in e and CONFLICTING_EVIDENCE in e for e in errors), errors)


class NullHandling(unittest.TestCase):
    def setUp(self) -> None:
        self.b = Bundle(CURRENT)

    def test_missing_is_not_zero_in_envelope_cells(self) -> None:
        env = self.b.read(ENVELOPE)
        obs = next(o for o in env["observations"] if o["observation_id"] == "synthetic-observation-d-g1-r1")
        obs["observed"]["passing"]["attempts"]["value"] = 0
        self.b.write(ENVELOPE, env)
        self.assertTrue(any("non-observed cell must carry null" in e for e in self.b.errors()))

    def test_checkpoint_cannot_invent_a_zero_for_an_unavailable_cell(self) -> None:
        cell = self.b.row("synthetic-seed-d")["observed"]["2026:syn-g1"]["passing"]["attempts"]
        cell["value"] = 0
        cell["availability"] = "observed_zero"
        self.assertTrue(any("rows[3].observed" in e for e in self.b.errors()))

    def test_prior_observed_must_be_carried_when_a_matched_prior_row_exists(self) -> None:
        self.b.row("synthetic-seed-d")["prior_observed"] = None
        self.assertTrue(any("rows[3].prior_observed" in e for e in self.b.errors()))

    def test_difference_is_null_when_either_side_is_unavailable(self) -> None:
        cell = self.b.row("synthetic-seed-d")["delta"]["2026:syn-g1"]["receiving"]["targets"]
        self.assertIsNone(cell["difference"])
        cell["difference"] = 0
        self.assertTrue(any("rows[3].delta" in e for e in self.b.errors()))

    def test_opportunity_stays_unavailable_without_a_denominator_contract(self) -> None:
        self.b.row("synthetic-seed-c")["opportunity"] = {"status": "available", "reason": "team_totals"}
        self.assertTrue(any(e.startswith("OPPORTUNITY") for e in self.b.errors()))


class ProhibitedOutputsAndGuardrails(unittest.TestCase):
    def setUp(self) -> None:
        self.b = Bundle(CURRENT)

    def test_row_level_score_is_rejected(self) -> None:
        self.b.row("synthetic-seed-c")["signal_score"] = 0.81
        errors = self.b.errors()
        self.assertTrue(any(e.startswith("UNKNOWN_FIELD") and "signal_score" in e for e in errors), errors)
        self.assertTrue(any(e.startswith("PROHIBITED_FIELD") for e in errors), errors)
        self.assertTrue(any(e.startswith("PROHIBITED_NUMERIC") for e in errors), errors)

    def test_opportunity_share_is_rejected(self) -> None:
        self.b.row("synthetic-seed-c")["evidence_window"]["opportunity_share"] = 0.31
        errors = self.b.errors()
        self.assertTrue(any(e.startswith("PROHIBITED_NUMERIC") and "opportunity_share" in e for e in errors), errors)

    def test_top_level_rank_is_rejected(self) -> None:
        self.b.checkpoint["rank"] = 1
        errors = self.b.errors()
        self.assertTrue(any(e.startswith("PROHIBITED_FIELD") and "rank" in e for e in errors), errors)

    def test_seed_watchlist_mutation_is_rejected(self) -> None:
        self.b.row("synthetic-seed-b")["auto_seed_watchlist_mutation"] = "append_to_seed_watchlist"
        self.assertTrue(any(e.startswith("SEED_MUTATION") for e in self.b.errors()))

    def test_proposals_cannot_mutate_seeds(self) -> None:
        self.b.checkpoint["seed_review_proposals"].append({
            "proposal_kind": "add_candidate",
            "seed_player_id": None,
            "evidence_refs": ["synthetic-observation-x-g1-r1"],
            "auto_seed_watchlist_mutation": "append",
            "note": "SYNTHETIC",
        })
        self.assertTrue(any(e.startswith("SEED_MUTATION") and "seed_review_proposals" in e for e in self.b.errors()))

    def test_rows_must_cover_the_pinned_seed_watchlist(self) -> None:
        self.b.checkpoint["rows"].pop()
        self.assertTrue(any("one row per seed" in e for e in self.b.errors()))

    def test_non_seed_rows_are_rejected(self) -> None:
        self.b.checkpoint["rows"].append(unresolved_row("synthetic-seed-z"))
        self.assertTrue(any(e.startswith("ROWS") and "one row per seed" in e for e in self.b.errors()))

    def test_empty_watchlist_requires_an_empty_row_list(self) -> None:
        seeds = self.b.read(SEEDS)
        seeds["prospects"] = []
        self.b.write(SEEDS, seeds)
        self.b.checkpoint["prior_checkpoint"] = None  # the prior's own rows would otherwise fail against the empty watchlist
        errors = self.b.errors()
        self.assertTrue(any(e.startswith("ROWS") and "one row per seed" in e for e in errors), errors)
        # Exact coverage of an empty watchlist is an empty row list; everything else is still validated.
        self.b.checkpoint["rows"] = []
        self.assertEqual(self.b.errors(), [])
        self.b.checkpoint["coverage_warnings"] = []
        self.assertTrue(any("coverage_warnings" in e for e in self.b.errors()))

    def test_context_from_any_source_is_rejected_until_a_qualified_input_exists(self) -> None:
        for source in ("manual", "seed_watchlist", "devy_roster_pulse_v1"):
            with self.subTest(source=source):
                b = Bundle(CURRENT)
                row = b.row("synthetic-seed-c")
                row["context"] = {"source": source, "program_state": "SYNTHETIC program", "roster_status": "program_changed", "class_context": "SYNTHETIC class"}
                row["context_change_state"] = "PROGRAM_CHANGED"
                errors = b.errors()
                self.assertTrue(any(e.startswith("CONTEXT_UNSUPPORTED") and "rows[2].context.source" in e for e in errors), errors)
        # An otherwise null context under a non-none source is rejected too; the source itself is the claim.
        self.b.row("synthetic-seed-c")["context"]["source"] = "manual"
        self.assertTrue(any(e.startswith("CONTEXT_UNSUPPORTED") for e in self.b.errors()))

    def test_context_none_keeps_null_fields_and_unknown_state(self) -> None:
        row = self.b.row("synthetic-seed-c")
        row["context"]["roster_status"] = "still_present"
        self.assertTrue(any("rows[2].context" in e and "entirely null" in e for e in self.b.errors()))
        row["context"]["roster_status"] = None
        row["context_change_state"] = "UNCHANGED"
        self.assertTrue(any("rows[2].context_change_state" in e and "UNKNOWN" in e for e in self.b.errors()))

    def test_tampered_input_fails_on_digest(self) -> None:
        self.b.files[ENVELOPE] = self.b.files[ENVELOPE] + b"\n"
        self.assertTrue(any(e.startswith("INPUT_DIGEST") for e in self.b.errors()))

    def test_promotion_claims_are_rejected(self) -> None:
        self.b.checkpoint["intake_audit"]["promotion_status"] = "promoted"
        self.b.checkpoint["artifact_position"] = "promoted"
        errors = self.b.errors()
        self.assertTrue(any(e.startswith("INTAKE") for e in errors))
        self.assertTrue(any(e.startswith("ARTIFACT_POSITION") for e in errors))


if __name__ == "__main__":
    unittest.main()
