"""Macro factor sensitivity, regimes, breadth, dispersion, relative strength -> factors.json

Univariate OLS of daily returns on each macro factor. Univariate (not multivariate)
on purpose: with 8 correlated factors and ~250 observations, multivariate betas are
unstable and hard to read. Univariate beta + R-squared is interpretable and honest.
"""
import json, math, collections, datetime as dt, statistics as st
from universe import UNIVERSE, ALL

HIST = json.load(open("hist.json"))
MAC = json.load(open("macro.json"))
TECH = json.load(open("tech.json"))["tech"]
D2 = json.load(open("data2.json"))
rows = {r["ticker"]: r for r in D2["rows"]}
S = MAC["series"]

# ---------------------------------------------------------------- factor series
def rets(dates, vals):
    return {dates[i]: (vals[i] / vals[i-1] - 1) for i in range(1, len(vals)) if vals[i-1]}

def diffs(dates, vals):
    return {dates[i]: (vals[i] - vals[i-1]) for i in range(1, len(vals))}

FACTORS = {}
def add(key, label, desc, series, invert=False, unit="%"):
    FACTORS[key] = {"label": label, "desc": desc, "unit": unit,
                    "series": {k: (-v if invert else v) for k, v in series.items()}}

# rates from the Treasury curve, in basis points
curve = [x for x in MAC["curve"] if x.get("y10") and x.get("s2s10") is not None]
cd = [x["date"] for x in curve]
add("RATES", "10y yield", "Daily change in the 10-year Treasury yield, basis points",
    diffs(cd, [x["y10"] * 100 for x in curve]), unit="bp")
add("CURVE", "2s10s slope", "Daily change in the 2s10s curve slope, basis points",
    diffs(cd, [x["s2s10"] * 100 for x in curve]), unit="bp")

for sym, key, label, desc in [
    ("DX-Y.NYB", "DOLLAR", "US dollar",      "Daily return on the US dollar index (UUP ETF)"),
    ("CL=F",     "OIL",    "Crude oil",      "Daily return on front-month WTI (USO ETF)"),
    ("GC=F",     "GOLD",   "Gold",           "Daily return on gold (GLD ETF)"),
    ("HG=F",     "COPPER", "Copper",         "Daily return on copper (CPER ETF) — industrial demand proxy"),
    ("^VIX",     "VOL",    "VIX",            "Daily return on the VIX"),
    ("CREDIT",   "CREDIT", "Credit appetite","Daily return on HYG/LQD — rising means risk appetite improving"),
    ("^GSPC",    "SPX",    "S&P 500",        "Daily return on the S&P 500 — the market factor"),
]:
    if sym in S:
        add(key, label, desc, rets(S[sym]["dates"], S[sym]["vals"]))

print("factors:", list(FACTORS))

# ---------------------------------------------------------------- return series
def series_for(tickers):
    """Equal-weighted daily returns across tickers, keyed by date."""
    per = []
    for t in tickers:
        h = HIST.get(t)
        if not h or len(h["c"]) < 60: continue
        ds = [dt.datetime.utcfromtimestamp(x).strftime("%Y-%m-%d") for x in h["ts"]]
        per.append(rets(ds, h["c"]))
    if not per: return {}
    keys = set.intersection(*[set(p) for p in per]) if len(per) > 1 else set(per[0])
    return {k: sum(p[k] for p in per) / len(per) for k in keys}

TICK_R = {t: series_for([t]) for t in ALL}
THEME_R = {th: series_for(tk) for th, tk in UNIVERSE.items()}

