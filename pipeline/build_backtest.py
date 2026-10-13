# -*- coding: utf-8 -*-
"""Backtest lab — buy-and-hold of this week's picks vs SPY."""
import mobile
import json, html

BT = json.load(open("backtest.json"))
asof = BT["asof"]
dates = BT["dates"]
e = lambda s: html.escape(str(s if s is not None else ""))

def n(v, d=1, s=""):
    return "—" if v is None else f"{v:,.{d}f}{s}"
def sg(v, d=1):
    if v is None: return '<span class="mut">—</span>'
    return f'<span class="{"up" if v>0 else "dn" if v<0 else "mut"}">{v:+.{d}f}%</span>'

# Default window 1y / model invested
S = BT["books"]["picks_model"]["stats"]["1y"] or {}
SP = BT["books"]["spy"]["stats"]["1y"] or {}

def hero_cell(label, val, pct=False, signed=False, danger=False):
    if val is None:
        inner, color = "—", "mut"
    elif signed or pct:
        inner = f"{val:+.1f}%" if signed else f"{val:.1f}%"
        color = ("dn" if danger else ("up" if val > 0 else "dn" if val < 0 else "mut")) if signed or danger else ""
    else:
        inner = f"{val:.2f}"
        color = ""
    return f'<div class="hs"><b class="mono {color}">{inner}</b><span>{label}</span></div>'

hero = "".join([
    hero_cell("Total", S.get("total"), signed=True),
    hero_cell("SPY", S.get("spy"), signed=True),
    hero_cell("Excess vs SPY", S.get("excess"), signed=True),
    hero_cell("CAGR", S.get("cagr"), signed=True),
    hero_cell("Vol", S.get("vol"), pct=True),
    hero_cell("Sharpe", S.get("sharpe")),
    hero_cell("Max DD", S.get("mdd"), pct=True, danger=True),
    hero_cell("Beta", S.get("beta")),
])

def stget(r, win, k):
    return ((r.get("stats") or {}).get(win) or {}).get(k)

def nrow(r, win="1y"):
    stt = (r.get("stats") or {}).get(win) or {}
    w = r.get("weight")
    sl = r.get("sleeve") or ""
    return f"""<tr data-t="{e(r['ticker'])}">
<td class="tk">{e(r['ticker'])}<div class="sub">{e((r.get('name') or '')[:36])}</div></td>
<td class="sub">{e(sl)}</td>
<td class="n mono">{n(w,1,'%') if w is not None else '—'}</td>
<td class="n">{sg(stget(r,'3m','total'))}</td>
<td class="n">{sg(stget(r,'6m','total'))}</td>
<td class="n">{sg(stt.get('total'))}</td>
<td class="n">{sg(stt.get('excess'))}</td>
<td class="n mono dn">{n(stt.get('mdd'),1,'%')}</td>
<td class="n mono">{n(stt.get('sharpe'),2)}</td>
</tr>"""

pick_rows = "".join(nrow(r) for r in BT["names"])
avoid_rows = "".join(nrow({**r, "weight": None, "sleeve": ""}, "1y") for r in BT["avoid_names"])

payload = json.dumps({
    "dates": dates,
    "nav": BT["nav"],
    "books": {k: v["label"] for k, v in BT["books"].items()},
    "stats": {k: v["stats"] for k, v in BT["books"].items()},
    "names": [{"ticker": r["ticker"], "nav": r["nav"]} for r in BT["names"]],
})

