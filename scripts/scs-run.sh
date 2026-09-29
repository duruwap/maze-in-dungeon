#!/bin/bash
# 공통 런처: scs-run.sh <앱이름> [start|--no-pull|stop|status|restart|logs]
#
#   프로젝트  $SCS_APP_DIR (기본 /scsrun/app/<앱이름>)
#   PID      $PID_DIR/<앱이름>.pid          (기본 /scsrun/pid)
#   데이터    $DATA_DIR                     (기본 /scsdat/app/<앱이름>)
#   로그     $LOG_DIR/app-YYYY-MM-DD.log   (기본 /scslog/app/<앱이름>, 일별)
#
# 설정은 프로젝트의 scsrun.conf, 비밀값은 .env 에서 읽는다.
set -u

APP_NAME="${1:?usage: scs-run.sh <app-name> [start|--no-pull|stop|status|restart|logs]}"
shift
APP_DIR="${SCS_APP_DIR:-/scsrun/app/$APP_NAME}"
cd "$APP_DIR" || { echo "[$APP_NAME] 프로젝트 디렉토리 없음: $APP_DIR" >&2; exit 1; }

# 기본값 → scsrun.conf → .env 순으로 덮어쓴다
PORT=15003
HOST=127.0.0.1
WORKERS=4
THREADS=2
DATA_DIR="/scsdat/app/$APP_NAME"
LOG_DIR="/scslog/app/$APP_NAME"
PID_DIR="/scsrun/pid"
LOG_KEEP_DAYS=30
HEALTH_TIMEOUT=20
[ -f scsrun.conf ] && . ./scsrun.conf
if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi

PID_FILE="$PID_DIR/$APP_NAME.pid"
VENV="$APP_DIR/venv"
export PORT HOST WORKERS THREADS DATA_DIR LOG_DIR
export DB_PATH="${DB_PATH:-$DATA_DIR/maze.db}"
export OG_CACHE_DIR="${OG_CACHE_DIR:-$DATA_DIR/og_cache}"

today_log() { echo "$LOG_DIR/app-$(date +%F).log"; }
say() { echo "[$APP_NAME] $*"; echo "$(date '+%F %T') [scs-run] $*" >> "$(today_log)" 2>/dev/null || true; }

read_pid() { [ -f "$PID_FILE" ] && cat "$PID_FILE" 2>/dev/null; }
is_running() {
    local pid
    pid="$(read_pid)"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

ensure_dirs() {
    local d
    for d in "$DATA_DIR" "$DATA_DIR/og_cache" "$DATA_DIR/backups" "$LOG_DIR" "$PID_DIR"; do
        if ! mkdir -p "$d" 2>/dev/null; then
            echo "[$APP_NAME] 디렉토리를 만들 수 없음: $d (sudo mkdir -p $d && sudo chown $(id -un): $d)" >&2
            exit 1
        fi
    done
}

do_stop() {
    if ! is_running; then
        rm -f "$PID_FILE"
        say "실행 중이 아님"
        return 0
    fi
    local pid i
    pid="$(read_pid)"
    say "종료 중 (pid $pid)"
    kill -TERM "$pid" 2>/dev/null
    for i in $(seq 1 30); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
        say "강제 종료 (pid $pid)"
        kill -KILL "$pid" 2>/dev/null
    fi
    rm -f "$PID_FILE"
    say "종료됨"
}

do_status() {
    if is_running; then
        say "실행 중 (pid $(read_pid), http://$HOST:$PORT)"
        curl -fsS -o /dev/null -w "[$APP_NAME] 응답 %{http_code} (%{time_total}s)\n" "http://127.0.0.1:$PORT/" 2>/dev/null \
            || echo "[$APP_NAME] 경고: 포트 $PORT 응답 없음"
        echo "[$APP_NAME] 로그: $(today_log)"
        return 0
    fi
    say "중지됨"
    return 3
}

do_start() {
    local pull=1 a
    for a in "$@"; do
        [ "$a" = "--no-pull" ] && pull=0
    done
    ensure_dirs
    do_stop
    if [ "$pull" = 1 ] && [ -d .git ]; then
        say "git pull"
        git pull --ff-only || { say "git pull 실패 — 중단"; exit 1; }
    fi
    if [ ! -x "$VENV/bin/python" ]; then
        say "venv 생성"
        python3 -m venv "$VENV" || exit 1
    fi
    say "의존성 설치"
    "$VENV/bin/pip" install --disable-pip-version-check -q -r requirements.txt || { say "pip 실패 — 중단"; exit 1; }

    # 오래된 일별 로그 정리
    find "$LOG_DIR" -maxdepth 1 -name 'app-*.log' -mtime +"$LOG_KEEP_DAYS" -delete 2>/dev/null || true

    if curl -fsS -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/" 2>/dev/null; then
        say "포트 $PORT 를 다른 프로세스가 사용 중 — 중단 (ss -ltnp | grep :$PORT)"
        exit 1
    fi

    say "기동 (port $PORT, workers $WORKERS, db $DB_PATH)"
    "$VENV/bin/gunicorn" -c deploy/gunicorn.conf.py --daemon --pid "$PID_FILE" \
        --capture-output --error-logfile "$LOG_DIR/console.log" wsgi:app \
        || { say "gunicorn 기동 실패 — $(today_log) 확인"; exit 1; }

    local i
    for i in $(seq 1 "$HEALTH_TIMEOUT"); do
        if is_running && curl -fsS -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null; then
            say "정상 기동 (pid $(read_pid), ${i}s)"
            return 0
        fi
        sleep 1
    done
    say "응답 없음 (${HEALTH_TIMEOUT}s) — $(today_log) 확인"
    exit 1
}

case "${1:-start}" in
    start|--no-pull|restart) do_start "$@" ;;
    stop) do_stop ;;
    status) do_status ;;
    logs) tail -n 100 -F "$(today_log)" ;;
    *) echo "usage: $0 $APP_NAME [start|--no-pull|stop|status|restart|logs]" >&2; exit 2 ;;
esac