def ols(y_map, x_map, min_n=60):
    """Univariate OLS. Returns beta, r2, n, and t-stat."""
    keys = sorted(set(y_map) & set(x_map))
    if len(keys) < min_n: return None
    y = [y_map[k] for k in keys]; x = [x_map[k] for k in keys]
    n = len(keys); mx, my = sum(x)/n, sum(y)/n
    sxx = sum((a-mx)**2 for a in x); sxy = sum((a-mx)*(b-my) for a, b in zip(x, y))
    if sxx == 0: return None
    beta = sxy / sxx; alpha = my - beta*mx
    ss_tot = sum((b-my)**2 for b in y)
    resid = [b - (alpha + beta*a) for a, b in zip(x, y)]
    ss_res = sum(r*r for r in resid)
    r2 = 1 - ss_res/ss_tot if ss_tot else None
    se = math.sqrt((ss_res/(n-2))/sxx) if n > 2 and sxx else None
    return {"beta": beta, "r2": round(r2, 3) if r2 is not None else None,
            "n": n, "t": round(beta/se, 2) if se else None}

def scale(key, beta):
    """Express beta in readable units: % move per 10bp for rates, per 1% for returns."""
    if beta is None: return None
    return round(beta * 10 * 100, 2) if FACTORS[key]["unit"] == "bp" else round(beta, 2)

def exposures(rmap):
    out = {}
    for key in FACTORS:
        f = ols(rmap, FACTORS[key]["series"])
        if not f: out[key] = None; continue
        out[key] = {"beta": scale(key, f["beta"]), "r2": f["r2"], "t": f["t"], "n": f["n"]}
    return out

THEME_X = {th: exposures(r) for th, r in THEME_R.items()}
TICK_X = {t: exposures(r) for t, r in TICK_R.items()}

# RATES/CURVE/DOLLAR/OIL/GOLD/COPPER/CREDIT are genuine macro.
# SPX is the market factor; VOL (VIX) is the market factor in another costume —
# it "wins" every univariate horse race simply because stocks fall when vol rises.
# Both are excluded from the macro ranking and reported separately.
MARKET = {"SPX", "VOL"}
TRUE_MACRO = [k for k in FACTORS if k not in MARKET]

def best(x, pool):
    c = [(k, v) for k, v in x.items() if k in pool and v and v["r2"] is not None]
    if not c: return None
    k, v = max(c, key=lambda kv: kv[1]["r2"])
    return {"factor": k, "label": FACTORS[k]["label"], **v}

def residualize(rmap):
    """Strip out market beta, return the residual series. Isolates macro effects
    that are NOT just 'this is a high-beta stock'."""
    spx = FACTORS["SPX"]["series"]
    keys = sorted(set(rmap) & set(spx))
    if len(keys) < 60: return {}
    y = [rmap[k] for k in keys]; x = [spx[k] for k in keys]
    n = len(keys); mx, my = sum(x)/n, sum(y)/n
    sxx = sum((a-mx)**2 for a in x)
    if not sxx: return {}
    b = sum((a-mx)*(c-my) for a, c in zip(x, y))/sxx; a0 = my - b*mx
    return {k: rmap[k] - (a0 + b*spx[k]) for k in keys}

for th in THEME_X:
    THEME_X[th]["_best"] = best(THEME_X[th], TRUE_MACRO)
    THEME_X[th]["_resid"] = exposures(residualize(THEME_R[th]))
    THEME_X[th]["_best_resid"] = best(THEME_X[th]["_resid"], TRUE_MACRO)
for t in TICK_X:
    TICK_X[t]["_best"] = best(TICK_X[t], TRUE_MACRO)

# ---------------------------------------------------------------- rolling corr
def roll_corr(y_map, x_map, win=60):
    keys = sorted(set(y_map) & set(x_map))
    outd, outv = [], []
    for i in range(win, len(keys)):
        w = keys[i-win:i]
        y = [y_map[k] for k in w]; x = [x_map[k] for k in w]
        my, mx = sum(y)/win, sum(x)/win
        sy = math.sqrt(sum((a-my)**2 for a in y)); sx = math.sqrt(sum((a-mx)**2 for a in x))
        if sy and sx:
            outd.append(keys[i])
            outv.append(round(sum((a-my)*(b-mx) for a, b in zip(y, x))/(sy*sx), 3))
    return {"dates": outd, "vals": outv}

ROLL = {th: {k: roll_corr(THEME_R[th], FACTORS[k]["series"]) for k in ("RATES", "DOLLAR", "COPPER", "VOL", "CREDIT")}
        for th in UNIVERSE}

