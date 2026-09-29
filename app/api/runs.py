"""기록 제출과 검증."""
import base64
import binascii
import secrets
import time

from flask import current_app, jsonify, request

from ..boards import player_rank
from ..db import get_db
from ..timeutil import utc_iso
from . import bp, error
from .player import current_player

LANGS = ("ko", "en", "zh", "ja")
MAX_TIME_MS = 6 * 60 * 60 * 1000
MAX_PREVIEW = 4096
CLOCK_SLACK_MS = 2000


def _int(v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise ValueError
    return v


@bp.post("/runs")
def submit_run():
    player = current_player()
    if player is None:
        return error("unknown_player", 401)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("bad_request")
    try:
        token = data.get("token")
        if not isinstance(token, str) or not 10 <= len(token) <= 64:
            raise ValueError
        time_ms = _int(data.get("time_ms"), 1, MAX_TIME_MS)
        torches = _int(data.get("torches", 0), 0, 999)
        teleports = _int(data.get("teleports", 0), 0, 999)
        explored = data.get("explored", 0)
        if isinstance(explored, bool) or not isinstance(explored, (int, float)) or not 0 <= explored <= 1:
            raise ValueError
        preview = data.get("path_preview")
        if preview is not None:
            if not isinstance(preview, str) or len(preview) > MAX_PREVIEW:
                raise ValueError
            base64.b64decode(preview, validate=True)
        lang = data.get("lang", "en")
        if lang not in LANGS:
            lang = "en"
    except (ValueError, TypeError, binascii.Error):
        return error("bad_request")

    db = get_db()
    now = time.time()
    pid = player["id"]
    # 4) 분당 제출 제한
    db.execute("DELETE FROM submit_log WHERE at < ?", (now - 3600,))
    recent = db.execute("SELECT COUNT(*) FROM submit_log WHERE player_id = ? AND at > ?",
                        (pid, now - 60)).fetchone()[0]
    if recent >= current_app.config["RATE_LIMIT_PER_MIN"]:
        return error("rate_limited", 429)
    db.execute("INSERT INTO submit_log (player_id, at) VALUES (?, ?)", (pid, now))

    # 1) 토큰
    sess = db.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    if sess is None or sess["player_id"] != pid:
        return error("invalid_token")
    if sess["used"]:
        return error("token_used")
    # 2) 서버 경과 시간보다 길 수 없다
    if time_ms > (now - sess["started_at"]) * 1000 + CLOCK_SLACK_MS:
        return error("time_exceeds_server")
    # 3) 하한 시간
    if time_ms < sess["min_time_ms"]:
        return error("time_below_min")

    board = sess["board"]
    before = player_rank(db, board, pid)
    db.execute("BEGIN IMMEDIATE")
    cur = db.execute("UPDATE sessions SET used = 1 WHERE token = ? AND used = 0", (token,))
    if cur.rowcount != 1:
        db.execute("ROLLBACK")
        return error("token_used")
    run_id = secrets.token_urlsafe(9)
    db.execute(
        "INSERT INTO runs (id, player_id, board, difficulty, time_ms, torches, teleports, explored, "
        "path_preview, lang, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, pid, board, sess["difficulty"], time_ms, torches, teleports, float(explored),
         preview, lang, utc_iso()))
    db.execute("COMMIT")
    r = player_rank(db, board, pid)
    return jsonify({
        "run_id": run_id, "board": board,
        "rank": r["rank"], "total": r["total"], "top_percent": r["top_percent"],
        "show_percent": r["show_percent"], "best": r["best"],
        "is_new_best": before is None or time_ms < before["best"],
    })


@bp.get("/players/<pid>/runs")
def player_runs(pid):
    from .player import UUID_RE
    pid = pid.lower()
    if not UUID_RE.match(pid):
        return error("bad_player")
    rows = get_db().execute(
        "SELECT id, board, difficulty, time_ms, torches, teleports, explored, created_at "
        "FROM runs WHERE player_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 20", (pid,)).fetchall()
    return jsonify({"runs": [dict(r) for r in rows]})