HTML = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ten Themes — Pick Backtest</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
:root{{--bg:#08090b;--pan:#111317;--pan2:#171a1f;--line:#23272e;--tx:#e8ecf1;--mut:#7d8a9c;
--up:#00c805;--dn:#ff5000;--acc:#5b9cff;--warn:#ffb020}}
*{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:var(--bg);color:var(--tx);font:15px/1.55 Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1480px;margin:0 auto;padding:0 clamp(14px,4vw,44px)}}
.mono{{font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums}}
.up{{color:var(--up)}} .dn{{color:var(--dn)}} .mut,.sub{{color:var(--mut)}}
.sub{{font-size:11.5px;font-weight:400}}
header{{padding:26px 0 0;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#0d1014,#08090b)}}
.top{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap}}
.kick{{color:var(--up);font:700 10.5px/1 'JetBrains Mono';letter-spacing:.2em;text-transform:uppercase;margin-bottom:8px}}
h1{{font:800 clamp(26px,5vw,38px)/1 Inter;margin:0;letter-spacing:-1px}}
.asof{{color:var(--mut);font-size:12px;text-align:right}}
.asof a{{color:#5b9cff;text-decoration:none}}
.hero{{display:grid;grid-template-columns:repeat(auto-fit,minmax(126px,1fr));gap:1px;background:var(--line);margin-top:22px;border-top:1px solid var(--line)}}
.hs{{background:var(--bg);padding:15px 12px 18px}}
.hs b{{display:block;font:700 clamp(19px,3vw,25px)/1 'JetBrains Mono'}}
.hs span{{font-size:9.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--mut);display:block;margin-top:5px}}
section{{padding:40px 0;border-bottom:1px solid var(--line)}}
h2{{font:700 11px/1 'JetBrains Mono';letter-spacing:.2em;text-transform:uppercase;color:var(--acc);margin:0 0 8px}}
.lede{{color:#9fb0c4;font-size:15px;line-height:1.65;max-width:78ch;margin:0 0 22px}}
.warn{{background:rgba(255,176,32,.08);border:1px solid rgba(255,176,32,.28);border-radius:10px;padding:14px 16px;color:#e8d5a8;font-size:13.5px;line-height:1.6;max-width:92ch}}
.ctrl{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px}}
.ctrl button{{background:var(--pan);border:1px solid var(--line);color:var(--mut);font:700 10.5px 'JetBrains Mono';letter-spacing:.08em;text-transform:uppercase;padding:8px 11px;border-radius:6px;cursor:pointer}}
.ctrl button.on{{color:#08090b;background:var(--acc);border-color:var(--acc)}}
#chart{{height:380px;background:var(--pan);border:1px solid var(--line);border-radius:12px}}
.scroll{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;font:700 9.5px/1 'JetBrains Mono';letter-spacing:.1em;text-transform:uppercase;color:var(--mut);padding:10px 8px;border-bottom:1px solid var(--line)}}
td{{padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
th.n,td.n{{text-align:right}}
.tk{{font:700 14px 'JetBrains Mono'}}
.note{{color:#9fb0c4;font-size:13px;line-height:1.65;max-width:88ch}}
footer{{padding:26px 0;color:var(--mut);font-size:11.5px}}
@media(max-width:820px){{th,td{{padding:8px 6px;font-size:11.5px}}#chart{{height:280px}}}}
{mobile.CSS}
</style></head><body>
<header><div class="wrap">
<div class="top"><div><div class="kick">● Backtest lab · buy and hold</div><h1>Pick book vs the market</h1></div>
<div class="asof">Prices {BT['start']} → {BT['end']} · {BT['n_days']} sessions<br>Ratings as of <b class="mono" style="color:#fff">{asof}</b><br>
<a href="/">← Desk</a> · <a href="/map">Map</a> · <a href="/grants">Grants</a></div></div>
<div class="hero" id="hero">{hero}</div>
</div></header>

<section><div class="wrap">
<h2>What this is</h2>
<p class="lede">{e(BT['note'])} Default book is the model portfolio, weights renormalized to 100% invested. Cash is a separate toggle. Benchmark is SPY.</p>
<div class="warn"><b>Not a scoring-model backtest.</b> A name that is a PICK on {asof} is treated as a pick on every day in the window. That embeds hindsight. Use this to see whether the <i>current</i> book is a momentum pile-up or a lagged recovery — not to claim the five-factor composite had edge historically. No commissions, no slippage, daily close-to-close.</div>
</div></section>

<section><div class="wrap">
<h2>Path</h2>
<p class="lede">Indexed to 100 at the start of the selected window. Switch the book and the lookback; the table below stays on trailing 3m / 6m / 1y from {asof}.</p>
<div class="ctrl" id="books">
<button class="on" data-k="picks_model">Model weights</button>
<button data-k="picks_model_cash">Published (cash drag)</button>
<button data-k="picks_ew">Equal-weight picks</button>
<button data-k="avoids_ew">Avoids</button>
<button data-k="universe_ew">Universe EW</button>
</div>
<div class="ctrl" id="wins">
<button data-n="63">3 months</button>
<button data-n="126">6 months</button>
<button class="on" data-n="0">Full window ({BT['n_days']}d)</button>
</div>
<div id="chart"></div>
</div></section>

<section><div class="wrap">
<h2>Picks — {len(BT['names'])} names</h2>
<p class="lede">Model weights sum to 100% invested. 3m / 6m / 1y are buy-and-hold total returns to {asof} versus SPY over the same window.</p>
<div class="scroll"><table><thead><tr>
<th>Ticker</th><th>Sleeve</th><th class="n">Weight</th>
<th class="n">3m</th><th class="n">6m</th><th class="n">1y</th>
<th class="n">vs SPY</th><th class="n">Max DD</th><th class="n">Sharpe</th>
</tr></thead><tbody>{pick_rows}</tbody></table></div>
</div></section>

<section><div class="wrap">
<h2>Avoids — {len(BT['avoid_names'])} names</h2>
<p class="lede">Equal-weight foil. If the pick book is just high-beta beta, this list should not look dramatically worse. If it does, the rating at least sorted the trailing tape.</p>
<div class="scroll"><table><thead><tr>
<th>Ticker</th><th></th><th class="n"></th>
<th class="n">3m</th><th class="n">6m</th><th class="n">1y</th>
<th class="n">vs SPY</th><th class="n">Max DD</th><th class="n">Sharpe</th>
</tr></thead><tbody>{avoid_rows}</tbody></table></div>
</div></section>

<section><div class="wrap">
<h2>Method</h2>
<p class="note"><b>Alignment.</b> Daily closes (CBOE delayed history) via <code>hist.json</code>, inner-joined to SPY and every pick with a full tape ({BT['n_days']} sessions, {BT['start']} to {BT['end']}).
<b>Weights.</b> Model = inverse-vol sleeves with a 12% cap, renormalized to fully invested. Published keeps the {BT.get('cash')}% cash sleeve at a 0% return.
<b>Sharpe.</b> Daily mean annualized minus 4%, divided by annualized daily vol.
<b>Next.</b> Once Railway has more than one daily snapshot, this page can walk ratings forward instead of freezing this week's list.</p>
</div></section>

<footer><div class="wrap">Ten Themes · pick backtest · ratings {asof} · {len(BT['picks'])} picks · SPY benchmark · not investment advice</div></footer>
<script>
const BT = {payload};
const chart = echarts.init(document.getElementById('chart'));
let book = 'picks_model', win = 0;
const COL = {{spy:'#8ea0b5', picks_model:'#00c805', picks_model_cash:'#5b9cff',
 picks_ew:'#00d9c0', avoids_ew:'#ff5000', universe_ew:'#c77dff'}};
function slice(arr,n){{return n>0?arr.slice(-n):arr;}}
function draw(){{
  const d = slice(BT.dates, win);
  const spy = slice(BT.nav.spy, win);
  const ser = slice(BT.nav[book]||[], win);
  const z = (a)=>{{const s=a[0]||100; return a.map(v=>+(v/s*100).toFixed(3));}};
  chart.setOption({{
    backgroundColor:'transparent',
    grid:{{left:48,right:18,top:24,bottom:36}},
    tooltip:{{trigger:'axis',valueFormatter:v=>v==null?'—':v.toFixed(1)}},
    legend:{{top:0,textStyle:{{color:'#7d8a9c',fontSize:11}}}},
    xAxis:{{type:'category',data:d,axisLine:{{lineStyle:{{color:'#23272e'}}}},
      axisLabel:{{color:'#7d8a9c',fontSize:10,interval:Math.max(0,Math.floor(d.length/6))}}}},
    yAxis:{{type:'value',scale:true,splitLine:{{lineStyle:{{color:'#23272e'}}}},
      axisLabel:{{color:'#7d8a9c',fontSize:10}}}},
    series:[
      {{name:'SPY',type:'line',showSymbol:false,data:z(spy),lineStyle:{{width:1.5,color:COL.spy}},itemStyle:{{color:COL.spy}}}},
      {{name:(BT.books[book]||book),type:'line',showSymbol:false,data:z(ser),
        lineStyle:{{width:2.2,color:COL[book]||'#00c805'}},itemStyle:{{color:COL[book]||'#00c805'}}}}
    ]
  }}, true);
}}
function bind(id, attr, set){{
  document.querySelectorAll('#'+id+' button').forEach(b=>b.onclick=()=>{{
    document.querySelectorAll('#'+id+' button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); set(b.getAttribute(attr)); draw();
  }});
}}
bind('books','data-k',v=>book=v);
bind('wins','data-n',v=>win=+v);
draw();
window.addEventListener('resize',()=>chart.resize());
</script>{mobile.JS}</body></html>"""
open("backtest.html", "w").write(HTML)
print("wrote backtest.html", len(HTML), "bytes")
