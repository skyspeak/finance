"""Market-based macro indicators + sector/thematic benchmarks -> macro.json

Sources (all free, no auth):
  - treasury.gov daily par yield curve CSV  (rates; ^TNX on Yahoo is too sparse)
  - Yahoo v8 chart                          (vol, dollar, commodities, credit, crypto, ETFs)
"""
import json, csv, io, time, math, urllib.request, datetime as dt, statistics as st, os
from yahoo_http import get_json

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
_CACHE_PATH = os.environ.get("CHART_CACHE")
_CACHE = json.load(open(_CACHE_PATH)) if _CACHE_PATH and os.path.exists(_CACHE_PATH) else None

# ---------------------------------------------------------------- Treasury curve
TCSV = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        "daily-treasury-rates.csv/{yr}/all?type=daily_treasury_yield_curve"
        "&field_tdr_date_value={yr}&page&_format=csv")

def treasury(years=None):
    if years is None:
        y = dt.date.today().year
        years = (y - 1, y)
    rows = []
    for yr in years:
        try:
            with urllib.request.urlopen(urllib.request.Request(TCSV.format(yr=yr), headers=UA), timeout=40) as r:
                rd = list(csv.DictReader(io.StringIO(r.read().decode())))
            for x in rd:
                try:
                    d = dt.datetime.strptime(x["Date"], "%m/%d/%Y").date().isoformat()
                except Exception:
                    continue
                g = lambda k: float(x[k]) if x.get(k) not in (None, "", "N/A") else None
                rows.append({"date": d, "m3": g("3 Mo"), "y2": g("2 Yr"), "y5": g("5 Yr"),
                             "y10": g("10 Yr"), "y30": g("30 Yr")})
            print(f"  treasury {yr}: {len(rd)} rows", flush=True)
        except Exception as e:
            print(f"  treasury {yr} FAILED: {str(e)[:70]}", flush=True)
    rows.sort(key=lambda x: x["date"])
    for x in rows:
        x["s2s10"] = round(x["y10"] - x["y2"], 3) if (x["y10"] and x["y2"]) else None
        x["s3m10"] = round(x["y10"] - x["m3"], 3) if (x["y10"] and x["m3"]) else None
    return rows

# ---------------------------------------------------------------- Yahoo series
SERIES = {
    # macro factors
    "^VIX":     ("VIX",              "vol",       "Equity implied volatility"),
    "DX-Y.NYB": ("Dollar Index",     "fx",        "Trade-weighted US dollar"),
    "CL=F":     ("WTI Crude",        "commodity", "Front-month crude oil"),
    "GC=F":     ("Gold",             "commodity", "Front-month gold"),
    "HG=F":     ("Copper",           "commodity", "Front-month copper — industrial demand proxy"),
    "TLT":      ("TLT 20y+ Treasury","rates",     "Long-duration Treasury price"),
    "HYG":      ("HYG High Yield",   "credit",    "High-yield corporate bond price"),
    "LQD":      ("LQD Inv Grade",    "credit",    "Investment-grade corporate bond price"),
    "BTC-USD":  ("Bitcoin",          "crypto",    "Crypto risk appetite"),
    # benchmarks
    "^GSPC":    ("S&P 500",          "benchmark", "Broad market"),
    "^NDX":     ("Nasdaq 100",       "benchmark", "Large-cap growth"),
    "^RUT":     ("Russell 2000",     "benchmark", "Small caps"),
    # GICS sector SPDRs
    "XLK": ("Technology", "sector", "GICS Information Technology"),
    "XLE": ("Energy", "sector", "GICS Energy"),
    "XLU": ("Utilities", "sector", "GICS Utilities"),
    "XLV": ("Health Care", "sector", "GICS Health Care"),
    "XLF": ("Financials", "sector", "GICS Financials"),
    "XLI": ("Industrials", "sector", "GICS Industrials"),
    "XLB": ("Materials", "sector", "GICS Materials"),
    "XLY": ("Cons. Discretionary", "sector", "GICS Consumer Discretionary"),
    "XLP": ("Cons. Staples", "sector", "GICS Consumer Staples"),
    "XLC": ("Comm. Services", "sector", "GICS Communication Services"),
    "XLRE": ("Real Estate", "sector", "GICS Real Estate"),
    # thematic benchmarks
    "SMH":  ("Semiconductors", "thematic", "VanEck Semiconductor"),
    "ITA":  ("Aerospace & Defense", "thematic", "iShares US Aerospace & Defense"),
    "URA":  ("Uranium", "thematic", "Global X Uranium"),
    "TAN":  ("Solar", "thematic", "Invesco Solar"),
    "BOTZ": ("Robotics & AI", "thematic", "Global X Robotics & AI"),
    "HACK": ("Cybersecurity", "thematic", "Amplify Cybersecurity"),
    "ARKG": ("Genomics", "thematic", "ARK Genomic Revolution"),
    "LIT":  ("Lithium & Battery", "thematic", "Global X Lithium"),
    "FINX": ("FinTech", "thematic", "Global X FinTech"),
    "IGV":  ("Software", "thematic", "iShares Expanded Tech-Software"),
}

