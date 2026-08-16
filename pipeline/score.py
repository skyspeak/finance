import json, collections
from universe import UNIVERSE

P  = json.load(open("prices.json"))
A  = {**json.load(open("analysts_1.json")), **json.load(open("analysts_2.json"))}
I  = json.load(open("insiders.json"))
AC = json.load(open("activists.json"))
HF = json.load(open("hedgefunds.json"))
PR = json.load(open("private_1.json")) + json.load(open("private_2.json"))

hf_by = HF.get("by_ticker", {}) or {}
hf_moves = collections.defaultdict(list)
for m in HF.get("moves", []):
    if m.get("ticker"): hf_moves[m["ticker"]].append(m)
act_by = collections.defaultdict(list)
for a in AC: act_by[a["ticker"]].append(a)
priv_by_ticker = collections.defaultdict(list)
for p in PR:
    for t in (p.get("competes_with") or []): priv_by_ticker[t].append(p["name"])

# Theme-level secular demand conviction (1-5), analyst-assigned with rationale
THEME = {
 "AI Compute & Semiconductors":      (5.0, "Capex supercycle still compounding; the bottleneck the whole AI economy pays a toll to."),
 "Power & Grid for AI Datacenters":  (4.7, "Electricity is the binding constraint on AI. Multi-decade buildout, but 2026 prices already discount a lot."),
 "Defense Tech & Autonomy":          (4.5, "Structural rearmament plus a genuine software/autonomy displacement of primes."),
 "Space & Satellite Economy":        (4.0, "Launch cost collapse is real; direct-to-device is the swing factor. High dispersion, high beta."),
 "Robotics & Physical AI":           (4.2, "The next frontier after language models, but revenue is still mostly ahead of the narrative."),
 "Cybersecurity":                    (3.8, "Non-discretionary spend, but AI is compressing seat-based pricing and inviting autonomous-agent entrants."),
 "Biotech & AI Drug Discovery":      (3.7, "Obesity franchise economics are extraordinary; AI-discovery pure plays remain unproven."),
 "Energy Storage & Critical Minerals":(4.1,"Storage attach rates and supply-chain onshoring are policy-supported and accelerating."),
 "Fintech & Payment Rails":          (3.6, "Stablecoin rails are a real threat to card economics — this theme has a genuine short side."),
 "Enterprise Software & AI Agents":  (3.5, "Biggest winners are the hyperscalers; seat-based SaaS faces the clearest AI business-model risk."),
}

def s_valuation(t):
    a = A.get(t, {}); pt = a.get("pt_mean"); px = P.get(t, {}).get("last")
    if not pt or not px: return 3.0, "no target"
    up = (pt - px) / px * 100
    s = 5.0 if up > 40 else 4.3 if up > 25 else 3.5 if up > 12 else 2.8 if up > 2 else 2.0 if up > -10 else 1.3
    return s, f"{up:+.0f}% to mean PT ${pt:,.0f}"

def s_analyst(t):
    a = A.get(t, {}); c = (a.get("consensus") or "").lower()
    base = {"strong buy":4.6,"buy":3.8,"outperform":3.8,"hold":2.6,"neutral":2.6,"sell":1.4}.get(c, 3.0)
    acts = a.get("recent_actions") or []
    up = sum(1 for x in acts if any(k in str(x.get("action","")).lower() for k in ("upgrade","raise","initiate")))
    dn = sum(1 for x in acts if any(k in str(x.get("action","")).lower() for k in ("downgrade","cut")))
    base += 0.3*up - 0.4*dn
    return max(1, min(5, base)), f"{a.get('consensus','n/a')} ({a.get('num_analysts') or '?'} analysts), {up}↑/{dn}↓ recent"

def s_smart(t):
    ins = I.get(t, {}); sig = (ins.get("signal") or "").lower()
    s = {"buying":4.6,"quiet":3.4,"moderate selling":2.9,"heavy selling":2.0}.get(sig, 3.0)
    bits = [f"insiders: {sig or 'n/a'} ({ins.get('n_form4',0)} Form 4s/90d)"]
    net = (hf_by.get(t, {}) or {}).get("net_signal")
    if net and net != "no data":
        s += {"accumulating":0.7,"mixed":0.0,"distributing":-0.7}.get(net, 0)
        bits.append(f"13F: {net}")
    if act_by.get(t):
        bits.append(f"13D: {len(act_by[t])} filer(s)")
        if any(a.get("is_known_activist") for a in act_by[t]): s += 0.4
    return max(1, min(5, s)), "; ".join(bits)

