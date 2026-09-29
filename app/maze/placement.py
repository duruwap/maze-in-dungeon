"""구역 분할과 오브젝트(열쇠/텔레포트/횃불/장식) 배치."""
import math
from collections import deque

from .generator import (CORR, DIFFICULTIES, ROOM, WALL,
                        center_of, reserved_bounds)

KEY_COLORS = ("red", "blue", "green", "yellow")
TELEPORT_MIN_GAP = 8.0
TORCH_PRIORITY_GAP = 5.0
TORCH_FILL_GAP = 8.5
DECOR_RATE = 0.07
DECOR_KINDS = ("pebbles", "bones", "puddle", "rune", "cobweb")


def bfs(tiles, w, h, start, passable=(CORR, ROOM)):
    """4방향 BFS 거리 (평면 리스트, 도달 불가 = -1)."""
    dist = [-1] * (w * h)
    s = start[1] * w + start[0]
    dist[s] = 0
    q = deque([s])
    while q:
        i = q.popleft()
        d = dist[i] + 1
        for k in (i - 1, i + 1, i - w, i + w):
            if dist[k] == -1 and tiles[k] in passable:
                dist[k] = d
                q.append(k)
    return dist


def _pick_in_band(rng, cands, dist, maxd, lo, hi):
    band = [i for i in cands if lo * maxd <= dist[i] <= hi * maxd]
    if band:
        return band
    # 범위가 비면 점점 넓힌다
    for lo2 in (lo - 0.1, lo - 0.2, lo - 0.3):
        band = [i for i in cands if lo2 * maxd <= dist[i] <= min(1.0, hi + 0.1) * maxd]
        if band:
            return band
    return list(cands)


def _far_enough(i, w, others, gap):
    x, y = i % w, i // w
    for (ox, oy) in others:
        if math.hypot(x - ox, y - oy) < gap:
            return False
    return True


