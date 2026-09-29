import time

from app.db import connect
from tests.conftest import new_player


def start(client, pid, mode="free", difficulty="easy"):
    r = client.get(f"/api/maze?mode={mode}&difficulty={difficulty}", headers={"X-Player-Id": pid})
    assert r.status_code == 200
    return r.get_json()


def age_session(app, token, seconds):
    """서버 시작 시각을 과거로 옮겨 경과 시간을 흉내 낸다."""
    db = connect(app.config["DB_PATH"])
    db.execute("UPDATE sessions SET started_at = started_at - ? WHERE token = ?", (seconds, token))
    db.close()


def min_time(app, token):
    db = connect(app.config["DB_PATH"])
    v = db.execute("SELECT min_time_ms FROM sessions WHERE token = ?", (token,)).fetchone()[0]
    db.close()
    return v


def submit(client, pid, tok, time_ms, **extra):
    body = {"token": tok, "time_ms": time_ms, "torches": 3, "teleports": 1, "explored": 0.5, "lang": "ko"}
    body.update(extra)
    return client.post("/api/runs", json=body, headers={"X-Player-Id": pid})


def test_valid_submission(app, client):
    p = new_player(client)
    m = start(client, p["id"])
    age_session(app, m["token"], 120)
    r = submit(client, p["id"], m["token"], 90_000, path_preview="AAAA")
    assert r.status_code == 200, r.get_json()
    j = r.get_json()
    assert j["rank"] == 1 and j["total"] == 1 and j["top_percent"] == 100.0
    assert j["best"] == 90_000 and j["is_new_best"] is True and j["run_id"]
    runs = client.get(f"/api/players/{p['id']}/runs").get_json()["runs"]
    assert len(runs) == 1 and runs[0]["time_ms"] == 90_000


def test_token_reuse_rejected(app, client):
    p = new_player(client)
    m = start(client, p["id"])
    age_session(app, m["token"], 120)
    assert submit(client, p["id"], m["token"], 90_000).status_code == 200
    r = submit(client, p["id"], m["token"], 80_000)
    assert r.status_code == 400 and r.get_json()["error"] == "token_used"


def test_token_of_other_player_rejected(app, client):
    a, b = new_player(client), new_player(client)
    m = start(client, a["id"])
    age_session(app, m["token"], 120)
    r = submit(client, b["id"], m["token"], 90_000)
    assert r.status_code == 400 and r.get_json()["error"] == "invalid_token"


def test_too_fast_rejected(app, client):
    p = new_player(client)
    m = start(client, p["id"], difficulty="hard")
    age_session(app, m["token"], 3600)
    mt = min_time(app, m["token"])
    r = submit(client, p["id"], m["token"], mt - 1)
    assert r.status_code == 400 and r.get_json()["error"] == "time_below_min"
    # 거부된 제출은 토큰을 소모하지 않는다
    assert submit(client, p["id"], m["token"], mt).status_code == 200


def test_longer_than_server_elapsed_rejected(app, client):
    p = new_player(client)
    m = start(client, p["id"])
    age_session(app, m["token"], 30)
    r = submit(client, p["id"], m["token"], 45_000)
    assert r.status_code == 400 and r.get_json()["error"] == "time_exceeds_server"
    # 2초 여유는 허용
    assert submit(client, p["id"], m["token"], 31_500).status_code == 200


def test_rate_limit(app, client):
    p = new_player(client)
    tokens = []
    for _ in range(11):
        m = start(client, p["id"])
        age_session(app, m["token"], 600)
        tokens.append(m["token"])
    for i in range(10):
        assert submit(client, p["id"], tokens[i], 100_000 + i).status_code == 200
    r = submit(client, p["id"], tokens[10], 100_000)
    assert r.status_code == 429 and r.get_json()["error"] == "rate_limited"


def test_bad_input(app, client):
    p = new_player(client)
    m = start(client, p["id"])
    age_session(app, m["token"], 120)
    for bad in ({"time_ms": "fast"}, {"time_ms": -5}, {"explored": 3}, {"torches": True},
                {"path_preview": "not base64!!"}, {"token": 5}):
        r = submit(client, p["id"], m["token"], 90_000, **bad) if "time_ms" not in bad else \
            client.post("/api/runs", json={"token": m["token"], **bad}, headers={"X-Player-Id": p["id"]})
        assert r.status_code == 400, bad
    assert client.post("/api/runs", data="x", headers={"X-Player-Id": p["id"]}).status_code == 400
    assert submit(client, "not-a-uuid", m["token"], 90_000).status_code == 401


def test_share_and_og(app, client):
    p = new_player(client)
    m = start(client, p["id"])
    age_session(app, m["token"], 120)
    run_id = submit(client, p["id"], m["token"], 95_310, path_preview="VVVV").get_json()["run_id"]
    for lang in ("ko", "en", "zh", "ja"):
        r = client.get(f"/share/{run_id}?lang={lang}")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert f"/og/{run_id}.png?lang={lang}" in html and "1:35.31" in html
        img = client.get(f"/og/{run_id}.png?lang={lang}")
        assert img.status_code == 200 and img.mimetype == "image/png"
        from PIL import Image
        import io
        assert Image.open(io.BytesIO(img.data)).size == (1200, 630)
        d = client.get(f"/og/default.png?lang={lang}")
        assert d.status_code == 200
    assert "미로 인 던전 탈출 1:35.31" in client.get(f"/share/{run_id}?lang=ko").get_data(as_text=True)
    assert client.get("/share/nope!!").status_code == 404
    assert client.get("/og/doesnotexist.png").status_code == 404
