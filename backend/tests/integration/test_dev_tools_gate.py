from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, replace_settings
from app.database import configure_database, init_db
from app.main import app


@pytest.fixture(autouse=True)
def restore_settings():
    original = Settings()
    yield
    replace_settings(original)


def _client(tmp_path: Path) -> TestClient:
    configure_database(f"sqlite:///{tmp_path / 'dev_gate.db'}")
    init_db(drop_existing=True)
    return TestClient(app)


def test_dev_seed_works_when_dev_tools_enabled(tmp_path: Path):
    replace_settings(Settings(app_env="development", enable_dev_tools=True))
    client = _client(tmp_path)

    response = client.post("/api/dev/seed-panimalar")

    assert response.status_code == 201
    assert response.json()["verification_summary"]["bundle_status"] == "REVIEW_REQUIRED"


def test_dev_seed_is_blocked_when_dev_tools_disabled(tmp_path: Path):
    replace_settings(Settings(app_env="production", enable_dev_tools=False))
    client = _client(tmp_path)

    response = client.post("/api/dev/seed-panimalar")

    assert response.status_code in {403, 404}
    assert "disabled" in response.text.lower() or "not found" in response.text.lower()
