"""Buy-and-hold backtest of the published pick book vs SPY.

This is not a walk-forward of the scoring model — there is only one rating
date. It answers: if you had held *this week's* picks over the trailing
window, how would that book have behaved against the market and against
the AVOID list.

Writes backtest.json
"""
from __future__ import annotations

import json
import datetime as dt
import math
import statistics as st

HIST = json.load(open("hist.json"))
D2 = json.load(open("data2.json"))
rows = {r["ticker"]: r for r in D2["rows"]}
port = D2.get("portfolio") or []
asof = D2["asof"]

picks = [r["ticker"] for r in D2["rows"] if r["rating"] == "PICK"]
avoids = [r["ticker"] for r in D2["rows"] if r["rating"] == "AVOID"]
wt = {p["ticker"]: p["weight"] for p in port}
sleeve = {p["ticker"]: p["sleeve"] for p in port}


def to_date(ts):
    return dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")


def series(ticker):
    h = HIST.get(ticker)
    if not h or not h.get("ts"):
        return {}
    return {to_date(t): c for t, c in zip(h["ts"], h["c"]) if c}


spy = series("SPY")
if not spy:
    raise SystemExit("hist.json has no SPY — tech.py must fetch it")

# Align on dates present for SPY and every pick with history.
have = [t for t in picks if series(t)]
missing = [t for t in picks if t not in have]
keys = set(spy)
for t in have:
    keys &= set(series(t))
dates = sorted(keys)
if len(dates) < 40:
    raise SystemExit(f"backtest alignment too short: {len(dates)} days")

px = {t: [series(t)[d] for d in dates] for t in have}
px["SPY"] = [spy[d] for d in dates]
avoid_have = [t for t in avoids if set(dates) <= set(series(t))]
px.update({t: [series(t)[d] for d in dates] for t in avoid_have})
uni_have = [t for t in rows if t in HIST and set(dates) <= set(series(t))]
for t in uni_have:
    if t not in px:
        px[t] = [series(t)[d] for d in dates]


def rets(closes):
    out = [0.0]
    for i in range(1, len(closes)):
        a, b = closes[i - 1], closes[i]
        out.append((b / a - 1) if a else 0.0)
    return out


def nav_from_rets(r):
    n = [100.0]
    for x in r[1:]:
        n.append(n[-1] * (1 + x))
    return [round(v, 4) for v in n]


def blend(members, weights):
    """Daily book return from member returns. weights need not sum to 1;
    leftover is treated as cash at 0."""
    rr = {t: rets(px[t]) for t in members}
    n = len(dates)
    out = [0.0]
    for i in range(1, n):
        out.append(sum(weights.get(t, 0) / 100.0 * rr[t][i] for t in members))
    return out


inv = sum(wt.get(t, 0) for t in have) or 100.0
w_model_cash = {t: wt.get(t, 0) for t in have}          # published weights, cash drag
w_model = {t: wt.get(t, 0) / inv * 100.0 for t in have}  # renormalized invested book
w_ew = {t: 100.0 / len(have) for t in have}
w_avoid = {t: 100.0 / len(avoid_have) for t in avoid_have} if avoid_have else {}
w_uni = {t: 100.0 / len(uni_have) for t in uni_have} if uni_have else {}

nav = {
    "spy": nav_from_rets(rets(px["SPY"])),
    "picks_model": nav_from_rets(blend(have, w_model)),
    "picks_model_cash": nav_from_rets(blend(have, w_model_cash)),
    "picks_ew": nav_from_rets(blend(have, w_ew)),
    "avoids_ew": nav_from_rets(blend(avoid_have, w_avoid)) if avoid_have else None,
    "universe_ew": nav_from_rets(blend(uni_have, w_uni)) if uni_have else None,
}


