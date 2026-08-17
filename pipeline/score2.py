"""v2 merge: enrich + technicals + short interest + options + events + IPOs -> data2.json"""
import json, collections, datetime as dt

from dates import today
D = json.load(open("data.json")); EN = json.load(open("enrich.json"))
TJ = json.load(open("tech.json")); TECH, CORR = TJ["tech"], TJ["theme_corr"]
OPT = json.load(open("options.json")); EV = json.load(open("events.json")); IPO = json.load(open("ipos.json"))
HIST = json.load(open("hist.json"))
TODAY = today()
rows = D["rows"]

ev_by_ticker = collections.defaultdict(list)
for e in EV:
    for t in (e.get("tickers") or []): ev_by_ticker[t].append(e)
def edate(e):
    d = str(e.get("date") or "")
    try:
        if len(d) == 10: return dt.date.fromisoformat(d)
        if len(d) == 7: return dt.date.fromisoformat(d+"-15")
    except Exception: pass
    return None
for t in ev_by_ticker:
    ev_by_ticker[t].sort(key=lambda e: (edate(e) or dt.date(2099,1,1)))

ipo_by_ticker = collections.defaultdict(list)
for p in IPO:
    for t in rows:
        pass
# link IPOs to public comps by scanning read_across text for tickers
TICKS = {r["ticker"] for r in rows}
for p in IPO:
    txt = (p.get("read_across") or "") + " " + (p.get("description") or "")
    hits = {w.strip(".,;:()") for w in txt.split()} & TICKS
    p["affects"] = sorted(hits)
    for h in hits: ipo_by_ticker[h].append(p["name"])

def pct(x): return round(x*100, 2) if isinstance(x, (int, float)) else None

for r in rows:
    t = r["ticker"]; en = EN.get(t, {}); tc = TECH.get(t, {}); op = OPT.get(t, {})
    sp = en.get("short_pct_float"); ss, ssp = en.get("shares_short"), en.get("shares_short_prior")
    r["short_pct_float"] = pct(sp)
    r["short_ratio"] = en.get("short_ratio")
    r["shares_short"] = ss
    r["short_chg_pct"] = round((ss/ssp-1)*100, 1) if ss and ssp else None
    r["short_date"] = dt.datetime.utcfromtimestamp(en["short_date"]).strftime("%Y-%m-%d") if en.get("short_date") else None
    for k in ("market_cap","float_shares","beta","fwd_pe","trail_pe","ps","pb","ev_rev","ev_ebitda",
              "profit_margin","gross_margin","op_margin","rev_growth","earn_growth","roe","fcf_yield",
              "div_yield","earnings_next","total_cash","total_debt"):
        r[k] = en.get(k)
    for k in ("rsi14","sma50","sma200","vs_sma50","vs_sma200","golden_cross","rvol30","rvol90",
              "mdd_1y","mom_12_1","beta_1y","corr_spy","sharpe_1y","vol_vs_avg","avg_dollar_vol"):
        r[k] = tc.get(k)
    r["opt"] = {k: op.get(k) for k in ("iv30","rv30","iv_rv","pc_vol","pc_oi","imp_move_pct","imp_move_exp","unusual","oi_total")} if op else {}
    r["trade"] = op.get("trade")
    r["spark"] = HIST.get(t, {}).get("c", [])[-90:]
    evs = ev_by_ticker.get(t, [])
    up = [e for e in evs if (edate(e) or dt.date(2099,1,1)) >= TODAY]
    r["events"] = up[:6]
    r["n_events"] = len(up)
    nxt = up[0] if up else None
    r["next_event"] = nxt
    r["days_to_earnings"] = (dt.date.fromisoformat(r["earnings_next"]) - TODAY).days if r.get("earnings_next") else None
    r["ipo_links"] = ipo_by_ticker.get(t, [])

    # ---- squeeze score 0-100: crowded short + momentum + tight float + rising cost to cover
    s = 0
    if r["short_pct_float"]: s += min(40, r["short_pct_float"]*4)
    if r["short_ratio"]: s += min(20, r["short_ratio"]*4)
    if r.get("vs_sma50") and r["vs_sma50"] > 0: s += min(15, r["vs_sma50"]/2)
    if r.get("rsi14") and r["rsi14"] > 55: s += min(10, (r["rsi14"]-55)/2)
    if r.get("short_chg_pct") and r["short_chg_pct"] > 0: s += min(15, r["short_chg_pct"]/2)
    r["squeeze"] = round(min(100, s))

    # ---- overbought / overextended flag
    r["overbought"] = bool(r.get("rsi14") and r["rsi14"] >= 75)
    r["oversold"] = bool(r.get("rsi14") and r["rsi14"] <= 32)

# ---------- WATCHLIST: why you should pay attention this week
W = []
def add(t, kind, pri, why):
    W.append({"ticker": t, "kind": kind, "priority": pri, "why": why})
