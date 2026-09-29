#!/usr/bin/env python3
"""미로 인 던전 스프라이트 생성기.

모든 이미지를 Pillow로 코드에서 절차적으로 그린다 (외부 에셋 없음).
실행: python tools/make_sprites.py
출력: static/assets/{tiles,objects,player}.png, atlas.json, logo.png, icon.png, _preview.png
"""
import json
import math
import os
import random

from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "static", "assets")
T = 16
SHEET_COLS = 16
VERSION = "3"

# ---------------------------------------------------------------- 팔레트 (32색 고정)
PAL = {
    "void": (5, 6, 12), "dark0": (11, 14, 26), "dark1": (20, 26, 46), "dark2": (30, 38, 64),
    "st0": (42, 47, 69), "st1": (58, 64, 96), "st2": (77, 85, 120), "st3": (106, 115, 150),
    "st4": (142, 151, 184),
    "fl0": (38, 36, 48), "fl1": (54, 51, 66), "fl2": (70, 66, 84), "fl3": (92, 87, 108),
    "moss0": (47, 74, 58), "moss1": (86, 128, 72),
    "br0": (58, 30, 22), "br1": (110, 62, 36),
    "or0": (199, 102, 44), "or1": (255, 179, 71), "or2": (255, 224, 138), "wh": (255, 246, 208),
    "te0": (15, 76, 92), "te1": (31, 138, 138), "te2": (72, 224, 208), "te3": (184, 255, 244),
    "red": (224, 65, 58), "blue": (63, 127, 224), "green": (76, 194, 90), "yellow": (242, 208, 59),
    "plum0": (74, 29, 51), "plum1": (128, 50, 80), "skin": (232, 183, 150),
}
assert len(PAL) <= 32, len(PAL)
KEY_COLORS = ["red", "blue", "green", "yellow"]


def C(name, a=255):
    r, g, b = PAL[name]
    return (r, g, b, a)


class Spr:
    """16x16 (또는 임의 크기) RGBA 픽셀 캔버스."""

    def __init__(self, w=T, h=T):
        self.im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.px = self.im.load()
        self.w, self.h = w, h

    def put(self, x, y, c, a=255):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x, y] = C(c, a) if isinstance(c, str) else c

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[x, y]
        return (0, 0, 0, 0)

    def rect(self, x0, y0, x1, y1, c, a=255):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, c, a)

    def hline(self, x0, x1, y, c):
        self.rect(x0, y, x1, y, c)

    def vline(self, x, y0, y1, c):
        self.rect(x, y0, x, y1, c)

    def outline(self, c="void", diag=False):
        """불투명 픽셀 둘레에 외곽선."""
        src = self.im.copy().load()
        nb = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        if diag:
            nb += [(1, 1), (-1, -1), (1, -1), (-1, 1)]
        for y in range(self.h):
            for x in range(self.w):
                if src[x, y][3]:
                    continue
                for dx, dy in nb:
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < self.w and 0 <= yy < self.h and src[xx, yy][3] > 200:
                        self.put(x, y, c)
                        break
        return self

    def copy(self):
        s = Spr(self.w, self.h)
        s.im = self.im.copy()
        s.px = s.im.load()
        return s

    def paste(self, other, dx=0, dy=0):
        self.im.alpha_composite(other.im, (dx, dy)) if dx >= 0 and dy >= 0 else self.im.paste(other.im, (dx, dy), other.im)
        self.px = self.im.load()


