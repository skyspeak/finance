# -*- coding: utf-8 -*-
import json, html, collections
D = json.load(open("data.json"))
rows, themes, privates, activists = D["rows"], D["themes"], D["privates"], D["activists"]
asof = D["asof"]
by_t = {r["ticker"]: r for r in rows}
picks   = [r for r in rows if r["rating"]=="PICK"]
avoids  = [r for r in rows if r["rating"]=="AVOID"]
neutral = [r for r in rows if r["rating"]=="NEUTRAL"]
e = lambda s: html.escape(str(s if s is not None else ""))
def num(v, d=2, suf="", pre=""):
    return "—" if v is None else f"{pre}{v:,.{d}f}{suf}"
def sgn(v):
    if v is None: return '<span class="mut">—</span>'
    c = "up" if v > 0 else ("dn" if v < 0 else "mut")
    return f'<span class="{c}">{v:+.1f}%</span>'

STRATEGY = """
The portfolio this week is built on one asymmetry: **the market is paying up for AI narrative and paying down for AI infrastructure.**
Nine of the fourteen PICKs sit in compute and power — the two layers where demand is contracted, capacity is physically constrained, and
private-market competition is least able to disintermediate an incumbent. Every AVOID sits in a layer where software margins are exposed to
either agentic substitution (cybersecurity, application SaaS) or a rails change the incumbent does not control (card networks vs. stablecoins).

**Core longs (55–65%).** Anchor in the toll-collectors: TSM, AVGO, MU, NVDA. This sleeve is deliberately unclever. Foundry and
custom-silicon economics are the part of the AI trade with contracted visibility rather than projected TAM, and consensus still carries
double-digit upside to mean targets on all four. Memory (MU) is the highest-torque member and the one most likely to be trimmed first.

**The contrarian sleeve (15–20%) is where the actual edge is.** Power is the only theme scoring near the top while trading *down* on the
year — VST is 27% lower over twelve months and TLN is negative, against a demand curve that has not bent. That combination, a top-quartile
composite paired with a negative one-year print, is the single most interesting setup in the dataset. ETN is the lower-beta way to hold it.
Size this sleeve to survive being early, because being early is the base case.

**Tactical / high-beta (10–15%).** KTOS and CRCL earn small positions on genuine momentum, not on valuation. Cap each at roughly a third of a
core position and treat the analyst target as a exit reference rather than a destination.

**Underweights and funding sources.** Cybersecurity is the lowest-ranked theme in the book and the most crowded consensus long — three AVOIDs
(PANW, FTNT, S) against a private challenger set (XBOW and peers) attacking exactly the human-labor line item that justifies the multiple.
PYPL and C3.ai are the two clearest structural shorts-or-avoids: one is losing the rails argument, the other is the only Sell-rated consensus
name in the universe. Fund the contrarian power sleeve from here, not from cash.

**What would break this.** A genuine slowdown in hyperscaler capex guidance breaks the core and the contrarian sleeve simultaneously — they
are the same bet expressed at two layers, and that correlation is the portfolio's main structural risk. Watch three things over the next
quarter: hyperscaler capex language on Q3 calls, PJM and ERCOT capacity auction prints for the power thesis, and whether any of the tracked
private challengers (OpenAI silicon, Anthropic, XBOW, Cerebras) converts funding into disclosed enterprise revenue.
"""

def md(t):
    t = e(t).replace("**", "\x00")
    out, b = [], False
    for part in t.split("\x00"):
        out.append(part if not b else f"<b>{part}</b>"); b = not b
    return "".join(out)

# ---------- theme rows
theme_rows = "".join(f"""<tr>
<td class="rk">{i+1}</td><td class="th"><b>{e(t['theme'])}</b><div class="sub">{e(t['thesis'])}</div></td>
<td class="n"><div class="bar"><i style="width:{t['score']/5*100:.0f}%"></i></div><span class="mono">{t['score']:.2f}</span></td>
<td class="n mono">{t['secular']:.1f}</td><td class="n">{sgn(t['med_1y'])}</td>
<td class="n mono">{len(t['tickers'])}</td><td class="n mono">{t['n_private']}</td>
<td class="n"><span class="pill pk">{len(t['picks'])}</span> <span class="pill av">{len(t['avoids'])}</span></td>
</tr>""" for i, t in enumerate(themes))

