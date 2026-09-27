"""Daily history in Yahoo v8 chart shape, from sources that work on cloud hosts.

Yahoo rate-limits datacenter IPs (Railway gets 429 on every call), so the chart
callers (prices.py, tech.py, macro.py) go through daily_chart() instead:

  1. CHART_CACHE file, if set (unchanged behaviour for replays)
  2. CBOE delayed-quotes historical OHLCV (stocks, ETFs, _SPX/_VIX/_RUT) plus the
     latest CBOE quote for the most recent close
  3. Yahoo, one quick attempt — still works from residential IPs

Symbols keep their Yahoo spelling everywhere downstream; PROXY maps the index,
futures, FX and crypto symbols CBOE doesn't carry to the ETF that tracks them
(macro.py / factors.py labels say so). FRED was tried and stalls scripted clients.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
CBOE_HIST = "https://cdn.cboe.com/api/global/delayed_quotes/charts/historical/{s}.json"
CBOE_QUOTE = "https://cdn.cboe.com/api/global/delayed_quotes/quotes/{s}.json"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{s}?range={rng}&interval=1d"

CBOE_INDEX = {"^GSPC": "_SPX", "^VIX": "_VIX", "^RUT": "_RUT"}
PROXY = {"^NDX": "QQQ", "CL=F": "USO", "BTC-USD": "IBIT", "GC=F": "GLD", "HG=F": "CPER", "DX-Y.NYB": "UUP"}

# CBOE 429s after ~50 back-to-back calls: space calls out and back off hard on 429.
MIN_GAP = float(os.environ.get("CBOE_MIN_GAP", "0.6"))
BACKOFF = (20, 45, 90)
# prices.py, tech.py and macro.py want the same histories; fetch each once per day.
DAY_CACHE = os.environ.get("MD_CACHE_DIR", ".md_cache")
_last_call = [0.0]

_CACHE_PATH = os.environ.get("CHART_CACHE")
_CACHE = json.load(open(_CACHE_PATH)) if _CACHE_PATH and os.path.exists(_CACHE_PATH) else None
SOURCES: dict[str, str] = {}  # symbol -> source actually used, for logging/provenance


def _get(url: str, timeout: int = 40, tries: int = 4) -> bytes:
    last = None
    for i in range(tries):
        wait = MIN_GAP - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 404):
                raise
            delay = BACKOFF[min(i, len(BACKOFF) - 1)] if e.code == 429 else 3 * (i + 1)
        except Exception as e:  # timeouts, resets
            last = e
            delay = 3 * (i + 1)
        if i < tries - 1:
            print(f"  retry in {delay}s: {str(last)[:60]}  {url.split('?')[0][-60:]}", flush=True)
            time.sleep(delay)
    raise last


def _day_cache(sym: str, rng: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in sym)
    return os.path.join(DAY_CACHE, f"{dt.date.today().isoformat()}_{safe}_{rng}.json")


def _epoch(day: str) -> int:
    # 20:00 UTC ~ US close, so utcfromtimestamp() downstream lands on the same date
    return int(dt.datetime.strptime(day, "%Y-%m-%d").replace(hour=20, tzinfo=dt.timezone.utc).timestamp())


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _shape(sym: str, rows: list[tuple], rng_days: int, name: str | None = None) -> dict:
    """rows: [(YYYY-MM-DD, close, high, low, volume)] ascending -> Yahoo chart result."""
    cut = (dt.date.today() - dt.timedelta(days=rng_days)).isoformat()
    rows = [r for r in rows if r[0] >= cut and r[1] is not None]
    if not rows:
        raise ValueError(f"{sym}: no rows in range")
    closes = [r[1] for r in rows]
    yr = (dt.date.today() - dt.timedelta(days=365)).isoformat()
    y = [r for r in rows if r[0] >= yr] or rows
    return {
        "meta": {
            "symbol": sym, "currency": "USD", "longName": name,
            "regularMarketPrice": closes[-1], "regularMarketTime": _epoch(rows[-1][0]),
            "fiftyTwoWeekHigh": max((r[2] if r[2] is not None else r[1]) for r in y),
            "fiftyTwoWeekLow": min((r[3] if r[3] is not None else r[1]) for r in y),
            "chartPreviousClose": closes[-2] if len(closes) > 1 else None,
        },
        "timestamp": [_epoch(r[0]) for r in rows],
        "indicators": {"quote": [{"close": closes, "volume": [r[4] for r in rows]}]},
    }


def _cboe(sym: str, rng_days: int) -> dict:
    s = CBOE_INDEX.get(sym, PROXY.get(sym, sym)).replace(".", "/")
    data = json.loads(_get(CBOE_HIST.format(s=s))).get("data") or []
    rows = [(d["date"], _num(d.get("close")), _num(d.get("high")), _num(d.get("low")), _num(d.get("volume")))
            for d in data]
    rows = [r for r in rows if r[1]]
    # The history file lags a session; the quote carries the latest close.
    try:
        q = json.loads(_get(CBOE_QUOTE.format(s=s))).get("data") or {}
        day = (q.get("last_trade_time") or "")[:10]
        px = _num(q.get("close")) or _num(q.get("current_price"))
        if day and px and rows and day > rows[-1][0]:
            rows.append((day, px, _num(q.get("high")), _num(q.get("low")), _num(q.get("volume"))))
    except Exception:
        pass
    return _shape(sym, rows, rng_days)


def _yahoo(sym: str, rng: str) -> dict:
    return json.loads(_get(YAHOO.format(s=sym, rng=rng), timeout=20, tries=1))["chart"]["result"][0]


def daily_chart(sym: str, rng: str = "2y") -> dict:
    """Yahoo-v8-shaped chart result for sym. Raises if every source fails."""
    if _CACHE and sym in _CACHE and _CACHE[sym].get("timestamp"):
        SOURCES[sym] = "cache"
        return _CACHE[sym]
    cached = _day_cache(sym, rng)
    if os.path.exists(cached):
        blob = json.load(open(cached))
        SOURCES[sym] = blob["source"]
        return blob["chart"]
    rng_days = int(rng[:-1]) * 365 if rng.endswith("y") else int(rng[:-2]) * 31 if rng.endswith("mo") else 730
    chain = [("cboe", lambda: _cboe(sym, rng_days)), ("yahoo", lambda: _yahoo(sym, rng))]
    errors = []
    for name, fn in chain:
        try:
            out = fn()
            SOURCES[sym] = name if sym not in PROXY or name != "cboe" else f"cboe:{PROXY[sym]}"
            os.makedirs(DAY_CACHE, exist_ok=True)
            json.dump({"source": SOURCES[sym], "chart": out}, open(cached, "w"))
            return out
        except Exception as e:
            errors.append(f"{name}: {str(e)[:60]}")
    raise RuntimeError(f"{sym}: all sources failed ({'; '.join(errors)})")


def cboe_json(url: str) -> dict:
    """Any CBOE delayed-quotes JSON, sharing the pacing/backoff above (options chains)."""
    return json.loads(_get(url, timeout=60))


def cboe_quote(sym: str) -> dict:
    """Latest CBOE delayed quote (current_price, close, iv30, ...)."""
    return json.loads(_get(CBOE_QUOTE.format(s=sym.replace(".", "/")), tries=2)).get("data") or {}
