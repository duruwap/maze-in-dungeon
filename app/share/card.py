"""결과 카드 이미지(1200x630) 생성: 어두운 던전 배경 + 탐험 경로 미니맵 + 기록."""
import base64
import math
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import BASE_DIR
from ..i18n import format_time, t

W, H = 1200, 630
ASSETS = os.path.join(BASE_DIR, "static", "assets")
SIZES = {"easy": 25, "normal": 41, "hard": 61}

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
# 기본은 Pretendard, 일본어 한자는 Pretendard JP, 둘 다 없는 글자(중국어 간체 일부)만 대체 글꼴
PRIMARY_FONTS = [os.path.join(FONT_DIR, "Pretendard-Bold.otf"), os.path.join(FONT_DIR, "PretendardJP-Bold.otf")]
FALLBACK_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]


@lru_cache(maxsize=1)
def font_chain():
    """[(경로, face index, 지원 코드포인트 집합)]"""
    from fontTools.ttLib import TTCollection, TTFont
    paths = [p for p in PRIMARY_FONTS if os.path.exists(p)]
    env = os.environ.get("FONT_PATH")
    fb = [env] if env and os.path.exists(env) else []
    fb += [p for p in FALLBACK_CANDIDATES if os.path.exists(p)]
    if fb:
        paths.append(fb[0])
    chain = []
    for path in paths:
        index = 0
        if path.lower().endswith(".ttc"):
            if "NotoSansCJK" in os.path.basename(path):
                index = 2   # SC
            cmap = set(TTCollection(path).fonts[index].getBestCmap())
        else:
            cmap = set(TTFont(path).getBestCmap())
        chain.append((path, index, cmap))
    return chain


def font_path():
    chain = font_chain()
    return chain[0][0] if chain else None


@lru_cache(maxsize=128)
def _font(i, size):
    path, index, _ = font_chain()[i]
    return ImageFont.truetype(path, size, index=index)


def font(size, lang="en"):
    return _font(0, size) if font_chain() else ImageFont.load_default(size)


def runs(s, size):
    """글자마다 글리프가 있는 첫 글꼴을 골라 (글꼴, 문자열) 구간으로 나눈다."""
    chain = font_chain()
    if not chain:
        return [(ImageFont.load_default(size), s)]
    out = []
    for ch in s:
        idx = 0
        for i, (_, _, cmap) in enumerate(chain):
            if ord(ch) in cmap or ch.isspace():
                idx = i
                break
        f = _font(idx, size)
        if out and out[-1][0] is f:
            out[-1] = (f, out[-1][1] + ch)
        else:
            out.append((f, ch))
    return out


@lru_cache(maxsize=1)
def sprites():
    import json
    with open(os.path.join(ASSETS, "atlas.json")) as f:
        atlas = json.load(f)
    sheets = {k: Image.open(os.path.join(ASSETS, v)).convert("RGBA") for k, v in atlas["sheets"].items()}
    return atlas["frames"], sheets


def sprite(name, scale):
    frames, sheets = sprites()
    s, x, y, w, h = frames[name]
    im = sheets[s].crop((x, y, x + w, y + h))
    return im.resize((w * scale, h * scale), Image.NEAREST)


@lru_cache(maxsize=1)
def background():
    """던전 벽/바닥 스프라이트로 만든 어두운 배경 (한 번만 생성)."""
    bg = Image.new("RGBA", (W, H), (11, 14, 26, 255))
    sc = 5
    ts = 16 * sc
    tiles = {n: sprite(n, sc) for n in ["wall.top.15", "wall.face.0", "wall.face.1", "wall.face.2",
                                         "floor.corr.0", "floor.corr.1", "floor.corr.2", "floor.corr.3", "shade.n"]}
    torch = sprite("torch.on.1", sc)
    for ty in range(H // ts + 1):
        for tx in range(W // ts + 1):
            hv = (tx * 7349 + ty * 1931) % 97
            if ty == 0:
                im = tiles["wall.top.15"]
            elif ty == 1:
                im = tiles[f"wall.face.{0 if hv % 5 else (1 if hv % 2 else 2)}"]
            else:
                im = tiles[f"floor.corr.{hv % 4}"]
            bg.alpha_composite(im, (tx * ts, ty * ts))
            if ty == 2:
                bg.alpha_composite(tiles["shade.n"], (tx * ts, ty * ts))
    for tx in (1, 14):
        bg.alpha_composite(torch, (tx * ts, ts))
    # 어둠 + 횃불빛
    dark = Image.new("RGBA", (W, H), (11, 14, 26, 0))
    dp = dark.load()
    lights = [(1.5 * ts, 1.6 * ts), (14.5 * ts, 1.6 * ts)]
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            lv = 0.0
            for (lx, ly) in lights:
                d = math.hypot(x - lx, y - ly) / 380
                lv = max(lv, 1 - d)
            a = int(255 * min(0.93, max(0.55, 0.93 - lv * 0.55)))
            for yy in (y, y + 1):
                for xx in (x, x + 1):
                    if xx < W and yy < H:
                        dp[xx, yy] = (11, 14, 26, a)
    bg.alpha_composite(dark)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for (lx, ly) in lights:
        gd.ellipse([lx - 160, ly - 120, lx + 160, ly + 200], fill=(255, 150, 60, 50))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    bg.alpha_composite(glow)
    return bg


def decode_preview(b64, size):
    if not b64:
        return None
    try:
        raw = base64.b64decode(b64)
    except ValueError:
        return None
    n = size * size
    if len(raw) * 4 < n:
        return None
    out = bytearray(n)
    for i in range(n):
        out[i] = (raw[i >> 2] >> (6 - 2 * (i & 3))) & 3
    return out


def draw_path(img, cells, size, box):
    x0, y0, bw = box
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0 - 14, y0 - 14, x0 + bw + 14, y0 + bw + 14], radius=16,
                        fill=(5, 6, 12, 235), outline=(42, 49, 80, 255), width=3)
    if cells is None:
        return
    cell = bw / size
    colors = {1: (42, 49, 80), 2: (59, 63, 92), 3: (255, 179, 71)}
    for i, v in enumerate(cells):
        if not v:
            continue
        cx, cy = i % size, i // size
        d.rectangle([x0 + cx * cell, y0 + cy * cell, x0 + (cx + 1) * cell - 0.5, y0 + (cy + 1) * cell - 0.5],
                    fill=colors[v] + (255,))
    c = size // 2
    d.rectangle([x0 + (c - 0.5) * cell, y0 + (c - 0.5) * cell, x0 + (c + 1.5) * cell, y0 + (c + 1.5) * cell],
                fill=(72, 224, 208, 255))


