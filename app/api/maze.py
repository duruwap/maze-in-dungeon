"""라운드별 맵 JSON 발급.

한 판 = 3라운드 (쉬움 → 보통 → 어려움). 1라운드 요청 때 판 토큰을 발급하고,
2·3라운드는 같은 토큰으로 요청한다. 서버는 라운드마다 하한 시간을 누적한다.
"""
import secrets
import time

from flask import jsonify, request

from ..boards import ROUNDS, run_board
from ..db import get_db
from ..maze.generator import get_maze
from ..timeutil import daily_date
from . import bp, error
from .player import current_player

PUBLIC_KEYS = ("width", "height", "tiles", "start", "exit_room", "door", "exit",
               "keys", "teleports", "torches", "decor", "floor_variant_seed")


@bp.get("/maze")
def maze():
    player = current_player()
    if player is None:
        return error("unknown_player", 401)
    try:
        rnd = int(request.args.get("round", "1"))
    except ValueError:
        return error("bad_round")
    if not 1 <= rnd <= len(ROUNDS):
        return error("bad_round")
    difficulty = ROUNDS[rnd - 1]
    seed = f"run-{daily_date()}-r{rnd}-{secrets.token_hex(6)}"   # 판마다 새 맵
    m = get_maze(seed, difficulty)
    db = get_db()
    token = request.args.get("token") or None
    if rnd == 1:
        token = secrets.token_urlsafe(24)
        db.execute(
            "INSERT INTO sessions (token, player_id, board, seed, difficulty, min_time_ms, started_at, round) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            (token, player["id"], run_board(), seed, difficulty, m["min_time_ms"], time.time()))
    elif token:
        sess = db.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
        if sess is None or sess["player_id"] != player["id"]:
            return error("invalid_token")
        if sess["used"]:
            return error("token_used")
        if sess["round"] != rnd - 1:
            return error("round_out_of_order")
        db.execute("UPDATE sessions SET round = ?, seed = ?, difficulty = ?, min_time_ms = min_time_ms + ? "
                   "WHERE token = ? AND round = ?",
                   (rnd, seed, difficulty, m["min_time_ms"], token, rnd - 1))
    # 토큰 없는 2·3라운드 요청(이어하기한 판)은 기록 없이 맵만 준다
    body = {"token": token, "round": rnd, "rounds": len(ROUNDS), "difficulty": difficulty,
            "seed": seed, "board": run_board()}
    body.update({k: m[k] for k in PUBLIC_KEYS})
    return jsonify(body)