# ---------- universe rows
def urow(r):
    acts = " · ".join(f"{a.get('firm','')} {a.get('action','')} {a.get('to','')}" for a in (r["recent_actions"] or [])[:2])
    return f"""<tr data-theme="{e(r['theme'])}" data-rating="{r['rating']}">
<td class="tk"><b>{e(r['ticker'])}</b><div class="sub">{e((r.get('name') or '')[:34])}</div></td>
<td class="sub">{e(r['theme'])}</td>
<td><span class="tag {r['rating'].lower()}">{r['rating']}</span></td>
<td class="n mono b">{r['composite']:.2f}</td>
<td class="n mono">{num(r.get('last'),2,'','$')}</td>
<td class="n">{sgn(r.get('chg_1w'))}</td><td class="n">{sgn(r.get('chg_3m'))}</td><td class="n">{sgn(r.get('chg_1y'))}</td>
<td class="n mono sub">{num(r.get('wk52_low'),0,'','$')} – {num(r.get('wk52_high'),0,'','$')}</td>
<td class="n">{sgn(r.get('pct_off_high'))}</td>
<td class="n sub">{e(r.get('consensus') or '—')}<div class="mono">{num(r.get('pt_mean'),0,'','$')}</div></td>
<td class="n sub">{e(r.get('insider_signal') or '—')}<div class="mono">{r.get('n_form4') or 0} F4</div></td>
<td class="n sub">{e((r.get('hf') or {}).get('net_signal') or 'no data')}</td>
<td class="n mono">{len(r['privates'])}</td>
<td class="sub xs">{e(acts) or '—'}</td></tr>"""
universe_rows = "".join(urow(r) for r in rows)

# ---------- pick cards
def card(r):
    return f"""<div class="card {r['rating'].lower()}">
<div class="ch"><div><span class="ct">{e(r['ticker'])}</span><span class="tag {r['rating'].lower()}">{r['rating']}</span></div>
<div class="cs mono">{r['composite']:.2f}</div></div>
<div class="cn">{e(r.get('name'))}</div><div class="cth">{e(r['theme'])}</div>
<div class="fac">
{''.join(f'<div class="f"><span>{n}</span><div class="fb"><i style="width:{v/5*100:.0f}%"></i></div><em>{v:.1f}</em></div>' for n,v in [("Secular",r["sc_secular"]),("Moat",r["sc_moat"]),("Value",r["sc_valuation"]),("Flow",r["sc_smart"]),("Analyst",r["sc_analyst"])])}
</div>
<ul class="ev">
<li><b>Price</b> {num(r.get('last'),2,'','$')} · {sgn(r.get('chg_1y'))} 1Y · {sgn(r.get('pct_off_high'))} off high</li>
<li><b>Analysts</b> {e(r['n_analyst'])} · {e(r['n_valuation'])}</li>
<li><b>Flow</b> {e(r['n_smart'])}</li>
<li><b>Private threat</b> {e(', '.join(r['privates'][:4]) or 'none tracked')}</li>
</ul></div>"""
pick_cards  = "".join(card(r) for r in picks)
avoid_cards = "".join(card(r) for r in avoids)

# ---------- privates
pv_by_theme = collections.defaultdict(list)
for p in privates: pv_by_theme[p["theme"]].append(p)
def pcard(p):
    val = f"${p['valuation']:,.1f}B" if isinstance(p.get("valuation"), (int, float)) else "undisclosed"
    ipo = '<span class="ipo">IPO WATCH</span>' if p.get("ipo_watch") else ""
    src = f'<a href="{e(p["source_url"])}" target="_blank" rel="noopener noreferrer">source</a>' if p.get("source_url") else ""
    return f"""<div class="pv"><div class="pvh"><b>{e(p['name'])}</b>{ipo}</div>
<div class="pvv mono">{val}<span class="sub"> · {e(p.get('stage') or '')}</span></div>
<div class="pvd">{e(p.get('description'))}</div>
<div class="pvm"><b>Last round</b> {e(p.get('last_round') or '—')} · <b>Backers</b> {e(', '.join((p.get('key_backers') or [])[:3]))}</div>
<div class="pvt"><b>Threatens</b> {' '.join(f'<code>{e(c)}</code>' for c in (p.get('competes_with') or []))} — {e(p.get('threat'))} {src}</div></div>"""
priv_sections = "".join(
    f"""<div class="pvsec"><h3>{e(th)} <span class="sub">{len(pv_by_theme[th])} private</span></h3><div class="pvg">{''.join(pcard(p) for p in pv_by_theme[th])}</div></div>"""
    for th in [t["theme"] for t in themes] if pv_by_theme[th])