# ---------------------------------------------------------------- 아틀라스
class Sheet:
    def __init__(self, name):
        self.name = name
        self.frames = []   # (name, Spr)

    def add(self, name, spr):
        self.frames.append((name, spr))

    def build(self):
        n = len(self.frames)
        rows = (n + SHEET_COLS - 1) // SHEET_COLS
        img = Image.new("RGBA", (SHEET_COLS * T, rows * T), (0, 0, 0, 0))
        meta = {}
        for i, (name, spr) in enumerate(self.frames):
            x, y = (i % SHEET_COLS) * T, (i // SHEET_COLS) * T
            img.alpha_composite(spr.im, (x, y))
            meta[name] = [self.name, x, y, spr.w, spr.h]
        return img, meta


# ================================================================ 타일
def rng_for(*key):
    return random.Random("|".join(map(str, key)))


def wall_top(mask):
    """벽 윗면. mask 비트: 1=N, 2=E, 4=S, 8=W 가 벽이면 연결."""
    s = Spr()
    r = rng_for("walltop", mask)
    s.rect(0, 0, 15, 15, "st0")
    # 넓은 판석 이음새
    for y in (5, 11):
        for x in range(16):
            if r.random() < 0.8:
                s.put(x, y, "dark2")
    for x in (4, 12):
        for y in range(0, 5):
            s.put(x, y, "dark2")
    for x in (8,):
        for y in range(6, 11):
            s.put(x, y, "dark2")
    for _ in range(14):
        s.put(r.randrange(16), r.randrange(16), "st1")
    for _ in range(6):
        s.put(r.randrange(16), r.randrange(16), "dark1")
    # 열린 가장자리: 테두리
    if not mask & 1:
        s.hline(0, 15, 0, "st3")
        s.hline(0, 15, 1, "st2")
    if not mask & 4:
        s.hline(0, 15, 15, "void")
        s.hline(0, 15, 14, "dark1")
    if not mask & 8:
        s.vline(0, 0, 15, "st2")
        s.vline(1, 0, 15, "st1")
    if not mask & 2:
        s.vline(15, 0, 15, "void")
        s.vline(14, 0, 15, "dark1")
    if not mask & 1 and not mask & 8:
        s.put(0, 0, "dark1")
    if not mask & 1 and not mask & 2:
        s.put(15, 0, "dark1")
    return s


def brick_face(variant):
    """벽 앞면 (아래 칸이 바닥일 때). 위 4줄은 윗면, 아래는 벽돌."""
    s = Spr()
    r = rng_for("face", variant)
    # 윗면 가장자리
    s.rect(0, 0, 15, 2, "st1")
    s.hline(0, 15, 0, "st3")
    for x in range(16):
        if r.random() < 0.3:
            s.put(x, 1, "st2")
    s.hline(0, 15, 3, "dark1")
    # 벽돌 3줄
    rows = [(4, 7), (8, 11), (12, 15)]
    for ri, (y0, y1) in enumerate(rows):
        off = 0 if ri % 2 == 0 else 4
        xs = [-8 + off, off, 8 + off, 16 + off]
        for bx in xs:
            x0, x1 = bx, bx + 7
            base = r.choice(["st2", "st2", "st2", "st1", "st3"])
            for y in range(y0, y1 + 1):
                for x in range(max(0, x0), min(15, x1) + 1):
                    if x == x0 or y == y1:
                        s.put(x, y, "dark1")  # 줄눈
                        continue
                    c = base
                    n = r.random()
                    if n < 0.12:
                        c = "st1" if base != "st1" else "st0"
                    elif n < 0.18:
                        c = "st3" if base != "st3" else "st4"
                    s.put(x, y, c)
            # 하이라이트 1픽셀, 아래 그림자
            if 0 <= x0 + 1 <= 15:
                s.put(x0 + 1, y0, "st4" if base == "st3" else "st3")
            for x in range(max(0, x0 + 1), min(15, x1) + 1):
                if y1 - 1 >= y0:
                    px = s.get(x, y1 - 1)
                    if px[3] and px[:3] != PAL["dark1"]:
                        s.put(x, y1 - 1, "st1" if base != "st1" else "st0")
    s.hline(0, 15, 15, "dark0")
    if variant == 1:   # 금간 벽돌
        x, y = 5, 5
        for _ in range(9):
            s.put(x, y, "dark0")
            y += 1
            x += r.choice((-1, 0, 1))
            if y > 14:
                break
    elif variant == 2:  # 이끼
        for x in range(16):
            for y in (7, 11, 15, 14):
                if r.random() < 0.45:
                    s.put(x, y, r.choice(["moss0", "moss1"]))
        for _ in range(8):
            s.put(r.randrange(16), r.randrange(4, 16), "moss0")
    elif variant == 3:  # 깨진 모서리
        for y in range(3, 9):
            for x in range(16 - (9 - y) * 2 + 4, 16):
                if 0 <= x < 16:
                    s.put(x, y, "dark0" if y > 4 else "st0")
        s.put(13, 9, "st1")
        s.put(14, 10, "st3")
    return s


def floor_corr(variant):
    s = Spr()
    r = rng_for("floor", variant)
    s.rect(0, 0, 15, 15, "fl1")
    for _ in range(26):
        s.put(r.randrange(16), r.randrange(16), r.choice(["fl0", "fl2", "fl2"]))
    if variant == 0:  # 판석 2x2
        s.hline(0, 15, 7, "fl0")
        s.vline(7, 0, 7, "fl0")
        s.vline(11, 8, 15, "fl0")
        for (x, y) in ((0, 0), (8, 0), (0, 8), (12, 8)):
            s.put(x, y, "fl3")
            s.put(x + 1, y, "fl2")
    elif variant == 1:  # 큰 판석 + 금
        s.hline(0, 15, 15, "fl0")
        s.vline(15, 0, 15, "fl0")
        x, y = 3, 2
        for _ in range(10):
            s.put(x, y, "fl0")
            x += 1
            y += r.choice((0, 1, 1))
        s.put(0, 0, "fl3")
    elif variant == 2:  # 엇갈린 판석
        s.hline(0, 15, 4, "fl0")
        s.hline(0, 15, 11, "fl0")
        s.vline(9, 0, 4, "fl0")
        s.vline(3, 5, 11, "fl0")
        s.vline(12, 12, 15, "fl0")
        s.put(10, 0, "fl3")
        s.put(4, 5, "fl3")
    else:  # 자갈
        for (cx, cy, rr) in ((4, 4, 3), (11, 3, 2), (8, 10, 3), (2, 12, 2), (13, 12, 2)):
            for y in range(cy - rr, cy + rr + 1):
                for x in range(cx - rr, cx + rr + 1):
                    d = (x - cx) ** 2 + (y - cy) ** 2
                    if d <= rr * rr:
                        s.put(x, y, "fl2" if d < rr * rr - rr else "fl0")
            s.put(cx - 1, cy - 1, "fl3")
    return s


def floor_room(variant):
    s = Spr()
    r = rng_for("room", variant)
    s.rect(0, 0, 15, 15, "st1")
    # 네모 타일 + 모서리 장식
    s.hline(0, 15, 0, "st0")
    s.vline(0, 0, 15, "st0")
    s.hline(1, 15, 1, "st2")
    s.vline(1, 1, 15, "st2")
    for i in range(3, 13):
        if (i % 2) == 0:
            s.put(i, i, "st2")
            s.put(15 - i + 1, i, "st2")
    for _ in range(18):
        s.put(r.randrange(2, 16), r.randrange(2, 16), r.choice(["st0", "st2"]))
    if variant == 1:  # 닳은 중앙
        for y in range(5, 11):
            for x in range(5, 11):
                if (x - 8) ** 2 + (y - 8) ** 2 < 9:
                    s.put(x, y, "fl2")
        s.put(7, 7, "fl3")
    return s


def floor_exit():
    s = Spr()
    s.rect(0, 0, 15, 15, "dark2")
    s.hline(0, 15, 0, "plum0")
    s.vline(0, 0, 15, "plum0")
    # 새긴 문양 (다이아몬드 + 점)
    for i in range(8):
        s.put(8 + i // 2 - 2, 3 + i, "plum1") if False else None
    pts = [(8, 3), (9, 4), (10, 5), (11, 6), (12, 7), (11, 8), (10, 9), (9, 10), (8, 11),
           (7, 10), (6, 9), (5, 8), (4, 7), (5, 6), (6, 5), (7, 4)]
    for x, y in pts:
        s.put(x, y, "plum1")
    s.put(8, 7, "te1")
    s.put(8, 6, "plum1")
    s.put(8, 8, "plum1")
    s.put(7, 7, "plum1")
    s.put(9, 7, "plum1")
    for (x, y) in ((2, 2), (14, 2), (2, 14), (14, 14)):
        s.put(x, y, "te0")
    return s


def shade(kind):
    s = Spr()
    if kind == "n":
        for y, a in enumerate((150, 105, 70, 40, 18)):
            s.rect(0, y, 15, y, "void", a)
    elif kind == "w":
        for x, a in enumerate((80, 40, 15)):
            s.rect(x, 0, x, 15, "void", a)
    else:
        for x, a in enumerate((80, 40, 15)):
            s.rect(15 - x, 0, 15 - x, 15, "void", a)
    return s


# ================================================================ 오브젝트
FLAMES = [
    # (높이, 기울기, 흔들림) 프레임별 불꽃 모양
    [(7, 0), (6, 0), (5, 1)],
]


def flame(s, cx, base_y, frame, scale=1.0):
    """불꽃: 바깥 주황 → 노랑 → 흰 심지."""
    heights = [6, 7, 5, 7]
    lean = [0, 1, 0, -1]
    h = int(heights[frame] * scale)
    for i in range(h):
        y = base_y - i
        k = i / max(1, h - 1)
        w = max(0, int(round((1 - k) * 2.2 * scale + (0.5 if i < 2 else 0))))
        cx2 = cx + (lean[frame] if i > h // 2 else 0)
        for x in range(cx2 - w, cx2 + w + 1):
            d = abs(x - cx2)
            c = "or0"
            if d < w * 0.7 and k < 0.8:
                c = "or1"
            if d == 0 and k < 0.55:
                c = "or2"
            s.put(x, y, c)
    s.put(cx, base_y, "wh")
    s.put(cx, base_y - 1, "or2")
    # 튀는 불똥
    spark = [(cx + 2, base_y - h - 1), (cx - 2, base_y - h), (cx + 1, base_y - h - 2), (cx - 1, base_y - h - 1)]
    s.put(*spark[frame], "or1")


def torch_n(lit, frame=0):
    """앞면 벽에 붙은 횃불. 칸의 아래쪽(벽 앞면)에 그린다."""
    s = Spr()
    # 쇠 받침
    s.hline(6, 9, 13, "st3")
    s.put(6, 12, "st3")
    s.put(9, 12, "st3")
    s.vline(7, 13, 14, "st4")
    s.vline(8, 13, 14, "st2")
    # 나무 손잡이
    s.vline(7, 8, 12, "br1")
    s.vline(8, 8, 12, "br0")
    # 머리 (감은 천)
    s.rect(6, 6, 9, 7, "br0")
    s.hline(6, 9, 6, "br1")
    if lit:
        s.rect(6, 6, 9, 6, "or0")
        flame(s, 7, 5, frame)
        s.put(8, 5, "or1")
    else:
        s.put(7, 5, "st0")
        s.put(8, 5, "dark2")
        s.put(7, 6, "void")
    s.outline("void")
    return s


def torch_side(lit, frame=0):
    """옆 벽(동쪽)에 붙은 횃불. 칸 오른쪽 가장자리가 벽."""
    s = Spr()
    # 벽 고정쇠
    s.vline(14, 9, 13, "st3")
    s.hline(10, 14, 12, "st3")
    s.put(10, 11, "st4")
    # 기울어진 손잡이
    for i, (x, y) in enumerate([(9, 11), (9, 10), (8, 9), (8, 8)]):
        s.put(x, y, "br1")
        s.put(x + 1, y, "br0")
    s.rect(7, 6, 9, 7, "br0")
    s.hline(7, 9, 6, "br1")
    if lit:
        s.hline(7, 9, 6, "or0")
        flame(s, 8, 5, frame, 0.9)
    else:
        s.put(8, 5, "st0")
    s.outline("void")
    return s


def key_sprite(color, frame):
    s = Spr()
    col = color
    # 고리 (bow)
    ring = [(3, 5), (4, 4), (5, 4), (6, 5), (7, 6), (7, 7), (6, 8), (5, 9), (4, 9), (3, 8), (2, 7), (2, 6)]
    for (x, y) in ring:
        s.put(x, y + 1, col)
    s.put(4, 5, "wh")
    s.put(3, 6, "wh")
    # 자루
    for x in range(8, 14):
        s.put(x, 8, col)
        s.put(x, 9, col)
    s.hline(8, 12, 8, "wh")
    # 이
    s.rect(11, 10, 11, 11, col)
    s.rect(13, 10, 13, 12, col)
    s.outline("dark0")
    # 반짝임
    glints = [None, (4, 5), (10, 8), (13, 9)]
    g = glints[frame]
    if g:
        s.put(g[0], g[1], "wh")
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            s.put(g[0] + dx, g[1] + dy, "or2")
    return s


def sparkle(color, frame):
    s = Spr()
    cx, cy = 8, 8
    size = [1, 2, 3, 1][frame]
    for i in range(-size, size + 1):
        s.put(cx + i, cy, "wh" if abs(i) < size else color)
        s.put(cx, cy + i, "wh" if abs(i) < size else color)
    if frame == 2:
        for d in (-2, 2):
            s.put(cx + d, cy + d, color, 180)
            s.put(cx + d, cy - d, color, 180)
    return s


RUNE_POS = [(8, 2), (12, 4), (14, 8), (12, 12), (8, 14), (4, 12), (2, 8), (4, 4)]


def teleport(active, frame=0):
    s = Spr()
    # 원형 석판
    for y in range(16):
        for x in range(16):
            d = math.hypot(x - 7.5, y - 8)
            if d <= 7.4:
                c = "st1"
                if d > 6.3:
                    c = "st2" if y < 8 else "st0"
                elif d < 3.4:
                    c = "st2"
                s.put(x, y, c)
    # 룬
    for i, (x, y) in enumerate(RUNE_POS):
        on = active and ((i - frame) % 8) in (0, 1, 2, 4)
        c = "te3" if (active and (i - frame) % 8 == 0) else ("te2" if on else ("te0" if active else "st0"))
        s.put(x, y, c)
        if i % 2 == 0:
            s.put(x + (1 if x < 8 else -1 if x > 8 else 0), y + (1 if y < 8 else -1 if y > 8 else 0), c)
    # 중앙 문양
    core = "te2" if active else "st0"
    for (x, y) in ((7, 6), (8, 6), (6, 7), (9, 7), (6, 8), (9, 8), (7, 9), (8, 9)):
        s.put(x, y, core)
    if active:
        s.put(7, 7, "te3" if frame % 2 == 0 else "te2")
        s.put(8, 8, "te3" if frame % 2 == 1 else "te2")
        s.put(7, 8, "te1")
        s.put(8, 7, "te1")
    else:
        s.rect(7, 7, 8, 8, "dark2")
    s.outline("void")
    return s


def door(total, filled, open_frame=None):
    """탈출 방 문 (벽 앞면 자리). total 자물쇠 중 filled 개가 채워진 상태."""
    s = Spr()
    # 돌 아치 틀
    s.rect(0, 0, 15, 15, "st2")
    s.rect(0, 0, 15, 2, "st1")
    s.hline(0, 15, 0, "st3")
    s.hline(0, 15, 3, "dark1")
    s.rect(2, 4, 13, 15, "st3")
    s.rect(3, 5, 12, 15, "dark0")
    s.put(3, 5, "st3")
    s.put(12, 5, "st3")
    if open_frame is None or open_frame < 3:
        # 문짝 (열림 프레임에 따라 폭이 줄어든다)
        shrink = 0 if open_frame is None else (open_frame + 1) * 2
        lw = 5 - shrink
        if lw > 0:
            s.rect(3, 6, 3 + lw - 1, 15, "br1")
            s.rect(12 - lw + 1, 6, 12, 15, "br1")
            for x in range(3, 3 + lw):
                if x % 2 == 0:
                    s.vline(x, 6, 15, "br0")
            for x in range(12 - lw + 1, 13):
                if x % 2 == 1:
                    s.vline(x, 6, 15, "br0")
            # 쇠 띠
            s.hline(3, 3 + lw - 1, 8, "st3")
            s.hline(12 - lw + 1, 12, 8, "st3")
            s.hline(3, 3 + lw - 1, 13, "st3")
            s.hline(12 - lw + 1, 12, 13, "st3")
        if open_frame is None:
            s.vline(7, 6, 15, "br0")
            s.vline(8, 6, 15, "br0")
            # 자물쇠 판
            s.rect(4, 9, 11, 12, "st0")
            s.hline(4, 11, 9, "st2")
            xs = {2: [6, 9], 3: [5, 7, 10], 4: [4, 6, 9, 11]}[total]
            for i, x in enumerate(xs):
                if i < filled:
                    col = KEY_COLORS[i]
                    s.rect(x, 10, x, 11, col)
                    s.put(x, 10, "wh")
                else:
                    s.put(x, 10, "void")
                    s.put(x, 11, "dark1")
        else:
            # 틈 사이 빛
            s.rect(3 + max(0, lw), 6, 12 - max(0, lw), 15, "dark2" if open_frame < 1 else "plum0")
            s.vline(7, 7, 15, "or1")
            s.vline(8, 7, 15, "or2")
    else:
        # 완전히 열림: 안쪽 바닥의 빛
        s.rect(3, 6, 12, 15, "plum0")
        s.rect(5, 9, 10, 15, "plum1")
        s.rect(7, 11, 8, 15, "or1")
    return s


def exit_marker(frame):
    s = Spr()
    r = [5, 6, 7, 6][frame]
    for y in range(16):
        for x in range(16):
            d = math.hypot(x - 7.5, y - 7.5)
            if abs(d - r) < 0.7:
                s.put(x, y, "or1", 200)
            elif abs(d - (r - 3)) < 0.6 and r - 3 > 0:
                s.put(x, y, "or2", 170)
    for (x, y) in ((7, 4), (8, 4), (7, 11), (8, 11), (4, 7), (4, 8), (11, 7), (11, 8)):
        s.put(x, y, "wh", 230)
    s.rect(7, 7, 8, 8, "wh")
    return s


def decor(kind, v):
    s = Spr()
    r = rng_for("decor", kind, v)
    if kind == "pebbles":
        for _ in range(3 + v * 2):
            x, y = r.randrange(2, 13), r.randrange(3, 13)
            s.put(x, y, r.choice(["st3", "st2"]))
            s.put(x + 1, y, "st2")
            s.put(x, y + 1, "dark1")
            s.put(x + 1, y + 1, "dark1")
    elif kind == "bones":
        if v == 0:
            for i in range(7):
                s.put(4 + i, 9 - i // 3, "st4")
            for (x, y) in ((3, 9), (3, 10), (11, 6), (11, 7)):
                s.put(x, y, "wh")
            s.put(6, 11, "st4")
            s.put(7, 11, "st4")
            s.put(8, 12, "st3")
        else:  # 해골
            s.rect(5, 6, 10, 10, "st4")
            s.rect(6, 5, 9, 5, "st4")
            s.put(6, 8, "void")
            s.put(9, 8, "void")
            s.put(7, 10, "void")
            s.put(8, 10, "void")
            s.hline(6, 9, 11, "st3")
            s.put(6, 6, "wh")
            s.put(11, 12, "st4")
            s.put(12, 12, "st4")
            s.put(13, 13, "st3")
        s.outline("dark0")
    elif kind == "puddle":
        cx, cy = 8, 9
        for y in range(16):
            for x in range(16):
                d = ((x - cx) / (5.5 - v)) ** 2 + ((y - cy) / (3.2 - v * 0.5)) ** 2
                if d <= 1:
                    s.put(x, y, "te0" if d > 0.55 else "dark2")
        s.hline(6, 8, 8, "te1")
        s.put(10, 10, "te1")
        s.put(7, 8, "te3", 160)
    elif kind == "rune":
        pts = [(8, 3), (8, 4), (8, 5), (8, 6), (8, 7), (8, 8), (8, 9), (8, 10), (8, 11), (8, 12),
               (5, 5), (6, 6), (7, 7), (11, 5), (10, 6), (9, 7), (5, 11), (6, 10), (11, 11), (10, 10)]
        if v == 1:
            pts = [(4 + i, 8) for i in range(9)] + [(8, 4 + i) for i in range(9)] + \
                  [(5, 5), (11, 5), (5, 11), (11, 11)]
        for (x, y) in pts:
            s.put(x, y, "plum1", 200)
        s.put(8, 8, "te1", 220)
    elif kind == "cobweb":
        flip = v == 1
        for i in range(0, 12):
            x = i if not flip else 15 - i
            s.put(x, 0, "st4", 170)
        for i in range(0, 10):
            s.put(0 if not flip else 15, i, "st4", 170)
        for i in range(10):
            x = i if not flip else 15 - i
            s.put(x, i, "st4", 190)
        for rad in (4, 7, 10):
            for a in range(0, 90, 6):
                x = int(round(math.cos(math.radians(a)) * rad))
                y = int(round(math.sin(math.radians(a)) * rad))
                s.put(x if not flip else 15 - x, y, "st3", 150)
    return s


def ui_slot(color=None):
    s = Spr()
    s.rect(1, 1, 14, 14, "dark1")
    s.hline(1, 14, 1, "st2")
    s.hline(1, 14, 14, "void")
    s.vline(1, 1, 14, "st2")
    s.vline(14, 1, 14, "void")
    s.rect(2, 2, 13, 13, "dark2" if color else "dark1")
    k = key_sprite(color or "st1", 0 if not color else 1)
    if not color:
        # 빈 슬롯: 어두운 실루엣
        for y in range(16):
            for x in range(16):
                p = k.get(x, y)
                if p[3] and p[:3] != PAL["dark0"]:
                    s.put(x, y + 0, "st0")
    else:
        s.im.alpha_composite(k.im)
        s.px = s.im.load()
    return s


def icon_player(direction):
    s = Spr()
    ang = direction * math.pi / 4
    pts = [(7, 0), (-5, -5), (-2, 0), (-5, 5)]
    poly = []
    for (x, y) in pts:
        rx = x * math.cos(ang) - y * math.sin(ang)
        ry = x * math.sin(ang) + y * math.cos(ang)
        poly.append((7.5 + rx, 7.5 + ry))
    ImageDraw.Draw(s.im).polygon(poly, fill=C("or2"))
    s.px = s.im.load()
    s.outline("void")
    return s


def icon_simple(kind, color=None):
    s = Spr()
    if kind == "torch":
        flame(s, 7, 12, 0, 1.3)
        s.vline(7, 13, 15, "br1")
    elif kind in ("tp_on", "tp_off"):
        c1 = "te2" if kind == "tp_on" else "st3"
        c2 = "te3" if kind == "tp_on" else "st1"
        for y in range(16):
            for x in range(16):
                d = math.hypot(x - 7.5, y - 7.5)
                if 4.2 <= d <= 6.8:
                    s.put(x, y, c1)
                elif d < 2.2:
                    s.put(x, y, c2)
    elif kind == "key":
        for y in range(3, 9):
            for x in range(1, 8):
                if 2.2 <= math.hypot(x - 4, y - 6) <= 3.3:
                    s.put(x, y, color)
        s.rect(7, 5, 14, 7, color)
        s.rect(11, 8, 12, 10, color)
        s.rect(14, 8, 14, 11, color)
        s.put(3, 4, "wh")
    elif kind == "exit":
        s.rect(3, 3, 12, 14, "plum1")
        s.rect(5, 5, 10, 14, "or1")
        s.rect(6, 7, 9, 14, "or2")
        s.hline(3, 12, 2, "st4")
        s.vline(2, 2, 14, "st4")
        s.vline(13, 2, 14, "st4")
    s.outline("void")
    return s


# ================================================================ 플레이어
CLOAK, CLOAK_D = "plum1", "plum0"


def player_frame(direction, anim, f):
    """망토를 두르고 램프를 든 작은 탐험가."""
    s = Spr()
    # 애니메이션 파라미터
    bob = 0
    legL = legR = 0          # 다리 들림 (위로 -)
    legLx = legRx = 0        # 옆모습 다리 앞뒤
    hem = 0                  # 망토 자락 흔들림
    lamp_dx = lamp_dy = 0
    reach = 0
    trail = 1                # 옆모습 망토 뒤로 날림
    armswing = 0
    if anim == "idle":
        bob = [0, 0, 1, 1][f]
        lamp_dx = [0, 1, 0, -1][f] if direction != "side" else 0
        lamp_dy = [0, 0, 1, 0][f]
        hem = [0, 0, 0, 0][f]
        trail = [1, 1, 1, 1][f]
    elif anim == "walk":
        bob = [0, 1, 0, 0, 1, 0][f]
        legL = [0, -1, -2, 0, 0, 0][f]
        legR = [0, 0, 0, 0, -1, -2][f]
        legLx = [2, 1, 0, -2, -1, 0][f]
        legRx = -legLx
        hem = [0, 1, 1, 0, -1, -1][f]
        armswing = [0, 1, 1, 0, -1, -1][f]
        lamp_dy = [0, 1, 1, 0, -1, -1][f] if direction != "side" else [0, 1, 0, 0, 1, 0][f]
        trail = [2, 3, 4, 2, 3, 4][f]
    elif anim == "interact":
        reach = [1, 2, 3][f]

    y0 = bob
    if direction in ("down", "up"):
        # 다리/장화
        for (lx, dy) in ((5, legL), (9, legR)):
            top = 13 + dy
            s.rect(lx, top, lx + 1, 14 + min(0, dy + 1), "st1")
            s.rect(lx, 15 + dy if dy < 0 else 15, lx + 1, 15 + dy if dy < 0 else 15, "br1")
        # 망토 몸통
        rows = [(7, 4, 11), (8, 4, 11), (9, 3, 12), (10, 3, 12), (11, 3, 12), (12, 3 + min(0, hem), 12 + max(0, hem))]
        for (yy, a, b) in rows:
            s.hline(a, b, yy + y0, CLOAK)
        s.hline(3 + min(0, hem), 12 + max(0, hem), 12 + y0, CLOAK_D)  # 자락
        s.vline(4, 8 + y0, 11 + y0, CLOAK_D)
        s.vline(11, 8 + y0, 11 + y0, CLOAK_D) if direction == "up" else None
        if direction == "down":
            # 앞섶 + 튜닉
            s.vline(7, 8 + y0, 11 + y0, "br1")
            s.vline(8, 8 + y0, 11 + y0, "br1")
            s.hline(7, 8, 10 + y0, "br0")
            s.put(7, 8 + y0, "or0")  # 망토 단추
        else:
            s.vline(7, 8 + y0, 11 + y0, CLOAK_D)
            s.put(9, 9 + y0, CLOAK_D)
            s.put(6, 10 + y0, CLOAK_D)
        # 두건
        hood = [(2, 6, 9), (3, 5, 10), (4, 4, 11), (5, 4, 11), (6, 4, 11)]
        for (yy, a, b) in hood:
            s.hline(a, b, yy + y0, CLOAK)
        s.put(6, 2 + y0, CLOAK_D)
        s.put(9, 2 + y0, CLOAK_D) if direction == "up" else s.put(8, 2 + y0, "plum1")
        if direction == "down":
            s.hline(6, 9, 4 + y0, "skin")
            s.hline(5, 10, 5 + y0, "skin")
            s.hline(6, 9, 6 + y0, "skin")
            s.hline(5, 10, 4 + y0, CLOAK_D) if False else None
            s.put(5, 4 + y0, CLOAK_D)
            s.put(10, 4 + y0, CLOAK_D)
            s.put(6, 5 + y0, "void")
            s.put(9, 5 + y0, "void")
            s.put(7, 6 + y0, "or0") if anim == "interact" else None
        else:
            s.vline(7, 3 + y0, 6 + y0, CLOAK_D)
            s.put(6, 3 + y0, "st3") if False else s.put(9, 3 + y0, "plum1")
        # 빈 손 (왼쪽)
        hy = 10 + y0 + armswing
        s.put(3, hy, "skin")
        # 램프 팔 (오른쪽)
        lx = 12 + lamp_dx
        ly = 10 + y0 + lamp_dy - armswing
        if anim == "interact":
            if direction == "down":
                ly += reach
                lx -= 1 if reach == 3 else 0
            else:
                ly -= reach + 2
        s.put(12, min(ly, 11 + y0), "skin")
        s.put(lx, ly, "st3")           # 손잡이
        s.rect(lx, ly + 1, lx + 1, ly + 2, "or1")
        s.put(lx, ly + 1, "wh")
        s.put(lx + 1, ly + 2, "or0")
        s.hline(lx, lx + 1, ly + 3, "br0")
        if direction == "up":
            # 뒷모습에선 램프가 몸 뒤로 살짝 가려진다
            s.put(lx, ly + 1, "or2")
    else:  # 측면 (오른쪽을 향함)
        # 다리
        for (lx, dy, col, boot) in ((7 + legRx, legR, "st0", "br0"), (7 + legLx, legL, "st1", "br1")):
            s.rect(lx, 13 + dy, lx + 1, 14, col)
            s.hline(lx, lx + 2, 15 + min(0, dy), boot)
        # 망토 뒤로 날림
        for yy in range(7, 13):
            a = 4 - (trail if yy >= 10 else max(0, trail - 2))
            s.hline(max(1, a), 10, yy + y0, CLOAK)
        for yy in range(9, 13):
            a = 4 - (trail if yy >= 10 else 0)
            s.put(max(1, a), yy + y0, CLOAK_D)
        s.hline(max(1, 4 - trail), 10, 12 + y0, CLOAK_D)
        s.vline(9, 8 + y0, 11 + y0, "br1")
        # 두건 옆모습
        hood = [(2, 6, 9), (3, 5, 10), (4, 4, 10), (5, 4, 11), (6, 4, 11)]
        for (yy, a, b) in hood:
            s.hline(a, b, yy + y0, CLOAK)
        s.put(4, 4 + y0, CLOAK_D)
        s.put(3, 5 + y0, CLOAK)       # 두건 꼬리
        s.put(3, 6 + y0, CLOAK_D)
        s.rect(9, 4 + y0, 10, 6 + y0, "skin")
        s.put(11, 5 + y0, "skin")      # 코
        s.put(10, 5 + y0, "void")
        s.hline(8, 10, 3 + y0, CLOAK_D)
        # 램프를 앞으로
        lx = 11 + (reach if anim == "interact" else 0)
        ly = 9 + y0 + lamp_dy - (1 if anim == "interact" and reach > 1 else 0)
        s.hline(10, lx, ly - 1 if anim == "interact" else ly, "skin")
        s.put(lx + 1, ly, "st3")
        s.rect(lx + 1, ly + 1, lx + 2, ly + 2, "or1")
        s.put(lx + 1, ly + 1, "wh")
        s.put(lx + 2, ly + 2, "or0")
        s.hline(lx + 1, lx + 2, ly + 3, "br0")
    s.outline("void")
    return s


def player_teleport(f, base):
    """빛 입자로 흩어짐(0~2) → 재조립(3~5)."""
    s = Spr()
    r = rng_for("tp", f)
    amount = [0.25, 0.6, 0.95, 0.9, 0.55, 0.15][f]
    lift = [0, 1, 3, 3, 1, 0][f]
    for y in range(16):
        for x in range(16):
            p = base.get(x, y)
            if not p[3]:
                continue
            if r.random() < amount:
                if r.random() < 0.35:
                    s.put(x + r.choice((-1, 0, 1)), y - lift - r.randrange(0, 3), r.choice(["te3", "te2", "wh"]))
            else:
                if f in (0, 5) and r.random() < 0.35:
                    s.put(x, y, "te2")
                else:
                    s.put(x, y, p)
    return s


def player_clear(f):
    s = player_frame("down", "idle", 0)
    # 팔을 들어 열쇠를 머리 위로
    s2 = Spr()
    s2.im.alpha_composite(s.im)
    s2.px = s2.im.load()
    s = s2
    # 기존 손 지우고 들어올린 팔
    for (x, y) in ((3, 10), (12, 10), (12, 11), (13, 11), (12, 12), (13, 12), (12, 13), (13, 13), (2, 10), (14, 11),
                   (14, 12), (14, 13), (11, 14), (14, 10), (12, 14), (13, 14), (13, 10)):
        s.put(x, y, (0, 0, 0, 0))
    lift = [0, 1, 2, 2][f]
    bob = [0, 0, 0, 1][f]
    hand_y = [8, 6, 4, 4][f] + bob
    s.vline(3, hand_y, 9, CLOAK)
    s.vline(12, hand_y, 9, CLOAK)
    s.put(3, hand_y - 1, "skin")
    s.put(12, hand_y - 1, "skin")
    # 황금 열쇠
    ky = [7, 4, 1, 1][f] + bob - lift + 2
    for x in range(4, 12):
        s.put(x, ky, "yellow")
    s.put(4, ky - 1, "yellow")
    s.put(5, ky - 1, "wh")
    s.put(4, ky + 1, "yellow")
    s.put(10, ky + 1, "yellow")
    s.outline("void")
    if f >= 2:
        for (x, y) in ((2, ky - 2), (13, ky - 2), (8, max(0, ky - 3))):
            s.put(x, y, "wh")
        if f == 3:
            s.put(1, ky, "or2")
            s.put(14, ky, "or2")
    return s


# ================================================================ 로고/아이콘
def logo():
    s = Spr(32, 32)
    # 아치 문
    for y in range(4, 30):
        for x in range(6, 26):
            d = math.hypot(x - 15.5, y - 13)
            inside_arch = y >= 13 or d <= 10
            if not inside_arch:
                continue
            edge = (y >= 13 and (x in (6, 7, 24, 25))) or (y < 13 and d > 8.3)
            s.put(x, y, "st3" if edge else "br1")
    for x in range(8, 24):
        for y in range(6, 30):
            p = s.get(x, y)
            if p[:3] == PAL["br1"] and x % 3 == 0:
                s.put(x, y, "br0")
    s.hline(8, 23, 17, "st3")
    s.hline(8, 23, 24, "st3")
    s.hline(4, 27, 30, "st2")
    s.hline(3, 28, 31, "st1")
    # 가운데 열쇠 구멍 빛
    s.rect(14, 18, 17, 23, "dark0")
    s.rect(15, 19, 16, 22, "or1")
    s.put(15, 19, "wh")
    # 양쪽 횃불
    for cx in (2, 29):
        s.vline(cx, 14, 20, "br1")
        flame(s, cx, 12, 1, 1.1)
    # 황금 열쇠 대각
    for i in range(12):
        s.put(10 + i, 26 - i // 2, "yellow")
    s.outline("void")
    return s


# ================================================================ 빌드
def build():
    os.makedirs(OUT, exist_ok=True)
    tiles = Sheet("tiles")
    for m in range(16):
        tiles.add(f"wall.top.{m}", wall_top(m))
    for v in range(4):
        tiles.add(f"wall.face.{v}", brick_face(v))
    for v in range(4):
        tiles.add(f"floor.corr.{v}", floor_corr(v))
    for v in range(2):
        tiles.add(f"floor.room.{v}", floor_room(v))
    tiles.add("floor.exit.0", floor_exit())
    for k in ("n", "w", "e"):
        tiles.add(f"shade.{k}", shade(k))

    objects = Sheet("objects")
    objects.add("torch.off", torch_n(False))
    for f in range(4):
        objects.add(f"torch.on.{f}", torch_n(True, f))
    objects.add("torch.side.off", torch_side(False))
    for f in range(4):
        objects.add(f"torch.side.on.{f}", torch_side(True, f))
    for c in KEY_COLORS:
        for f in range(4):
            objects.add(f"key.{c}.{f}", key_sprite(c, f))
    for c in KEY_COLORS:
        for f in range(4):
            objects.add(f"fx.sparkle.{c}.{f}", sparkle(c, f))
    objects.add("tp.off", teleport(False))
    for f in range(6):
        objects.add(f"tp.on.{f}", teleport(True, f))
    for total in (2, 3, 4):
        for filled in range(total + 1):
            objects.add(f"door.{total}.{filled}", door(total, filled))
    for f in range(4):
        objects.add(f"door.open.{f}", door(4, 4, f))
    for f in range(4):
        objects.add(f"exit.{f}", exit_marker(f))
    for kind in ("pebbles", "bones", "puddle", "rune", "cobweb"):
        for v in range(2):
            objects.add(f"decor.{kind}.{v}", decor(kind, v))
    objects.add("ui.slot.empty", ui_slot(None))
    for c in KEY_COLORS:
        objects.add(f"ui.slot.{c}", ui_slot(c))
    for d in range(8):
        objects.add(f"icon.player.{d}", icon_player(d))
    objects.add("icon.torch", icon_simple("torch"))
    objects.add("icon.tp_on", icon_simple("tp_on"))
    objects.add("icon.tp_off", icon_simple("tp_off"))
    for c in KEY_COLORS:
        objects.add(f"icon.key.{c}", icon_simple("key", c))
    objects.add("icon.exit", icon_simple("exit"))

    player = Sheet("player")
    for d in ("down", "up", "side"):
        for f in range(4):
            player.add(f"player.idle.{d}.{f}", player_frame(d, "idle", f))
    for d in ("down", "up", "side"):
        for f in range(6):
            player.add(f"player.walk.{d}.{f}", player_frame(d, "walk", f))
    for d in ("down", "up", "side"):
        for f in range(3):
            player.add(f"player.interact.{d}.{f}", player_frame(d, "interact", f))
    base = player_frame("down", "idle", 0)
    for f in range(6):
        player.add(f"player.teleport.{f}", player_teleport(f, base))
    for f in range(4):
        player.add(f"player.clear.{f}", player_clear(f))

    atlas = {"version": VERSION, "tile": T, "sheets": {}, "frames": {}}
    images = {}
    for sh in (tiles, objects, player):
        img, meta = sh.build()
        fn = f"{sh.name}.png"
        img.save(os.path.join(OUT, fn), optimize=True)
        atlas["sheets"][sh.name] = fn
        atlas["frames"].update(meta)
        images[sh.name] = img
    with open(os.path.join(OUT, "atlas.json"), "w") as f:
        json.dump(atlas, f, separators=(",", ":"))

    lg = logo()
    lg.im.resize((128, 128), Image.NEAREST).save(os.path.join(OUT, "logo.png"), optimize=True)
    lg.im.resize((64, 64), Image.NEAREST).save(os.path.join(OUT, "icon.png"), optimize=True)
    images["logo"] = lg.im

    make_preview(images)
    check_palette(images)
    print(f"frames: {len(atlas['frames'])}")


def check_palette(images):
    allowed = {v for v in PAL.values()}
    for name, img in images.items():
        for (cnt, (r, g, b, a)) in img.getcolors(1 << 16) or []:
            if a == 255 and (r, g, b) not in allowed:
                raise SystemExit(f"{name}: off-palette color {(r, g, b)}")


def make_preview(images):
    """모든 시트를 4배 확대해 한 장으로 (사람 검토용)."""
    scale = 4
    pad = 24
    parts = []
    for name in ("tiles", "objects", "player", "logo"):
        img = images[name]
        parts.append((name, img.resize((img.width * scale, img.height * scale), Image.NEAREST)))
    w = max(p.width for _, p in parts) + pad * 2
    h = sum(p.height + pad + 20 for _, p in parts) + pad
    out = Image.new("RGBA", (w, h), PAL["dark1"] + (255,))
    d = ImageDraw.Draw(out)
    y = pad
    for name, p in parts:
        d.text((pad, y), name, fill=PAL["or2"] + (255,))
        y += 20
        # 체커보드 배경
        for yy in range(0, p.height, 16):
            for xx in range(0, p.width, 16):
                c = PAL["dark0"] if (xx // 16 + yy // 16) % 2 == 0 else PAL["dark2"]
                d.rectangle([pad + xx, y + yy, pad + xx + 15, y + yy + 15], fill=c + (255,))
        out.alpha_composite(p, (pad, y))
        y += p.height + pad
    out.save(os.path.join(OUT, "_preview.png"), optimize=True)


if __name__ == "__main__":
    build()
