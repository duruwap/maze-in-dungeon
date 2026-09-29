import uuid

from app.boards import player_rank, time_rank
from app.db import connect
from tests.conftest import new_player

BOARD = "free:easy:2026-W40"


def add_run(db, pid, t, board=BOARD):
    db.execute("INSERT INTO runs (id, player_id, board, difficulty, time_ms, torches, teleports, explored, created_at) "
               "VALUES (?, ?, ?, 'easy', ?, 0, 0, 0.5, '2026-09-29T00:00:00Z')", (uuid.uuid4().hex[:12], pid, board, t))


def players(client, n):
    return [new_player(client)["id"] for _ in range(n)]


def test_best_per_player(app, client):
    a, b = players(client, 2)
    db = connect(app.config["DB_PATH"])
    add_run(db, a, 50_000)
    add_run(db, a, 30_000)
    add_run(db, a, 70_000)
    add_run(db, b, 40_000)
    ra = player_rank(db, BOARD, a)
    rb = player_rank(db, BOARD, b)
    assert ra["rank"] == 1 and ra["best"] == 30_000 and ra["total"] == 2
    assert rb["rank"] == 2 and rb["total"] == 2
    lb = client.get(f"/api/leaderboard?board={BOARD}&player_id={a}").get_json()
    assert lb["total"] == 2 and [e["time_ms"] for e in lb["entries"]] == [30_000, 40_000]
    assert lb["entries"][0]["is_me"] and lb["me"]["rank"] == 1 and lb["me"]["in_top"]
    # 다른 보드와 섞이지 않는다
    add_run(db, b, 1_000, board="free:easy:2026-W41")
    assert player_rank(db, BOARD, b)["rank"] == 2


def test_ties_share_rank(app, client):
    a, b, c = players(client, 3)
    db = connect(app.config["DB_PATH"])
    add_run(db, a, 40_000)
    add_run(db, b, 40_000)
    add_run(db, c, 50_000)
    assert player_rank(db, BOARD, a)["rank"] == 1
    assert player_rank(db, BOARD, b)["rank"] == 1
    assert player_rank(db, BOARD, c)["rank"] == 3
    lb = client.get(f"/api/leaderboard?board={BOARD}").get_json()
    assert [e["rank"] for e in lb["entries"]] == [1, 1, 3]


def test_top_percent_and_display_branch(app, client):
    ids = players(client, 20)
    db = connect(app.config["DB_PATH"])
    for i, pid in enumerate(ids[:7]):
        add_run(db, pid, 10_000 * (i + 1))
    r = player_rank(db, BOARD, ids[2])
    assert (r["rank"], r["total"], r["show_percent"]) == (3, 7, False)
    for i, pid in enumerate(ids[7:], start=7):
        add_run(db, pid, 10_000 * (i + 1))
    r = player_rank(db, BOARD, ids[2])
    assert (r["rank"], r["total"], r["show_percent"]) == (3, 20, True)
    assert r["top_percent"] == 15.0
    r = player_rank(db, BOARD, ids[19])
    assert r["top_percent"] == 100.0
    assert time_rank(db, BOARD, 25_000)["rank"] == 3


def test_leaderboard_top100_and_me_outside(app, client):
    ids = players(client, 105)
    db = connect(app.config["DB_PATH"])
    db.execute("BEGIN")
    for i, pid in enumerate(ids):
        add_run(db, pid, 1_000 * (i + 1))
    db.execute("COMMIT")
    lb = client.get(f"/api/leaderboard?board={BOARD}&player_id={ids[-1]}").get_json()
    assert len(lb["entries"]) == 100 and lb["total"] == 105
    assert lb["me"]["rank"] == 105 and lb["me"]["in_top"] is False


def test_leaderboard_validation(client):
    assert client.get("/api/leaderboard?board=daily:bad").status_code == 400
    assert client.get("/api/leaderboard?board=free:xx:2026-W01").status_code == 400
    assert client.get("/api/leaderboard?board=daily").status_code == 200
    assert client.get("/api/leaderboard?board=hard").get_json()["board"].startswith("free:hard:")
    assert client.get("/api/leaderboard?board=daily&player_id=x").status_code == 400


def test_player_numbers_sequential(client):
    a, b = new_player(client), new_player(client)
    assert b["number"] == a["number"] + 1
