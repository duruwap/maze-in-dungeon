"""BFS 도달성 검사와 부정 기록 하한 시간 계산."""
import heapq
import math

from .placement import bfs

# 클라이언트 static/js/config.js 와 같은 값이어야 한다
MOVE_SPEED = 4.5          # 칸/초
SPEED_TOLERANCE = 1.1
INTERACT_REACH = 1.2      # 상호작용 가능 거리(칸)
DOOR_UNLOCK_MS = 0        # 상호작용은 즉시 적용되므로 필수 대기 시간 없음


def _flat(maze):
    return list("".join(maze["tiles"]))


def validate(maze):
    w, h = maze["width"], maze["height"]
    t = _flat(maze)
    s = maze["start"]
    dist = bfs(t, w, h, (s["x"], s["y"]))

    def reach(x, y):
        return dist[y * w + x] >= 0

    for k in maze["keys"]:
        if not reach(k["x"], k["y"]):
            return False, "key_unreachable"
    for tp in maze["teleports"]:
        if not reach(tp["x"], tp["y"]):
            return False, "teleport_unreachable"
    d = maze["door"]
    if t[d["y"] * w + d["x"]] != "D" or not reach(d["x"], d["y"] + 1):
        return False, "door_unreachable"
    # 문이 열렸을 때 출구까지
    dist2 = bfs(t, w, h, (d["x"], d["y"]), passable=("E",))
    e = maze["exit"]
    if dist2[e["y"] * w + e["x"]] < 0:
        return False, "exit_unreachable"
    # 모든 바닥이 하나로 이어져 있는지
    for i, ch in enumerate(t):
        if ch in (".", "R") and dist[i] < 0:
            return False, "island"
    for tr in maze["torches"]:
        if not reach(tr["x"], tr["y"]):
            return False, "torch_unreachable"
    return True, "ok"


def octile_dist(maze, start):
    """8방향(대각선 √2, 모서리 가로지르기 금지) 최단 거리. 연속 이동의 보수적 근사."""
    w, h = maze["width"], maze["height"]
    t = _flat(maze)
    walk = [ch in (".", "R") for ch in t]
    INF = float("inf")
    dist = [INF] * (w * h)
    s = start[1] * w + start[0]
    dist[s] = 0.0
    pq = [(0.0, s)]
    r2 = math.sqrt(2)
    while pq:
        d, i = heapq.heappop(pq)
        if d > dist[i]:
            continue
        for di, cost, a, b in ((-1, 1, 0, 0), (1, 1, 0, 0), (-w, 1, 0, 0), (w, 1, 0, 0),
                               (-w - 1, r2, -w, -1), (-w + 1, r2, -w, 1),
                               (w - 1, r2, w, -1), (w + 1, r2, w, 1)):
            j = i + di
            if not walk[j]:
                continue
            if a and not (walk[i + a] and walk[i + b]):
                continue
            nd = d + cost
            if nd < dist[j]:
                dist[j] = nd
                heapq.heappush(pq, (nd, j))
    return dist


def min_time_ms(maze):
    """부정 기록 하한: 가장 먼 열쇠까지의 거리 ÷ (속도×1.1) + 필수 상호작용 시간.

    텔레포트로 단축 가능한 귀환 경로는 넣지 않는 보수적 하한.
    """
    w = maze["width"]
    s = maze["start"]
    dist = octile_dist(maze, (s["x"], s["y"]))
    far = max(dist[k["y"] * w + k["x"]] for k in maze["keys"])
    far = max(0.0, far - INTERACT_REACH)
    return int(far / (MOVE_SPEED * SPEED_TOLERANCE) * 1000) + DOOR_UNLOCK_MS
