import json, time, urllib.request, datetime as dt
from universe import ALL, UNIVERSE

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"}

def fetch(t):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=2y&interval=1d"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)

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
        d = fetch(t)
        res = d["chart"]["result"][0]
        meta = res["meta"]
        ts = res["timestamp"]
        closes = res["indicators"]["quote"][0]["close"]
        adj = [c for c in closes if c is not None]
        last = meta.get("regularMarketPrice") or adj[-1]
        now = meta["regularMarketTime"]
        row = {
            "ticker": t,
            "name": meta.get("longName") or meta.get("shortName") or t,
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
        out[t] = row
        print(t, row["last"], row["chg_1y"], flush=True)
    except Exception as e:
        print("FAIL", t, e, flush=True)
    time.sleep(0.35)

json.dump(out, open("prices.json","w"), indent=1)
print("saved", len(out))
