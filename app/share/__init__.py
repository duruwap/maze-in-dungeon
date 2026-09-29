"""공유 랜딩 페이지와 OG 카드 이미지."""
import os
import re
import tempfile

from flask import Blueprint, abort, current_app, render_template, request, send_file

from ..boards import time_rank
from ..db import get_db
from ..i18n import HTML_LANG, LANGS, format_time, pick_lang, t, texts

bp = Blueprint("share", __name__)
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,32}$")


def _run(run_id):
    if not RUN_ID_RE.match(run_id):
        return None
    return get_db().execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()


def share_texts(run, rank, lang):
    if rank["show_percent"]:
        rank_text = t(lang, "top_percent", percent=rank["top_percent"])
    else:
        rank_text = t(lang, "result.rank_of", rank=rank["rank"], total=rank["total"])
    daily = run["board"].startswith("daily:")
    diff = t(lang, "share.daily_label") if daily else t(lang, f"difficulty.{run['difficulty']}")
    return {
        "title": t(lang, "share.title", time=format_time(run["time_ms"])),
        "desc": t(lang, "share.desc", rank_text=rank_text, torches=run["torches"], difficulty=diff),
    }


def _cached_png(name, builder):
    cache = current_app.config["OG_CACHE_DIR"]
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, name)
    if not os.path.exists(path):
        img = builder()
        fd, tmp = tempfile.mkstemp(dir=cache, suffix=".png")
        os.close(fd)
        img.save(tmp, "PNG", optimize=True)
        os.replace(tmp, path)   # 원자적 교체 (여러 워커 동시 생성 대비)
    resp = send_file(path, mimetype="image/png", max_age=86400)
    return resp


@bp.get("/share/<run_id>")
def share_page(run_id):
    lang = pick_lang(request)
    run = _run(run_id)
    base = current_app.config["BASE_URL"]
    if run is None:
        return render_template("share.html", lang=lang, html_lang=HTML_LANG[lang], texts=texts(lang),
                               found=False, base=base, title=t(lang, "title"),
                               desc=t(lang, "share.page_desc"),
                               image=f"{base}/og/default.png?lang={lang}", url=f"{base}/?lang={lang}",
                               play_url=f"/?lang={lang}", cfg=current_app.config), 404
    rank = time_rank(get_db(), run["board"], run["time_ms"])
    st = share_texts(run, rank, lang)
    daily = run["board"].startswith("daily:")
    return render_template(
        "share.html", lang=lang, html_lang=HTML_LANG[lang], texts=texts(lang), found=True, base=base,
        title=st["title"], desc=st["desc"], time=format_time(run["time_ms"]),
        image=f"{base}/og/{run_id}.png?lang={lang}", url=f"{base}/share/{run_id}?lang={lang}",
        play_url=f"/?lang={lang}" + ("&mode=daily" if daily else ""), cfg=current_app.config)


@bp.get("/og/default.png")
def og_default():
    from .card import render_default_card
    lang = request.args.get("lang")
    if lang not in LANGS:
        lang = "en"
    return _cached_png(f"default_{lang}.png", lambda: render_default_card(lang))


@bp.get("/og/<run_id>.png")
def og_card(run_id):
    from .card import render_run_card
    lang = request.args.get("lang")
    if lang not in LANGS:
        lang = "en"
    run = _run(run_id)
    if run is None:
        abort(404)
    rank = time_rank(get_db(), run["board"], run["time_ms"])
    return _cached_png(f"{run_id}_{lang}.png", lambda: render_run_card(dict(run), rank, lang))
