import json, time, datetime as dt, os
from universe import ALL, UNIVERSE
from market_data import daily_chart, SOURCES

# Last good snapshot (staged by job.py): names for sources that don't carry them,
# and a stale carry-forward for tickers no source returns this week.
PREV = json.load(open("prices_prev.json")) if os.path.exists("prices_prev.json") else {}

def pct(a, b):
    if a is None or b in (None, 0): return None
    return round((a - b) / b * 100, 2)

def nearest(ts, closes, target):
    best = None
    for i, t in enumerate(ts):
        if closes[i] is None: continue
        if t <= target: best = closes[i]
        else: break
    return best

out = {}
for t in ALL:
    try:
        res = daily_chart(t)
        meta = res["meta"]
        ts = res["timestamp"]
        closes = res["indicators"]["quote"][0]["close"]
        adj = [c for c in closes if c is not None]
        last = meta.get("regularMarketPrice") or adj[-1]
        now = meta["regularMarketTime"]
        row = {
            "ticker": t,
            "name": meta.get("longName") or meta.get("shortName") or PREV.get(t, {}).get("name") or t,
            "currency": meta.get("currency"),
            "last": round(last, 2),
            "asof": dt.datetime.utcfromtimestamp(now).strftime("%Y-%m-%d"),
            "wk52_high": round(meta.get("fiftyTwoWeekHigh") or max(adj), 2),
            "wk52_low": round(meta.get("fiftyTwoWeekLow") or min(adj), 2),
            "prev_close": meta.get("chartPreviousClose"),
        }
        row["pct_off_high"] = pct(last, row["wk52_high"])
        row["pct_abv_low"] = pct(last, row["wk52_low"])
        for label, days in [("1w",7),("1m",30),("3m",91),("1y",365)]:
            p = nearest(ts, closes, now - days*86400)
            row[f"px_{label}_ago"] = round(p,2) if p else None
            row[f"chg_{label}"] = pct(last, p)
        row["source"] = SOURCES.get(t)
        out[t] = row
        print(t, row["last"], row["chg_1y"], row["source"], flush=True)
    except Exception as e:
        if t in PREV:
            out[t] = {**PREV[t], "stale": True}
            print("STALE", t, "carried from", PREV[t].get("asof"), "-", str(e)[:120], flush=True)
        else:
            print("FAIL", t, e, flush=True)
    time.sleep(0.2)

json.dump(out, open("prices.json","w"), indent=1)
print("saved", len(out), "| stale:", [t for t, r in out.items() if r.get("stale")])
