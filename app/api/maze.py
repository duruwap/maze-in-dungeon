"""맵 JSON + 1회용 판 토큰 발급."""
import secrets
import time

from flask import jsonify, request

from ..boards import DIFFS, daily_board, free_board
from ..db import get_db
from ..maze.generator import get_maze
from ..timeutil import daily_date
from . import bp, error
from .player import current_player

PUBLIC_KEYS = ("width", "height", "tiles", "start", "exit_room", "door", "exit",
               "keys", "teleports", "torches", "decor", "floor_variant_seed")


@bp.get("/maze")
def maze():
    mode = request.args.get("mode", "daily")
    if mode not in ("daily", "free"):
        return error("bad_mode")
    player = current_player()
    if player is None:
        return error("unknown_player", 401)
    if mode == "daily":
        difficulty = "normal"
        seed = f"daily-{daily_date()}"
        board = daily_board()
    else:
        difficulty = request.args.get("difficulty", "normal")
        if difficulty not in DIFFS:
            return error("bad_difficulty")
        seed = f"free-{secrets.token_hex(6)}"
        board = free_board(difficulty)
    m = get_maze(seed, difficulty)
    token = secrets.token_urlsafe(24)
    get_db().execute(
        "INSERT INTO sessions (token, player_id, board, seed, difficulty, min_time_ms, started_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (token, player["id"], board, seed, difficulty, m["min_time_ms"], time.time()))
    body = {"token": token, "mode": mode, "difficulty": difficulty, "seed": seed, "board": board}
    body.update({k: m[k] for k in PUBLIC_KEYS})
    return jsonify(body)
