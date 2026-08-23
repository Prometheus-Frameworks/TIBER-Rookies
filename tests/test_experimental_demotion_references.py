"""Repository-wide reference control for the demoted ML lane (issue #286, WP-2).

Acceptance condition 10: no operational reference to the old promoted path may
survive, except deliberate migration documentation and negative tests.

That distinction cannot be a prose claim in a PR body — it has to be enforced,
or the next change that reintroduces `exports/promoted/rookie-ml-lane` slides in
unnoticed. This module holds the allowlist and fails on anything outside it.

Two categories are allowed to mention the old path:

* **Deliberate migration documentation and negative tests** — files whose whole
  purpose is to record or police the move. Listed in ALLOWED_REFERENCES.
* **Dated historical records** — audits and reports that describe repository
  state at an earlier point in time, several pinned to specific base commits.
  Rewriting them to reference the new path would falsify the record they exist
  to preserve, so they are left byte-unchanged. Listed in HISTORICAL_RECORDS.

Anything else mentioning the old path is an operational reference and fails.
"""

import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

OLD_PROMOTED_PATH = "exports/promoted/rookie-ml-lane"
NEW_EXPERIMENTAL_PATH = "exports/experimental/rookie-ml-lane"

# Files whose purpose is to record or police the demotion.
ALLOWED_REFERENCES = {
    "docs/migrations/2026-08-23-rookie-ml-lane-demotion.md",
    "exports/experimental/rookie-ml-lane/experimental_status_v0.json",
    "scripts/validate_experimental_integrity.py",
    "tests/test_compute_rookie_ml_lane.py",
    "tests/test_experimental_demotion_references.py",
    "tests/test_validate_experimental_integrity.py",
}

# Point-in-time records. Each describes repository state on a stated date, and
# several are pinned to a base commit; they are deliberately not rewritten.
HISTORICAL_RECORDS = {
    "docs/audits/2023-input-integrity-remediation.json",
    "docs/audits/2023-input-integrity-remediation.md",
    "docs/repo-state-audit-2026-postdraft.md",
    "docs/reports/2026-07-08-machine-readable-artifact-audit.md",
}


def tracked_files_mentioning(needle: str) -> set[str]:
    """Every git-tracked file containing `needle`, as repo-relative POSIX paths."""
    result = subprocess.run(
        # --untracked so a new file is policed before it is ever staged.
        ["git", "grep", "-l", "--fixed-strings", "--untracked", needle],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    # git grep exits 1 when there are no matches, which is not an error here.
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git grep failed: {result.stderr}")
    return {line for line in result.stdout.splitlines() if line}


class OldPromotedPathReferenceTests(unittest.TestCase):
    def test_no_unclassified_reference_to_the_old_promoted_path(self) -> None:
        referencing = tracked_files_mentioning(OLD_PROMOTED_PATH)
        unexpected = referencing - ALLOWED_REFERENCES - HISTORICAL_RECORDS
        self.assertEqual(
            unexpected,
            set(),
            "Operational reference(s) to the demoted promoted path found. Either point "
            "them at exports/experimental/rookie-ml-lane, or, if this is a dated "
            "historical record, add it to HISTORICAL_RECORDS with justification: "
            f"{sorted(unexpected)}",
        )

    def test_allowlists_have_no_stale_entries(self) -> None:
        """A cleaned-up file must not keep a standing licence to reference the old path."""
        referencing = tracked_files_mentioning(OLD_PROMOTED_PATH)
        for path in sorted(ALLOWED_REFERENCES | HISTORICAL_RECORDS):
            with self.subTest(path=path):
                self.assertIn(
                    path,
                    referencing,
                    f"{path} is allowlisted but no longer references the old path; "
                    f"remove the stale allowlist entry.",
                )

    def test_allowlists_are_disjoint(self) -> None:
        self.assertEqual(ALLOWED_REFERENCES & HISTORICAL_RECORDS, set())

    def test_historical_records_are_not_code(self) -> None:
        """Only documentation may sit in the historical-record exemption."""
        for path in sorted(HISTORICAL_RECORDS):
            with self.subTest(path=path):
                self.assertTrue(
                    path.startswith("docs/"),
                    f"{path} is exempted as a historical record but is not documentation",
                )

    def test_the_old_promoted_directory_does_not_exist(self) -> None:
        self.assertFalse((REPO_ROOT / OLD_PROMOTED_PATH).exists())

    def test_live_documentation_points_at_the_experimental_path(self) -> None:
        """Acceptance condition 2, for the docs a reader actually navigates by."""
        for relative in ("README.md", "AGENTS.md", "docs/source-of-truth-audit.md"):
            with self.subTest(doc=relative):
                text = (REPO_ROOT / relative).read_text(encoding="utf-8")
                self.assertNotIn(
                    OLD_PROMOTED_PATH,
                    text,
                    f"{relative} still classifies the ML lane as promoted",
                )

    def test_producer_default_output_is_not_a_promoted_path(self) -> None:
        """Acceptance condition 3, read off the producer itself."""
        from scripts.compute_rookie_ml_lane import DEFAULT_OUTPUT_DIR

        self.assertNotIn("exports/promoted", DEFAULT_OUTPUT_DIR)

    def test_producer_default_output_is_not_the_frozen_archive(self) -> None:
        """The documented default must not target the immutable archive.

        Pointing the producer at NEW_EXPERIMENTAL_PATH would make the documented
        command overwrite the frozen historical bytes on every run.
        """
        from scripts.compute_rookie_ml_lane import DEFAULT_OUTPUT_DIR

        self.assertNotEqual(DEFAULT_OUTPUT_DIR, NEW_EXPERIMENTAL_PATH)
        self.assertFalse(DEFAULT_OUTPUT_DIR.startswith("exports/"))

    def test_generated_run_destination_is_not_committed(self) -> None:
        """Run output must be gitignored, so a run can never become an export by accident."""
        from scripts.compute_rookie_ml_lane import DEFAULT_OUTPUT_DIR

        result = subprocess.run(
            ["git", "check-ignore", DEFAULT_OUTPUT_DIR],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0, f"{DEFAULT_OUTPUT_DIR} is not gitignored: {result.stderr}"
        )


if __name__ == "__main__":
    unittest.main()
