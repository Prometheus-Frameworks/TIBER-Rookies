"""Tests for the 2023 expectation-record freeze mechanism (issue #283)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import freeze_2023_expectation_records as freezer


class TestCommittedFreezeIntegrity(unittest.TestCase):
    """CI-enforced: the committed frozen layers must match their records."""

    def test_committed_records_verify_clean(self) -> None:
        self.assertEqual(freezer.verify(), 0, "A frozen 2023 reconstruction layer was edited without a logged re-freeze")

    def test_records_declare_no_outcomes(self) -> None:
        for _, stem in freezer.PILOTS:
            record = json.loads((freezer.RECORDS / f"{stem}_expectation_record_v0.json").read_text())
            self.assertFalse(record["nfl_outcomes_included"])


class TestFreezeGuard(unittest.TestCase):
    """freeze must not silently re-pin hashes over changed layers."""

    def _seed(self, tmp: Path, card_text: str = '{"card": 1}\n') -> None:
        (tmp / "predraft_cards").mkdir(parents=True)
        (tmp / "landing_context").mkdir(parents=True)
        for _, stem in freezer.PILOTS:
            (tmp / "predraft_cards" / f"{stem}_predraft_v0.json").write_text(card_text)
            (tmp / "landing_context" / f"{stem}_landing_context_v0.json").write_text('{"landing": 1}\n')

    def _patched(self, tmp: Path):
        return patch.multiple(
            freezer,
            CARDS=tmp / "predraft_cards",
            LANDING=tmp / "landing_context",
            RECORDS=tmp / "expectation_records",
        )

    def test_refreeze_without_reason_fails_closed(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            self._seed(tmp)
            with self._patched(tmp):
                freezer.freeze()
                self.assertEqual(freezer.verify(), 0)
                card = tmp / "predraft_cards" / f"{freezer.PILOTS[0][1]}_predraft_v0.json"
                card.write_text('{"card": "edited"}\n')
                self.assertGreater(freezer.verify(), 0)
                with self.assertRaises(SystemExit):
                    freezer.freeze()

    def test_refreeze_with_reason_logs_previous_hashes(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            self._seed(tmp)
            with self._patched(tmp):
                freezer.freeze()
                card = tmp / "predraft_cards" / f"{freezer.PILOTS[0][1]}_predraft_v0.json"
                old_hash = freezer.sha256_of(card)
                card.write_text('{"card": "edited"}\n')
                freezer.freeze(refreeze_reason="test: correcting a sourced defect")
                self.assertEqual(freezer.verify(), 0)
                record = json.loads(
                    (tmp / "expectation_records" / f"{freezer.PILOTS[0][1]}_expectation_record_v0.json").read_text()
                )
                log = record["refreeze_log"]
                self.assertEqual(len(log), 1)
                self.assertEqual(log[0]["reason"], "test: correcting a sourced defect")
                self.assertEqual(log[0]["previous_predraft_card_sha256"], old_hash)

    def test_unchanged_layers_keep_existing_record(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            self._seed(tmp)
            with self._patched(tmp):
                freezer.freeze()
                path = tmp / "expectation_records" / f"{freezer.PILOTS[0][1]}_expectation_record_v0.json"
                before = path.read_text()
                freezer.freeze()
                self.assertEqual(path.read_text(), before, "unchanged layers must not be re-stamped")


if __name__ == "__main__":
    unittest.main()