def text_width(d, s, size):
    return sum(d.textlength(part, font=f) for f, part in runs(s, size))


def text(d, xy, s, size, lang, fill, anchor="la", stroke=0):
    """글꼴 대체를 지원하는 텍스트. anchor: 'la'(왼쪽 위) 또는 'mt'(가운데 위)."""
    x, y = xy
    parts = runs(s, size)
    if anchor == "mt":
        x -= text_width(d, s, size) / 2
    base = y + font(size, lang).getmetrics()[0]   # 첫 글꼴의 ascent 기준 공통 기준선
    for f, part in parts:
        sw, sf = stroke, (20, 10, 4, 255)
        if not sw and "wqy" in getattr(f, "path", ""):
            sw, sf = max(1, size // 30), fill   # 굵은 글꼴이 없는 대체 글꼴은 획을 두껍게 보정
        d.text((x, base), part, font=f, fill=fill, anchor="ls", stroke_width=sw, stroke_fill=sf)
        x += d.textlength(part, font=f)


def fit_size(d, s, lang, size, max_w):
    while size > 16 and text_width(d, s, size) > max_w:
        size -= 2
    return size


def render_run_card(run, rank, lang):
    img = background().copy()
    d = ImageDraw.Draw(img)
    size = SIZES.get(run["difficulty"], 41)
    draw_path(img, decode_preview(run["path_preview"], size), size, (86, 115, 400))
    logo = sprite_logo(3)
    img.alpha_composite(logo, (590, 58))
    title = t(lang, "title")
    text(d, (700, 70), title, fit_size(d, title, lang, 44, 440), lang, (255, 224, 138, 255))
    diff = t(lang, "share.daily_label") if run["board"].startswith("daily:") else t(lang, f"difficulty.{run['difficulty']}")
    if run["board"].startswith("daily:"):
        diff += " " + run["board"][6:]
    text(d, (700, 128), diff, 26, lang, (154, 160, 189, 255))
    text(d, (596, 205), t(lang, "share.card_escaped"), 34, lang, (72, 224, 208, 255))
    text(d, (590, 250), format_time(run["time_ms"]), 132, "en", (255, 246, 208, 255), stroke=0)
    if rank["show_percent"]:
        big = t(lang, "top_percent", percent=rank["top_percent"])
        small = t(lang, "result.rank_of", rank=rank["rank"], total=rank["total"])
    else:
        big = t(lang, "result.rank_of", rank=rank["rank"], total=rank["total"])
        small = ""
    text(d, (596, 425), big, fit_size(d, big, lang, 54, 560), lang, (255, 179, 71, 255))
    if small:
        text(d, (600, 492), small, 26, lang, (154, 160, 189, 255))
    stats = (f"{t(lang, 'torch')} {run['torches']}  ·  {t(lang, 'teleport')} {run['teleports']}  ·  "
             f"{t(lang, 'result.explored')} {round(run['explored'] * 100)}%")
    text(d, (600, 540), stats, fit_size(d, stats, lang, 26, 560), lang, (232, 230, 240, 255))
    return img.convert("RGB")


def render_default_card(lang):
    img = background().copy()
    d = ImageDraw.Draw(img)
    logo = sprite_logo(7)
    img.alpha_composite(logo, ((W - logo.width) // 2, 70))
    title = t(lang, "title")
    text(d, (W // 2, 360), title, fit_size(d, title, lang, 96, 1000), lang, (255, 224, 138, 255), anchor="mt")
    sub = t(lang, "subtitle")
    text(d, (W // 2, 490), sub, fit_size(d, sub, lang, 36, 1000), lang, (232, 230, 240, 255), anchor="mt")
    daily = t(lang, "daily")
    text(d, (W // 2, 555), daily, 30, lang, (72, 224, 208, 255), anchor="mt")
    return img.convert("RGB")


@lru_cache(maxsize=8)
def sprite_logo(scale):
    im = Image.open(os.path.join(ASSETS, "logo.png")).convert("RGBA")
    base = im.resize((32, 32), Image.NEAREST)
    return base.resize((32 * scale, 32 * scale), Image.NEAREST)
