"""Clock for the weekly run. Override with ASOF=YYYY-MM-DD for replays."""
import datetime as dt
import os


def today():
    raw = os.environ.get("ASOF")
    if raw:
        return dt.date.fromisoformat(raw)
    return dt.date.today()
