"""Rooms and Mazes 생성기.

방을 먼저 배치하고 남은 공간을 Growing Tree로 채운 뒤, 방을 통로와 연결하고
막다른 길 일부를 뚫어 순환로를 만든다(브레이딩). 모든 무작위는 시드 하나에서
파생된 random.Random 으로 처리하므로 같은 시드는 항상 같은 맵을 만든다.
"""
import math
import random
from collections import OrderedDict

WALL, CORR, ROOM, EXIT, DOOR = "#", ".", "R", "E", "D"
WALKABLE = frozenset((CORR, ROOM, EXIT, DOOR))

DIFFICULTIES = {
    "easy":   {"keys": 2, "size": 25, "rooms": (2, 3), "braid": 0.20, "extra_tp": 0},
    "normal": {"keys": 3, "size": 41, "rooms": (3, 4), "braid": 0.15, "extra_tp": 1},
    "hard":   {"keys": 4, "size": 61, "rooms": (4, 6), "braid": 0.10, "extra_tp": 2},
}

ROOM_SIZES = (3, 3, 5, 5, 5, 7)
GROWING_TREE_NEWEST = 0.75
MAX_RETRIES = 20


class Grid:
    """평면 리스트 기반 격자. idx = y * w + x."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.t = [WALL] * (w * h)
        self.reserved = bytearray(w * h)   # 중앙 탈출 방/광장 블록 (미로가 침범 금지)
        self.room_id = [-1] * (w * h)       # 방 번호 (광장 포함)
        self.sector = [-1] * (w * h)

    def idx(self, x, y):
        return y * self.w + x

    def get(self, x, y):
        return self.t[y * self.w + x]

    def set(self, x, y, v):
        self.t[y * self.w + x] = v

    def inside(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def rows(self):
        w = self.w
        return ["".join(self.t[y * w:(y + 1) * w]) for y in range(self.h)]


def center_of(size):
    return size // 2


def sector_of(difficulty, size, x, y):
    """구역 번호. 중앙 블록은 -1 로 따로 처리한다."""
    c = center_of(size)
    if difficulty == "easy":
        return 0 if x < c else 1
    if difficulty == "hard":
        west = x < c
        north = y < c
        if north:
            return 0 if west else 1
        return 2 if not west else 3
    # normal: 중앙 기준 120도씩. 0=북, 1=남동, 2=남서 (광장 출구인 남쪽이 1/2 경계)
    ang = math.degrees(math.atan2(y - c, x - c))
    if -150 <= ang < -30:
        return 0
    if -30 <= ang < 90:
        return 1
    return 2


def reserved_bounds(size):
    """중앙 블록 (탈출 방 + 벽 + 출발 광장 + 벽) 경계 (포함)."""
    c = center_of(size)
    return c - 3, c - 3, c + 3, c + 7


def carve_center(g, c):
    x0, y0, x1, y1 = reserved_bounds(g.w)
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            g.reserved[g.idx(x, y)] = 1
    # 탈출 방 5x5 (내부)
    for y in range(c - 2, c + 3):
        for x in range(c - 2, c + 3):
            g.set(x, y, EXIT)
    # 문: 남쪽 벽 중앙
    g.set(c, c + 3, DOOR)
    # 출발 광장 3x3
    for y in range(c + 4, c + 7):
        for x in range(c - 1, c + 2):
            g.set(x, y, ROOM)
            g.room_id[g.idx(x, y)] = 0


def plaza_tunnels(c):
    """광장에서 서/동/남으로 뻗는 고정 통로 칸."""
    return [
        [(c - 2, c + 5), (c - 3, c + 5), (c - 4, c + 5)],
        [(c + 2, c + 5), (c + 3, c + 5), (c + 4, c + 5)],
        [(c, c + 7), (c, c + 8), (c, c + 9)],
    ]


def place_rooms(g, rng, difficulty, n_sectors, room_range):
    """구역마다 겹치지 않는 방을 배치. 반환: [(x, y, w, h, sector)]"""
    size = g.w
    rx0, ry0, rx1, ry1 = reserved_bounds(size)
    rooms = []

    def overlaps(x, y, w, h):
        # 방끼리, 중앙 블록과는 2칸 이상 떨어뜨려 사이에 통로 칸이 남게 한다
        for (ox, oy, ow, oh, _s) in rooms:
            if x <= ox + ow + 1 and ox <= x + w + 1 and y <= oy + oh + 1 and oy <= y + h + 1:
                return True
        if x <= rx1 + 2 and rx0 - 2 <= x + w - 1 and y <= ry1 + 2 and ry0 - 2 <= y + h - 1:
            return True
        return False

    for s in range(n_sectors):
        target = rng.randint(*room_range)
        placed = 0
        for attempt in range(400):
            if placed >= target:
                break
            # 여러 번 실패하면 작은 방으로 재시도
            if attempt > 250:
                w = h = 3
            else:
                w, h = rng.choice(ROOM_SIZES), rng.choice(ROOM_SIZES)
            x = rng.randrange(1, size - w, 2)
            y = rng.randrange(1, size - h, 2)
            if x + w > size - 1 or y + h > size - 1:
                continue
            if overlaps(x, y, w, h):
                continue
            ok = True
            for yy in (y, y + h - 1):
                for xx in range(x, x + w):
                    if sector_of(difficulty, size, xx, yy) != s:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                for xx in (x, x + w - 1):
                    for yy in range(y, y + h):
                        if sector_of(difficulty, size, xx, yy) != s:
                            ok = False
                            break
                    if not ok:
                        break
            if not ok:
                continue
            rooms.append((x, y, w, h, s))
            placed += 1
    for rid, (x, y, w, h, _s) in enumerate(rooms, start=1):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                g.set(xx, yy, ROOM)
                g.room_id[g.idx(xx, yy)] = rid
    return rooms


def growing_tree(g, rng):
    """방/중앙 블록이 아닌 홀수 격자 칸을 Growing Tree 로 채운다."""
    w, h = g.w, g.h
    t, reserved = g.t, g.reserved
    dirs = ((0, -2), (2, 0), (0, 2), (-2, 0))

    def free(x, y):
        if x < 1 or y < 1 or x > w - 2 or y > h - 2:
            return False
        i = y * w + x
        return t[i] == WALL and not reserved[i]

    for sy in range(1, h - 1, 2):
        for sx in range(1, w - 1, 2):
            if not free(sx, sy):
                continue
            t[sy * w + sx] = CORR
            cells = [(sx, sy)]
            while cells:
                if rng.random() < GROWING_TREE_NEWEST:
                    ci = len(cells) - 1
                else:
                    ci = rng.randrange(len(cells))
                cx, cy = cells[ci]
                opts = [(dx, dy) for dx, dy in dirs if free(cx + dx, cy + dy)]
                if not opts:
                    cells.pop(ci)
                    continue
                dx, dy = rng.choice(opts)
                t[(cy + dy // 2) * w + cx + dx // 2] = CORR
                t[(cy + dy) * w + cx + dx] = CORR
                cells.append((cx + dx, cy + dy))


class DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        p = self.p
        while p[a] != a:
            p[a] = p[p[a]]
            a = p[a]
        return a

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[b] = a
            return True
        return False


def label_components(g):
    """탈출 방/문을 제외한 보행 가능 칸의 연결 요소 라벨."""
    w, h, t = g.w, g.h, g.t
    comp = [-1] * (w * h)
    n = 0
    for i in range(w * h):
        if comp[i] != -1 or t[i] not in (CORR, ROOM):
            continue
        comp[i] = n
        stack = [i]
        while stack:
            j = stack.pop()
            for k in (j - 1, j + 1, j - w, j + w):
                if comp[k] == -1 and t[k] in (CORR, ROOM):
                    comp[k] = n
                    stack.append(k)
        n += 1
    return comp, n


def find_connectors(g, comp):
    """서로 다른 요소 사이의 벽 한 칸. 반환: [(idx, compA, compB)]"""
    w, h, t, reserved = g.w, g.h, g.t, g.reserved
    out = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            i = y * w + x
            if t[i] != WALL or reserved[i]:
                continue
            for a, b in ((i - 1, i + 1), (i - w, i + w)):
                ca, cb = comp[a], comp[b]
                if ca != -1 and cb != -1 and ca != cb:
                    out.append((i, ca, cb))
                    break
    return out


def connect_regions(g, rng, rooms):
    c = center_of(g.w)
    w = g.w
    # 광장 고정 통로
    for tunnel in plaza_tunnels(c):
        for (x, y) in tunnel:
            g.set(x, y, CORR)

    comp, n = label_components(g)
    dsu = DSU(n)
    connectors = find_connectors(g, comp)
    entrances = [0] * (len(rooms) + 1)

    def room_of_connector(i):
        rs = set()
        for k in (i - 1, i + 1, i - w, i + w):
            r = g.room_id[k]
            if r > 0:
                rs.add(r)
        return rs

    # 1) 방마다 출입구 1~3개
    by_room = {}
    for item in connectors:
        for r in room_of_connector(item[0]):
            by_room.setdefault(r, []).append(item)
    opened = set()
    for rid in range(1, len(rooms) + 1):
        cands = by_room.get(rid, [])
        if not cands:
            continue
        rng.shuffle(cands)
        want = rng.randint(1, 3)
        chosen = []
        for (i, ca, cb) in cands:
            if len(chosen) >= want:
                break
            if i in opened:
                continue
            ix, iy = i % w, i // w
            if any(abs(ix - j % w) + abs(iy - j // w) < 3 for j in chosen):
                continue
            rs = room_of_connector(i)
            if any(entrances[r] >= 3 for r in rs):
                continue
            chosen.append(i)
        for i in chosen:
            g.t[i] = CORR
            opened.add(i)
            for r in room_of_connector(i):
                entrances[r] += 1
            ca, cb = next((a, b) for (j, a, b) in connectors if j == i)
            dsu.union(ca, cb)

    # 2) 모든 영역이 하나로 이어질 때까지 연결
    main = comp[g.idx(c, c + 5)]
    while True:
        root = dsu.find(main)
        cands = [it for it in connectors
                 if it[0] not in opened and (dsu.find(it[1]) == root) != (dsu.find(it[2]) == root)]
        if not cands:
            break
        # 출입구가 3개 이상인 방은 가능하면 피한다
        good = [it for it in cands if all(entrances[r] < 3 for r in room_of_connector(it[0]))]
        i, ca, cb = rng.choice(good or cands)
        g.t[i] = CORR
        opened.add(i)
        for r in room_of_connector(i):
            entrances[r] += 1
        dsu.union(ca, cb)


def braid(g, rng, ratio):
    """막다른 길 중 ratio 비율을 인접 통로와 뚫어 순환로를 만든다."""
    w, h, t, reserved = g.w, g.h, g.t, g.reserved
    dirs = ((0, -1), (1, 0), (0, 1), (-1, 0))

    def open_count(i):
        return sum(1 for k in (i - 1, i + 1, i - w, i + w) if t[k] in WALKABLE)

    dead = [i for i in range(w * h) if t[i] == CORR and not reserved[i] and open_count(i) == 1]
    k = int(round(len(dead) * ratio))
    if k <= 0:
        return
    for i in rng.sample(dead, k):
        if open_count(i) != 1:
            continue
        x, y = i % w, i // w
        # 뚫린 한 방향의 반대(직진)를 우선
        back = next((dx, dy) for dx, dy in dirs if t[(y + dy) * w + x + dx] in WALKABLE)
        order = [(-back[0], -back[1])] + [d for d in dirs if d != back and d != (-back[0], -back[1])]
        rest = order[1:]
        rng.shuffle(rest)
        for dx, dy in [order[0]] + rest:
            wx, wy = x + dx, y + dy
            bx, by = x + 2 * dx, y + 2 * dy
            if not (1 <= wx < w - 1 and 1 <= wy < h - 1 and 0 < bx < w - 1 and 0 < by < h - 1):
                continue
            wi, bi = wy * w + wx, by * w + bx
            if t[wi] != WALL or reserved[wi] or reserved[bi]:
                continue
            if t[bi] != CORR:   # 방 출입구 수(1~3)를 지키기 위해 통로로만 뚫는다
                continue
            t[wi] = CORR
            break


def build_layout(seed, difficulty):
    """격자와 방 목록을 만든다 (오브젝트 배치 전)."""
    p = DIFFICULTIES[difficulty]
    rng = random.Random(seed)
    size = p["size"]
    g = Grid(size, size)
    c = center_of(size)
    carve_center(g, c)
    rooms = place_rooms(g, rng, difficulty, p["keys"], p["rooms"])
    growing_tree(g, rng)
    connect_regions(g, rng, rooms)
    braid(g, rng, p["braid"])
    x0, y0, x1, y1 = reserved_bounds(size)
    for y in range(size):
        for x in range(size):
            if x0 <= x <= x1 and y0 <= y <= y1:
                continue
            g.sector[g.idx(x, y)] = sector_of(difficulty, size, x, y)
    return g, rooms, rng


def generate(seed, difficulty):
    """맵 JSON(dict) 생성. 검증 실패 시 seed:retry{n} 으로 결정적 재생성."""
    from .placement import place_objects
    from .validate import validate, min_time_ms

    if difficulty not in DIFFICULTIES:
        raise ValueError("unknown difficulty")
    attempt_seed = seed
    for n in range(MAX_RETRIES + 1):
        if n:
            attempt_seed = f"{seed}:retry{n}"
        g, rooms, rng = build_layout(attempt_seed, difficulty)
        maze = place_objects(g, rooms, rng, difficulty)
        if maze is None:
            continue
        ok, info = validate(maze)
        if not ok:
            continue
        maze["seed"] = seed
        maze["difficulty"] = difficulty
        maze["min_time_ms"] = min_time_ms(maze)
        return maze
    raise RuntimeError(f"maze generation failed for {seed}")


_CACHE = OrderedDict()
_CACHE_MAX = 64


def get_maze(seed, difficulty):
    """(seed, difficulty) 기준 LRU 캐시."""
    key = (seed, difficulty)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    maze = generate(seed, difficulty)
    _CACHE[key] = maze
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return maze
