"""플레이어 ID 발급 (로그인·닉네임 없음)."""
import re
import sqlite3
import uuid

from flask import jsonify, request

from ..db import get_db
from ..timeutil import utc_iso
from . import bp, error

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def current_player():
    """X-Player-Id 헤더의 플레이어 행. 없거나 형식이 틀리면 None."""
    pid = (request.headers.get("X-Player-Id") or "").strip().lower()
    if not UUID_RE.match(pid):
        return None
    return get_db().execute("SELECT id, number FROM players WHERE id = ?", (pid,)).fetchone()


@bp.post("/player")
def create_player():
    db = get_db()
    pid = str(uuid.uuid4())
    for _ in range(5):
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT COALESCE(MAX(number), 0) + 1 AS n FROM players").fetchone()
            db.execute("INSERT INTO players (id, number, created_at) VALUES (?, ?, ?)",
                       (pid, row["n"], utc_iso()))
            db.execute("COMMIT")
            return jsonify({"id": pid, "number": row["n"]}), 201
        except sqlite3.IntegrityError:
            db.execute("ROLLBACK")
    return error("server_busy", 503)
