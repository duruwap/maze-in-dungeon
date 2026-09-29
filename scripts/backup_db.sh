#!/usr/bin/env bash
# SQLite 온라인 백업 (WAL 모드에서도 일관된 스냅샷). cron 예: 17 4 * * * /srv/maze-in-dungeon/scripts/backup_db.sh
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="${DB_PATH:-$APP_DIR/instance/maze.db}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/maze-$STAMP.db"
python3 - "$DB_PATH" "$OUT" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
dst.execute("PRAGMA integrity_check")
dst.close()
src.close()
PY
gzip -f "$OUT"
find "$BACKUP_DIR" -name 'maze-*.db.gz' -mtime +"$KEEP_DAYS" -delete
echo "backup: $OUT.gz"