MEGA = {"NVDA","MSFT","GOOGL","AVGO","TSM","LLY","V","MA","ISRG","RTX","LMT","ABBV","NVO","BA","ETN"}
def s_moat(t, theme):
    n = len(priv_by_ticker.get(t, []))
    s = 4.4 if t in MEGA else 3.4
    s -= min(1.4, 0.28*n)
    return max(1, min(5, s)), f"{n} tracked private challenger(s)"

W = {"secular":.25, "moat":.20, "valuation":.20, "smart":.15, "analyst":.20}
rows = []
for theme, tickers in UNIVERSE.items():
    sec, sec_note = THEME[theme]
    for t in tickers:
        v, vn = s_valuation(t); an, ann = s_analyst(t); sm, smn = s_smart(t); mo, mon = s_moat(t, theme)
        comp = W["secular"]*sec + W["moat"]*mo + W["valuation"]*v + W["smart"]*sm + W["analyst"]*an
        rows.append({**P.get(t, {"ticker":t}), "theme":theme,
            "sc_secular":round(sec,2),"sc_moat":round(mo,2),"sc_valuation":round(v,2),
            "sc_smart":round(sm,2),"sc_analyst":round(an,2),"composite":round(comp,2),
            "rating": "PICK" if comp>=3.70 else ("AVOID" if comp<3.05 else "NEUTRAL"),
            "n_valuation":vn,"n_analyst":ann,"n_smart":smn,"n_moat":mon,
            "consensus":A.get(t,{}).get("consensus"),"pt_mean":A.get(t,{}).get("pt_mean"),
            "num_analysts":A.get(t,{}).get("num_analysts"),
            "analyst_src":A.get(t,{}).get("source_url"),
            "recent_actions":A.get(t,{}).get("recent_actions") or [],
            "insider_signal":I.get(t,{}).get("signal"),"n_form4":I.get(t,{}).get("n_form4"),
            "insider_notable":I.get(t,{}).get("notable") or [],
            "hf":hf_by.get(t) or {}, "hf_moves":hf_moves.get(t,[]),
            "activists":act_by.get(t,[]), "privates":priv_by_ticker.get(t,[])})

themes = []
for theme, tickers in UNIVERSE.items():
    tr = [r for r in rows if r["theme"]==theme]
    themes.append({"theme":theme,"secular":THEME[theme][0],"thesis":THEME[theme][1],
        "score":round(sum(r["composite"] for r in tr)/len(tr),2),
        "tickers":tickers,"n_private":len([p for p in PR if p["theme"]==theme]),
        "med_1y":round(sorted([r.get("chg_1y") or 0 for r in tr])[len(tr)//2],1),
        "picks":[r["ticker"] for r in tr if r["rating"]=="PICK"],
        "avoids":[r["ticker"] for r in tr if r["rating"]=="AVOID"]})
themes.sort(key=lambda x:-x["score"])
rows.sort(key=lambda x:-x["composite"])
json.dump({"rows":rows,"themes":themes,"privates":PR,"activists":AC,
           "hf_limits":HF.get("limitations"),"asof":"2026-08-14"}, open("data.json","w"), indent=1)

print("themes ranked:"); [print(f"  {t['score']:.2f} {t['theme'][:38]:40s} picks={len(t['picks'])} avoid={len(t['avoids'])}") for t in themes]
print("\ncounts:", collections.Counter(r["rating"] for r in rows))
print("\ntop 12:"); [print(f"  {r['composite']:.2f} {r['rating']:8s} {r['ticker']:6s} {r['theme'][:30]}") for r in rows[:12]]
print("\nbottom 8:"); [print(f"  {r['composite']:.2f} {r['rating']:8s} {r['ticker']:6s} {r['theme'][:30]}") for r in rows[-8:]]
