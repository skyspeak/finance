# -*- coding: utf-8 -*-
"""Macro & Market Map dashboard. Descriptive only — states relationships, draws no trade conclusions."""
import json, html, collections
D2 = json.load(open("data2.json")); MAC = json.load(open("macro.json"))
FA = json.load(open("factors.json")); SEC = json.load(open("sectors.json")); LAY = json.load(open("layers.json"))
rows = {r["ticker"]: r for r in D2["rows"]}
privates = D2["privates"]; asof = MAC["asof"]
S = MAC["series"]; TX = FA["theme_exposure"]; KX = FA["ticker_exposure"]
STATS = FA["stats"]; FDEF = FA["factors"]; REG = FA["regime"]
TAX_ORDER = {}
for x in LAY["public"] + LAY["private"]:
    TAX_ORDER.setdefault(x["theme"], {})[x["layer"]] = x["layer_index"]
THEMES = [t["theme"] for t in D2["themes"]]

e = lambda s: html.escape(str(s if s is not None else ""))
def n(v, d=2, p="", s=""): return "—" if v is None else f"{p}{v:,.{d}f}{s}"
def sg(v, d=1):
    if v is None: return '<span class="mut">—</span>'
    return f'<span class="{"up" if v>0 else "dn" if v<0 else "mut"}">{v:+.{d}f}%</span>'
def ordn(v):
    """1st / 2nd / 3rd / 4th ... handles the 11-13 exception."""
    if v is None: return "—"
    v = int(v)
    suf = "th" if 10 <= v % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(v % 10, "th")
    return f"{v}{suf}"

def spark(vals, w=120, h=32, force=None):
    if not vals or len(vals) < 3: return ""
    lo, hi = min(vals), max(vals); rng = (hi-lo) or 1
    pts = " ".join(f"{i/(len(vals)-1)*w:.1f},{h-(v-lo)/rng*h:.1f}" for i, v in enumerate(vals))
    c = force or ("#00c805" if vals[-1] >= vals[0] else "#ff5000")
    return f'<svg class="spk" viewBox="0 0 {w} {h}" preserveAspectRatio="none"><polyline points="{pts}" fill="none" stroke="{c}" stroke-width="1.5"/></svg>'

# ---------- macro scorecard
KIND_ORDER = ["rates", "vol", "fx", "commodity", "credit", "crypto"]
def mcard(x):
    pc = x.get("pctile_1y")
    return f"""<div class="mc">
<div class="mch"><div><b>{e(x['name'])}</b><div class="sub">{e(x['desc'])}</div></div>
<div class="mv mono">{n(x['last'],2)}</div></div>
<div class="msp">{spark(x.get('vals') or [])}</div>
<div class="mrow"><span>1W</span>{sg(x.get('chg_1w'))}<span>1M</span>{sg(x.get('chg_1m'))}<span>3M</span>{sg(x.get('chg_3m'))}<span>1Y</span>{sg(x.get('chg_1y'))}</div>
<div class="mpc"><div class="pcb"><i style="left:{(pc or 0)}%"></i></div>
<span class="sub">{n(x.get('lo_1y'),2)} — {n(x.get('hi_1y'),2)} · {ordn(pc)} pctile</span></div></div>"""
macro_cards = "".join(mcard(S[k]) for k in
    ["^VIX","DX-Y.NYB","HG=F","CL=F","GC=F","CREDIT","BTC-USD","TLT"] if k in S)

R = MAC.get("rates", {})
curve_now = MAC["curve"][-1]; curve_1m = MAC["curve"][-22] if len(MAC["curve"]) > 22 else MAC["curve"][0]
curve_1y = MAC["curve"][-253] if len(MAC["curve"]) > 253 else MAC["curve"][0]
TEN = [("3M","m3"),("2Y","y2"),("5Y","y5"),("10Y","y10"),("30Y","y30")]
curve_rows = "".join(f"""<tr><td class="lbl">{lab}</td>
<td class="n mono b">{n(curve_now.get(k),2,'','%')}</td>
<td class="n mono sub">{n(curve_1m.get(k),2,'','%')}</td>
<td class="n">{sg((curve_now.get(k)-curve_1m.get(k))*100 if curve_now.get(k) and curve_1m.get(k) else None,0)}</td>
<td class="n mono sub">{n(curve_1y.get(k),2,'','%')}</td></tr>""" for lab, k in TEN)

# ---------- factor exposure heatmap
FKEYS = ["RATES","CURVE","DOLLAR","OIL","GOLD","COPPER","CREDIT","VOL","SPX"]
def bcol(k, v):
    if v is None: return "#141619"
    lim = 1.2 if k in ("RATES","CURVE") else (0.35 if k == "VOL" else 3.0 if k == "SPX" else 1.6)
    x = max(-1, min(1, v/lim))
    if x >= 0: return f"rgba(0,200,5,{0.10+0.62*x:.2f})"
    return f"rgba(255,80,0,{0.10+0.62*abs(x):.2f})"