# ---------------------------------------------------------------- regime
def chg(sym, n=21):
    s = S.get(sym)
    if not s or len(s["vals"]) <= n: return None
    return (s["vals"][-1] / s["vals"][-1-n] - 1) * 100

r10_1m = MAC.get("rates", {}).get("chg_1m_bp")
dollar_1m = chg("DX-Y.NYB"); vix_p = S.get("^VIX", {}).get("pctile_1y")
credit_1m = S.get("CREDIT", {}).get("chg_1m"); copper_1m = chg("HG=F")
REGIME = {
    "rates":  {"value": r10_1m, "unit": "bp 1m", "state": None if r10_1m is None else ("rising" if r10_1m > 10 else "falling" if r10_1m < -10 else "stable")},
    "dollar": {"value": round(dollar_1m, 2) if dollar_1m is not None else None, "unit": "% 1m", "state": None if dollar_1m is None else ("strengthening" if dollar_1m > 1 else "weakening" if dollar_1m < -1 else "stable")},
    "vol":    {"value": vix_p, "unit": "pctile 1y", "state": None if vix_p is None else ("elevated" if vix_p > 70 else "subdued" if vix_p < 30 else "normal")},
    "credit": {"value": credit_1m, "unit": "% 1m", "state": None if credit_1m is None else ("risk-on" if credit_1m > 0.3 else "risk-off" if credit_1m < -0.3 else "neutral")},
    "copper": {"value": round(copper_1m, 2) if copper_1m is not None else None, "unit": "% 1m", "state": None if copper_1m is None else ("expanding" if copper_1m > 2 else "contracting" if copper_1m < -2 else "flat")},
}

# historical theme performance in comparable days (trailing-21d conditions), 1y sample
def regime_perf():
    keys = sorted(set(FACTORS["RATES"]["series"]) & set(FACTORS["DOLLAR"]["series"]))
    rr, dd = FACTORS["RATES"]["series"], FACTORS["DOLLAR"]["series"]
    buckets = collections.defaultdict(list)
    for i in range(21, len(keys)):
        w = keys[i-21:i]; k = keys[i]
        rsum = sum(rr[x] for x in w); dsum = sum(dd[x] for x in w) * 100
        lab = ("rates↑" if rsum > 10 else "rates↓" if rsum < -10 else "rates flat") + " / " + \
              ("USD↑" if dsum > 1 else "USD↓" if dsum < -1 else "USD flat")
        buckets[lab].append(k)
    out = {}
    for lab, days in buckets.items():
        if len(days) < 15: continue
        out[lab] = {"days": len(days), "themes": {}}
        for th, rmap in THEME_R.items():
            v = [rmap[d] for d in days if d in rmap]
            if v: out[lab]["themes"][th] = round(sum(v)/len(v) * 252 * 100, 1)
    return out
REGIME_PERF = regime_perf()
cur_label = (("rates↑" if (r10_1m or 0) > 10 else "rates↓" if (r10_1m or 0) < -10 else "rates flat") + " / " +
             ("USD↑" if (dollar_1m or 0) > 1 else "USD↓" if (dollar_1m or 0) < -1 else "USD flat"))

# ---------------------------------------------------------------- breadth / dispersion / RS
THEME_ETF = {
 "AI Compute & Semiconductors": ("XLK", "SMH"),
 "Power & Grid for AI Datacenters": ("XLU", "URA"),
 "Defense Tech & Autonomy": ("XLI", "ITA"),
 "Space & Satellite Economy": ("XLI", "ITA"),
 "Robotics & Physical AI": ("XLI", "BOTZ"),
 "Cybersecurity": ("XLK", "HACK"),
 "Biotech & AI Drug Discovery": ("XLV", "ARKG"),
 "Energy Storage & Critical Minerals": ("XLB", "LIT"),
 "Fintech & Payment Rails": ("XLF", "FINX"),
 "Enterprise Software & AI Agents": ("XLK", "IGV"),
}
def theme_ret(th, n):
    v = [rows[t].get(f"chg_{n}") for t in UNIVERSE[th] if rows.get(t, {}).get(f"chg_{n}") is not None]
    return round(sum(v)/len(v), 1) if v else None