def stats(nav_s, spy_s, lookback=None):
    a = nav_s[-(lookback or len(nav_s)):]
    b = spy_s[-(lookback or len(spy_s)):]
    n = min(len(a), len(b))
    a, b = a[-n:], b[-n:]
    if n < 5:
        return None
    ra = [(a[i] / a[i - 1] - 1) for i in range(1, n)]
    rb = [(b[i] / b[i - 1] - 1) for i in range(1, n)]
    total = a[-1] / a[0] - 1
    spy_tot = b[-1] / b[0] - 1
    days = n - 1
    years = days / 252.0
    cagr = (a[-1] / a[0]) ** (1 / years) - 1 if years > 0 and a[0] > 0 else None
    vol = st.pstdev(ra) * math.sqrt(252) if len(ra) > 2 else None
    mean = sum(ra) / len(ra)
    sharpe = (mean * 252 - 0.04) / vol if vol else None
    pk = a[0]
    mdd = 0.0
    for x in a:
        pk = max(pk, x)
        mdd = min(mdd, x / pk - 1)
    cov = sum((x - mean) * (y - sum(rb) / len(rb)) for x, y in zip(ra, rb)) / len(ra)
    vb = sum((y - sum(rb) / len(rb)) ** 2 for y in rb) / len(rb)
    beta = cov / vb if vb else None
    return {
        "n": n,
        "total": round(total * 100, 2),
        "spy": round(spy_tot * 100, 2),
        "excess": round((total - spy_tot) * 100, 2),
        "cagr": round(cagr * 100, 2) if cagr is not None else None,
        "vol": round(vol * 100, 1) if vol is not None else None,
        "sharpe": round(sharpe, 2) if sharpe is not None else None,
        "mdd": round(mdd * 100, 1),
        "beta": round(beta, 2) if beta is not None else None,
    }


WINDOWS = {"3m": 63, "6m": 126, "1y": None}

def book_stats(key):
    s = nav.get(key)
    if not s:
        return {}
    return {w: stats(s, nav["spy"], n) for w, n in WINDOWS.items()}


name_rows = []
for t in have:
    r = rows[t]
    path = nav_from_rets(rets(px[t]))
    stt = {w: stats(path, nav["spy"], n) for w, n in WINDOWS.items()}
    name_rows.append({
        "ticker": t,
        "name": r.get("name"),
        "theme": r.get("theme"),
        "rating": r["rating"],
        "sleeve": sleeve.get(t),
        "weight": round(w_model.get(t, 0), 2),
        "weight_pub": round(w_model_cash.get(t, 0), 2),
        "stats": stt,
        "nav": path,
    })
name_rows.sort(key=lambda x: -x["weight"])

avoid_rows = []
for t in avoid_have:
    r = rows[t]
    path = nav_from_rets(rets(px[t]))
    avoid_rows.append({
        "ticker": t,
        "name": r.get("name"),
        "theme": r.get("theme"),
        "rating": "AVOID",
        "stats": {w: stats(path, nav["spy"], n) for w, n in WINDOWS.items()},
        "nav": path,
    })
avoid_rows.sort(key=lambda x: (x["stats"]["1y"] or {}).get("total") or 0)

out = {
    "asof": asof,
    "dates": dates,
    "start": dates[0],
    "end": dates[-1],
    "n_days": len(dates),
    "missing_picks": missing,
    "picks": have,
    "avoids": avoid_have,
    "cash": D2.get("cash"),
    "port_beta": D2.get("port_beta"),
    "nav": nav,
    "books": {
        "picks_model": {"label": "Pick book (model weights, fully invested)", "stats": book_stats("picks_model")},
        "picks_model_cash": {"label": "Pick book as published (cash at 0)", "stats": book_stats("picks_model_cash")},
        "picks_ew": {"label": "Picks equal-weight", "stats": book_stats("picks_ew")},
        "avoids_ew": {"label": "Avoids equal-weight", "stats": book_stats("avoids_ew")},
        "universe_ew": {"label": "Full universe equal-weight", "stats": book_stats("universe_ew")},
        "spy": {"label": "SPY", "stats": book_stats("spy")},
    },
    "names": name_rows,
    "avoid_names": avoid_rows,
    "note": (
        "Buy-and-hold of this week's PICK list over trailing prices. Ratings are not "
        "walked forward — a name that is a PICK today is treated as a pick on every "
        "day in the window. No costs, no rebalance. Cash earns 0 in the published book."
    ),
}
json.dump(out, open("backtest.json", "w"))
s = out["books"]["picks_model"]["stats"]["1y"]
print(f"wrote backtest.json  {len(dates)}d  {dates[0]} → {dates[-1]}")
print(f"  model book {s['total']:+.1f}%  spy {s['spy']:+.1f}%  excess {s['excess']:+.1f}%  "
      f"mdd {s['mdd']}%  sharpe {s['sharpe']}  beta {s['beta']}")
if missing:
    print("  skipped (no history)", missing)
