import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_promoted_export import sha256_file, validate_export_manifest


class ValidatePromotedExportTests(unittest.TestCase):
    def _write_contract_files(self, root: Path) -> tuple[Path, Path]:
        combine = root / "data/raw/2026_combine_results.json"
        production = root / "data/processed/2026_college_production.json"
        draft = root / "data/processed/2026_draft_capital_proxy.json"
        combine.parent.mkdir(parents=True, exist_ok=True)
        production.parent.mkdir(parents=True, exist_ok=True)
        draft.parent.mkdir(parents=True, exist_ok=True)

        combine.write_text(json.dumps([{"player_id": "p1"}], indent=2) + "\n", encoding="utf-8")
        production.write_text(json.dumps([{"player_id": "p1"}], indent=2) + "\n", encoding="utf-8")
        draft.write_text(json.dumps([{"player_id": "p1"}], indent=2) + "\n", encoding="utf-8")

        export_path = root / "exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json"
        csv_path = root / "exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.csv"
        manifest_path = root / "exports/promoted/rookie-alpha/2026_manifest.json"
        export_path.parent.mkdir(parents=True, exist_ok=True)

        export_payload = {
            "model": {"model_version": "rookie-alpha-predraft-v0.1.0"},
            "generated_at": "2026-03-25T01:46:12+00:00",
            "run_id": "rookie-alpha-2026-2026-03-25T01:46:12+00:00",
            "season": 2026,
            "coverage_summary": {
                "players_total": 1,
                "players_with_any_missing_input": 0,
                "players_with_full_inputs": 1,
            },
            "source_files_used": [
                "data/raw/2026_combine_results.json",
                "data/processed/2026_college_production.json",
                "data/processed/2026_draft_capital_proxy.json",
            ],
            "players": [],
        }
        export_path.write_text(json.dumps(export_payload, indent=2) + "\n", encoding="utf-8")
        csv_path.write_text(
            "rookie_alpha_rank,player_id,player_name,position,ras_0_100,production_0_100,draft_capital_proxy_0_100,rookie_alpha_0_100,model_inputs_missing\n",
            encoding="utf-8",
        )

        manifest_payload = {
            "season": 2026,
            "model_version": "rookie-alpha-predraft-v0.1.0",
            "generated_at": "2026-03-25T01:46:12+00:00",
            "run_id": "rookie-alpha-2026-2026-03-25T01:46:12+00:00",
            "input_files": [
                {
                    "path": "data/raw/2026_combine_results.json",
                    "sha256": sha256_file(combine),
                    "row_count": 1,
                },
                {
                    "path": "data/processed/2026_college_production.json",
                    "sha256": sha256_file(production),
                    "row_count": 1,
                },
                {
                    "path": "data/processed/2026_draft_capital_proxy.json",
                    "sha256": sha256_file(draft),
                    "row_count": 1,
                },
            ],
            "coverage_summary": {
                "players_total": 1,
                "players_with_any_missing_input": 0,
                "players_with_full_inputs": 1,
            },
            "output_files": [
                {
                    "path": "exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.json",
                    "sha256": sha256_file(export_path),
                },
                {
                    "path": "exports/promoted/rookie-alpha/2026_rookie_alpha_predraft_v0.csv",
                    "sha256": sha256_file(csv_path),
                },
            ],
            "export_metadata": {
                "season": 2026,
                "model_version": "rookie-alpha-predraft-v0.1.0",
                "generated_at": "2026-03-25T01:46:12+00:00",
                "run_id": "rookie-alpha-2026-2026-03-25T01:46:12+00:00",
                "coverage_summary": {
                    "players_total": 1,
                    "players_with_any_missing_input": 0,
                    "players_with_full_inputs": 1,
                },
                "source_files_used": [
                    "data/raw/2026_combine_results.json",
                    "data/processed/2026_college_production.json",
                    "data/processed/2026_draft_capital_proxy.json",
                ],
            },
        }
        manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")
        return (export_path, manifest_path)

    def test_validate_export_manifest_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_path, manifest_path = self._write_contract_files(root)
            errors = validate_export_manifest(export_path, manifest_path)
            self.assertEqual(errors, [])

    def test_validate_export_manifest_detects_metadata_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_path, manifest_path = self._write_contract_files(root)
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_payload["export_metadata"]["run_id"] = "wrong-run-id"
            manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")

            errors = validate_export_manifest(export_path, manifest_path)
            self.assertTrue(any("export_metadata does not exactly match export JSON metadata" in err for err in errors))

    def test_validate_export_manifest_detects_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_path, manifest_path = self._write_contract_files(root)
            export_path.write_text("{}\n", encoding="utf-8")
            errors = validate_export_manifest(export_path, manifest_path)
            self.assertTrue(any("Output hash mismatch" in err for err in errors))


if __name__ == "__main__":
    unittest.main()
