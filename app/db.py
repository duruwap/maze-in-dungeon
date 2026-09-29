"""SQLite 연결과 스키마 초기화 (WAL 모드, ORM 없음)."""
import os
import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
  id TEXT PRIMARY KEY,
  number INTEGER UNIQUE NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  player_id TEXT NOT NULL REFERENCES players(id),
  board TEXT NOT NULL,
  seed TEXT NOT NULL,
  difficulty TEXT NOT NULL,
  min_time_ms INTEGER NOT NULL,
  started_at REAL NOT NULL,
  used INTEGER NOT NULL DEFAULT 0,
  round INTEGER NOT NULL DEFAULT 1   -- 3라운드 판: 지금까지 발급한 라운드 수
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  player_id TEXT NOT NULL REFERENCES players(id),
  board TEXT NOT NULL,
  difficulty TEXT NOT NULL,
  time_ms INTEGER NOT NULL,
  torches INTEGER NOT NULL,
  teleports INTEGER NOT NULL,
  explored REAL NOT NULL,
  path_preview TEXT,
  lang TEXT,
  created_at TEXT NOT NULL,
  splits TEXT                 -- 라운드별 기록 JSON [ms, ms, ms]
);
CREATE INDEX IF NOT EXISTS idx_runs_board_time ON runs(board, time_ms);
CREATE INDEX IF NOT EXISTS idx_runs_player ON runs(player_id, board);
-- 분당 제출 제한용 시도 기록 (명세 외 추가 테이블, DECISIONS.md 참고)
CREATE TABLE IF NOT EXISTS submit_log (
  player_id TEXT NOT NULL,
  at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_submit_log ON submit_log(player_id, at);
"""


def connect(path):
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DB_PATH"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    conn = connect(path)
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.close()


def _migrate(conn):
    """이전 버전 DB에 새 컬럼 추가."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
    if "round" not in cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN round INTEGER NOT NULL DEFAULT 1")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(runs)")}
    if "splits" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN splits TEXT")


def init_app(app):
    init_db(app.config["DB_PATH"])
    app.teardown_appcontext(close_db)