fhead = "".join(f'<th class="n">{e(FDEF[k]["label"])}<div class="sub2">{e(FDEF[k]["unit"])}</div></th>' for k in FKEYS)
def frow(th):
    x = TX[th]; b = x.get("_best"); r = x.get("_best_resid")
    cells = ""
    for k in FKEYS:
        v = (x.get(k) or {})
        bt, r2, t = v.get("beta"), v.get("r2"), v.get("t")
        sig = "" if (t is None or abs(t) >= 2) else " faint"
        cells += (f'<td class="cx{sig}" style="background:{bcol(k,bt)}" title="R²={r2} t={t}">'
                  f'{n(bt,2)}<div class="sub2">{n(r2,2)}</div></td>')
    return f"""<tr><td class="thn">{e(th)}</td>{cells}
<td class="n sub">{e(b['label']) if b else '—'}<div class="mono">{n(b['r2'],3) if b else ''}</div></td>
<td class="n sub">{e(r['label']) if r else '—'}<div class="mono">{n(r['r2'],3) if r else ''}</div></td></tr>"""
fx_rows = "".join(frow(th) for th in THEMES)

mkt_vs_macro = "".join(f"""<tr><td class="thn">{e(th)}</td>
<td class="n mono b">{n((TX[th].get('SPX') or {}).get('beta'),2)}</td>
<td class="n"><div class="rb"><i style="width:{((TX[th].get('SPX') or {}).get('r2') or 0)*100:.0f}%;background:#5b9cff"></i></div><span class="mono">{n((TX[th].get('SPX') or {}).get('r2'),2)}</span></td>
<td class="n"><div class="rb"><i style="width:{((TX[th].get('_best') or {}).get('r2') or 0)*100:.0f}%;background:#ffb020"></i></div><span class="mono">{n((TX[th].get('_best') or {}).get('r2'),3)}</span></td>
<td class="n"><div class="rb"><i style="width:{((TX[th].get('_best_resid') or {}).get('r2') or 0)*100:.0f}%;background:#c77dff"></i></div><span class="mono">{n((TX[th].get('_best_resid') or {}).get('r2'),3)}</span></td>
</tr>""" for th in sorted(THEMES, key=lambda t: -((TX[t].get('SPX') or {}).get('r2') or 0)))

# ---------- regime
RP = FA["regime_perf"]; CUR = FA["regime_current"]
rlabels = sorted(RP, key=lambda k: -RP[k]["days"])
rhead = "".join(f'<th class="n{" cur" if k==CUR else ""}">{e(k)}<div class="sub2">{RP[k]["days"]}d</div></th>' for k in rlabels)
def rcell(v):
    if v is None: return '<td class="cx">—</td>'
    x = max(-1, min(1, v/120))
    c = f"rgba(0,200,5,{0.10+0.6*x:.2f})" if x >= 0 else f"rgba(255,80,0,{0.10+0.6*abs(x):.2f})"
    return f'<td class="cx" style="background:{c}">{v:+.0f}%</td>'
reg_rows = "".join(f'<tr><td class="thn">{e(th)}</td>' +
    "".join(rcell(RP[k]["themes"].get(th)) for k in rlabels) + "</tr>" for th in THEMES)
reg_strip = "".join(f"""<div class="rs"><span>{e(k)}</span><b class="{'up' if (v['state'] or '') in ('risk-on','expanding','weakening','subdued') else 'dn' if (v['state'] or '') in ('risk-off','contracting','elevated') else ''}">{e(v['state'])}</b>
<div class="sub mono">{n(v['value'],1)} {e(v['unit'])}</div></div>""" for k, v in REG.items())

# ---------- sector reality check
GICS = sorted({v.get("sector") for v in SEC["tickers"].values() if v.get("sector")})
shead = "".join(f'<th class="rot"><div>{e(g)}</div></th>' for g in GICS)
def scell(th, g):
    c = SEC["cross_tab"].get(th, {}).get(g, 0)
    if not c: return '<td class="cx"></td>'
    tot = STATS[th]["n"]; x = c/tot
    return f'<td class="cx" style="background:rgba(91,156,255,{0.12+0.6*x:.2f})">{c}</td>'
sec_rows = "".join(f'<tr><td class="thn">{e(th)}</td>' + "".join(scell(th, g) for g in GICS) +
    f'<td class="n mono b">{SEC["purity"][th]["share"]}%</td></tr>' for th in
    sorted(THEMES, key=lambda t: -SEC["purity"][t]["share"]))

