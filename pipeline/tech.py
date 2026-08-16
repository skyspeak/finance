"""2y history -> technicals, risk metrics, correlation matrix. Writes tech.json, hist.json"""
import json, time, math, urllib.request, statistics as st
from universe import ALL, UNIVERSE

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
SYMS = ALL + ["SPY"]

def fetch(t):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=2y&interval=1d"
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25) as r:
        d = json.load(r)["chart"]["result"][0]
    ts = d["timestamp"]; c = d["indicators"]["quote"][0]["close"]
    v = d["indicators"]["quote"][0].get("volume") or [None]*len(ts)
    pair = [(a, b, w) for a, b, w in zip(ts, c, v) if b is not None]
    return [p[0] for p in pair], [p[1] for p in pair], [p[2] for p in pair]

H = {}
for t in SYMS:
    try:
        ts, c, v = fetch(t); H[t] = {"ts": ts, "c": c, "v": v}
        print(t, len(c), flush=True)
    except Exception as e: print("FAIL", t, str(e)[:50], flush=True)
    time.sleep(0.3)

def rets(c): return [(c[i]/c[i-1]-1) for i in range(1, len(c))]
def sma(c, n): return sum(c[-n:])/n if len(c) >= n else None
def rsi(c, n=14):
    if len(c) < n+1: return None
    g = l = 0.0
    for i in range(-n, 0):
        d = c[i]-c[i-1]
        g += max(d, 0); l += max(-d, 0)
    if l == 0: return 100.0
    rs = (g/n)/(l/n)
    return round(100 - 100/(1+rs), 1)
def vol(r, n):
    s = r[-n:]
    return round(st.pstdev(s)*math.sqrt(252)*100, 1) if len(s) > 2 else None
def mdd(c):
    pk = c[0]; w = 0
    for x in c:
        pk = max(pk, x); w = min(w, x/pk-1)
    return round(w*100, 1)

spy_r = rets(H["SPY"]["c"]) if "SPY" in H else []
T = {}
for t in ALL:
    if t not in H: continue
    c = H[t]["c"]; v = H[t]["v"]; r = rets(c); last = c[-1]
    s20, s50, s200 = sma(c, 20), sma(c, 50), sma(c, 200)
    row = {"ticker": t, "last": round(last, 2), "rsi14": rsi(c),
        "sma20": round(s20, 2) if s20 else None, "sma50": round(s50, 2) if s50 else None,
        "sma200": round(s200, 2) if s200 else None,
        "vs_sma50": round((last/s50-1)*100, 1) if s50 else None,
        "vs_sma200": round((last/s200-1)*100, 1) if s200 else None,
        "golden_cross": (s50 > s200) if (s50 and s200) else None,
        "rvol30": vol(r, 30), "rvol90": vol(r, 90), "rvol252": vol(r, 252),
        "mdd_1y": mdd(c[-252:]) if len(c) >= 252 else mdd(c),
        "mom_12_1": round((c[-21]/c[-252]-1)*100, 1) if len(c) >= 252 else None}
    # beta + correlation vs SPY on 1y daily
    n = min(len(r), len(spy_r), 252)
    if n > 30:
        a, b = r[-n:], spy_r[-n:]
        ma, mb = sum(a)/n, sum(b)/n
        cov = sum((x-ma)*(y-mb) for x, y in zip(a, b))/n
        vb = sum((y-mb)**2 for y in b)/n
        sa = math.sqrt(sum((x-ma)**2 for x in a)/n)
        row["beta_1y"] = round(cov/vb, 2) if vb else None
        row["corr_spy"] = round(cov/(sa*math.sqrt(vb)), 2) if sa and vb else None
        sd = st.pstdev(a)
        row["sharpe_1y"] = round((ma*252 - 0.04)/(sd*math.sqrt(252)), 2) if sd else None
    if v and v[-1] and len([x for x in v[-60:] if x]) > 20:
        av = sum(x for x in v[-60:] if x)/len([x for x in v[-60:] if x])
        row["vol_vs_avg"] = round(v[-1]/av, 2) if av else None
        row["avg_dollar_vol"] = round(av*last/1e6, 1)
    T[t] = row
    print(f"{t:6s} rsi={row['rsi14']} vs200={row['vs_sma200']} beta={row.get('beta_1y')} rvol30={row['rvol30']}", flush=True)

# theme-level correlation matrix (1y daily returns, theme composites)
theme_r = {}
for th, tk in UNIVERSE.items():
    series = [rets(H[t]["c"])[-252:] for t in tk if t in H and len(H[t]["c"]) > 253]
    if not series: continue
    n = min(len(s) for s in series)
    theme_r[th] = [sum(s[-n:][i] for s in series)/len(series) for i in range(n)]
names = list(theme_r)
M = {}
for a in names:
    M[a] = {}
    for b in names:
        x, y = theme_r[a], theme_r[b]; n = min(len(x), len(y))
        x, y = x[-n:], y[-n:]
        mx, my = sum(x)/n, sum(y)/n
        cov = sum((p-mx)*(q-my) for p, q in zip(x, y))/n
        sx = math.sqrt(sum((p-mx)**2 for p in x)/n); sy = math.sqrt(sum((q-my)**2 for q in y)/n)
        M[a][b] = round(cov/(sx*sy), 2) if sx and sy else None

json.dump({"tech": T, "theme_corr": M, "theme_names": names}, open("tech.json", "w"), indent=1)
json.dump({t: {"ts": H[t]["ts"][-260:], "c": [round(x, 2) for x in H[t]["c"][-260:]]} for t in H}, open("hist.json", "w"))
print("saved tech.json", len(T), "| corr themes", len(names))
