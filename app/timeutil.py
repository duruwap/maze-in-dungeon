"""한국 시간(KST) 기준 날짜/주차 계산."""
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def now_kst():
    return datetime.now(KST)


def daily_date(dt=None):
    return (dt or now_kst()).strftime("%Y-%m-%d")


def iso_week(dt=None):
    y, w, _ = (dt or now_kst()).isocalendar()
    return f"{y}-W{w:02d}"


def utc_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
