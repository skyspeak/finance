"""CBOE delayed chains -> IV/RV edge, flow, and defined-risk trade tickets. Writes options.json"""
import json, re, time, urllib.request, datetime as dt

from dates import today
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
D = json.load(open("data.json")); TECH = json.load(open("tech.json"))["tech"]; EN = json.load(open("enrich.json"))
rows = {r["ticker"]: r for r in D["rows"]}
TODAY = today()

# shortlist: all picks + all avoids + neutrals with the most extreme factor disagreement
picks = [r["ticker"] for r in D["rows"] if r["rating"] == "PICK"]
avoids = [r["ticker"] for r in D["rows"] if r["rating"] == "AVOID"]
neut = sorted([r for r in D["rows"] if r["rating"] == "NEUTRAL"],
              key=lambda r: -abs(r["sc_valuation"] - r["sc_analyst"]))[:8]
SHORT = picks + avoids + [r["ticker"] for r in neut]
print("shortlist", len(SHORT), SHORT)

OPT = re.compile(r"^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$")
def parse(sym):
    m = OPT.match(sym)
    if not m: return None
    _, y, mo, d, cp, k = m.groups()
    return dt.date(2000+int(y), int(mo), int(d)), cp, int(k)/1000.0

def mid(o):
    b, a = o.get("bid") or 0, o.get("ask") or 0
    return round((b+a)/2, 2) if b > 0 and a > 0 else (o.get("last_trade_price") or 0)
def spread_pct(o):
    b, a = o.get("bid") or 0, o.get("ask") or 0
    m = (b+a)/2
    return round((a-b)/m*100, 1) if m > 0 else 999
def liquid(o, min_oi=100):
    return (o.get("open_interest") or 0) >= min_oi and (o.get("bid") or 0) >= 0.05 and spread_pct(o) <= 30

def near(cands, key, target):
    return min(cands, key=lambda o: abs(key(o)-target)) if cands else None

