from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import configure_database, init_db
from app.main import app


@pytest.fixture()
def client(tmp_path: Path):
    configure_database(f"sqlite:///{tmp_path / 'order_assurance_test.db'}")
    init_db(drop_existing=True)
    return TestClient(app)


def test_cors_exposes_content_disposition_for_browser_downloads(client: TestClient):
    response = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5180"})

    assert response.status_code == 200
    assert response.headers["access-control-expose-headers"] == "Content-Disposition"
