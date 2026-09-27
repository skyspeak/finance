"""Fundamentals + FINRA short interest -> enrich.json, shortint.json

Yahoo quoteSummary (crumb-gated) is tried first; it works from residential IPs.
Cloud hosts (Railway) get 429s, so on the first refusal every remaining ticker is
built from SEC EDGAR filings (fundamentals.py) + FINRA short interest + this week's
price. Fields neither source has (forward P/E, PEG, recommendation, estimates,
float) are carried from last week's enrich_prev.json and listed in row["stale"].
"""
import json, os, time, urllib.request, urllib.error, http.cookiejar, datetime as dt, csv, io
from universe import ALL
import fundamentals as F

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
cj = http.cookiejar.CookieJar()
OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
OP.addheaders = [("User-Agent", UA)]

def get(url, timeout=25, tries=2):
    last = None
    for i in range(tries):
        try:
            with OP.open(url, timeout=timeout) as r:
                return r.read()
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

MODS = "defaultKeyStatistics,calendarEvents,financialData,summaryDetail"

def v(d, k, default=None):
    x = (d or {}).get(k)
    if isinstance(x, dict): return x.get("raw", default)
    return x if x is not None else default

def yahoo_row(t, cr):
    row = {"ticker": t}
    u = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{t}?modules={MODS}&crumb={cr}"
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
    row["source"] = "yahoo"
    return row

# ---- FINRA official consolidated short interest (latest 2 settlement periods) ----
def finra():
    fin = {}
    base = "https://api.finra.org/{kind}/group/otcMarket/name/consolidatedShortInterest"
    try:
        # FINRA only allows an exact settlementDate per query (no sorting across
        # partitions), so ask which dates exist and pull the latest two.
        req = urllib.request.Request(base.format(kind="partitions"), headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            parts = json.load(r)["availablePartitions"]
        dates = sorted((p["partitions"][0] for p in parts), reverse=True)[:2]
        rd = []
        for d in dates:
            body = {"limit": 5000,
                    "compareFilters": [{"compareType": "EQUAL", "fieldName": "settlementDate", "fieldValue": d}],
                    "domainFilters": [{"fieldName": "symbolCode", "values": ALL}]}
            req = urllib.request.Request(base.format(kind="data"), data=json.dumps(body).encode(),
                headers={"Content-Type":"application/json","User-Agent":UA})
            with urllib.request.urlopen(req, timeout=90) as r: raw = r.read().decode()
            rd += list(csv.DictReader(io.StringIO(raw)))
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
    return fin

# Everything the EDGAR path computes; anything it can't is carried from last week.
COMPUTED = ("market_cap", "shares_out", "enterprise_value", "trail_pe", "ps", "pb", "ev_rev", "ev_ebitda",
            "profit_margin", "gross_margin", "op_margin", "rev_growth", "earn_growth", "fcf", "fcf_yield",
            "total_cash", "total_debt", "roe")
CARRIED = ("float_shares", "beta", "fwd_pe", "peg", "rec_key", "div_yield", "earnings_estimate", "rev_estimate")
SHORT = ("shares_short", "shares_short_prior", "short_ratio", "short_pct_float", "short_date")

def fallback_row(t, edgar, fin, prev, price):
    row, stale = {"ticker": t}, []
    comp = None
    try:
        facts = edgar.facts(t)
        comp = F.compute(facts, price, prev.get("shares_out")) if facts else None
    except Exception as ex:
        print(f"  edgar {t}: {str(ex)[:80]}", flush=True)
    for k in COMPUTED:
        if comp and comp.get(k) is not None: row[k] = comp[k]
        elif prev.get(k) is not None: row[k] = prev[k]; stale.append(k)
    for k in CARRIED:
        if prev.get(k) is not None: row[k] = prev[k]; stale.append(k)
    f = fin.get(t)
    if f:
        cur = f[0]
        row["shares_short"] = cur["short_qty"]
        row["shares_short_prior"] = f[1]["short_qty"] if len(f) > 1 else cur["prior_qty"]
        row["short_ratio"] = cur["days_to_cover"]
        row["short_date"] = int(dt.datetime.strptime(cur["settlement"], "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp())
        denom = row.get("float_shares") or row.get("shares_out")
        row["short_pct_float"] = round(cur["short_qty"] / denom, 4) if denom else None
    else:
        for k in SHORT:
            if prev.get(k) is not None: row[k] = prev[k]; stale.append(k)
    # Only keep carried earnings dates that are still ahead of us.
    today = dt.date.today().isoformat()
    ds = [d for d in (prev.get("earnings_dates") or []) if d >= today]
    row["earnings_dates"], row["earnings_next"] = ds, (ds[0] if ds else None)
    if ds: stale.append("earnings_dates")
    row["source"] = "edgar+finra" if comp else ("finra+carried" if f else "carried")
    row["stale"] = stale
    if not comp and not prev:
        row["error"] = "no EDGAR data and no prior snapshot"
    return row

if __name__ == "__main__":
    PREV = json.load(open("enrich_prev.json")) if os.path.exists("enrich_prev.json") else {}
    PRICES = json.load(open("prices.json")) if os.path.exists("prices.json") else {}
    fin = finra()
    CR = crumb()
    print("crumb:", CR, "| yahoo" if CR else "| yahoo unavailable -> EDGAR + FINRA + carry-forward", flush=True)
    edgar = F.Edgar()
    out = {}
    for t in ALL:
        row = None
        if CR:
            try:
                row = yahoo_row(t, CR)
            except urllib.error.HTTPError as ex:
                if ex.code in (401, 403, 429):
                    print(f"yahoo refused ({ex.code}) at {t} -> switching to EDGAR + FINRA", flush=True)
                    CR = None
                else:
                    row = {"ticker": t, "error": str(ex)[:90]}
            except Exception as ex:
                row = {"ticker": t, "error": str(ex)[:90]}
        if row is None:
            row = fallback_row(t, edgar, fin, PREV.get(t, {}), PRICES.get(t, {}).get("last"))
        out[t] = row
        if row.get("error"): print("FAIL", t, row["error"][:70], flush=True)
        else: print(f"{t:6s} {row['source']:13s} mc={row.get('market_cap')} shortfloat={row.get('short_pct_float')} earn={row.get('earnings_next')} stale={len(row.get('stale') or [])}", flush=True)
        time.sleep(0.7 if CR else 0)

    json.dump(out, open("enrich.json", "w"), indent=1)
    print("enrich saved", sum(1 for r in out.values() if not r.get("error")), "/", len(out),
          "| sources:", {s: sum(1 for r in out.values() if r.get("source") == s) for s in {r.get("source") for r in out.values()}})
    json.dump(fin, open("shortint.json", "w"), indent=1)
