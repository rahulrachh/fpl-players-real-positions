import pytest

from app.mapping import overrides


@pytest.fixture(autouse=True)
def no_override_file(tmp_path, monkeypatch):
    """Tests never read the committed `backend/data/player_overrides.csv`."""
    monkeypatch.setattr(overrides, "OVERRIDES_PATH", tmp_path / "player_overrides.csv")