STATS = {}
for th, tks in UNIVERSE.items():
    a50 = [t for t in tks if (TECH.get(t, {}).get("vs_sma50") or 0) > 0]
    a200 = [t for t in tks if (TECH.get(t, {}).get("vs_sma200") or 0) > 0]
    r1y = [rows[t].get("chg_1y") for t in tks if rows.get(t, {}).get("chg_1y") is not None]
    sec, them = THEME_ETF.get(th, (None, None))
    rs = {}
    for lbl, n in (("1m", "1m"), ("3m", "3m"), ("1y", "1y")):
        tr = theme_ret(th, n)
        for tag, sym in (("sector", sec), ("thematic", them)):
            e = S.get(sym, {}).get(f"chg_{n}") if sym else None
            rs[f"{tag}_{lbl}"] = round(tr - e, 1) if (tr is not None and e is not None) else None
    STATS[th] = {
        "breadth_50": round(len(a50)/len(tks)*100), "breadth_200": round(len(a200)/len(tks)*100),
        "n": len(tks),
        "ret_1m": theme_ret(th, "1m"), "ret_3m": theme_ret(th, "3m"), "ret_1y": theme_ret(th, "1y"),
        "dispersion_1y": round(st.pstdev(r1y), 1) if len(r1y) > 2 else None,
        "best_1y": max(tks, key=lambda t: rows.get(t, {}).get("chg_1y") or -1e9),
        "worst_1y": min(tks, key=lambda t: rows.get(t, {}).get("chg_1y") or 1e9),
        "sector_etf": sec, "thematic_etf": them, "rs": rs,
        "avg_beta": round(sum((TECH.get(t, {}).get("beta_1y") or 0) for t in tks)/len(tks), 2),
    }

json.dump({"factors": {k: {"label": v["label"], "desc": v["desc"], "unit": v["unit"]} for k, v in FACTORS.items()},
           "theme_exposure": THEME_X, "ticker_exposure": TICK_X, "rolling": ROLL,
           "regime": REGIME, "regime_perf": REGIME_PERF, "regime_current": cur_label,
           "stats": STATS, "theme_etf": THEME_ETF, "asof": MAC["asof"]},
          open("factors.json", "w"), indent=1)

print(f"\nregime: {cur_label}  |  " + " · ".join(f"{k}={v['state']}" for k, v in REGIME.items() if v['state']))
print(f"regime buckets with >=15 days: {list(REGIME_PERF)}")
print("\ntheme -> strongest TRUE macro driver (market + VIX excluded):")
for th, x in sorted(THEME_X.items(), key=lambda kv: -((kv[1]["_best"] or {}).get("r2") or 0)):
    b = x["_best"]; r = x.get("_best_resid")
    if b:
        extra = f" | ex-beta: {r['label']} R2={r['r2']:.3f} t={r['t']}" if r else ""
        print(f"  R2={b['r2']:.3f} {th[:34]:36s} {b['label']:15s} beta={b['beta']:+.2f} t={b['t']}{extra}")
print("\nmarket sensitivity (reported separately, not ranked as macro):")
for th, x in sorted(THEME_X.items(), key=lambda kv: -((kv[1].get("SPX") or {}).get("beta") or 0)):
    sp, vo = x.get("SPX"), x.get("VOL")
    if sp: print(f"  SPX beta {sp['beta']:+.2f} (R2 {sp['r2']:.2f})   VIX beta {vo['beta']:+.2f}   {th[:36]}")
print("\nbreadth / dispersion:")
for th, s in sorted(STATS.items(), key=lambda kv: -kv[1]["breadth_50"]):
    print(f"  50d {s['breadth_50']:3d}%  200d {s['breadth_200']:3d}%  disp {str(s['dispersion_1y']):>6s}  vs sector 3m {str(s['rs']['sector_3m']):>7s}  {th[:34]}")
