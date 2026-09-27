"""GICS sector/industry per ticker via Yahoo assetProfile (crumb-gated) -> sectors.json

Classifications rarely change, so when Yahoo refuses (429 on cloud hosts) each ticker
keeps last week's entry from sectors_prev.json and the cross-tabs are recomputed.
"""
import json, os, time, urllib.request, urllib.error, http.cookiejar
from universe import ALL, UNIVERSE

PREV = (json.load(open("sectors_prev.json")).get("tickers") or {}) if os.path.exists("sectors_prev.json") else {}

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
cj = http.cookiejar.CookieJar()
OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
OP.addheaders = [("User-Agent", UA)]

def get(u, t=25, tries=2):
    last = None
    for i in range(tries):
        try:
            return OP.open(u, timeout=t).read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (500, 502, 503) and i < tries - 1:
                time.sleep(5 * (i + 1))
                continue
            raise
    raise last

def crumb():
    for seed in ("https://fc.yahoo.com", "https://finance.yahoo.com/quote/NVDA"):
        try: get(seed, 15, tries=1)
        except Exception: pass
    try:
        c = get("https://query2.finance.yahoo.com/v1/test/getcrumb", 15, tries=1).decode().strip()
        return c if c and "<" not in c else None
    except Exception: return None

CR = crumb(); print("crumb:", CR)
out = {}
for t in ALL:
    if not CR:
        if t in PREV:
            out[t] = {**PREV[t], "stale": True}
            print(f"  {t:6s} carried  {str(PREV[t].get('sector'))[:24]}", flush=True)
        else:
            out[t] = {"ticker": t, "sector": None, "industry": None, "error": "yahoo unavailable, no prior"}
            print(f"  {t:6s} FAIL no prior classification", flush=True)
        continue
    try:
        u = (f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{t}"
             f"?modules=assetProfile,price&crumb={CR}")
        d = json.loads(get(u))["quoteSummary"]["result"][0]
        ap = d.get("assetProfile", {}) or {}
        pr = d.get("price", {}) or {}
        out[t] = {"ticker": t,
                  "sector": ap.get("sector"), "industry": ap.get("industry"),
                  "country": ap.get("country"), "employees": ap.get("fullTimeEmployees"),
                  "exchange": pr.get("exchangeName"),
                  "long_name": (pr.get("longName") or pr.get("shortName"))}
        print(f"  {t:6s} {str(out[t]['sector'])[:24]:26s} {str(out[t]['industry'])[:38]}", flush=True)
    except Exception as e:
        if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 429):
            print(f"  yahoo refused ({e.code}) at {t} -> carrying prior classifications", flush=True)
            CR = None
        if t in PREV:
            out[t] = {**PREV[t], "stale": True}
        else:
            out[t] = {"ticker": t, "sector": None, "industry": None, "error": str(e)[:60]}
            print(f"  {t:6s} FAIL {str(e)[:50]}", flush=True)
    time.sleep(0.7)

# theme x sector cross-tab
import collections
xtab = collections.defaultdict(lambda: collections.Counter())
for th, tks in UNIVERSE.items():
    for t in tks:
        xtab[th][out.get(t, {}).get("sector") or "Unknown"] += 1
cross = {th: dict(c) for th, c in xtab.items()}
# how concentrated is each theme in one GICS sector?
purity = {}
for th, c in xtab.items():
    tot = sum(c.values()); top, n = c.most_common(1)[0]
    purity[th] = {"dominant_sector": top, "share": round(n / tot * 100), "n_sectors": len(c), "total": tot}

json.dump({"tickers": out, "cross_tab": cross, "purity": purity}, open("sectors.json", "w"), indent=1)
ok = sum(1 for v in out.values() if v.get("sector"))
print(f"\nsaved sectors.json — {ok}/{len(out)} classified")
print("\ntheme -> dominant GICS sector (share of basket):")
for th, p in sorted(purity.items(), key=lambda x: -x[1]["share"]):
    print(f"  {p['share']:3d}%  {th[:38]:40s} {p['dominant_sector']}  ({p['n_sectors']} sectors)")