# ---------- signals
act_rows = "".join(f"""<tr><td class="tk"><b>{e(a['ticker'])}</b></td><td>{e(a.get('filer_name'))}</td>
<td class="sub mono">{e(a.get('form_type'))}</td><td class="mono sub">{e(a.get('filing_date'))}</td>
<td class="sub">{e(a.get('activist_agenda'))}</td>
<td><a href="{e(a.get('accession_url'))}" target="_blank" rel="noopener noreferrer">filing</a></td></tr>"""
 for a in sorted(activists, key=lambda x: x.get("filing_date") or "", reverse=True))

ins = sorted([r for r in rows if r.get("insider_signal") == "heavy selling"], key=lambda r: -(r.get("n_form4") or 0))
ins_rows = "".join(f"""<tr><td class="tk"><b>{e(r['ticker'])}</b></td><td class="sub">{e(r['theme'])}</td>
<td class="mono n">{r.get('n_form4') or 0}</td>
<td class="sub">{e('; '.join(f"{x.get('insider','')} ({x.get('date','')})" for x in (r['insider_notable'] or [])[:2]))}</td>
<td><span class="tag {r['rating'].lower()}">{r['rating']}</span></td></tr>""" for r in ins)

hf_moves = [m for r in rows for m in r["hf_moves"]]
hf_rows = "".join(f"""<tr><td>{e(m.get('fund'))}</td><td class="tk"><b>{e(m.get('ticker'))}</b></td>
<td><span class="tag {'pick' if 'new' in str(m.get('action','')).lower() or 'add' in str(m.get('action','')).lower() else 'avoid' if 'exit' in str(m.get('action','')).lower() or 'trim' in str(m.get('action','')).lower() else 'neutral'}">{e(m.get('action'))}</span></td>
<td class="mono sub">{e(m.get('size') or m.get('pct_of_portfolio') or '—')}</td>
<td>{f'<a href="{e(m.get("source_url"))}" target="_blank" rel="noopener noreferrer">source</a>' if m.get('source_url') else ''}</td></tr>"""
 for m in hf_moves[:60])

scatter = [{"value": [r.get("chg_1y") or 0, r["composite"], (r.get("pt_mean") or 0)], "name": r["ticker"], "rating": r["rating"]} for r in rows if r.get("chg_1y") is not None]

