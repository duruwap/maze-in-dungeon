import logging
import time

from app.logutil import DailyFileHandler


def test_daily_files(tmp_path):
    h = DailyFileHandler(str(tmp_path))
    h.setFormatter(logging.Formatter("%(message)s"))
    day1 = time.mktime((2026, 9, 29, 23, 59, 0, 0, 0, -1))
    day2 = day1 + 120
    for ts, msg in ((day1, "a"), (day2, "b"), (day2, "c")):
        rec = logging.LogRecord("t", logging.INFO, __file__, 1, msg, None, None)
        rec.created = ts
        h.handle(rec)
    h.close()
    assert (tmp_path / "app-2026-09-29.log").read_text() == "a\n"
    assert (tmp_path / "app-2026-09-30.log").read_text() == "b\nc\n"
