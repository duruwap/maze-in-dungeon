"""일별 로그 파일: {LOG_DIR}/app-YYYY-MM-DD.log

여러 gunicorn 워커가 같은 파일에 append 하므로 회전(rename) 대신
날짜가 바뀌면 새 파일을 여는 방식을 쓴다 (프로세스 간 충돌 없음).
"""
import logging
import os
import time

FORMAT = "%(asctime)s %(levelname)s [%(process)d] %(name)s: %(message)s"


class DailyFileHandler(logging.Handler):
    def __init__(self, log_dir, prefix="app"):
        super().__init__()
        self.log_dir = log_dir
        self.prefix = prefix
        self._day = None
        self._stream = None
        os.makedirs(log_dir, exist_ok=True)

    def path_for(self, day):
        return os.path.join(self.log_dir, f"{self.prefix}-{day}.log")

    def emit(self, record):
        try:
            day = time.strftime("%Y-%m-%d", time.localtime(record.created))
            if day != self._day:
                if self._stream:
                    self._stream.close()
                self._stream = open(self.path_for(day), "a", encoding="utf-8")
                self._day = day
            self._stream.write(self.format(record) + "\n")
            self._stream.flush()
        except Exception:
            self.handleError(record)

    def close(self):
        if self._stream:
            self._stream.close()
            self._stream = None
        super().close()


def configure(log_dir=None, level=logging.INFO):
    """루트 로거 설정 (중복 호출 안전). log_dir 가 없으면 stderr."""
    root = logging.getLogger()
    if any(getattr(h, "_mid", False) or isinstance(h, DailyFileHandler) for h in root.handlers):
        return
    if os.environ.get("MID_GUNICORN_LOGGING") and root.handlers:
        return
    if log_dir:
        h = DailyFileHandler(log_dir)
    else:
        h = logging.StreamHandler()
    h._mid = True
    h.setFormatter(logging.Formatter(FORMAT))
    root.addHandler(h)
    root.setLevel(level)
