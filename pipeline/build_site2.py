# -*- coding: utf-8 -*-
import mobile
import json, html, collections, datetime as dt
from pathlib import Path
from dates import today
D = json.load(open("data2.json"))
rows, themes, privates = D["rows"], D["themes"], D["privates"]
watch, port, EV, IPO, OPT = D["watch"], D["portfolio"], D["events"], D["ipos"], D["options"]
asof = D["asof"]; TODAY = today()
picks = [r for r in rows if r["rating"] == "PICK"]
avoids = [r for r in rows if r["rating"] == "AVOID"]
neutral = [r for r in rows if r["rating"] == "NEUTRAL"]
byT = {r["ticker"]: r for r in rows}
e = lambda s: html.escape(str(s if s is not None else ""))
def n(v, d=2, p="", s=""):
    return "—" if v is None else f"{p}{v:,.{d}f}{s}"
def sg(v, d=1):
    if v is None: return '<span class="mut">—</span>'
    return f'<span class="{"up" if v>0 else "dn" if v<0 else "mut"}">{v:+.{d}f}%</span>'
def cap(v):
    if not v: return "—"
    return f"${v/1e12:.2f}T" if v >= 1e12 else f"${v/1e9:.1f}B" if v >= 1e9 else f"${v/1e6:.0f}M"

def spark(vals, w=104, h=30):
    if not vals or len(vals) < 3: return ""
    lo, hi = min(vals), max(vals); rng = (hi-lo) or 1
    pts = " ".join(f"{i/(len(vals)-1)*w:.1f},{h-(v-lo)/rng*h:.1f}" for i, v in enumerate(vals))
    c = "#00c805" if vals[-1] >= vals[0] else "#ff5000"
    return f'<svg class="spk" viewBox="0 0 {w} {h}" preserveAspectRatio="none"><polyline points="{pts}" fill="none" stroke="{c}" stroke-width="1.6"/></svg>'

_FALLBACK_STRATEGY = """
The book is a leveraged bet on one sentence: **AI demand is physically constrained, and the market is mispricing the constraint rather than the demand.**
Thirteen picks, 82.9% invested, 17.1% cash held back by the single-name cap. Portfolio beta is **2.06** — this is not a defensive book and should not be described as one.

**Core (48%, capped at 12% a name).** TSM, AVGO, NVDA, ETN. Foundry, custom silicon, and the electrical equipment that
energizes the racks. These are the toll-collectors with contracted visibility, and all four still carry double-digit upside
to consensus targets. The 12% cap is binding on every one of them, which is the portfolio telling you it wants to be
more concentrated than is prudent.

**Contrarian (22%).** VST, TLN, ISRG, KTOS, CRCL. This is where the edge is. Power scores in the top quartile while trading
*down* on the year — VST is −27% over twelve months against a demand curve that has not bent, and the options market
prices a ±24.6% move into its next print. ISRG earns a place for a different reason: implied vol is **0.55x realized**,
the cheapest optionality in the universe.

**Tactical (13%).** FSLR, AMD, MU, ARM. High realized vol, sized small deliberately — MU runs 94% annualized, ARM 89%.
FSLR doubles as the cleanest squeeze setup in the book: 12.5% of float short with 5.4 days to cover.

**Funding sources.** Cybersecurity is the lowest-ranked theme and the most crowded consensus long. PANW and S are both
AVOID-rated, both overbought into earnings, and both are what pays for the contrarian sleeve. C3.ai is the only Sell-rated
consensus name in the universe and trades at 1.67x implied-to-realized vol — the market is charging a fat premium to
insure a business the sell side has already given up on.

**The risk that actually matters.** 67% of invested capital sits in three themes that correlate at 0.65-0.68 with each other.
Compute, power, and enterprise software are one trade wearing three hats, and a single hyperscaler capex guide-down breaks
all of them together. Cybersecurity and Enterprise Software correlate at **0.80** — the highest pair in the matrix — so the
short side is not the diversifier it appears to be either. Size accordingly, and treat the 17.1% cash as thesis insurance
rather than laziness.
"""
_sp = Path("strategy.md")
STRATEGY = _sp.read_text() if _sp.exists() else _FALLBACK_STRATEGY
def md(t):
    """Bold via **, italic via single * — order matters, bold first."""
    t = e(t).replace("**", "\x00"); out, b = [], False
    for p in t.split("\x00"): out.append(p if not b else f"<b>{p}</b>"); b = not b
    t = "".join(out)
    parts = t.split("*"); res, i = [], False
    for p in parts: res.append(p if not i else f"<i>{p}</i>"); i = not i
    return "".join(res)

# ---------- watchlist cards
KIND = {"Contrarian":"#00c805","Squeeze":"#ffb020","Earnings":"#5b9cff","Rich vol":"#c77dff",
        "Cheap vol":"#00d9c0","Put flow":"#ff5000","Overextended":"#ff5000","Conflict":"#ffb020","IPO read-across":"#8ea0b5"}
