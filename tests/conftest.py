import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Chaque test utilise sa propre base SQLite, jamais data/careops.db."""
    monkeypatch.setenv("CAREOPS_DB", str(tmp_path / "test.db"))