def chart(sym, rng="2y"):
    if _CACHE and sym in _CACHE and _CACHE[sym].get("timestamp"):
        d = _CACHE[sym]
    else:
        u = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval=1d"
        d = get_json(u, UA)["chart"]["result"][0]
    ts, c = d["timestamp"], d["indicators"]["quote"][0]["close"]
    pair = [(t, v) for t, v in zip(ts, c) if v is not None]
    return ([dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d") for t, _ in pair],
            [v for _, v in pair], d["meta"])

def pct(a, b): return round((a/b - 1) * 100, 2) if (a is not None and b) else None
def pctile(series, v):
    s = sorted(series)
    if not s: return None
    return round(sum(1 for x in s if x <= v) / len(s) * 100)

def build():
    out = {"asof": None, "curve": [], "series": {}}
    print("Treasury curve:")
    out["curve"] = treasury()
    if out["curve"]:
        out["asof"] = out["curve"][-1]["date"]
        last = out["curve"][-1]
        prev = {k: None for k in ("w", "m", "q")}
        by = {x["date"]: x for x in out["curve"]}
        dates = [x["date"] for x in out["curve"]]
        def back(n):
            i = max(0, len(dates) - 1 - n)
            return out["curve"][i]
        out["rates"] = {
            "asof": last["date"],
            "levels": {k: last.get(k) for k in ("m3", "y2", "y5", "y10", "y30")},
            "s2s10": last.get("s2s10"), "s3m10": last.get("s3m10"),
            "chg_1w_bp":  round((last["y10"] - back(5)["y10"]) * 100) if last.get("y10") and back(5).get("y10") else None,
            "chg_1m_bp":  round((last["y10"] - back(21)["y10"]) * 100) if last.get("y10") and back(21).get("y10") else None,
            "chg_3m_bp":  round((last["y10"] - back(63)["y10"]) * 100) if last.get("y10") and back(63).get("y10") else None,
            "s2s10_1m_bp": round((last["s2s10"] - back(21)["s2s10"]) * 100) if last.get("s2s10") and back(21).get("s2s10") else None,
            "y10_1y_range": [min(x["y10"] for x in out["curve"][-252:] if x.get("y10")),
                             max(x["y10"] for x in out["curve"][-252:] if x.get("y10"))],
        }
        out["rates"]["y10_pctile_1y"] = pctile([x["y10"] for x in out["curve"][-252:] if x.get("y10")], last["y10"])

    print("Yahoo series:")
    for sym, (name, kind, desc) in SERIES.items():
        try:
            dates, vals, meta = chart(sym)
            if len(vals) < 30:
                print(f"  SKIP {sym:10s} only {len(vals)} points"); continue
            w = vals[-6] if len(vals) > 6 else None
            m = vals[-22] if len(vals) > 22 else None
            q = vals[-64] if len(vals) > 64 else None
            y = vals[-253] if len(vals) > 253 else vals[0]
            y1 = vals[-252:]
            out["series"][sym] = {
                "symbol": sym, "name": name, "kind": kind, "desc": desc,
                "last": round(vals[-1], 2), "asof": dates[-1],
                "chg_1w": pct(vals[-1], w), "chg_1m": pct(vals[-1], m),
                "chg_3m": pct(vals[-1], q), "chg_1y": pct(vals[-1], y),
                "lo_1y": round(min(y1), 2), "hi_1y": round(max(y1), 2),
                "pctile_1y": pctile(y1, vals[-1]),
                "dates": dates[-260:], "vals": [round(v, 4) for v in vals[-260:]],
            }
            print(f"  ok   {sym:10s} {name[:22]:24s} last={vals[-1]:>10.2f}  1m={out['series'][sym]['chg_1m']}", flush=True)
        except Exception as e:
            print(f"  FAIL {sym:10s} {str(e)[:50]}", flush=True)
        time.sleep(0.7)

    # derived credit-appetite spread proxy: HYG relative to LQD
    S = out["series"]
    if "HYG" in S and "LQD" in S:
        hd, hv = S["HYG"]["dates"], S["HYG"]["vals"]
        ld = {d: v for d, v in zip(S["LQD"]["dates"], S["LQD"]["vals"])}
        dates, ratio = [], []
        for d, v in zip(hd, hv):
            if d in ld and ld[d]:
                dates.append(d); ratio.append(v / ld[d])
        if len(ratio) > 60:
            out["series"]["CREDIT"] = {
                "symbol": "CREDIT", "name": "Credit Appetite (HYG/LQD)", "kind": "credit",
                "desc": "High-yield relative to investment grade — rising means risk appetite improving",
                "last": round(ratio[-1], 4), "asof": dates[-1],
                "chg_1w": pct(ratio[-1], ratio[-6]), "chg_1m": pct(ratio[-1], ratio[-22]),
                "chg_3m": pct(ratio[-1], ratio[-64]),
                "chg_1y": pct(ratio[-1], ratio[-253] if len(ratio) > 253 else ratio[0]),
                "lo_1y": round(min(ratio[-252:]), 4), "hi_1y": round(max(ratio[-252:]), 4),
                "pctile_1y": pctile(ratio[-252:], ratio[-1]),
                "dates": dates[-260:], "vals": [round(v, 5) for v in ratio[-260:]],
            }
            print(f"  ok   CREDIT     HYG/LQD ratio            last={ratio[-1]:.4f}")

    json.dump(out, open("macro.json", "w"), indent=1)
    print(f"\nsaved macro.json — curve {len(out['curve'])} days, {len(out['series'])} series, asof {out['asof']}")

if __name__ == "__main__":
    build()
