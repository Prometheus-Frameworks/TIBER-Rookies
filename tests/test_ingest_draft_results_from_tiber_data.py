"""Tests for scripts/ingest_draft_results_from_tiber_data.py

Covers:
- Valid canonical artifact ingestion and field mapping
- fixture_only rows are rejected unconditionally
- player_id=null rows are skipped
- needs_verification rows are accepted with a warning flag
- Missing upstream file fails closed
- Empty upstream array fails closed
- Zero accepted rows after filtering fails closed (no output written)
- draft_day derivation
- is_udfa is always False for drafted players
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.ingest_draft_results_from_tiber_data import (
    ingest,
    load_upstream,
    map_row,
    normalize_team_name,
    validate_row,
)

FIXTURE_PATH = REPO_ROOT / "data" / "fixtures" / "nfl_draft_results_v1_fixture.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_row(**overrides) -> dict:
    base = {
        "draft_year": 2026,
        "player_id": "wr-test-player",
        "player_name": "Test Player",
        "position": "WR",
        "team": "Kansas City Chiefs",
        "round": 1,
        "pick_in_round": 10,
        "overall_pick": 10,
        "source": "Test source",
        "source_url": None,
        "generated_at": "2026-05-16T00:00:00+00:00",
        "provenance_status": "source_verified",
    }
    return {**base, **overrides}


# ---------------------------------------------------------------------------
# normalize_team_name
# ---------------------------------------------------------------------------

class TestNormalizeTeamName:
    def test_simple_full_name(self):
        assert normalize_team_name("Kansas City Chiefs") == "KC"

    def test_trade_notation_stripped(self):
        assert normalize_team_name("Los Angeles Rams from Atlanta Falcons") == "LAR"

    def test_trade_notation_acquiring_team_used(self):
        assert normalize_team_name("Cleveland Browns from Jacksonville Jaguars") == "CLE"

    def test_new_york_jets_from_colts(self):
        assert normalize_team_name("New York Jets from Indianapolis Colts") == "NYJ"

    def test_all_32_teams_map_without_error(self):
        from scripts.ingest_draft_results_from_tiber_data import _NFL_TEAM_FULL_TO_ABBREV
        for full_name, abbrev in _NFL_TEAM_FULL_TO_ABBREV.items():
            assert normalize_team_name(full_name) == abbrev
            assert len(abbrev) in (2, 3)

    def test_unknown_team_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown team name"):
            normalize_team_name("Fictional City Team")

    def test_unknown_team_in_trade_notation_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown team name"):
            normalize_team_name("Fictional City Team from Kansas City Chiefs")


# ---------------------------------------------------------------------------
# validate_row
# ---------------------------------------------------------------------------

class TestValidateRow:
    def test_valid_source_verified_row_passes(self):
        assert validate_row(make_row(), 0) is None

    def test_fixture_only_is_rejected(self):
        reason = validate_row(make_row(provenance_status="fixture_only"), 0)
        assert reason is not None
        assert "fixture_only" in reason

    def test_null_player_id_is_skipped(self):
        reason = validate_row(make_row(player_id=None, provenance_status="source_verified_player_id_unresolved"), 0)
        assert reason is not None
        assert "null" in reason

    def test_needs_verification_passes(self):
        assert validate_row(make_row(provenance_status="needs_verification"), 0) is None

    def test_unknown_provenance_is_rejected(self):
        reason = validate_row(make_row(provenance_status="invented_status"), 0)
        assert reason is not None

    def test_invalid_round_is_rejected(self):
        reason = validate_row(make_row(round=0), 0)
        assert reason is not None

    def test_invalid_overall_pick_is_rejected(self):
        reason = validate_row(make_row(overall_pick=-1), 0)
        assert reason is not None

    def test_missing_team_is_rejected(self):
        reason = validate_row(make_row(team=""), 0)
        assert reason is not None


# ---------------------------------------------------------------------------
# map_row
# ---------------------------------------------------------------------------

class TestMapRow:
    def test_field_mapping(self):
        row = make_row(round=2, team="San Francisco 49ers", overall_pick=42)
        mapped = map_row(row, 2026)

        assert mapped["draft_round"] == 2
        assert mapped["nfl_team"] == "SF"
        assert mapped["overall_pick"] == 42
        assert mapped["player_id"] == "wr-test-player"
        assert mapped["is_udfa"] is False
        assert mapped["draft_result_status"] == "drafted"
        assert mapped["ingested_from"] == "tiber_data_nfl_draft_results_v1"
        assert mapped["upstream_provenance_status"] == "source_verified"

    def test_source_verified_maps_to_external_verified_status(self):
        mapped = map_row(make_row(provenance_status="source_verified"), 2026)
        assert mapped["source_status"] == "external_verified"

    def test_needs_verification_maps_to_needs_verification_status(self):
        mapped = map_row(make_row(provenance_status="needs_verification"), 2026)
        assert mapped["source_status"] == "needs_verification"

    def test_is_udfa_always_false(self):
        # Drafted players from this artifact are never UDFA
        for round_num in range(1, 8):
            mapped = map_row(make_row(round=round_num, overall_pick=round_num * 10), 2026)
            assert mapped["is_udfa"] is False

    def test_draft_day_round_1(self):
        mapped = map_row(make_row(round=1), 2026)
        assert mapped["draft_day"] == 1

    def test_draft_day_round_2(self):
        mapped = map_row(make_row(round=2, overall_pick=50), 2026)
        assert mapped["draft_day"] == 2

    def test_draft_day_round_3(self):
        mapped = map_row(make_row(round=3, overall_pick=80), 2026)
        assert mapped["draft_day"] == 2

    def test_draft_day_round_4_and_later(self):
        for round_num in range(4, 8):
            mapped = map_row(make_row(round=round_num, overall_pick=round_num * 30), 2026)
            assert mapped["draft_day"] == 3

    def test_player_id_normalized_to_lowercase(self):
        mapped = map_row(make_row(player_id="WR-Mixed-Case-Player"), 2026)
        assert mapped["player_id"] == "wr-mixed-case-player"


# ---------------------------------------------------------------------------
# ingest (integration-level, using fixture file)
# ---------------------------------------------------------------------------

class TestIngest:
    def test_fixture_file_exists(self):
        assert FIXTURE_PATH.exists(), f"Fixture not found: {FIXTURE_PATH}"

    def test_fixture_produces_expected_output(self):
        output, stats = ingest(FIXTURE_PATH, 2026)
        # Fixture has 5 rows:
        #   1 source_verified WR (accepted)
        #   1 source_verified RB (accepted)
        #   1 source_verified_player_id_unresolved TE w/ null id (skipped)
        #   1 needs_verification QB (accepted with warning)
        #   1 fixture_only WR (rejected)
        assert stats["accepted"] == 3
        assert stats["skipped_fixture"] == 1
        assert stats["skipped_null_id"] == 1
        assert stats["warned"] == 1
        assert len(output) == 3

    def test_no_fixture_only_rows_in_output(self):
        output, _ = ingest(FIXTURE_PATH, 2026)
        for row in output:
            assert row.get("upstream_provenance_status") != "fixture_only"

    def test_no_null_player_id_in_output(self):
        output, _ = ingest(FIXTURE_PATH, 2026)
        for row in output:
            assert row["player_id"] is not None
            assert row["player_id"] != ""

    def test_all_output_rows_have_is_udfa_false(self):
        output, _ = ingest(FIXTURE_PATH, 2026)
        for row in output:
            assert row["is_udfa"] is False

    def test_all_output_rows_have_required_fields(self):
        output, _ = ingest(FIXTURE_PATH, 2026)
        required = {"player_id", "nfl_team", "draft_round", "overall_pick", "is_udfa",
                    "draft_result_status", "source_status", "ingested_from"}
        for row in output:
            assert required.issubset(row.keys()), f"Missing fields in: {row}"


# ---------------------------------------------------------------------------
# Fail-closed behaviour
# ---------------------------------------------------------------------------

class TestFailClosed:
    def test_missing_upstream_file_exits(self, tmp_path):
        missing = tmp_path / "does_not_exist.json"
        with pytest.raises(SystemExit) as exc_info:
            load_upstream(missing)
        assert exc_info.value.code != 0

    def test_empty_upstream_array_exits(self, tmp_path):
        empty = tmp_path / "empty.json"
        empty.write_text("[]", encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            load_upstream(empty)
        assert exc_info.value.code != 0

    def test_all_fixture_only_rows_yields_zero_accepted(self, tmp_path):
        all_fixture = [
            {**make_row(player_id=f"wr-player-{i}"), "provenance_status": "fixture_only"}
            for i in range(3)
        ]
        path = tmp_path / "all_fixture.json"
        path.write_text(json.dumps(all_fixture), encoding="utf-8")
        output, stats = ingest(path, 2026)
        assert stats["accepted"] == 0
        assert len(output) == 0

    def test_non_array_upstream_exits(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text('{"not": "an array"}', encoding="utf-8")
        with pytest.raises(SystemExit) as exc_info:
            load_upstream(bad)
        assert exc_info.value.code != 0