def wcard(w):
    r = byT[w["ticker"]]
    sig = "".join(f'<span class="chip" style="--c:{KIND.get(s["kind"],"#8ea0b5")}">{e(s["kind"])}</span>' for s in w["signals"])
    why = "".join(f'<li>{e(s["why"])}</li>' for s in w["signals"])
    return f"""<div class="wc">
<div class="wch"><div><span class="tk">{e(w['ticker'])}</span><span class="tag {r['rating'].lower()}">{r['rating']}</span></div>
<div class="wpx">{n(r.get('last'),2,'$')}<span class="d">{sg(r.get('chg_1w'))}</span></div></div>
<div class="wsp">{spark(r.get('spark') or [])}</div>
<div class="chips">{sig}</div><ul class="why">{why}</ul></div>"""

# ---------- trade tickets
def ticket(r):
    t = r["trade"]; o = r.get("opt") or {}
    legs = "".join(f"""<div class="leg {('buy' if g['action']=='BUY' else 'sell')}">
<span class="act">{g['action']}</span><span class="lk">{n(g['strike'],0,'$')} {'CALL' if g['cp']=='C' else 'PUT'}</span>
<span class="lm mono">{n(g['mid'],2,'$')}</span><span class="ld mono">Δ{n(g.get('delta'),2)}</span><span class="lo mono">{n(g.get('oi'),0)} OI</span></div>""" for g in t["legs"])
    credit = t["net_type"] == "credit"
    return f"""<div class="tkt">
<div class="tkh"><div><span class="tk">{e(r['ticker'])}</span><span class="tag {r['rating'].lower()}">{r['rating']}</span></div>
<div class="tst">{e(t['structure'])}</div></div>
<div class="tmeta"><span>{e(t['expiry'])}</span><span>{t['dte']}d</span><span>Spot {n(t['spot'],2,'$')}</span>
<span>IV {n(o.get('iv30'),1,'','%')}</span><span class="{'hot' if (o.get('iv_rv') or 0)>1.2 else 'cool' if (o.get('iv_rv') or 1)<0.7 else ''}">IV/RV {n(o.get('iv_rv'),2)}</span></div>
<div class="legs">{legs}</div>
<div class="tstats">
<div><span>Net {t['net_type']}</span><b class="mono">{n(t['net'],2,'$')}</b></div>
<div><span>Max gain</span><b class="mono up">{n(t['max_gain_1lot'],0,'$')}</b></div>
<div><span>Max loss</span><b class="mono dn">{n(t['max_loss_1lot'],0,'$')}</b></div>
<div><span>Breakeven</span><b class="mono">{n(t['breakeven'],2,'$')}</b></div>
<div><span>BE move</span><b class="mono">{t['be_move_pct']:+.1f}%</b></div>
<div><span>Reward:risk</span><b class="mono">{n(t['rr'],2)}x</b></div>
</div>
<div class="tfoot">{'Credit received up front; max loss is width minus credit.' if credit else 'Debit paid up front; max loss is the debit.'} Per 1 lot (100 shares). Delayed quotes — your fill will differ.</div>
</div>"""
trades = [r for r in rows if r.get("trade")]
trades.sort(key=lambda r: ({"PICK":0,"NEUTRAL":1,"AVOID":2}[r["rating"]], -r["composite"]))

# ---------- portfolio
prow = "".join(f"""<tr><td class="tk">{e(p['ticker'])}<div class="sub">{e((p.get('name') or '')[:24])}</div></td>
<td><span class="sl {p['sleeve'].lower()}">{p['sleeve']}</span></td>
<td class="sub">{e(p['theme'][:26])}</td>
<td class="n"><div class="wbar"><i style="width:{p['weight']/12*100:.0f}%"></i></div><b class="mono">{p['weight']:.1f}%</b></td>
<td class="n mono">{n(p.get('last'),2,'$')}</td><td class="n">{sg(p.get('chg_1y'))}</td>
<td class="n mono">{n(p.get('beta'),2)}</td><td class="n mono">{n(p.get('rvol30'),0,'','%')}</td>
<td class="n mono b">{p['composite']:.2f}</td></tr>""" for p in port)

# ---------- squeeze board
sq = sorted([r for r in rows if r.get("short_pct_float")], key=lambda r: -r["squeeze"])[:20]
sqrow = "".join(f"""<tr><td class="tk">{e(r['ticker'])}</td><td class="sub">{e(r['theme'][:24])}</td>
<td><span class="tag {r['rating'].lower()}">{r['rating']}</span></td>
<td class="n"><div class="sqb"><i style="width:{r['squeeze']}%"></i></div><b class="mono">{r['squeeze']}</b></td>
<td class="n mono">{n(r.get('short_pct_float'),1,'','%')}</td><td class="n mono">{n(r.get('short_ratio'),1)}</td>
<td class="n">{sg(r.get('short_chg_pct'))}</td><td class="n mono">{n(r.get('rsi14'),0)}</td>
<td class="n">{sg(r.get('vs_sma50'))}</td></tr>""" for r in sq)

