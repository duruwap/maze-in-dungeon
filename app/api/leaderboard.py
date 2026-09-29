"""랭킹: 상위 100 + 내 순위."""
from flask import jsonify, request

from ..boards import LEADERBOARD_SQL, player_rank, resolve_board
from ..db import get_db
from . import bp, error
from .player import UUID_RE


@bp.get("/leaderboard")
def leaderboard():
    board = resolve_board(request.args.get("board", ""))
    if board is None:
        return error("bad_board")
    pid = (request.args.get("player_id") or "").lower()
    if pid and not UUID_RE.match(pid):
        return error("bad_player")
    db = get_db()
    rows = db.execute(LEADERBOARD_SQL, (board,)).fetchall()
    entries = [{"rank": r["rank"], "number": r["number"], "time_ms": r["time_ms"],
                "is_me": bool(pid) and r["player_id"] == pid} for r in rows]
    me = None
    if pid:
        r = player_rank(db, board, pid)
        if r:
            num = db.execute("SELECT number FROM players WHERE id = ?", (pid,)).fetchone()
            me = dict(r, number=num["number"] if num else None, time_ms=r["best"],
                      in_top=any(e["is_me"] for e in entries))
    total = db.execute("SELECT COUNT(DISTINCT player_id) FROM runs WHERE board = ?", (board,)).fetchone()[0]
    return jsonify({"board": board, "total": total, "entries": entries, "me": me})
