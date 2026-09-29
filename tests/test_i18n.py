import json
import os
import re

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LANGS = ["ko", "en", "zh", "ja"]


def load(lang):
    with open(os.path.join(ROOT, "static", "i18n", f"{lang}.json"), encoding="utf-8") as f:
        return json.load(f)


def test_same_keys():
    base = set(load("ko"))
    for lang in LANGS:
        d = load(lang)
        assert set(d) == base, (lang, set(d) ^ base)
        assert all(isinstance(v, str) and v.strip() for v in d.values()), lang


@pytest.mark.parametrize("lang", LANGS)
def test_placeholders_match(lang):
    ko, d = load("ko"), load(lang)
    for k, v in ko.items():
        assert set(re.findall(r"\{(\w+)\}", v)) == set(re.findall(r"\{(\w+)\}", d[k])), (lang, k)


def test_core_terms():
    expect = {
        "title": ["미로 인 던전", "Maze in Dungeon", "地牢迷宫", "ダンジョン迷宮"],
        "daily": ["오늘의 던전", "Today's Dungeon", "今日地牢", "今日のダンジョン"],
        "key": ["열쇠", "Key", "钥匙", "鍵"],
        "torch": ["횃불", "Torch", "火把", "松明"],
        "teleport": ["텔레포트", "Teleport", "传送阵", "テレポート"],
        "explorer": ["탐험가", "Explorer", "探险家", "探検家"],
        "top_percent": ["상위 {percent}%", "Top {percent}%", "前 {percent}%", "上位 {percent}%"],
    }
    for key, vals in expect.items():
        for lang, v in zip(LANGS, vals):
            assert load(lang)[key] == v


def test_all_code_keys_exist():
    """JS/템플릿에서 쓰는 i18n 키가 모두 사전에 있다."""
    keys = set(load("en"))
    used = set()
    for folder in ("static/js", "app/templates"):
        for fn in os.listdir(os.path.join(ROOT, folder)):
            src = open(os.path.join(ROOT, folder, fn), encoding="utf-8").read()
            used |= set(re.findall(r'data-i18n(?:-aria)?="([\w.]+)"', src))
            used |= set(re.findall(r"\bt\('([\w.]+)'", src))
            used |= set(re.findall(r"texts\['([\w.]+)'\]", src))
    missing = {k for k in used if k not in keys}
    assert not missing, missing
