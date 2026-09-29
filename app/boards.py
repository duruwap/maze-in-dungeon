"""랭킹 보드 키 규칙과 순위 계산."""
import re

from .timeutil import daily_date, iso_week

DIFFS = ("easy", "normal", "hard")
BOARD_RE = re.compile(r"^(daily:\d{4}-\d{2}-\d{2}|free:(easy|normal|hard):\d{4}-W\d{2})$")


def daily_board(dt=None):
    return f"daily:{daily_date(dt)}"


def free_board(difficulty, dt=None):
    return f"free:{difficulty}:{iso_week(dt)}"


def resolve_board(value):
    """'daily'/'easy'/... 단축형을 현재 보드 키로. 형식이 틀리면 None."""
    if value == "daily":
        return daily_board()
    if value in DIFFS:
        return free_board(value)
    if value and BOARD_RE.match(value):
        return value
    return None


RANK_SQL = """
WITH best AS (
  SELECT player_id, MIN(time_ms) AS t FROM runs WHERE board = :board GROUP BY player_id
)
SELECT
  (SELECT COUNT(*) FROM best WHERE t < (SELECT t FROM best WHERE player_id = :pid)) + 1 AS rank,
  (SELECT COUNT(*) FROM best) AS total,
  (SELECT t FROM best WHERE player_id = :pid) AS best
"""


def top_percent(rank, total):
    if not total:
        return None
    return round(rank / total * 100, 1)


def player_rank(db, board, player_id):
    """보드별 플레이어당 최고 기록 1개 기준 순위. 동점은 같은 순위."""
    row = db.execute(RANK_SQL, {"board": board, "pid": player_id}).fetchone()
    if row is None or row["best"] is None:
        return None
    return {
        "rank": row["rank"], "total": row["total"], "best": row["best"],
        "top_percent": top_percent(row["rank"], row["total"]),
        "show_percent": row["total"] >= 10,
    }


def time_rank(db, board, time_ms):
    """특정 기록 시간이 보드에서 몇 위에 해당하는지 (공유 카드용)."""
    row = db.execute(
        """WITH best AS (SELECT player_id, MIN(time_ms) AS t FROM runs WHERE board = ? GROUP BY player_id)
           SELECT (SELECT COUNT(*) FROM best WHERE t < ?) + 1 AS rank, (SELECT COUNT(*) FROM best) AS total""",
        (board, time_ms)).fetchone()
    total = max(row["total"], 1)
    rank = min(row["rank"], total)
    return {"rank": rank, "total": total, "top_percent": top_percent(rank, total),
            "show_percent": total >= 10}


LEADERBOARD_SQL = """
WITH best AS (
  SELECT player_id, MIN(time_ms) AS t FROM runs WHERE board = ? GROUP BY player_id
)
SELECT RANK() OVER (ORDER BY b.t) AS rank, b.player_id, b.t AS time_ms, p.number
FROM best b JOIN players p ON p.id = b.player_id
ORDER BY b.t, p.number
LIMIT 100
"""