rs_rows = "".join(f"""<tr><td class="thn">{e(th)}</td>
<td class="sub mono">{e(STATS[th]['sector_etf'])}</td>
<td class="n">{sg(STATS[th]['rs']['sector_1m'])}</td><td class="n">{sg(STATS[th]['rs']['sector_3m'])}</td><td class="n">{sg(STATS[th]['rs']['sector_1y'])}</td>
<td class="sub mono">{e(STATS[th]['thematic_etf'])}</td>
<td class="n">{sg(STATS[th]['rs']['thematic_1m'])}</td><td class="n">{sg(STATS[th]['rs']['thematic_3m'])}</td><td class="n">{sg(STATS[th]['rs']['thematic_1y'])}</td>
</tr>""" for th in sorted(THEMES, key=lambda t: -(STATS[t]['rs']['sector_3m'] or -1e9)))

# ---------- market maps
pub_by = collections.defaultdict(list); prv_by = collections.defaultdict(list)
for x in LAY["public"]: pub_by[(x["theme"], x["layer"])].append(x)
for x in LAY["private"]: prv_by[(x["theme"], x["layer"])].append(x)
gap_by = {(g["theme"], g["layer"]): g["observation"] for g in LAY["layer_gaps"]}

def maps():
    out = ""
    for th in THEMES:
        layers = sorted(TAX_ORDER.get(th, {}).items(), key=lambda kv: kv[1])
        cols = ""
        for lname, li in layers:
            pubs = pub_by.get((th, lname), []); prvs = prv_by.get((th, lname), [])
            chips = "".join(
                f'<span class="cp pub{" ss" if p.get("spans_stack") else ""}" title="{e(p["note"])}">{e(p["ticker"])}</span>'
                for p in sorted(pubs, key=lambda z: z["ticker"]))
            chips += "".join(
                f'<span class="cp prv" title="{e(p["note"])}">{e(p["name"][:20])}</span>'
                for p in sorted(prvs, key=lambda z: z["name"]))
            gap = gap_by.get((th, lname))
            flag = ""
            if not pubs and prvs: flag = '<span class="gflag priv">private only</span>'
            elif pubs and not prvs: flag = '<span class="gflag inc">no private rival</span>'
            elif not pubs and not prvs: flag = '<span class="gflag none">unpopulated</span>'
            cols += f"""<div class="lcol">
<div class="lch"><span class="li">{li}</span><b>{e(lname)}</b>{flag}</div>
<div class="chips">{chips or '<span class="cp emp">—</span>'}</div>
<div class="lcount sub">{len(pubs)} public · {len(prvs)} private</div>
{f'<div class="gobs">{e(gap)}</div>' if gap else ''}</div>"""
        out += f"""<div class="tmap"><div class="tmh"><h3>{e(th)}</h3>
<div class="sub">{STATS[th]['n']} public · {len([p for p in privates if p['theme']==th])} private · dominant GICS {e(SEC['purity'][th]['dominant_sector'])} ({SEC['purity'][th]['share']}%)</div></div>
<div class="lrow">{cols}</div></div>"""
    return out
market_maps = maps()

# ---------- competition pressure
press = collections.Counter(); threat = {}
for p in privates:
    cw = [t for t in (p.get("competes_with") or []) if t in rows]
    for t in cw: press[t] += 1
    if cw: threat[p["name"]] = {"n": len(cw), "tickers": cw, "theme": p["theme"],
                                "val": p.get("valuation"), "ipo": p.get("ipo_watch")}
press_rows = "".join(f"""<tr><td class="tk">{e(t)}</td><td class="sub">{e(rows[t]['theme'][:26])}</td>
<td class="n"><div class="pb"><i style="width:{min(100,c*16)}%"></i></div><b class="mono">{c}</b></td>
<td class="sub">{e(', '.join(x['name'] for x in privates if t in (x.get('competes_with') or []))[:74])}</td>
<td class="n mono">{n(rows[t].get('sc_moat'),2)}</td></tr>"""
 for t, c in press.most_common(14))
threat_rows = "".join(f"""<tr><td><b>{e(k)}</b><div class="sub">{e(v['theme'][:30])}</div></td>
<td class="n mono">{('$%.0fB'%v['val']) if isinstance(v['val'],(int,float)) else '—'}</td>
<td class="n mono b">{v['n']}</td>
<td>{''.join(f'<code>{e(x)}</code>' for x in v['tickers'][:7])}</td>
<td class="n">{'<span class="gflag priv">IPO watch</span>' if v['ipo'] else ''}</td></tr>"""
 for k, v in sorted(threat.items(), key=lambda kv: -kv[1]["n"])[:14])

