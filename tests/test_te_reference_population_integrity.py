import json
import unittest
from pathlib import Path

TE_DIR = Path("data/historical/te_reference_populations")
WR_DIR = Path("data/historical/wr_reference_populations")


class TeReferencePopulationIntegrityTests(unittest.TestCase):
    """Regression coverage for issue #257: TE reference population files were
    found to contain WR rows with only `position` relabeled to "TE"."""

    def test_te_population_files_are_valid_json_arrays(self) -> None:
        paths = sorted(TE_DIR.glob("*_te_receiving_population.json"))
        self.assertTrue(paths, "expected at least one te_receiving_population.json file")
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsInstance(payload, list, f"{path} must be a JSON array")

    def test_te_population_rows_are_not_copied_from_wr_population(self) -> None:
        for te_path in sorted(TE_DIR.glob("*_te_receiving_population.json")):
            te_rows = json.loads(te_path.read_text(encoding="utf-8"))
            if not te_rows:
                continue

            year = te_path.name.split("_", 1)[0]
            wr_path = WR_DIR / f"{year}_wr_receiving_population.json"
            if not wr_path.exists():
                continue
            wr_rows = json.loads(wr_path.read_text(encoding="utf-8"))
            wr_signatures = {
                (row["player_name"], row["receptions"], row["receiving_yards"], row["receiving_tds"])
                for row in wr_rows
            }

            for row in te_rows:
                signature = (
                    row["player_name"],
                    row["receptions"],
                    row["receiving_yards"],
                    row["receiving_tds"],
                )
                self.assertNotIn(
                    signature,
                    wr_signatures,
                    f"{te_path}: row for {row['player_name']!r} matches a WR reference "
                    "population row with identical stats. TE reference populations must not "
                    "be copied from WR data (see data/historical/te_reference_populations/README.md).",
                )

    def test_te_population_files_are_currently_quarantined(self) -> None:
        """No verified TE population data exists yet (see README.md in this
        directory). Update this test only after populating real, source-verified
        TE rows via scripts/fetch_te_reference_populations.py."""
        for path in sorted(TE_DIR.glob("*_te_receiving_population.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                payload,
                [],
                f"{path} is expected to be empty (quarantined) pending real CFBD TE data",
            )


if __name__ == "__main__":
    unittest.main()