OUT = {}
for t in SHORT:
    try:
        u = f"https://cdn.cboe.com/api/global/delayed_quotes/options/{t}.json"
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
            raw = json.load(r)["data"]
    except Exception as e:
        print("FAIL", t, str(e)[:60]); continue
    S = raw.get("close") or rows[t].get("last")
    chain = []
    for o in raw["options"]:
        p = parse(o["option"])
        if not p: continue
        exp, cp, k = p
        dte = (exp - TODAY).days
        if dte < 1: continue
        o.update({"exp": exp.isoformat(), "cp": cp, "k": k, "dte": dte, "mid": mid(o), "sprd": spread_pct(o)})
        chain.append(o)
    if not chain: continue

    tot_c = sum(o.get("volume") or 0 for o in chain if o["cp"] == "C")
    tot_p = sum(o.get("volume") or 0 for o in chain if o["cp"] == "P")
    oi_c = sum(o.get("open_interest") or 0 for o in chain if o["cp"] == "C")
    oi_p = sum(o.get("open_interest") or 0 for o in chain if o["cp"] == "P")

    exps = sorted({o["exp"] for o in chain})
    oi_by_exp = {}
    for o in chain:
        oi_by_exp[o["exp"]] = oi_by_exp.get(o["exp"], 0) + (o.get("open_interest") or 0)
    def pick_exp(lo, hi):
        """Most liquid expiry in the window — naturally selects monthlies over thin weeklies."""
        c = [e for e in exps if lo <= (dt.date.fromisoformat(e)-TODAY).days <= hi]
        return max(c, key=lambda e: oi_by_exp.get(e, 0)) if c else None
    # ATM IV on the ~30d expiry -> IV/RV edge
    e30 = pick_exp(21, 45) or exps[0]
    atm = [o for o in chain if o["exp"] == e30 and abs(o["k"]-S)/S < 0.06 and (o.get("iv") or 0) > 0]
    iv30 = round(sum(o["iv"] for o in atm)/len(atm)*100, 1) if atm else (raw.get("iv30") or None)
    rv30 = TECH.get(t, {}).get("rvol30")
    ivrv = round(iv30/rv30, 2) if iv30 and rv30 else None

    # ---- straddle-implied move on the expiry that covers next earnings
    earn = EN.get(t, {}).get("earnings_next")
    imp_move = imp_exp = None
    if earn:
        nxt = sorted([e for e in exps if e >= earn])[:3]
        cand = [max(nxt, key=lambda e: oi_by_exp.get(e, 0))] if nxt else []
        if cand:
            ee = cand[0]
            cs = [o for o in chain if o["exp"] == ee and o["cp"] == "C"]
            ps = [o for o in chain if o["exp"] == ee and o["cp"] == "P"]
            ca, pa = near(cs, lambda o: o["k"], S), near(ps, lambda o: o["k"], S)
            if ca and pa and ca["mid"] and pa["mid"]:
                imp_move = round((ca["mid"]+pa["mid"])/S*100, 1); imp_exp = ee

    # ---- unusual activity: highest volume/OI contracts
    unusual = sorted([o for o in chain if (o.get("open_interest") or 0) > 200 and (o.get("volume") or 0) > 300],
                     key=lambda o: -(o["volume"]/max(o["open_interest"], 1)))[:5]
    unusual = [{"exp": o["exp"], "cp": o["cp"], "strike": o["k"], "vol": o["volume"],
                "oi": o["open_interest"], "v_oi": round(o["volume"]/max(o["open_interest"], 1), 2),
                "iv": round((o.get("iv") or 0)*100, 1), "mid": o["mid"]} for o in unusual]

    # ---- build the trade ticket
    rt = rows[t]["rating"]
    tgt = pick_exp(35, 80) or pick_exp(20, 120) or exps[-1]
    leg = [o for o in chain if o["exp"] == tgt]
    dte = (dt.date.fromisoformat(tgt)-TODAY).days
    trade = None
    if rt == "PICK":
        longs = [o for o in leg if o["cp"] == "C" and liquid(o) and 0.30 <= (o.get("delta") or 0) <= 0.55]
        shorts = [o for o in leg if o["cp"] == "C" and liquid(o) and 0.12 <= (o.get("delta") or 0) <= 0.28]
        lo = near(longs, lambda o: o.get("delta") or 0, 0.42); sh = near(shorts, lambda o: o.get("delta") or 0, 0.20)
        if lo and sh and sh["k"] > lo["k"]:
            deb = round(lo["mid"]-sh["mid"], 2); wid = sh["k"]-lo["k"]
            trade = {"structure": "Bull call debit spread", "bias": "long",
                     "legs": [{"action": "BUY", "cp": "C", "strike": lo["k"], "mid": lo["mid"], "delta": lo.get("delta"), "iv": round((lo.get("iv") or 0)*100,1), "oi": lo.get("open_interest")},
                              {"action": "SELL", "cp": "C", "strike": sh["k"], "mid": sh["mid"], "delta": sh.get("delta"), "iv": round((sh.get("iv") or 0)*100,1), "oi": sh.get("open_interest")}],
                     "net": deb, "net_type": "debit", "width": wid,
                     "max_gain": round(wid-deb, 2), "max_loss": deb,
                     "breakeven": round(lo["k"]+deb, 2),
                     "rr": round((wid-deb)/deb, 2) if deb > 0 else None}
    elif rt == "AVOID":
        longs = [o for o in leg if o["cp"] == "P" and liquid(o) and -0.55 <= (o.get("delta") or 0) <= -0.30]
        shorts = [o for o in leg if o["cp"] == "P" and liquid(o) and -0.28 <= (o.get("delta") or 0) <= -0.12]
        lo = near(longs, lambda o: o.get("delta") or 0, -0.42); sh = near(shorts, lambda o: o.get("delta") or 0, -0.20)
        if lo and sh and sh["k"] < lo["k"]:
            deb = round(lo["mid"]-sh["mid"], 2); wid = lo["k"]-sh["k"]
            trade = {"structure": "Bear put debit spread", "bias": "short",
                     "legs": [{"action": "BUY", "cp": "P", "strike": lo["k"], "mid": lo["mid"], "delta": lo.get("delta"), "iv": round((lo.get("iv") or 0)*100,1), "oi": lo.get("open_interest")},
                              {"action": "SELL", "cp": "P", "strike": sh["k"], "mid": sh["mid"], "delta": sh.get("delta"), "iv": round((sh.get("iv") or 0)*100,1), "oi": sh.get("open_interest")}],
                     "net": deb, "net_type": "debit", "width": wid,
                     "max_gain": round(wid-deb, 2), "max_loss": deb,
                     "breakeven": round(lo["k"]-deb, 2),
                     "rr": round((wid-deb)/deb, 2) if deb > 0 else None}
    else:  # NEUTRAL -> sell premium when IV is rich vs realized
        puts = [o for o in leg if o["cp"] == "P" and liquid(o) and -0.32 <= (o.get("delta") or 0) <= -0.18]
        sh = near(puts, lambda o: o.get("delta") or 0, -0.25)
        wing = None
        if sh:
            wings = [o for o in leg if o["cp"] == "P" and o["k"] < sh["k"] and liquid(o, 50)]
            wing = near(wings, lambda o: o["k"], sh["k"]-max(round(S*0.06), 5))
        if sh and wing:
            cr = round(sh["mid"]-wing["mid"], 2); wid = sh["k"]-wing["k"]
            trade = {"structure": "Bull put credit spread", "bias": "neutral-to-long",
                     "legs": [{"action": "SELL", "cp": "P", "strike": sh["k"], "mid": sh["mid"], "delta": sh.get("delta"), "iv": round((sh.get("iv") or 0)*100,1), "oi": sh.get("open_interest")},
                              {"action": "BUY", "cp": "P", "strike": wing["k"], "mid": wing["mid"], "delta": wing.get("delta"), "iv": round((wing.get("iv") or 0)*100,1), "oi": wing.get("open_interest")}],
                     "net": cr, "net_type": "credit", "width": wid,
                     "max_gain": cr, "max_loss": round(wid-cr, 2),
                     "breakeven": round(sh["k"]-cr, 2),
                     "rr": round(cr/(wid-cr), 2) if wid-cr > 0 else None}
    if trade:
        trade.update({"expiry": tgt, "dte": dte, "spot": round(S, 2),
                      "max_loss_1lot": round(trade["max_loss"]*100, 0),
                      "max_gain_1lot": round(trade["max_gain"]*100, 0),
                      "be_move_pct": round((trade["breakeven"]/S-1)*100, 1)})

    OUT[t] = {"ticker": t, "spot": round(S, 2), "rating": rt, "iv30": iv30, "rv30": rv30, "iv_rv": ivrv,
              "pc_vol": round(tot_p/tot_c, 2) if tot_c else None,
              "pc_oi": round(oi_p/oi_c, 2) if oi_c else None,
              "call_vol": tot_c, "put_vol": tot_p, "oi_total": oi_c+oi_p,
              "imp_move_pct": imp_move, "imp_move_exp": imp_exp, "earnings": earn,
              "unusual": unusual, "trade": trade, "n_expiries": len(exps)}
    print(f"{t:6s} IV{iv30} RV{rv30} IV/RV={ivrv} P/C={OUT[t]['pc_vol']} move±{imp_move} trade={'Y' if trade else 'n'}", flush=True)
    time.sleep(0.4)

json.dump(OUT, open("options.json", "w"), indent=1)
print("saved", len(OUT), "| with trades:", sum(1 for v in OUT.values() if v.get("trade")))
