import pytest


@pytest.fixture(autouse=True)
def _isolated_cfbd_cache(tmp_path, monkeypatch):
    """Keep tests off the operator's local CFBD cache (and out of the repo)."""
    monkeypatch.setenv("CFBD_CACHE_DIR", str(tmp_path / "cfbd_cache"))