# ---------- breadth
bd_rows = "".join(f"""<tr><td class="thn">{e(th)}</td>
<td class="n"><div class="rb"><i style="width:{STATS[th]['breadth_50']}%;background:#00c805"></i></div><span class="mono">{STATS[th]['breadth_50']}%</span></td>
<td class="n"><div class="rb"><i style="width:{STATS[th]['breadth_200']}%;background:#5b9cff"></i></div><span class="mono">{STATS[th]['breadth_200']}%</span></td>
<td class="n">{sg(STATS[th]['ret_1m'])}</td><td class="n">{sg(STATS[th]['ret_3m'])}</td><td class="n">{sg(STATS[th]['ret_1y'])}</td>
<td class="n mono">{n(STATS[th]['dispersion_1y'],0)}</td>
<td class="n mono">{n(STATS[th]['avg_beta'],2)}</td>
<td class="sub mono up">{e(STATS[th]['best_1y'])}</td><td class="sub mono dn">{e(STATS[th]['worst_1y'])}</td></tr>"""
 for th in sorted(THEMES, key=lambda t: -STATS[t]['breadth_50']))

# ---------- rolling correlation chart data
ROLL = FA["rolling"]
roll_series = [{"name": th, "dates": ROLL[th]["COPPER"]["dates"][-180:], "vals": ROLL[th]["COPPER"]["vals"][-180:]} for th in THEMES]
roll_rates = [{"name": th, "dates": ROLL[th]["RATES"]["dates"][-180:], "vals": ROLL[th]["RATES"]["vals"][-180:]} for th in THEMES]
curve_chart = {"labels": [l for l, _ in TEN],
               "now": [curve_now.get(k) for _, k in TEN],
               "m1": [curve_1m.get(k) for _, k in TEN],
               "y1": [curve_1y.get(k) for _, k in TEN]}

max_macro = max((TX[t].get("_best") or {}).get("r2") or 0 for t in THEMES)
max_mkt = max((TX[t].get("SPX") or {}).get("r2") or 0 for t in THEMES)
max_resid = max((TX[t].get("_best_resid") or {}).get("r2") or 0 for t in THEMES)
gapcount = sum(1 for g in LAY["layer_gaps"] if "private" in g["observation"].lower())

