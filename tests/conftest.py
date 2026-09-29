import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DB_PATH": str(tmp_path / "t.db"),
                       "OG_CACHE_DIR": str(tmp_path / "og")})


@pytest.fixture
def client(app):
    return app.test_client()


def new_player(client):
    r = client.post("/api/player")
    assert r.status_code == 201
    return r.get_json()