def place_objects(g, rooms, rng, difficulty):
    p = DIFFICULTIES[difficulty]
    w, h, t = g.w, g.h, g.t
    c = center_of(w)
    n_sec = p["keys"]
    start = (c, c + 5)
    door = (c, c + 3)
    exit_ = (c, c)
    dist = bfs(t, w, h, start)
    rx0, ry0, rx1, ry1 = reserved_bounds(w)

    sector_tiles = [[] for _ in range(n_sec)]
    for i in range(w * h):
        s = g.sector[i]
        if s >= 0 and dist[i] >= 0:
            sector_tiles[s].append(i)
    if any(not tl for tl in sector_tiles):
        return None
    sector_max = [max(dist[i] for i in tl) for tl in sector_tiles]

    occupied = set()
    # --- 열쇠: 구역마다 1개, 방 안 칸, BFS 거리 60~90% ---
    keys = []
    for s in range(n_sec):
        room_cells = [i for i in sector_tiles[s] if t[i] == ROOM]
        if not room_cells:
            return None
        band = _pick_in_band(rng, room_cells, dist, sector_max[s], 0.6, 0.9)
        i = rng.choice(sorted(band))
        occupied.add(i)
        keys.append({"id": s, "color": KEY_COLORS[s], "x": i % w, "y": i // w, "sector": s})

    # --- 텔레포트: 광장 1 + 구역마다 1 + 경계 추가분, 서로 8칸 이상 ---
    tp_pos = [(c, c + 6)]
    teleports = [{"id": 0, "x": c, "y": c + 6, "active": True}]
    occupied.add((c + 6) * w + c)
    for s in range(n_sec):
        cands = [i for i in sector_tiles[s] if i not in occupied]
        band = _pick_in_band(rng, cands, dist, sector_max[s], 0.4, 0.7)
        band = [i for i in band if _far_enough(i, w, tp_pos, TELEPORT_MIN_GAP)]
        if not band:
            band = [i for i in cands if _far_enough(i, w, tp_pos, TELEPORT_MIN_GAP)]
        if not band:
            return None
        i = rng.choice(sorted(band))
        occupied.add(i)
        tp_pos.append((i % w, i // w))
        teleports.append({"id": len(teleports), "x": i % w, "y": i // w, "active": False})

    if p["extra_tp"]:
        gmax = max(sector_max)
        boundary = []
        for s in range(n_sec):
            for i in sector_tiles[s]:
                if i in occupied or dist[i] < 0.3 * gmax:
                    continue
                x, y = i % w, i // w
                near = False
                for yy in range(max(0, y - 3), min(h, y + 4)):
                    for xx in range(max(0, x - 3), min(w, x + 4)):
                        s2 = g.sector[yy * w + xx]
                        if s2 >= 0 and s2 != s:
                            near = True
                            break
                    if near:
                        break
                if near:
                    boundary.append(i)
        rng.shuffle(boundary)
        added = 0
        for i in boundary:
            if added >= p["extra_tp"]:
                break
            if _far_enough(i, w, tp_pos, TELEPORT_MIN_GAP):
                occupied.add(i)
                tp_pos.append((i % w, i // w))
                teleports.append({"id": len(teleports), "x": i % w, "y": i // w, "active": False})
                added += 1
        if added < p["extra_tp"]:
            return None

    # --- 횃불: 벽에 붙은 칸, 갈림길/방 입구 우선, 서로 5칸 이상 ---
    def walk(i):
        return t[i] in (CORR, ROOM)

    def wall_dirs(i):
        out = []
        for d, k in (("N", i - w), ("E", i + 1), ("W", i - 1), ("S", i + w)):
            if t[k] == WALL:
                out.append(d)
        return out

    priority, normal = [], []
    for i in range(w * h):
        if not walk(i) or dist[i] < 0 or i in occupied:
            continue
        x, y = i % w, i // w
        if rx0 <= x <= rx1 and ry0 <= y <= ry1:
            continue   # 중앙 블록(광장)은 제외
        wd = wall_dirs(i)
        if not wd:
            continue
        n_open = sum(1 for k in (i - 1, i + 1, i - w, i + w) if walk(k))
        entrance = False
        if t[i] == ROOM:
            for k in (i - 1, i + 1, i - w, i + w):
                if t[k] == CORR:
                    entrance = True
        if n_open >= 3 and t[i] == CORR or entrance:
            priority.append(i)
        elif t[i] == CORR:
            normal.append(i)
    rng.shuffle(priority)
    rng.shuffle(normal)
    torches, torch_pos = [], []

    def add_torch(i):
        wd = wall_dirs(i)
        if "N" in wd:
            d = "N"
        else:
            d = rng.choice(wd)
        torches.append({"x": i % w, "y": i // w, "wall": d})
        torch_pos.append((i % w, i // w))
        occupied.add(i)

    for i in priority:
        if _far_enough(i, w, torch_pos, TORCH_PRIORITY_GAP):
            add_torch(i)
    for i in normal:
        if _far_enough(i, w, torch_pos, TORCH_FILL_GAP):
            add_torch(i)
    torches.sort(key=lambda o: (o["y"], o["x"]))

    # --- 장식: 이동을 막지 않는 바닥 소품 ---
    decor = []
    blocked = set(occupied)
    blocked.add(start[1] * w + start[0])
    blocked.add((door[1] + 1) * w + door[0])
    for i in range(w * h):
        if t[i] not in (CORR, ROOM) or i in blocked:
            continue
        if rng.random() >= DECOR_RATE:
            continue
        x, y = i % w, i // w
        corner = t[i - w] == WALL and (t[i - 1] == WALL or t[i + 1] == WALL)
        kinds = ["pebbles", "pebbles", "bones", "puddle"]
        if t[i] == ROOM:
            kinds += ["rune", "bones"]
        if corner:
            kinds += ["cobweb", "cobweb", "cobweb"]
        decor.append({"x": x, "y": y, "kind": rng.choice(kinds)})

    return {
        "width": w, "height": h,
        "tiles": g.rows(),
        "start": {"x": start[0], "y": start[1]},
        "exit_room": {"x": c - 2, "y": c - 2, "w": 5, "h": 5},
        "door": {"x": door[0], "y": door[1]},
        "exit": {"x": exit_[0], "y": exit_[1]},
        "keys": keys,
        "teleports": teleports,
        "torches": torches,
        "decor": decor,
        "floor_variant_seed": rng.randrange(1, 2 ** 31),
    }