# ---------- events
def ed(x):
    d = str(x.get("date") or "")
    try:
        if len(d) == 10: return dt.date.fromisoformat(d)
        if len(d) == 7: return dt.date.fromisoformat(d+"-15")
    except Exception: pass
    return dt.date(2099,1,1)
DIR = {"bullish_if_hit":("Bullish","up"),"bearish_risk":("Risk","dn"),"binary":("Binary","bin"),"informational":("Info","mut")}
evs = sorted([x for x in EV if ed(x) >= TODAY], key=ed)
erow = "".join(f"""<tr><td class="mono dt">{e(x.get('date'))}<div class="sub">{e(x.get('date_confidence'))}</div></td>
<td>{''.join(f'<code>{e(k)}</code>' for k in (x.get('tickers') or [])[:5])}</td>
<td class="ev"><b>{e(x.get('title'))}</b><div class="sub">{e(x.get('why_it_matters') or x.get('description'))}</div></td>
<td><span class="etype">{e(x.get('event_type'))}</span></td>
<td><span class="dirl {DIR.get(x.get('direction'),('','mut'))[1]}">{DIR.get(x.get('direction'),('—','mut'))[0]}</span></td>
<td>{f'<a href="{e(x.get("source_url"))}" target="_blank" rel="noopener noreferrer">src</a>' if x.get('source_url') else ''}</td></tr>""" for x in evs[:60])

# earnings strip
earn = sorted([r for r in rows if r.get("days_to_earnings") is not None and 0 <= r["days_to_earnings"] <= 75],
              key=lambda r: r["days_to_earnings"])
ecard = "".join(f"""<div class="ec"><div class="ecd">{r['days_to_earnings']}<span>d</span></div>
<div><div class="tk">{e(r['ticker'])}</div><div class="sub">{e(r.get('earnings_next'))}</div></div>
<div class="ecm">{'±'+str((r.get('opt') or {}).get('imp_move_pct'))+'%' if (r.get('opt') or {}).get('imp_move_pct') else '—'}<span>implied</span></div></div>"""
 for r in earn[:24])

# ---------- IPOs
ST = {"priced":"#00c805","pending":"#ffb020","rumored":"#8ea0b5"}
def icard(p):
    return f"""<div class="ip"><div class="iph"><b>{e(p['name'])}</b><span class="ist" style="--c:{ST.get(p.get('status'),'#8ea0b5')}">{e(p.get('status'))}</span></div>
<div class="ipv mono">{('$%.1fB'%p['valuation_b']) if isinstance(p.get('valuation_b'),(int,float)) else 'undisclosed'}
<span class="sub">{e(p.get('expected_date') or '')} {('· '+e(p.get('ticker'))) if p.get('ticker') else ''}</span></div>
<div class="ipd">{e(p.get('description'))}</div>
<div class="ipr"><b>Read-across</b> {e(p.get('read_across'))}</div>
<div class="ipm">{''.join(f'<code>{e(a)}</code>' for a in (p.get('affects') or [])[:6])}
{f'<a href="{e(p.get("source_url"))}" target="_blank" rel="noopener noreferrer">source</a>' if p.get('source_url') else ''}</div></div>"""
ipo_sec = "".join(f"""<div class="ipsec"><h3>{s.title()} <span class="sub">{len([p for p in IPO if p.get('status')==s])}</span></h3>
<div class="ipg" data-mcollapse="4">{''.join(icard(p) for p in IPO if p.get('status')==s)}</div></div>""" for s in ("pending","priced","rumored"))

