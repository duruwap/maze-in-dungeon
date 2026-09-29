# gunicorn 설정: gunicorn -c deploy/gunicorn.conf.py wsgi:app
import multiprocessing
import os

bind = os.environ.get("BIND", "127.0.0.1:15003")
workers = int(os.environ.get("WORKERS", min(4, multiprocessing.cpu_count() * 2 + 1)))
threads = 2
timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = "info"
