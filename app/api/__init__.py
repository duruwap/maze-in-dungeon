from flask import Blueprint, jsonify

bp = Blueprint("api", __name__, url_prefix="/api")


def error(code, status=400):
    return jsonify({"error": code}), status


from . import player, maze, runs, leaderboard  # noqa: E402,F401