# ---------- universe table
def urow(r):
    o = r.get("opt") or {}
    return f"""<tr data-rating="{r['rating']}" data-theme="{e(r['theme'])}">
<td class="tk">{e(r['ticker'])}<div class="sub">{e((r.get('name') or '')[:22])}</div></td>
<td class="sub">{e(r['theme'][:22])}</td><td><span class="tag {r['rating'].lower()}">{r['rating']}</span></td>
<td class="n mono b">{r['composite']:.2f}</td><td class="n">{spark(r.get('spark') or [])}</td>
<td class="n mono">{n(r.get('last'),2,'$')}</td><td class="n">{sg(r.get('chg_1w'))}</td><td class="n">{sg(r.get('chg_1y'))}</td>
<td class="n mono sub">{n(r.get('wk52_low'),0,'$')}–{n(r.get('wk52_high'),0,'$')}</td>
<td class="n mono">{cap(r.get('market_cap'))}</td><td class="n mono">{n(r.get('fwd_pe'),1)}</td>
<td class="n">{sg((r.get('rev_growth') or 0)*100 if r.get('rev_growth') is not None else None)}</td>
<td class="n mono">{n(r.get('rsi14'),0)}</td><td class="n">{sg(r.get('vs_sma200'))}</td>
<td class="n mono">{n(r.get('beta_1y'),2)}</td><td class="n mono">{n(r.get('short_pct_float'),1,'','%')}</td>
<td class="n mono">{n(r.get('squeeze'),0)}</td><td class="n mono">{n(o.get('iv_rv'),2)}</td>
<td class="n sub">{e(r.get('consensus') or '—')}<div class="mono">{n(r.get('pt_mean'),0,'$')}</div></td>
<td class="n sub">{e(r.get('earnings_next') or '—')}</td></tr>"""
uni = "".join(urow(r) for r in rows)

# ---------- correlation matrix
CN = D["corr_names"]; C = D["corr"]
def cc(v):
    if v is None: return "#1a1c20"
    x = max(0, min(1, (v+0.2)/1.2))
    return f"rgba({int(255*x)},{int(60+80*(1-x))},{int(90*(1-x))},{0.25+0.65*x:.2f})"
chead = "".join(f'<th class="rot"><div>{e(a[:22])}</div></th>' for a in CN)
cbody = "".join(f'<tr><td class="cl">{e(a[:26])}</td>' + "".join(
    f'<td class="cx" style="background:{cc(C[a][b])}">{"" if a==b else (C[a][b] if C[a][b] is not None else "")}</td>' for b in CN) + "</tr>" for a in CN)

