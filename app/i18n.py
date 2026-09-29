"""서버 측 다국어: 클라이언트와 같은 static/i18n/*.json 을 읽는다."""
import json
import os
from functools import lru_cache

from .config import BASE_DIR

LANGS = ("ko", "en", "zh", "ja")
HTML_LANG = {"ko": "ko", "en": "en", "zh": "zh-CN", "ja": "ja"}


@lru_cache(maxsize=8)
def texts(lang):
    if lang not in LANGS:
        lang = "en"
    with open(os.path.join(BASE_DIR, "static", "i18n", f"{lang}.json"), encoding="utf-8") as f:
        return json.load(f)


def t(lang, key, **params):
    s = texts(lang).get(key) or texts("en").get(key, key)
    for k, v in params.items():
        s = s.replace("{" + k + "}", str(v))
    return s


def pick_lang(request):
    lang = request.args.get("lang")
    if lang in LANGS:
        return lang
    return request.accept_languages.best_match(list(LANGS)) or "en"


def format_time(ms):
    ms = max(0, int(ms))
    return f"{ms // 60000}:{(ms % 60000) // 1000:02d}.{(ms % 1000) // 10:02d}"