HTML = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ten Themes — Weekly Investment Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Serif:wght@600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
:root{{--ink:#0b1220;--mut:#5b6b82;--line:#dfe6ef;--bg:#fff;--pan:#f6f9fc;--blue:#0b5cd5;--dk:#08183a;--up:#0a7d4f;--dn:#c62828;--am:#b26a00}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 'IBM Plex Sans',system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1500px;margin:0 auto;padding:0 6%}}
.mono{{font-family:'IBM Plex Mono',monospace;font-variant-numeric:tabular-nums}}
.sub{{color:var(--mut);font-size:12px;font-weight:400}} .xs{{font-size:11px}} .mut{{color:var(--mut)}}
.up{{color:var(--up);font-weight:600}} .dn{{color:var(--dn);font-weight:600}} .b{{font-weight:700}}
header{{background:var(--dk);color:#fff;padding:34px 0 0}}
header .wrap{{padding-bottom:0}}
.brand{{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1px solid rgba(255,255,255,.15);padding-bottom:14px;flex-wrap:wrap;gap:12px}}
h1{{font:700 30px/1.1 'IBM Plex Serif',serif;margin:0;letter-spacing:-.4px}}
.kick{{color:#7fb0ff;font:600 11px/1 'IBM Plex Mono';letter-spacing:.18em;text-transform:uppercase;margin-bottom:9px}}
.meta{{color:#9fb6d4;font-size:12px;text-align:right}}
.stats{{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:rgba(255,255,255,.13);margin-top:0}}
.stat{{background:var(--dk);padding:16px 4px 20px}}
.stat b{{display:block;font:600 26px/1 'IBM Plex Mono';color:#fff}}
.stat span{{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:#8fa9c9}}
section{{padding:46px 0;border-bottom:1px solid var(--line)}}
h2{{font:700 12px/1 'IBM Plex Mono';letter-spacing:.2em;text-transform:uppercase;color:var(--blue);margin:0 0 6px}}
.lede{{font:400 17px/1.6 'IBM Plex Sans';color:#33455c;max-width:74ch;margin:0 0 26px}}
h3{{font:600 16px/1.3 'IBM Plex Sans';margin:26px 0 12px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;font:600 10.5px/1.3 'IBM Plex Mono';letter-spacing:.09em;text-transform:uppercase;color:var(--mut);
border-bottom:1.5px solid var(--ink);padding:8px 8px;position:sticky;top:0;background:#fff;z-index:2;cursor:pointer;white-space:nowrap}}
td{{padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
tbody tr:hover{{background:var(--pan)}}
.n{{text-align:right}} .rk{{color:var(--mut);font:600 12px 'IBM Plex Mono'}}
.tk b{{font:600 13px 'IBM Plex Mono'}}
.bar{{display:inline-block;width:64px;height:7px;background:#e6edf6;vertical-align:middle;margin-right:7px;border-radius:1px}}
.bar i{{display:block;height:100%;background:var(--blue);border-radius:1px}}
.tag{{display:inline-block;font:600 9.5px/1 'IBM Plex Mono';letter-spacing:.09em;padding:4px 6px;border-radius:2px}}
.pick{{background:#e3f3ea;color:var(--up)}} .avoid{{background:#fdeaea;color:var(--dn)}} .neutral{{background:#eef1f5;color:var(--mut)}}
.pill{{display:inline-block;min-width:20px;text-align:center;font:600 11px 'IBM Plex Mono';padding:2px 5px;border-radius:2px}}
.pk{{background:#e3f3ea;color:var(--up)}} .av{{background:#fdeaea;color:var(--dn)}}
.scroll{{max-height:760px;overflow:auto;border:1px solid var(--line)}}
.ctrl{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}}
.ctrl button{{font:600 11px 'IBM Plex Mono';letter-spacing:.05em;padding:7px 11px;border:1px solid var(--line);background:#fff;cursor:pointer;border-radius:2px;color:var(--mut)}}
.ctrl button.on{{background:var(--dk);color:#fff;border-color:var(--dk)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px}}
.card{{border:1px solid var(--line);border-top:3px solid var(--mut);padding:15px;background:#fff}}
.card.pick{{border-top-color:var(--up);background:#fff}} .card.avoid{{border-top-color:var(--dn)}}
.ch{{display:flex;justify-content:space-between;align-items:center}}
.ct{{font:700 19px 'IBM Plex Mono';margin-right:8px}} .cs{{font:600 19px 'IBM Plex Mono';color:var(--blue)}}
.cn{{font-size:13px;font-weight:600;margin-top:4px}} .cth{{font-size:11px;color:var(--mut);margin-bottom:11px}}
.fac{{display:grid;gap:3px;margin-bottom:11px;padding:10px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}}
.f{{display:grid;grid-template-columns:52px 1fr 26px;align-items:center;gap:7px;font-size:10px;color:var(--mut)}}
.fb{{height:5px;background:#e6edf6}} .fb i{{display:block;height:100%;background:var(--blue)}}
.f em{{font:600 10px 'IBM Plex Mono';font-style:normal;color:var(--ink);text-align:right}}
.ev{{list-style:none;padding:0;margin:0;font-size:11.5px;line-height:1.55;color:#3c4c62}}
.ev li{{padding:3px 0;border-bottom:1px dotted var(--line)}} .ev b{{color:var(--ink);font-size:10px;text-transform:uppercase;letter-spacing:.05em}}
.strat{{background:var(--pan);border-left:3px solid var(--blue);padding:26px 30px;font-size:15.5px;line-height:1.72;color:#26374d}}
.strat p{{margin:0 0 15px;max-width:88ch}} .strat p:last-child{{margin:0}}
.pvsec{{margin-bottom:30px}}
.pvg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}}
.pv{{border:1px solid var(--line);padding:13px;background:var(--pan);font-size:12px}}
.pvh{{display:flex;justify-content:space-between;align-items:center;gap:8px}} .pvh b{{font-size:14px}}
.ipo{{font:600 8.5px 'IBM Plex Mono';letter-spacing:.09em;background:var(--am);color:#fff;padding:3px 5px;border-radius:2px}}
.pvv{{font-size:15px;font-weight:600;color:var(--blue);margin:3px 0 7px}}
.pvd{{color:#3c4c62;margin-bottom:7px;line-height:1.5}}
.pvm{{font-size:11px;color:var(--mut);padding-top:7px;border-top:1px solid var(--line)}}
.pvt{{font-size:11px;color:#3c4c62;margin-top:6px;line-height:1.5}}
.pvt code{{font:600 10px 'IBM Plex Mono';background:#e3ebf6;color:var(--blue);padding:1px 4px;border-radius:2px}}
a{{color:var(--blue)}} .pvm b,.pvt b{{color:var(--ink);font-size:9.5px;text-transform:uppercase;letter-spacing:.05em}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:34px}}
.note{{font-size:12.5px;color:var(--mut);line-height:1.65;max-width:92ch}}
.note b{{color:var(--ink)}}
footer{{background:var(--dk);color:#8fa9c9;padding:30px 0;font-size:11.5px}}
#sc{{height:430px;width:100%}}
@media(max-width:900px){{.stats{{grid-template-columns:repeat(3,1fr)}}.cols{{grid-template-columns:1fr}}h1{{font-size:23px}}}}
</style></head><body>
<header><div class="wrap">
<div class="brand"><div><div class="kick">Weekly Thematic Intelligence</div><h1>Ten Themes</h1></div>
<div class="meta">Market data as of <b style="color:#fff">{asof}</b><br>13F period Q2 2026 · Form 4 trailing 90d<br>Generated 2026-08-16</div></div>
<div class="stats">
<div class="stat"><b>10</b><span>Themes</span></div>
<div class="stat"><b>{len(rows)}</b><span>Public names</span></div>
<div class="stat"><b>{len(privates)}</b><span>Private rivals</span></div>
<div class="stat"><b style="color:#5fd39a">{len(picks)}</b><span>Picks</span></div>
<div class="stat"><b>{len(neutral)}</b><span>Neutral</span></div>
<div class="stat"><b style="color:#ff8a8a">{len(avoids)}</b><span>Avoid</span></div>
</div></div></header>

<section><div class="wrap"><h2>The Strategy</h2>
<div class="strat">{''.join(f'<p>{md(p.strip())}</p>' for p in STRATEGY.strip().split(chr(10)+chr(10)))}</div>
</div></section>

<section><div class="wrap"><h2>Theme Ranking</h2>
<p class="lede">Themes ranked by the mean composite score of their constituents. Secular is the standalone conviction in the demand curve; the composite blends it with moat, valuation, smart-money flow and analyst momentum across every name in the basket.</p>
<table><thead><tr><th>#</th><th>Theme &amp; thesis</th><th class="n">Composite</th><th class="n">Secular</th><th class="n">Median 1Y</th><th class="n">Public</th><th class="n">Private</th><th class="n">P / A</th></tr></thead>
<tbody>{theme_rows}</tbody></table></div></section>

<section><div class="wrap"><h2>Valuation vs. Conviction</h2>
<p class="lede">Each name plotted by trailing one-year price change against its composite score. The upper-left quadrant — high conviction, negative one-year performance — is where the contrarian sleeve lives.</p>
<div id="sc"></div></div></section>

<section><div class="wrap"><h2>The Picks — {len(picks)} names</h2>
<p class="lede">Composite of 3.70 or better. Factor bars read left to right: secular demand, moat against private disruption, valuation versus analyst target, smart-money flow, analyst momentum.</p>
<div class="grid">{pick_cards}</div></div></section>

<section><div class="wrap"><h2>The Avoids — {len(avoids)} names</h2>
<p class="lede">Composite below 3.05. These are the funding sources for the book, not necessarily outright shorts.</p>
<div class="grid">{avoid_cards}</div></div></section>

<section><div class="wrap"><h2>Full Universe — {len(rows)} names</h2>
<p class="lede">Click any column header to sort. Filter by rating below.</p>
<div class="ctrl"><button class="on" data-f="all">All {len(rows)}</button><button data-f="PICK">Picks {len(picks)}</button><button data-f="NEUTRAL">Neutral {len(neutral)}</button><button data-f="AVOID">Avoid {len(avoids)}</button></div>
<div class="scroll"><table id="uni"><thead><tr>
<th>Ticker</th><th>Theme</th><th>Rating</th><th class="n">Score</th><th class="n">Last</th><th class="n">1W</th><th class="n">3M</th><th class="n">1Y</th>
<th class="n">52w range</th><th class="n">Off high</th><th class="n">Consensus / PT</th><th class="n">Insiders</th><th class="n">13F</th><th class="n">Priv</th><th>Recent analyst actions</th>
</tr></thead><tbody>{universe_rows}</tbody></table></div></div></section>

<section><div class="wrap"><h2>Private Market Competitors — {len(privates)} companies</h2>
<p class="lede">The private side of each theme: who is funded, at what valuation, by whom, and which public names they pressure. Valuations are last disclosed post-money and are press-reported, not audited.</p>
{priv_sections}</div></section>

<section><div class="wrap"><h2>Filing Signals</h2>
<div class="cols">
<div><h3>Activist &amp; strategic 13D positions <span class="sub">{len(activists)} filers, trailing 12 months</span></h3>
<p class="note">No classic activist campaign (Elliott, Starboard, ValueAct, Jana, Trian) opened a new position in this universe in the window. What the screen surfaced instead is strategic and sponsor ownership — Cerberus at EOSE, SoftBank and Walmart at SYM, American Tower and Vodafone at ASTS.</p>
<div class="scroll" style="max-height:430px;margin-top:12px"><table><thead><tr><th>Ticker</th><th>Filer</th><th>Form</th><th>Date</th><th>Agenda</th><th></th></tr></thead><tbody>{act_rows}</tbody></table></div></div>
<div><h3>Heaviest insider selling <span class="sub">{len(ins)} names flagged</span></h3>
<p class="note">Ranked by Form 4 volume over the trailing 90 days where the signal read as heavy selling. Note that filing volume conflates open-market sales with grants and 10b5-1 exercises; the named transactions below were confirmed as open-market where the XML carried a price.</p>
<div class="scroll" style="max-height:430px;margin-top:12px"><table><thead><tr><th>Ticker</th><th>Theme</th><th class="n">Form 4s</th><th>Notable filers</th><th>Rating</th></tr></thead><tbody>{ins_rows}</tbody></table></div></div>
</div>
<h3 style="margin-top:34px">Hedge fund moves <span class="sub">Q2 2026 13F — {len(hf_moves)} documented positions</span></h3>
<p class="note">Position-level data was confirmable for only a minority of the universe. Absence of a fund here means the filing was not retrievable from free sources, not that no position exists.</p>
<div class="scroll" style="max-height:400px;margin-top:12px"><table><thead><tr><th>Fund</th><th>Ticker</th><th>Action</th><th>Size</th><th></th></tr></thead><tbody>{hf_rows}</tbody></table></div>
</div></section>

<section><div class="wrap"><h2>Method &amp; Limitations</h2>
<div class="cols"><div class="note">
<p><b>Scoring.</b> Every name is scored 1–5 on five factors and weighted into a composite: secular demand 25%, moat against private disruption 20%, valuation versus mean analyst target 20%, analyst momentum 20%, smart-money flow 15%. PICK is 3.70 and above, AVOID is below 3.05, everything between is NEUTRAL. Secular scores are assigned at theme level and are the one deliberately judgmental input; the other four are derived mechanically from the data on this page.</p>
<p><b>Prices.</b> Daily closes and 52-week ranges from Yahoo Finance's public chart endpoint, as of {asof}. Quarter-ago and year-ago prices are the last close on or before the target date. Not split- or dividend-adjusted beyond the source's own adjustment.</p>
<p><b>Analyst data.</b> Consensus ratings, mean targets and recent actions from stockanalysis.com's S&amp;P Global aggregation, one ADR (FANUY) from investing.com. Every ticker carries its source link in the table.</p>
</div><div class="note">
<p><b>Filings.</b> Form 4 and SC 13D pulled directly from SEC EDGAR. The 13D screen used quarterly crawler indexes rather than full-text search, because EDGAR's EFTS index does not cover filings after December 2024. Insider dollar values were parsed from Form 4 XML for 59 of 69 covered issuers; the remainder are volume-based signals only.</p>
<p><b>13F caveat — read this one.</b> Institutional positions are a 45-day-lagged snapshot as of 30 June 2026, cover long US equity only, and were confirmable for 27 of 71 tickers from free sources. Six funds had retrievable position-level detail. Treat the flow factor as the weakest input in the composite; it is weighted lowest for exactly that reason.</p>
<p><b>Private valuations</b> are last disclosed post-money from press reports and are frequently stale or structured with preferences that make the headline number misleading.</p>
<p><b>This is research, not investment advice.</b> No position sizing here accounts for your existing exposure, tax situation or risk tolerance.</p>
</div></div></div></section>

<footer><div class="wrap">Ten Themes · Weekly thematic intelligence · Data as of {asof} · Refreshed every Monday</div></footer>

<script>
const D={json.dumps(scatter)};
const col=r=>r==='PICK'?'#0a7d4f':r==='AVOID'?'#c62828':'#93a5bb';
const ch=echarts.init(document.getElementById('sc'));
ch.setOption({{
 grid:{{left:58,right:26,top:26,bottom:52}},
 xAxis:{{name:'1-year price change (%)',nameLocation:'middle',nameGap:32,nameTextStyle:{{fontSize:11,color:'#5b6b82'}},
  splitLine:{{lineStyle:{{color:'#eef2f7'}}}},axisLine:{{lineStyle:{{color:'#dfe6ef'}}}},axisLabel:{{fontSize:11,color:'#5b6b82'}}}},
 yAxis:{{name:'Composite score',nameLocation:'middle',nameGap:40,nameTextStyle:{{fontSize:11,color:'#5b6b82'}},min:2.2,max:4.6,
  splitLine:{{lineStyle:{{color:'#eef2f7'}}}},axisLine:{{lineStyle:{{color:'#dfe6ef'}}}},axisLabel:{{fontSize:11,color:'#5b6b82'}}}},
 tooltip:{{formatter:p=>`<b>${{p.data.name}}</b><br>1Y ${{p.value[0].toFixed(1)}}%<br>Score ${{p.value[1].toFixed(2)}}<br>${{p.data.rating}}`}},
 series:[{{type:'scatter',data:D,symbolSize:11,
   itemStyle:{{color:p=>col(p.data.rating),opacity:.85,borderColor:'#fff',borderWidth:1}},
   label:{{show:true,position:'right',formatter:p=>p.data.name,fontSize:9.5,color:'#5b6b82',fontFamily:'IBM Plex Mono'}},
   markLine:{{silent:true,symbol:'none',lineStyle:{{color:'#c8d4e3',type:'dashed'}},
     data:[{{xAxis:0}},{{yAxis:3.7}}],label:{{show:false}}}}}}]
}});
window.addEventListener('resize',()=>ch.resize());
document.querySelectorAll('.ctrl button').forEach(b=>b.onclick=()=>{{
 document.querySelectorAll('.ctrl button').forEach(x=>x.classList.remove('on'));b.classList.add('on');
 const f=b.dataset.f;
 document.querySelectorAll('#uni tbody tr').forEach(r=>r.style.display=(f==='all'||r.dataset.rating===f)?'':'none');
}});
document.querySelectorAll('#uni th').forEach((th,i)=>{{let asc=false;th.onclick=()=>{{asc=!asc;
 const tb=th.closest('table').querySelector('tbody');
 [...tb.rows].sort((a,b)=>{{
  const g=r=>{{const t=r.cells[i].innerText.replace(/[$,%+]/g,'').split('\\n')[0].trim();
   const n=parseFloat(t);return isNaN(n)?t.toLowerCase():n;}};
  const x=g(a),y=g(b);return (x>y?1:x<y?-1:0)*(asc?1:-1);}}).forEach(r=>tb.appendChild(r));}};}});
</script></body></html>"""
open("site.html","w").write(HTML)
print("wrote site.html", len(HTML), "bytes")