for r in rows:
    t = r["ticker"]
    if r["rating"] == "PICK" and (r.get("chg_1y") or 0) < 0:
        add(t, "Contrarian", 1, f"Top-decile score {r['composite']} while down {r['chg_1y']:.0f}% on the year — conviction and price disagree.")
    if r["squeeze"] >= 45 and r["rating"] != "AVOID":
        add(t, "Squeeze", 2, f"{r['short_pct_float']}% of float short, {r['short_ratio']} days to cover, trading {r.get('vs_sma50',0)}% over its 50-day.")
    if r.get("days_to_earnings") is not None and 0 <= r["days_to_earnings"] <= 21:
        im = (r["opt"] or {}).get("imp_move_pct")
        add(t, "Earnings", 1 if r["rating"] != "NEUTRAL" else 3,
            f"Reports in {r['days_to_earnings']} days; options imply ±{im}%." if im else f"Reports in {r['days_to_earnings']} days.")
    iv = (r["opt"] or {}).get("iv_rv")
    if iv and iv >= 1.30:
        add(t, "Rich vol", 2, f"Implied vol is {iv}x realized — the option market is charging a premium worth selling into.")
    if iv and iv <= 0.60:
        add(t, "Cheap vol", 2, f"Implied vol only {iv}x realized — leverage is unusually cheap here.")
    pc = (r["opt"] or {}).get("pc_vol")
    if pc and pc >= 2.0:
        add(t, "Put flow", 3, f"Put/call volume {pc} — positioning is defensive.")
    if r.get("overbought") and r["rating"] == "AVOID":
        add(t, "Overextended", 2, f"RSI {r['rsi14']} on an AVOID-rated name {r.get('vs_sma200',0)}% above its 200-day.")
    if r["ipo_links"]:
        add(t, "IPO read-across", 3, f"Repriced by {', '.join(r['ipo_links'][:2])} coming public.")
    if r.get("insider_signal") == "heavy selling" and r["rating"] == "PICK":
        add(t, "Conflict", 1, f"Rated PICK but insiders are selling heavily ({r.get('n_form4')} Form 4s in 90 days).")
pri_rank = collections.defaultdict(list)
for w in W: pri_rank[w["ticker"]].append(w)
watch = sorted([{"ticker": t, "signals": v, "score": sum(4-x["priority"] for x in v),
                 "rating": next(r["rating"] for r in rows if r["ticker"] == t),
                 "theme": next(r["theme"] for r in rows if r["ticker"] == t)}
                for t, v in pri_rank.items()], key=lambda x: -x["score"])

# ---------- MODEL PORTFOLIO: conviction x inverse-vol, bucketed into sleeves
picks = [r for r in rows if r["rating"] == "PICK"]
avoids = [r for r in rows if r["rating"] == "AVOID"]
def sleeve(r):
    if (r.get("chg_1y") or 0) < 5 and r["composite"] >= 3.7: return "Contrarian"
    if (r.get("rvol30") or 0) > 55 or (r.get("market_cap") or 0) < 3e10: return "Tactical"
    return "Core"
TARGET = {"Core": 60.0, "Contrarian": 22.0, "Tactical": 13.0}
port = []
for name, cap in TARGET.items():
    grp = [r for r in picks if sleeve(r) == name]
    if not grp: continue
    wts = [(r, r["composite"] / max(r.get("rvol30") or 40, 15)) for r in grp]
    # hard 12% single-name cap; whatever the sleeve can't absorb falls to cash
    CAP = 12.0
    tot = sum(w for _, w in wts)
    for r, w in wts:
        port.append({"ticker": r["ticker"], "name": r.get("name"), "theme": r["theme"], "sleeve": name,
                     "weight": round(min(cap*w/tot, CAP), 1), "composite": r["composite"],
                     "rvol30": r.get("rvol30"), "beta": r.get("beta_1y"),
                     "chg_1y": r.get("chg_1y"), "last": r.get("last")})
port.sort(key=lambda x: -x["weight"])
cash = round(100 - sum(p["weight"] for p in port), 1)
pw = sum(p["weight"] for p in port)
port_beta = round(sum(p["weight"]*(p["beta"] or 1) for p in port)/pw, 2) if pw else None
theme_w = collections.Counter()
for p in port: theme_w[p["theme"]] += p["weight"]

# concentration: how much of the book is one bet
ai_cluster = ["AI Compute & Semiconductors", "Power & Grid for AI Datacenters", "Enterprise Software & AI Agents"]
cluster_w = round(sum(v for k, v in theme_w.items() if k in ai_cluster), 1)
corr_pairs = []
names = TJ["theme_names"]
for i, a in enumerate(names):
    for b in names[i+1:]:
        c = CORR.get(a, {}).get(b)
        if c is not None: corr_pairs.append({"a": a, "b": b, "corr": c})
corr_pairs.sort(key=lambda x: -x["corr"])

json.dump({"rows": rows, "themes": D["themes"], "privates": D["privates"], "activists": D["activists"],
           "events": EV, "ipos": IPO, "watch": watch, "portfolio": port, "cash": cash,
           "port_beta": port_beta, "theme_weights": dict(theme_w), "cluster_w": cluster_w,
           "corr": CORR, "corr_names": names, "corr_pairs": corr_pairs,
           "options": OPT, "asof": D["asof"], "hf_limits": D.get("hf_limits")},
          open("data2.json", "w"), indent=1)

print("watchlist:", len(watch), "| trades:", sum(1 for r in rows if r.get("trade")))
print("portfolio legs:", len(port), "cash", cash, "beta", port_beta, "AI-cluster weight", cluster_w)
print("\ntop watch:"); [print(f"  {w['score']:2d} {w['ticker']:6s} {w['rating']:8s} {[s['kind'] for s in w['signals']]}") for w in watch[:12]]
print("\nportfolio:"); [print(f"  {p['weight']:5.1f}% {p['ticker']:6s} {p['sleeve']:11s} rvol={p['rvol30']}") for p in port]
print("\nhighest theme correlations:"); [print(f"  {c['corr']} {c['a'][:32]} / {c['b'][:32]}") for c in corr_pairs[:5]]
print("\nsqueeze leaders:"); [print(f"  {r['squeeze']:3d} {r['ticker']:6s} sf={r['short_pct_float']}% dtc={r['short_ratio']}") for r in sorted(rows,key=lambda x:-x['squeeze'])[:8]]
