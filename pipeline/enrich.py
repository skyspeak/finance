"""Yahoo quoteSummary (crumb-gated) + FINRA short interest -> enrich.json, shortint.json"""
import json, time, urllib.request, http.cookiejar, datetime as dt, csv, io
from universe import ALL

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
cj = http.cookiejar.CookieJar()
OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
OP.addheaders = [("User-Agent", UA)]

def get(url, timeout=25):
    with OP.open(url, timeout=timeout) as r: return r.read()

def crumb():
    for seed in ("https://fc.yahoo.com", "https://finance.yahoo.com/quote/NVDA"):
        try: get(seed, 15)
        except Exception: pass
    try:
        c = get("https://query2.finance.yahoo.com/v1/test/getcrumb", 15).decode().strip()
        return c if c and "<" not in c else None
    except Exception: return None

CR = crumb()
print("crumb:", CR)
MODS = "defaultKeyStatistics,calendarEvents,financialData,summaryDetail"

def v(d, k, default=None):
    x = (d or {}).get(k)
    if isinstance(x, dict): return x.get("raw", default)
    return x if x is not None else default

out = {}
for t in ALL:
    row = {"ticker": t}
    try:
        u = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{t}?modules={MODS}&crumb={CR}"
        d = json.loads(get(u))["quoteSummary"]["result"][0]
        ks, ce, fd, sd = d.get("defaultKeyStatistics", {}), d.get("calendarEvents", {}), d.get("financialData", {}), d.get("summaryDetail", {})
        row.update({
            "market_cap": v(sd, "marketCap") or v(ks, "enterpriseValue"),
            "enterprise_value": v(ks, "enterpriseValue"),
            "float_shares": v(ks, "floatShares"),
            "shares_out": v(ks, "sharesOutstanding"),
            "shares_short": v(ks, "sharesShort"),
            "shares_short_prior": v(ks, "sharesShortPriorMonth"),
            "short_ratio": v(ks, "shortRatio"),
            "short_pct_float": v(ks, "shortPercentOfFloat"),
            "short_date": v(ks, "dateShortInterest"),
            "beta": v(ks, "beta") or v(sd, "beta"),
            "fwd_pe": v(sd, "forwardPE") or v(ks, "forwardPE"),
            "trail_pe": v(sd, "trailingPE"),
            "peg": v(ks, "pegRatio"),
            "ps": v(ks, "priceToSalesTrailing12Months") or v(sd, "priceToSalesTrailing12Months"),
            "pb": v(ks, "priceToBook"),
            "ev_rev": v(ks, "enterpriseToRevenue"),
            "ev_ebitda": v(ks, "enterpriseToEbitda"),
            "profit_margin": v(fd, "profitMargins"),
            "gross_margin": v(fd, "grossMargins"),
            "op_margin": v(fd, "operatingMargins"),
            "rev_growth": v(fd, "revenueGrowth"),
            "earn_growth": v(fd, "earningsGrowth"),
            "fcf": v(fd, "freeCashflow"),
            "total_cash": v(fd, "totalCash"),
            "total_debt": v(fd, "totalDebt"),
            "roe": v(fd, "returnOnEquity"),
            "rec_key": (fd or {}).get("recommendationKey"),
            "div_yield": v(sd, "dividendYield"),
        })
        ed = (ce or {}).get("earnings", {}) or {}
        dates = ed.get("earningsDate") or []
        ds = [dt.datetime.utcfromtimestamp(x["raw"]).strftime("%Y-%m-%d") for x in dates if isinstance(x, dict) and x.get("raw")]
        row["earnings_dates"] = ds
        row["earnings_next"] = ds[0] if ds else None
        row["earnings_estimate"] = v(ed, "earningsAverage")
        row["rev_estimate"] = v(ed, "revenueAverage")
        if row.get("fcf") and row.get("market_cap"): row["fcf_yield"] = round(row["fcf"]/row["market_cap"]*100, 2)
        print(f"{t:6s} mc={row.get('market_cap')} shortfloat={row.get('short_pct_float')} earn={row.get('earnings_next')}", flush=True)
    except Exception as ex:
        row["error"] = str(ex)[:90]; print("FAIL", t, str(ex)[:70], flush=True)
    out[t] = row
    time.sleep(0.3)

json.dump(out, open("enrich.json", "w"), indent=1)
print("enrich saved", sum(1 for r in out.values() if not r.get("error")), "/", len(out))

# ---- FINRA official consolidated short interest (latest 2 settlement periods) ----
fin = {}
try:
    req = urllib.request.Request("https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest",
        data=json.dumps({"limit":5000,"sortFields":["-settlementDate"]}).encode(),
        headers={"Content-Type":"application/json","User-Agent":UA})
    with urllib.request.urlopen(req, timeout=90) as r: raw = r.read().decode()
    rd = list(csv.DictReader(io.StringIO(raw)))
    uni = set(ALL)
    for r in rd:
        s = r.get("symbolCode")
        if s in uni:
            fin.setdefault(s, []).append({
                "settlement": r.get("settlementDate"),
                "short_qty": float(r["currentShortPositionQuantity"] or 0),
                "prior_qty": float(r["previousShortPositionQuantity"] or 0),
                "adv": float(r["averageDailyVolumeQuantity"] or 0),
                "days_to_cover": float(r["daysToCoverQuantity"] or 0),
                "change_pct": float(r["changePercent"] or 0)})
    for s in fin: fin[s].sort(key=lambda x: x["settlement"], reverse=True)
    print("FINRA covered:", len(fin), "of", len(ALL), "| latest:", max((v[0]["settlement"] for v in fin.values()), default="none"))
except Exception as ex:
    print("FINRA failed:", str(ex)[:120])
json.dump(fin, open("shortint.json", "w"), indent=1)