HTML = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ten Themes — Macro &amp; Market Map</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
:root{{--bg:#08090b;--pan:#111317;--pan2:#171a1f;--line:#23272e;--tx:#e8ecf1;--mut:#7d8a9c;
--up:#00c805;--dn:#ff5000;--acc:#5b9cff;--warn:#ffb020;--pur:#c77dff}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--tx);font:15px/1.55 Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1560px;margin:0 auto;padding:0 clamp(14px,3.5vw,40px)}}
.mono{{font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums}}
.up{{color:var(--up)}} .dn{{color:var(--dn)}} .mut,.sub{{color:var(--mut)}}
.sub{{font-size:11.5px;font-weight:400}} .sub2{{font-size:9.5px;color:var(--mut);font-weight:400}}
.b{{font-weight:700}}
header{{padding:26px 0 0;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#0d1014,#08090b)}}
.top{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap}}
.kick{{color:var(--acc);font:700 10.5px/1 'JetBrains Mono';letter-spacing:.2em;text-transform:uppercase;margin-bottom:8px}}
h1{{font:800 clamp(25px,4.6vw,36px)/1 Inter;margin:0;letter-spacing:-1px}}
.asof{{color:var(--mut);font-size:12px;text-align:right}}
.regstrip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);margin-top:20px;border-top:1px solid var(--line)}}
.rs{{background:var(--bg);padding:13px 12px 15px}}
.rs span{{font-size:9.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--mut);display:block}}
.rs b{{font-size:16px;display:block;margin:3px 0 1px;text-transform:capitalize}}
section{{padding:38px 0;border-bottom:1px solid var(--line)}}
h2{{font:700 11px/1 'JetBrains Mono';letter-spacing:.2em;text-transform:uppercase;color:var(--acc);margin:0 0 8px}}
h3{{font:600 15px/1.3 Inter;margin:0}}
.lede{{color:#9fb0c4;font-size:14.5px;line-height:1.65;max-width:88ch;margin:0 0 20px}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{text-align:left;font:600 9.5px/1.3 'JetBrains Mono';letter-spacing:.09em;text-transform:uppercase;color:var(--mut);
padding:8px 7px;border-bottom:1px solid var(--line);background:#0c0e11;white-space:nowrap;vertical-align:bottom}}
th.cur{{color:var(--warn)}}
td{{padding:8px 7px;border-bottom:1px solid rgba(35,39,46,.55)}}
tbody tr:hover{{background:var(--pan)}} .n{{text-align:right}}
.thn{{white-space:nowrap;font-size:12px;font-weight:500}}
.lbl{{font:600 11px 'JetBrains Mono';color:var(--mut)}}
.tk{{font:700 13px 'JetBrains Mono'}}
.scroll{{overflow:auto;border:1px solid var(--line);border-radius:10px}}
.cx{{text-align:center;font:600 11px 'JetBrains Mono';min-width:58px}}
.cx.faint{{opacity:.42}}
.rot{{height:120px;vertical-align:bottom;padding:0 !important}}
.rot div{{writing-mode:vertical-rl;transform:rotate(200deg);white-space:nowrap;font-size:9.5px;padding:7px 0}}
.rb,.pb{{display:inline-block;width:64px;height:6px;background:var(--pan2);border-radius:3px;margin-right:7px;vertical-align:middle}}
.rb i,.pb i{{display:block;height:100%;border-radius:3px}} .pb i{{background:linear-gradient(90deg,var(--acc),var(--dn))}}
.mgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(258px,1fr));gap:11px}}
.mc{{background:var(--pan);border:1px solid var(--line);border-radius:11px;padding:13px}}
.mch{{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}}
.mch b{{font-size:13.5px}} .mv{{font-size:17px;font-weight:700;white-space:nowrap}}
.msp{{margin:8px 0 6px}} .spk{{width:100%;height:32px;display:block}}
.mrow{{display:grid;grid-template-columns:repeat(4,auto);gap:4px 8px;font-size:11px;align-items:center}}
.mrow span{{font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}}
.mpc{{margin-top:9px;padding-top:8px;border-top:1px solid var(--line)}}
.pcb{{position:relative;height:4px;background:linear-gradient(90deg,#1d3a5c,#2f5f8f);border-radius:2px;margin-bottom:5px}}
.pcb i{{position:absolute;top:-3px;width:2px;height:10px;background:#fff;border-radius:1px}}
.cols2{{display:grid;grid-template-columns:1.15fr .85fr;gap:26px}}
.cols3{{display:grid;grid-template-columns:1fr 1fr;gap:26px}}
#curve,#rollc,#rollr{{height:300px;width:100%}}
.tmap{{background:var(--pan);border:1px solid var(--line);border-radius:12px;padding:15px;margin-bottom:13px}}
.tmh{{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:12px}}
.lrow{{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(180px,1fr);gap:9px;overflow-x:auto;padding-bottom:6px}}
.lcol{{background:var(--pan2);border:1px solid var(--line);border-radius:9px;padding:10px;min-width:180px}}
.lch{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:8px}}
.lch b{{font-size:11.5px;line-height:1.3}}
.li{{font:700 9px 'JetBrains Mono';background:#22262d;color:var(--mut);padding:2px 5px;border-radius:3px}}
.chips{{display:flex;flex-wrap:wrap;gap:4px;min-height:26px}}
.cp{{font:600 10px 'JetBrains Mono';padding:3px 5px;border-radius:3px;white-space:nowrap}}
.cp.pub{{background:rgba(91,156,255,.2);color:#a9cbff;border:1px solid rgba(91,156,255,.35)}}
.cp.pub.ss{{border-color:var(--warn);color:#ffd489}}
.cp.prv{{background:transparent;color:#8fa0b5;border:1px dashed #3a424e}}
.cp.emp{{color:#3a424e;border:none}}
.lcount{{margin-top:7px;font-size:9.5px}}
.gobs{{margin-top:6px;font-size:10px;color:#9fb0c4;line-height:1.4;border-top:1px solid var(--line);padding-top:6px}}
.gflag{{font:700 8px 'JetBrains Mono';letter-spacing:.06em;text-transform:uppercase;padding:2px 4px;border-radius:3px}}
.gflag.priv{{background:rgba(255,176,32,.16);color:var(--warn)}}
.gflag.inc{{background:rgba(0,200,5,.14);color:var(--up)}}
.gflag.none{{background:rgba(125,138,156,.14);color:var(--mut)}}
code{{font:600 9.5px 'JetBrains Mono';background:rgba(91,156,255,.13);color:var(--acc);padding:2px 4px;border-radius:3px;margin-right:3px}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;font-size:11px;color:var(--mut);margin-bottom:14px;align-items:center}}
.note{{font-size:12px;color:var(--mut);line-height:1.65}} .note b{{color:var(--tx)}}
.callout{{background:rgba(91,156,255,.07);border:1px solid rgba(91,156,255,.28);border-radius:10px;padding:15px 17px;margin:16px 0;font-size:13px;color:#c3d4e8;line-height:1.65}}
.callout b{{color:#fff}}
.warnbox{{background:rgba(255,176,32,.06);border:1px solid rgba(255,176,32,.26);border-radius:10px;padding:14px 16px;margin:16px 0;font-size:12.5px;color:#e8cfa4;line-height:1.6}}
.warnbox b{{color:var(--warn)}}
footer{{padding:26px 0;color:var(--mut);font-size:11.5px}}
@media(max-width:900px){{.cols2,.cols3{{grid-template-columns:1fr}}th,td{{padding:7px 5px;font-size:11.5px}}}}
</style></head><body>
<header><div class="wrap">
<div class="top"><div><div class="kick">Macro &amp; Market Structure</div><h1>Ten Themes — Map Room</h1></div>
<div class="asof">Market data <b class="mono" style="color:#fff">{asof}</b><br>Yield curve: US Treasury · Factors: 1y daily<br>Descriptive view — no trade conclusions<br><a href="/" style="color:#5b9cff">← Desk</a> · <a href="/backtest" style="color:#5b9cff">Backtest →</a></div></div>
<div class="regstrip">{reg_strip}</div></div></header>

<section><div class="wrap"><h2>1 · Macro Scorecard</h2>
<p class="lede">Level, trailing changes, and position within the one-year range for each market-based macro indicator. The marker on the range bar shows where today sits between the 1-year low and high.</p>
<div class="mgrid">{macro_cards}</div>
<div class="cols2" style="margin-top:26px">
<div><h3>Treasury curve</h3><p class="lede" style="margin:8px 0 12px">Current par yields against one month and one year ago. 2s10s at {n(R.get('s2s10'),2,'','%')}, 10-year {n(R.get('chg_1m_bp'),0,'',' bp')} over the past month and sitting at the {ordn(R.get('y10_pctile_1y'))} percentile of its 1-year range.</p>
<div class="scroll"><table><thead><tr><th>Tenor</th><th class="n">Now</th><th class="n">1M ago</th><th class="n">Δ bp</th><th class="n">1Y ago</th></tr></thead><tbody>{curve_rows}</tbody></table></div></div>
<div><h3>Curve shape</h3><div id="curve"></div></div>
</div></div></section>

<section><div class="wrap"><h2>2 · Macro Factor Sensitivity</h2>
<p class="lede">Univariate regression of each theme's equal-weighted daily returns on each factor, over the trailing year. Cells show <b>beta</b> with <b>R²</b> beneath. Rates and curve betas are expressed as percent move per 10 basis points; the rest are per 1% move in the factor. Cells are dimmed where |t| &lt; 2, meaning the relationship is not statistically distinguishable from noise.</p>
<div class="scroll"><table><thead><tr><th>Theme</th>{fhead}<th class="n">Top macro<div class="sub2">excl. mkt</div></th><th class="n">Ex-beta<div class="sub2">residual</div></th></tr></thead><tbody>{fx_rows}</tbody></table></div>
<div class="callout"><b>How to read this, and the honest caveat.</b> VIX and the S&amp;P are the market factor in two costumes — VIX "wins" any naive horse race simply because equities fall when volatility rises, which is why both are excluded from the "Top macro" column and reported separately below. Copper is the strongest genuine macro driver across most themes, consistent with these being industrial-buildout trades. But note the magnitudes: the best true-macro R² across all ten themes is <b>{max_macro:.2f}</b>, against a market-factor R² reaching <b>{max_mkt:.2f}</b>. Strip market beta out and the strongest residual macro relationship falls to <b>{max_resid:.3f}</b>. On this year of data these themes are overwhelmingly beta stories, not macro stories.</div>
<h3 style="margin-top:26px">Market factor versus macro — variance explained</h3>
<p class="lede" style="margin:8px 0 12px">Side by side: how much of each theme's daily variance the market explains, versus its best macro factor, versus its best macro factor after market beta is removed.</p>
<div class="scroll"><table><thead><tr><th>Theme</th><th class="n">S&amp;P beta</th><th class="n">Market R²</th><th class="n">Best macro R²</th><th class="n">Residual macro R²</th></tr></thead><tbody>{mkt_vs_macro}</tbody></table></div>
</div></section>

<section><div class="wrap"><h2>3 · Rolling Correlation</h2>
<p class="lede">Sixty-day rolling correlation of each theme against copper and against the 10-year yield. Regime shifts appear here as lines crossing zero or converging — a theme whose correlation is unstable is one where the macro relationship is not durable.</p>
<div class="cols3">
<div><h3>vs Copper</h3><div id="rollc"></div></div>
<div><h3>vs 10y yield change</h3><div id="rollr"></div></div>
</div></div></section>

<section><div class="wrap"><h2>4 · Regime Lens</h2>
<p class="lede">Trailing-year days bucketed by rate direction and dollar direction over the preceding month, showing each theme's annualised average return within each bucket. The current regime is <b>{e(CUR)}</b>, highlighted below.</p>
<div class="scroll"><table><thead><tr><th>Theme</th>{rhead}</tr></thead><tbody>{reg_rows}</tbody></table></div>
<div class="warnbox"><b>Small-sample warning.</b> This is one year of history sliced into buckets. The current regime bucket contains only <b>{RP.get(CUR,{}).get('days','—')} days</b>, and annualising a handful of daily observations produces large, unstable numbers. Read the sign and the relative ordering, not the magnitudes. Buckets with fewer than 15 days are omitted entirely.</div>
</div></section>

<section><div class="wrap"><h2>5 · Sector Reality Check</h2>
<p class="lede">What GICS sector each theme is actually made of. The right-hand column is concentration — the share of the basket sitting in its single largest sector.</p>
<div class="scroll"><table><thead><tr><th>Theme</th>{shead}<th class="n">Top sector share</th></tr></thead><tbody>{sec_rows}</tbody></table></div>
<div class="callout"><b>Three themes are single-sector.</b> AI Compute &amp; Semiconductors, Cybersecurity, and Biotech &amp; AI Drug Discovery are each 100% one GICS sector — they are sector exposures with thematic labels, and will behave like the sector regardless of the narrative. At the other end, Energy Storage &amp; Critical Minerals spans five sectors with only 29% in its largest, which is why it behaves least like a single coherent bet.</div>
<h3 style="margin-top:26px">Relative strength versus benchmarks</h3>
<p class="lede" style="margin:8px 0 12px">Theme return minus benchmark return. The sector column asks whether the theme beat its GICS sector; the thematic column asks whether it beat the closest thematic ETF. Positive on both is where thematic selection added something beyond simply owning the sector.</p>
<div class="scroll"><table><thead><tr><th>Theme</th><th>Sector</th><th class="n">1M</th><th class="n">3M</th><th class="n">1Y</th><th>Thematic</th><th class="n">1M</th><th class="n">3M</th><th class="n">1Y</th></tr></thead><tbody>{rs_rows}</tbody></table></div>
</div></section>

<section><div class="wrap"><h2>6 · Market Maps — Value Chain by Theme</h2>
<p class="lede">All 72 public tickers and 74 private companies placed in the layer where their centre of gravity sits, ordered upstream to downstream. Hover any chip for the placement rationale.</p>
<div class="legend">
<span><span class="cp pub">TICKER</span> public</span>
<span><span class="cp pub ss">TICKER</span> spans 3+ layers</span>
<span><span class="cp prv">Private Co</span> private</span>
<span><span class="gflag priv">private only</span> no public pure play</span>
<span><span class="gflag inc">no private rival</span> incumbent-held</span>
</div>
{market_maps}
</div></section>

<section><div class="wrap"><h2>7 · Competitive Pressure</h2>
<p class="lede">The public-versus-private relationships in the dataset, counted. These same relationships drive the moat factor in the ratings model — shown here as structure rather than a score.</p>
<div class="cols3">
<div><h3>Public names facing the most private challengers</h3>
<div class="scroll" style="max-height:520px;margin-top:11px"><table><thead><tr><th>Ticker</th><th>Theme</th><th class="n">Rivals</th><th>Named challengers</th><th class="n">Moat</th></tr></thead><tbody>{press_rows}</tbody></table></div></div>
<div><h3>Private companies pressuring the most public names</h3>
<div class="scroll" style="max-height:520px;margin-top:11px"><table><thead><tr><th>Company</th><th class="n">Valuation</th><th class="n">Targets</th><th>Tickers</th><th></th></tr></thead><tbody>{threat_rows}</tbody></table></div></div>
</div></div></section>

<section><div class="wrap"><h2>8 · Breadth &amp; Dispersion</h2>
<p class="lede">Share of each theme's constituents trading above their 50- and 200-day averages, with return dispersion. Low dispersion means the theme moves as one bet; high dispersion means constituent selection matters more than the theme call.</p>
<div class="scroll"><table><thead><tr><th>Theme</th><th class="n">&gt;50d</th><th class="n">&gt;200d</th><th class="n">1M</th><th class="n">3M</th><th class="n">1Y</th><th class="n">Dispersion</th><th class="n">Avg beta</th><th class="n">Best 1Y</th><th class="n">Worst 1Y</th></tr></thead><tbody>{bd_rows}</tbody></table></div>
</div></section>

<section><div class="wrap"><h2>Method &amp; Limitations</h2>
<div class="cols3"><div class="note">
<p><b>Rates</b> come from the US Treasury daily par yield curve CSV, not from Yahoo's <code>^TNX</code>, which returned only 16 usable daily closes over a year. <b>Everything else</b> — volatility, credit, sector and thematic ETFs — is CBOE's delayed daily history. The Nasdaq 100, dollar, crude, gold, copper and bitcoin are shown through the ETFs that track them (QQQ, UUP, USO, GLD, CPER, IBIT), so levels are ETF prices and changes track the underlying net of fees. Credit appetite is the HYG/LQD price ratio, a proxy for the high-yield spread rather than the spread itself.</p>
<p><b>Factor betas</b> are univariate ordinary least squares on daily returns over the trailing year. Univariate rather than multivariate on purpose: with nine correlated factors and roughly 250 observations, multivariate coefficients are unstable and hard to interpret. The trade-off is that univariate betas do not separate overlapping factors — a copper beta partly reflects the market beta riding underneath it, which is exactly why the residual column exists.</p>
<p><b>Residual exposure</b> regresses theme returns on the S&amp;P first, then regresses the residuals on each macro factor. That isolates macro sensitivity that is not simply high beta.</p>
</div><div class="note">
<p><b>These are descriptive, not predictive.</b> A beta measured over one year describes what happened; it does not forecast. Correlations over a single year are unstable, which is what the rolling chart is for. R² is shown on every cell so weak relationships read as weak instead of being quietly presented as signal, and cells where |t| &lt; 2 are dimmed.</p>
<p><b>Regime analysis is a small sample.</b> One year sliced into direction buckets leaves tens of days per bucket. Signs and ordering are informative; magnitudes are not.</p>
<p><b>GICS classification</b> is Yahoo's, which occasionally differs from S&amp;P's official assignment. <b>Value-chain layers</b> are an editorial taxonomy — a company's centre of gravity is a judgment call, and the <code>spans 3+ layers</code> flag marks vertical integrators whose single-layer placement understates their reach.</p>
<p><b>Hard macro is absent.</b> CPI, payrolls, and ISM are not reachable from this environment. Everything here is market-priced and daily, which suits correlating against daily equity returns but omits the official economic series entirely.</p>
<p><b>Nothing here is investment advice.</b> This page states relationships and leaves the conclusions to the reader by design.</p>
</div></div></div></section>

<footer><div class="wrap">Ten Themes Map Room · 10 themes · 72 public · 74 private · {len(LAY['layer_gaps'])} structural observations · data as of {asof}</div></footer>
<script>
const CV={json.dumps(curve_chart)}, RC={json.dumps(roll_series)}, RR={json.dumps(roll_rates)};
const PAL=["#5b9cff","#00c805","#ffb020","#c77dff","#ff5000","#00d9c0","#ff8ac4","#a3e635","#f59e0b","#94a3b8"];
const AX={{axisLine:{{lineStyle:{{color:'#23272e'}}}},axisLabel:{{color:'#7d8a9c',fontSize:10}},splitLine:{{lineStyle:{{color:'#16191d'}}}}}};
const cv=echarts.init(document.getElementById('curve'));
cv.setOption({{grid:{{left:46,right:18,top:34,bottom:30}},legend:{{textStyle:{{color:'#7d8a9c',fontSize:10}},top:0}},
 tooltip:{{trigger:'axis',valueFormatter:v=>v==null?'—':v.toFixed(2)+'%'}},
 xAxis:{{type:'category',data:CV.labels,...AX}},yAxis:{{type:'value',...AX,axisLabel:{{color:'#7d8a9c',fontSize:10,formatter:'{{value}}%'}},scale:true}},
 series:[{{name:'Now',type:'line',data:CV.now,smooth:true,symbolSize:6,lineStyle:{{width:2.4,color:'#5b9cff'}},itemStyle:{{color:'#5b9cff'}}}},
   {{name:'1M ago',type:'line',data:CV.m1,smooth:true,symbolSize:4,lineStyle:{{width:1.4,color:'#7d8a9c',type:'dashed'}},itemStyle:{{color:'#7d8a9c'}}}},
   {{name:'1Y ago',type:'line',data:CV.y1,smooth:true,symbolSize:4,lineStyle:{{width:1.4,color:'#3a424e',type:'dotted'}},itemStyle:{{color:'#3a424e'}}}}]}});
function rollChart(id,data){{
 const c=echarts.init(document.getElementById(id));
 c.setOption({{grid:{{left:40,right:14,top:12,bottom:56}},
  tooltip:{{trigger:'axis',valueFormatter:v=>v==null?'—':v.toFixed(2)}},
  legend:{{type:'scroll',bottom:0,textStyle:{{color:'#7d8a9c',fontSize:9}},itemWidth:9,itemHeight:9}},
  xAxis:{{type:'category',data:(data[0]||{{dates:[]}}).dates,...AX,axisLabel:{{color:'#7d8a9c',fontSize:9,interval:35}}}},
  yAxis:{{type:'value',min:-1,max:1,...AX}},
  series:data.map((s,i)=>({{name:s.name.length>26?s.name.slice(0,24)+'…':s.name,type:'line',data:s.vals,
    smooth:true,symbol:'none',lineStyle:{{width:1.5,color:PAL[i%PAL.length]}},itemStyle:{{color:PAL[i%PAL.length]}}}}))
   .concat([{{type:'line',data:(data[0]||{{vals:[]}}).vals.map(()=>0),symbol:'none',silent:true,
     lineStyle:{{width:1,color:'#3a424e',type:'dashed'}},tooltip:{{show:false}},legendHoverLink:false,name:'zero'}}])}});
 window.addEventListener('resize',()=>c.resize());
}}
rollChart('rollc',RC); rollChart('rollr',RR);
window.addEventListener('resize',()=>cv.resize());
</script></body></html>"""
open("map.html", "w").write(HTML)
print("wrote map.html", len(HTML), "bytes | layers", len(LAY["public"]) + len(LAY["private"]),
      "| gaps", len(LAY["layer_gaps"]), "| series", len(S))
