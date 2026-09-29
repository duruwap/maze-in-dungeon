import json
import math
import time

import pytest

from app.maze.generator import DIFFICULTIES, generate
from app.maze.placement import bfs

N_SEEDS = 1000


def check_maze(m, difficulty):
    p = DIFFICULTIES[difficulty]
    w, h = m["width"], m["height"]
    assert w == h == p["size"]
    assert len(m["tiles"]) == h and all(len(r) == w for r in m["tiles"])
    flat = list("".join(m["tiles"]))
    c = w // 2
    # 탈출 방·출발 광장 위치
    assert m["exit_room"] == {"x": c - 2, "y": c - 2, "w": 5, "h": 5}
    assert m["exit"] == {"x": c, "y": c}
    assert m["door"] == {"x": c, "y": c + 3}
    assert m["start"] == {"x": c, "y": c + 5}
    for y in range(c - 2, c + 3):
        for x in range(c - 2, c + 3):
            assert flat[y * w + x] == "E"
    assert flat[(c + 3) * w + c] == "D"
    for y in range(c + 4, c + 7):
        for x in range(c - 1, c + 2):
            assert flat[y * w + x] == "R"
    # 테두리는 벽
    assert set(m["tiles"][0]) == {"#"} and set(m["tiles"][-1]) == {"#"}
    # 열쇠 수와 구역
    assert len(m["keys"]) == p["keys"]
    assert sorted(k["sector"] for k in m["keys"]) == list(range(p["keys"]))
    for k in m["keys"]:
        assert flat[k["y"] * w + k["x"]] == "R"
    # 텔레포트 수와 간격
    tps = m["teleports"]
    assert len(tps) == 1 + p["keys"] + p["extra_tp"]
    assert tps[0]["active"] and all(not t["active"] for t in tps[1:])
    for i, a in enumerate(tps):
        for b in tps[i + 1:]:
            assert math.hypot(a["x"] - b["x"], a["y"] - b["y"]) >= 8
    # 도달성
    dist = bfs(flat, w, h, (c, c + 5))
    for o in m["keys"] + tps + m["torches"]:
        assert dist[o["y"] * w + o["x"]] >= 0
    assert dist[(c + 4) * w + c] >= 0
    for tr in m["torches"]:
        dx, dy = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0)}[tr["wall"]]
        assert flat[(tr["y"] + dy) * w + tr["x"] + dx] == "#"
    for d in m["decor"]:
        assert flat[d["y"] * w + d["x"]] in ".R"
    assert m["min_time_ms"] > 0


@pytest.mark.parametrize("difficulty", list(DIFFICULTIES))
def test_deterministic(difficulty):
    a = generate("seed-abc", difficulty)
    b = generate("seed-abc", difficulty)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    c = generate("seed-abd", difficulty)
    assert a["tiles"] != c["tiles"]


@pytest.mark.parametrize("difficulty", list(DIFFICULTIES))
def test_many_seeds(difficulty):
    for i in range(N_SEEDS):
        check_maze(generate(f"bulk-{i}", difficulty), difficulty)


def test_hard_generation_time():
    generate("warm", "hard")
    worst = 0
    for i in range(30):
        t = time.perf_counter()
        generate(f"speed-{i}", "hard")
        worst = max(worst, time.perf_counter() - t)
    assert worst < 0.2


def test_maze_api(client):
    from tests.conftest import new_player
    p = new_player(client)
    r = client.get("/api/maze?mode=daily", headers={"X-Player-Id": p["id"]})
    assert r.status_code == 200
    j = r.get_json()
    assert j["difficulty"] == "normal" and j["seed"].startswith("daily-")
    assert j["board"] == "daily:" + j["seed"][6:]
    assert "min_time_ms" not in j and j["token"]
    r2 = client.get("/api/maze?mode=daily", headers={"X-Player-Id": p["id"]}).get_json()
    assert r2["tiles"] == j["tiles"] and r2["token"] != j["token"]
    r = client.get("/api/maze?mode=free&difficulty=hard", headers={"X-Player-Id": p["id"]})
    assert r.get_json()["width"] == 61 and r.get_json()["board"].startswith("free:hard:")
    assert client.get("/api/maze?mode=free&difficulty=xx", headers={"X-Player-Id": p["id"]}).status_code == 400
    assert client.get("/api/maze?mode=daily").status_code == 401
