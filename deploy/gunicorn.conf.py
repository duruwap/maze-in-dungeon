# gunicorn 설정: startup.sh(scripts/scs-run.sh)가 사용한다.
#   gunicorn -c deploy/gunicorn.conf.py wsgi:app
import multiprocessing
import os

bind = os.environ.get("BIND", f"{os.environ.get('HOST', '127.0.0.1')}:{os.environ.get('PORT', '15003')}")
workers = int(os.environ.get("WORKERS", min(4, multiprocessing.cpu_count() * 2 + 1)))
threads = int(os.environ.get("THREADS", 2))
timeout = 30
graceful_timeout = 20
loglevel = "info"

# 로그: LOG_DIR 이 있으면 {LOG_DIR}/app-YYYY-MM-DD.log 에 앱·gunicorn(접근/에러) 로그를 일별로 남긴다
_log_dir = os.environ.get("LOG_DIR")
if _log_dir:
    _handler = {"class": "app.logutil.DailyFileHandler", "log_dir": _log_dir, "formatter": "std"}
    logconfig_dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"std": {"format": "%(asctime)s %(levelname)s [%(process)d] %(name)s: %(message)s"}},
        "handlers": {"daily": _handler},
        "root": {"level": "INFO", "handlers": ["daily"]},
        "loggers": {
            "gunicorn.error": {"level": "INFO", "handlers": ["daily"], "propagate": False},
            "gunicorn.access": {"level": "INFO", "handlers": ["daily"], "propagate": False},
        },
    }
    accesslog = "-"   # logconfig_dict 의 gunicorn.access 로 전달
    # 루트 핸들러를 gunicorn 이 붙였으므로 앱(create_app)은 중복 추가하지 않도록 표시
    os.environ["MID_GUNICORN_LOGGING"] = "1"
else:
    accesslog = "-"
    errorlog = "-"