pw = sum(p["weight"] for p in port)
inv = round(pw, 1)
HTML = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ten Themes — Trading Desk</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#08090b;--pan:#111317;--pan2:#171a1f;--line:#23272e;--tx:#e8ecf1;--mut:#7d8a9c;
--up:#00c805;--dn:#ff5000;--acc:#5b9cff;--warn:#ffb020}}
*{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:var(--bg);color:var(--tx);font:15px/1.55 Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1480px;margin:0 auto;padding:0 clamp(14px,4vw,44px)}}
.mono{{font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums}}
.up{{color:var(--up)}} .dn{{color:var(--dn)}} .mut,.sub{{color:var(--mut)}}
.sub{{font-size:11.5px;font-weight:400}} .b{{font-weight:700}}
header{{padding:26px 0 0;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#0d1014,#08090b)}}
.top{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap}}
.kick{{color:var(--up);font:700 10.5px/1 'JetBrains Mono';letter-spacing:.2em;text-transform:uppercase;margin-bottom:8px}}
h1{{font:800 clamp(26px,5vw,38px)/1 Inter;margin:0;letter-spacing:-1px}}
.asof{{color:var(--mut);font-size:12px;text-align:right}}
.hero{{display:grid;grid-template-columns:repeat(auto-fit,minmax(126px,1fr));gap:1px;background:var(--line);margin-top:22px;border-top:1px solid var(--line)}}
.hs{{background:var(--bg);padding:15px 12px 18px}}
.hs b{{display:block;font:700 clamp(19px,3vw,25px)/1 'JetBrains Mono'}}
.hs span{{font-size:9.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--mut);display:block;margin-top:5px}}
section{{padding:40px 0;border-bottom:1px solid var(--line)}}
h2{{font:700 11px/1 'JetBrains Mono';letter-spacing:.2em;text-transform:uppercase;color:var(--acc);margin:0 0 8px}}
h3{{font:600 15px/1.3 Inter;margin:22px 0 11px}}
.lede{{color:#9fb0c4;font-size:15px;line-height:1.65;max-width:76ch;margin:0 0 22px}}
.tag{{display:inline-block;font:700 9px/1 'JetBrains Mono';letter-spacing:.08em;padding:4px 6px;border-radius:3px;margin-left:7px;vertical-align:middle}}
.pick{{background:rgba(0,200,5,.14);color:var(--up)}} .avoid{{background:rgba(255,80,0,.14);color:var(--dn)}}
.neutral{{background:rgba(125,138,156,.14);color:var(--mut)}}
.tk{{font:700 14px 'JetBrains Mono'}}
.spk{{width:104px;height:30px;display:block}}
.strat{{background:var(--pan);border:1px solid var(--line);border-left:3px solid var(--up);padding:26px 32px;border-radius:10px;max-width:1020px}}
.strat p{{margin:0 0 14px;color:#c3cede;line-height:1.72;max-width:92ch}} .strat p:last-child{{margin:0}}
.strat b{{color:#fff}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(288px,1fr));gap:12px}}
.wc{{background:var(--pan);border:1px solid var(--line);border-radius:11px;padding:14px}}
.wch{{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}}
.wpx{{text-align:right;font:700 16px 'JetBrains Mono'}} .wpx .d{{display:block;font-size:11.5px;font-weight:500}}
.wsp{{margin:9px 0}}
.chips{{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:9px}}
.chip{{font:700 8.5px 'JetBrains Mono';letter-spacing:.07em;text-transform:uppercase;padding:4px 6px;border-radius:3px;color:var(--c);background:color-mix(in srgb,var(--c) 15%,transparent)}}
.why{{margin:0;padding-left:15px;font-size:11.5px;color:#9fb0c4;line-height:1.5}} .why li{{margin-bottom:4px}}
.tkt{{background:var(--pan);border:1px solid var(--line);border-radius:12px;padding:15px;display:flex;flex-direction:column}}
.tkh{{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}}
.tst{{font-size:11.5px;color:var(--acc);font-weight:600}}
.tmeta{{display:flex;flex-wrap:wrap;gap:9px;font:500 10.5px 'JetBrains Mono';color:var(--mut);margin:9px 0 11px}}
.tmeta .hot{{color:var(--warn)}} .tmeta .cool{{color:#00d9c0}}
.leg{{display:grid;grid-template-columns:38px 1fr auto auto auto;gap:7px;align-items:center;font-size:11px;padding:7px 8px;border-radius:6px;margin-bottom:5px;background:var(--pan2)}}
.leg .act{{font:700 8.5px 'JetBrains Mono';padding:3px 4px;border-radius:3px;text-align:center}}
.buy .act{{background:rgba(0,200,5,.18);color:var(--up)}} .sell .act{{background:rgba(255,80,0,.18);color:var(--dn)}}
.lk{{font-weight:600}} .lm,.ld,.lo{{font-size:10.5px;color:var(--mut)}}
.tstats{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border-radius:7px;overflow:hidden;margin-top:8px}}
.tstats>div{{background:var(--pan2);padding:9px 8px}}
.tstats span{{display:block;font-size:8.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--mut);margin-bottom:3px}}
.tstats b{{font-size:13px}}
.tfoot{{font-size:10px;color:var(--mut);margin-top:9px;line-height:1.45}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{text-align:left;font:600 9.5px/1.3 'JetBrains Mono';letter-spacing:.09em;text-transform:uppercase;color:var(--mut);
padding:9px 8px;border-bottom:1px solid var(--line);position:sticky;top:0;background:#0c0e11;z-index:2;cursor:pointer;white-space:nowrap}}
td{{padding:9px 8px;border-bottom:1px solid rgba(35,39,46,.6);vertical-align:middle}}
tbody tr:hover{{background:var(--pan)}} .n{{text-align:right}}
.scroll{{overflow:auto;border:1px solid var(--line);border-radius:10px;max-height:740px;-webkit-overflow-scrolling:touch}}
.wbar,.sqb{{display:inline-block;width:52px;height:6px;background:var(--pan2);border-radius:3px;margin-right:7px;vertical-align:middle}}
.wbar i{{display:block;height:100%;background:var(--up);border-radius:3px}}
.sqb i{{display:block;height:100%;background:linear-gradient(90deg,var(--acc),var(--warn));border-radius:3px}}
.sl{{font:700 8.5px 'JetBrains Mono';letter-spacing:.07em;text-transform:uppercase;padding:4px 6px;border-radius:3px}}
.core{{background:rgba(91,156,255,.15);color:var(--acc)}} .contrarian{{background:rgba(0,200,5,.15);color:var(--up)}}
.tactical{{background:rgba(255,176,32,.15);color:var(--warn)}}
.ctrl{{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:14px}}
.ctrl button{{font:600 11px 'JetBrains Mono';padding:8px 13px;border:1px solid var(--line);background:var(--pan);color:var(--mut);cursor:pointer;border-radius:7px}}
.ctrl button.on{{background:var(--tx);color:#08090b;border-color:var(--tx)}}
.estrip{{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:9px;margin-bottom:22px}}
.ec{{background:var(--pan);border:1px solid var(--line);border-radius:9px;padding:11px;display:flex;align-items:center;gap:10px}}
.ecd{{font:700 21px 'JetBrains Mono';color:var(--acc);line-height:1}} .ecd span{{font-size:10px;color:var(--mut)}}
.ecm{{margin-left:auto;text-align:right;font:700 13px 'JetBrains Mono';color:var(--warn)}}
.ecm span{{display:block;font-size:8.5px;color:var(--mut);font-weight:500;letter-spacing:.08em;text-transform:uppercase}}
.dt{{white-space:nowrap;font-size:11.5px}} .ev b{{font-weight:600}}
.etype{{font:600 9px 'JetBrains Mono';letter-spacing:.07em;text-transform:uppercase;color:var(--mut);background:var(--pan2);padding:4px 6px;border-radius:3px}}
.dirl{{font:700 9px 'JetBrains Mono';letter-spacing:.07em;text-transform:uppercase}}
.dirl.up{{color:var(--up)}} .dirl.dn{{color:var(--dn)}} .dirl.bin{{color:var(--warn)}} .dirl.mut{{color:var(--mut)}}
.ipg,.pvg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:11px}}
.ip,.pv{{background:var(--pan);border:1px solid var(--line);border-radius:10px;padding:13px;font-size:12px}}
.iph{{display:flex;justify-content:space-between;align-items:center;gap:8px}} .iph b{{font-size:14px}}
.ist{{font:700 8.5px 'JetBrains Mono';letter-spacing:.08em;text-transform:uppercase;color:var(--c);background:color-mix(in srgb,var(--c) 16%,transparent);padding:4px 6px;border-radius:3px}}
.ipv{{font-size:15px;font-weight:700;color:var(--up);margin:4px 0 7px}}
.ipd{{color:#9fb0c4;line-height:1.5;margin-bottom:7px}}
.ipr{{font-size:11px;color:#b6c4d6;border-top:1px solid var(--line);padding-top:7px;line-height:1.5}}
.ipm{{margin-top:7px;display:flex;gap:5px;flex-wrap:wrap;align-items:center}}
code{{font:600 9.5px 'JetBrains Mono';background:rgba(91,156,255,.13);color:var(--acc);padding:3px 5px;border-radius:3px}}
b.lbl,.ipr b,.pvt b{{font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)}}
a{{color:var(--acc);font-size:11px}}
.cmx{{overflow:auto;border:1px solid var(--line);border-radius:10px}}
.cmx table{{font-size:11px}} .rot{{height:118px;vertical-align:bottom;padding:0 !important}}
.rot div{{writing-mode:vertical-rl;transform:rotate(200deg);white-space:nowrap;font-size:9.5px;padding:7px 0}}
.cl{{white-space:nowrap;font-size:11px;color:#9fb0c4;position:sticky;left:0;background:#0c0e11}}
.cx{{text-align:center;font:600 10px 'JetBrains Mono';min-width:46px}}
.warn{{background:rgba(255,80,0,.07);border:1px solid rgba(255,80,0,.28);border-radius:10px;padding:15px 17px;margin-top:18px;font-size:12.5px;color:#f0c0aa;line-height:1.6}}
.warn b{{color:var(--dn)}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:26px}}
.note{{font-size:12px;color:var(--mut);line-height:1.65}} .note b{{color:var(--tx)}}
.pvsec{{margin-bottom:24px}} .pvt{{font-size:11px;color:#9fb0c4;margin-top:6px;line-height:1.5}}
.ipo-w{{font:700 8.5px 'JetBrains Mono';background:var(--warn);color:#08090b;padding:3px 5px;border-radius:3px}}
footer{{padding:26px 0;color:var(--mut);font-size:11.5px}}
@media(max-width:820px){{.cols{{grid-template-columns:1fr}}.tstats{{grid-template-columns:repeat(2,1fr)}}
th,td{{padding:8px 6px;font-size:11.5px}}section{{padding:30px 0}}}}
{mobile.CSS}
</style></head><body>
<header><div class="wrap">
<div class="top"><div><div class="kick">● Live desk · refreshed each weekday</div><h1>Ten Themes</h1></div>
<div class="asof">Market data <b class="mono" style="color:#fff">{asof}</b><br>Options: CBOE delayed · 13F Q2 2026<br>Form 4 trailing 90d<br><a href="/map" style="color:#5b9cff">Macro map</a> · <a href="/backtest" style="color:#5b9cff">Backtest →</a></div></div>
<div class="hero">
<div class="hs"><b>10</b><span>Themes</span></div>
<div class="hs"><b>{len(rows)}</b><span>Public</span></div>
<div class="hs"><b>{len(privates)}</b><span>Private</span></div>
<div class="hs"><b class="up">{len(picks)}</b><span>Picks</span></div>
<div class="hs"><b class="dn">{len(avoids)}</b><span>Avoid</span></div>
<div class="hs"><b>{len(trades)}</b><span>Trades</span></div>
<div class="hs"><b>{len(evs)}</b><span>Catalysts</span></div>
<div class="hs"><b>{len(IPO)}</b><span>IPOs</span></div>
<div class="hs"><b class="mono">{D['port_beta']}</b><span>Book beta</span></div>
</div></div></header>

<section><div class="wrap"><h2>The Strategy</h2>
<div class="strat">{''.join(f'<p>{md(p.strip())}</p>' for p in STRATEGY.strip().split(chr(10)+chr(10)))}</div>
</div></section>

<section><div class="wrap"><h2>Pay Attention — {len(watch)} names flagged</h2>
<p class="lede">Ranked by how many independent signals fired this week. A name here is not automatically a buy — it is where the data stopped agreeing with itself.</p>
<div class="grid" data-mcollapse="6">{''.join(wcard(w) for w in watch[:18])}</div></div></section>

<section><div class="wrap"><h2>Model Portfolio — {inv}% invested, {D['cash']}% cash</h2>
<p class="lede">Conviction weighted by inverse realized volatility, bucketed into sleeves, hard-capped at 12% per name. The cap binds on all four core positions — the model wants more concentration than is prudent, and the overflow becomes cash rather than forced diversification.</p>
<div class="scroll"><table><thead><tr><th>Name</th><th>Sleeve</th><th>Theme</th><th class="n">Weight</th><th class="n">Last</th><th class="n">1Y</th><th class="n">Beta</th><th class="n">RVol30</th><th class="n">Score</th></tr></thead><tbody>{prow}</tbody></table></div>
<div class="warn"><b>Concentration warning.</b> {D['cluster_w']}% of invested capital sits in AI Compute, Power &amp; Grid, and Enterprise Software — three themes that correlate 0.65–0.68 with one another. Book beta is <b>{D['port_beta']}</b>, roughly twice the market. This is one trade expressed at three layers of the stack, not three diversified bets. A hyperscaler capex guide-down is the single event that breaks all of it at once.</div>
</div></section>

<section><div class="wrap"><h2>Trade Tickets — {len(trades)} defined-risk structures</h2>
<p class="lede">Built from live CBOE chains and screened for tradability: minimum 100 contracts of open interest, bid above $0.05, and bid-ask inside 30% of mid. Names that failed the screen got no ticket rather than an untradeable one. Every figure below is a real quoted strike.</p>
<div class="grid" data-mcollapse="5">{''.join(ticket(r) for r in trades)}</div>
<div class="warn"><b>Read this before trading any of it.</b> These are illustrative defined-risk structures generated from delayed quotes — not personalised advice, and not sized to your account. Options can expire worthless; a debit spread can lose 100% of the premium paid, and a credit spread can lose the full width minus credit. Max loss figures are per single lot. Your fill will differ from the mid prices shown.</div>
</div></section>

<section><div class="wrap"><h2>Squeeze &amp; Short Interest</h2>
<p class="lede">Squeeze score blends short interest as a share of float, days to cover, the change since the prior settlement, and price momentum. High score on a PICK is a setup; high score on an AVOID means the market already agrees with the rating.</p>
<div class="scroll"><table><thead><tr><th>Ticker</th><th>Theme</th><th>Rating</th><th class="n">Squeeze</th><th class="n">% Float</th><th class="n">Days cover</th><th class="n">Δ Short</th><th class="n">RSI</th><th class="n">vs 50d</th></tr></thead><tbody>{sqrow}</tbody></table></div></div></section>

<section><div class="wrap"><h2>Earnings Runway</h2>
<p class="lede">Days until the next confirmed report, with the move the options market is pricing into it — derived from the at-the-money straddle on the first expiry after the print.</p>
<div class="estrip" data-mcollapse="8">{ecard}</div>
<h2 style="margin-top:26px">Catalyst Calendar — {len(evs)} events</h2>
<p class="lede">Non-earnings catalysts over the next four months: product launches, regulatory decisions, capacity auctions, clinical readouts and index rebalances.</p>
<div class="scroll"><table class="stack"><thead><tr><th>Date</th><th>Tickers</th><th>Event</th><th>Type</th><th>Direction</th><th></th></tr></thead><tbody data-mcollapse="6">{erow}</tbody></table></div></div></section>

<section><div class="wrap"><h2>IPO Pipeline — {len(IPO)} companies</h2>
<p class="lede">What is coming public in these themes, and which listed names it reprices. A large listing does not just add a ticker — it hands the market a fresh comparable, and comparables move multiples.</p>
{ipo_sec}</div></section>

<section><div class="wrap"><h2>Full Universe — {len(rows)} names</h2>
<p class="lede">Tap any column to sort.</p>
<div class="ctrl"><button class="on" data-f="all">All {len(rows)}</button><button data-f="PICK">Picks {len(picks)}</button><button data-f="NEUTRAL">Neutral {len(neutral)}</button><button data-f="AVOID">Avoid {len(avoids)}</button></div>
<div class="scroll"><table id="uni"><thead><tr><th>Ticker</th><th>Theme</th><th>Rating</th><th class="n">Score</th><th class="n">90d</th><th class="n">Last</th><th class="n">1W</th><th class="n">1Y</th><th class="n">52w range</th><th class="n">Mkt cap</th><th class="n">Fwd P/E</th><th class="n">Rev gr</th><th class="n">RSI</th><th class="n">vs 200d</th><th class="n">Beta</th><th class="n">Short%</th><th class="n">Squeeze</th><th class="n">IV/RV</th><th class="n">Consensus</th><th class="n">Earnings</th></tr></thead><tbody>{uni}</tbody></table></div></div></section>

<section><div class="wrap"><h2>Theme Correlation Matrix</h2>
<p class="lede">One-year daily return correlation between equal-weighted theme baskets. This is the diversification the book actually has, as opposed to the diversification the theme labels imply.</p>
<div class="cmx"><table><thead><tr><th></th>{chead}</tr></thead><tbody>{cbody}</tbody></table></div></div></section>

<section><div class="wrap"><h2>Method &amp; Limitations</h2>
<div class="cols"><div class="note">
<p><b>Composite scoring.</b> Secular demand 25%, moat against private disruption 20%, valuation versus mean analyst target 20%, analyst momentum 20%, smart-money flow 15%. PICK ≥ 3.70, AVOID &lt; 3.05. Secular is assigned per theme and is the one deliberately judgmental input.</p>
<p><b>Prices, technicals, fundamentals.</b> Two years of daily closes from CBOE's delayed-quote history as of {asof} (Yahoo when reachable). RSI, moving averages, realized volatility, beta, Sharpe and max drawdown computed locally. Valuation, margins and growth are computed from each company's latest 10-K/10-Q in SEC EDGAR against this week's price (free cash flow is operating cash flow less capex); when Yahoo's key-statistics module is reachable it is used instead. Short interest is FINRA's bi-monthly consolidated report, so it is up to two weeks stale by construction. Forward P/E, PEG, consensus and estimates have no free cloud-reachable source and are carried from the last week Yahoo answered; foreign (IFRS) filers carry all fundamentals.</p>
<p><b>Options.</b> Chains from CBOE's delayed-quote feed: real bid, ask, open interest, implied vol and greeks. IV/RV compares at-the-money implied vol on the ~30-day expiry against 30-day realized vol. Implied move is the at-the-money straddle on the first expiry after the earnings date. Expiries are selected by open interest so tickets land on liquid monthlies rather than thin weeklies.</p>
</div><div class="note">
<p><b>13F caveat.</b> Institutional positioning is a 45-day-lagged Q2 2026 snapshot, long US equity only, and was confirmable for 27 of 71 tickers from free sources. It carries the lowest weight in the composite for exactly that reason.</p>
<p><b>Insider data</b> is Form 4 filing counts and parsed XML from EDGAR; volume conflates open-market sales with grants and 10b5-1 exercises. <b>Activist screen</b> used EDGAR quarterly indexes, since full-text search does not cover filings after December 2024.</p>
<p><b>Events and IPOs</b> are researched from public reporting and carry a confidence flag and a source link each. Dates marked expected or rumored are not confirmed. <b>Private valuations</b> are last disclosed post-money, press-reported, often stale and preference-laden.</p>
<p><b>Correction this week:</b> ABBV was misfiled under Robotics &amp; Physical AI in the prior run and has been moved to Biotech &amp; AI Drug Discovery; SERV was added to keep the robotics basket at seven names. Theme scores for both baskets changed as a result.</p>
<p><b>This is research, not investment advice.</b> Nothing here accounts for your existing exposure, tax situation, time horizon or risk tolerance.</p>
</div></div></div></section>

<footer><div class="wrap">Ten Themes · {len(rows)} public names · {len(privates)} private competitors · {len(trades)} trade tickets · data as of {asof} · refreshed each weekday after the US close</div></footer>
<script>
document.querySelectorAll('.ctrl button').forEach(b=>b.onclick=()=>{{
 document.querySelectorAll('.ctrl button').forEach(x=>x.classList.remove('on'));b.classList.add('on');
 const f=b.dataset.f;
 document.querySelectorAll('#uni tbody tr').forEach(r=>r.style.display=(f==='all'||r.dataset.rating===f)?'':'none');}});
document.querySelectorAll('#uni th').forEach((th,i)=>{{let asc=false;th.onclick=()=>{{asc=!asc;
 const tb=th.closest('table').querySelector('tbody');
 [...tb.rows].sort((a,b)=>{{const g=r=>{{const t=(r.cells[i].innerText||'').replace(/[$,%+x]/g,'').split('\\n')[0].trim();
 const v=parseFloat(t);return isNaN(v)?t.toLowerCase():v;}};const x=g(a),y=g(b);
 return (x>y?1:x<y?-1:0)*(asc?1:-1);}}).forEach(r=>tb.appendChild(r));}};}});
</script>{mobile.JS}</body></html>"""
open("site2.html", "w").write(HTML)
print("wrote site2.html", len(HTML), "bytes | trades", len(trades), "| watch", len(watch), "| events", len(evs))
