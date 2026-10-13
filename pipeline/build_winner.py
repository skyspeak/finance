# -*- coding: utf-8 -*-
"""Last Year's Winner page: winner.json -> winner.html (served at /winner)."""
import datetime as dt
import html
import json

import mobile

W = json.load(open("winner.json"))
P, S, B = W["position"], W["summary"], W["screen"]
Y, asof = W["year"], W["asof"]
e = lambda s: html.escape(str(s if s is not None else ""))
day = lambda s: dt.date.fromisoformat(s).strftime("%b %-d, %Y")


def money(v):
    return f"${v / 1e6:.2f}M" if v >= 1e6 else f"${v:,.0f}"


def pct(v, d=1):
    return "—" if v is None else f"{v:+.{d}f}%".replace("-", "−")


def sg(v, d=1):
    return f'<span class="{"up" if v > 0 else "dn" if v < 0 else "mut"}">{pct(v, d)}</span>'


def spark(vals):
    w, h = 96, 26
    lo, hi = min(min(vals), 1), max(vals)
    x = lambda i: i * w / max(len(vals) - 1, 1)
    y = lambda v: h - 2 - (v - lo) / ((hi - lo) or 1) * (h - 4)
    d = "".join(f"{'L' if i else 'M'}{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-hidden="true">'
            f'<line x1="0" x2="{w}" y1="{y(1):.1f}" y2="{y(1):.1f}" stroke="#23272e"/>'
            f'<path d="{d}" fill="none" stroke="#00c805" stroke-width="1.5"/>'
            f'<circle cx="{x(len(vals) - 1):.1f}" cy="{y(vals[-1]):.1f}" r="2.5" fill="#00c805"/></svg>')


lead, second = B[0], B[1]
next_jan = dt.date(Y + 1, 1, 1)
while next_jan.weekday() >= 5 or next_jan.day == 1:
    next_jan += dt.timedelta(days=1)
odds = sorted(B[:10], key=lambda r: -r["p_win"])[:4]
cushion = (1 - P["stop_price"] / P["last"]) * 100

if P["stopped"]:
    hold_note = (f'<b class="dn">Stopped out.</b> {e(P["sym"])} hit {P["stop_price"]:,.2f} on or before {day(P["low_date"])}. '
                 f'The rules hold cash until {day(next_jan.isoformat())}.')
    hold_tag = "Stopped · in cash"
else:
    hold_note = (f'<b>Hold.</b> The stop needs a {cushion:.0f}% fall from here to fire. '
                 + (f'Lowest this year: {pct(P["low"])} vs the January price.' if P["low"] < 0 else
                    f'It has not traded below its January price this year (lowest: {pct(P["low"])}).'))
    hold_tag = f"Holding · until Dec 31, {Y}"

odds_rows = "".join(
    f'<div class="odd"><span class="mono">{e(r["sym"])}</span><span class="bar"><i style="width:{r["p_win"]:.1f}%"></i></span>'
    f'<span class="mono n">{r["p_win"]:.0f}%</span></div>' for r in odds)
race_note = ("The year is over: this is the pick." if W["trading_days_left"] == 0 else
             f'{e(lead["name"])} leads {e(second["name"])} by {lead["ytd"] - second["ytd"]:.0f} points with '
             f'{W["trading_days_left"]} sessions left. At today\'s price its stop would sit near ${lead["last"] * (1 - W["stop"]):,.2f}.')

board_rows = "".join(f"""<tr{' class="lead"' if i == 0 else ''}>
<td class="mono mut">{i + 1}</td>
<td class="tk">{e(r['sym'])}{' <span class="chip">held</span>' if r['sym'] == P['sym'] else ''}<div class="sub">{e(r['name'][:34])}</div></td>
<td class="sub hide-m">{e(r['sector'])}</td>
<td class="n mono"><b>{pct(r['ytd'])}</b></td>
<td>{spark(r['spark'])}</td>
<td class="n mono {'dn' if r['low'] < 0 else ''}">{pct(r['low'])}</td>
<td class="n mono {'dn' if r['offhigh'] < -30 else ''}">{pct(r['offhigh'])}</td>
<td class="n mono">{f"{r['p_win']:.0f}%" if r['p_win'] >= 1 else '&lt;1%'}</td>
</tr>""" for i, r in enumerate(B[:15]))

hero = "".join(f'<div class="hs"><b class="mono {c}">{v}</b><span>{k}</span></div>' for k, v, c in [
    ("$100 in 1997 · 35% stop", money(S["stop_end"]), "up"),
    ("Same, no stop", money(S["nostop_end"]), ""),
    ("S&amp;P 500 (SPY)", money(S["spy_end"]), ""),
    ("Per year · stop", f'{S["stop_cagr"]}%', "up"),
    ("Per year · no stop", f'{S["nostop_cagr"]}%', ""),
    ("Per year · S&amp;P", f'{S["spy_cagr"]}%', ""),
])
fired = ", ".join(str(y) for y in S["fired"])

payload = json.dumps({k: W[k] for k in ("years", "paths", "sweep", "stop")}, separators=(",", ":"))

HTML = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ten Themes — Last Year's Winner</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
:root{--bg:#08090b;--pan:#111317;--pan2:#171a1f;--line:#23272e;--tx:#e8ecf1;--mut:#7d8a9c;
--up:#00c805;--dn:#ff5000;--acc:#5b9cff;--warn:#ffb020}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.55 Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1480px;margin:0 auto;padding:0 clamp(14px,4vw,44px)}
.mono{font-family:'JetBrains Mono',monospace;font-variant-numeric:tabular-nums}
.up{color:var(--up)} .dn{color:var(--dn)} .mut,.sub{color:var(--mut)}
.sub{font-size:11.5px;font-weight:400}
header{padding:26px 0 0;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#0d1014,#08090b)}
.top{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap}
.kick{color:var(--up);font:700 10.5px/1 'JetBrains Mono';letter-spacing:.2em;text-transform:uppercase;margin-bottom:8px}
h1{font:800 clamp(26px,5vw,38px)/1 Inter;margin:0;letter-spacing:-1px}
.asof{color:var(--mut);font-size:12px;text-align:right}
.asof a{color:#5b9cff;text-decoration:none}
.hero{display:grid;grid-template-columns:repeat(auto-fit,minmax(126px,1fr));gap:1px;background:var(--line);margin-top:22px;border-top:1px solid var(--line)}
.hs{background:var(--bg);padding:15px 12px 18px}
.hs b{display:block;font:700 clamp(19px,3vw,25px)/1 'JetBrains Mono'}
.hs span{font-size:9.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--mut);display:block;margin-top:5px}
section{padding:40px 0;border-bottom:1px solid var(--line)}
h2{font:700 11px/1 'JetBrains Mono';letter-spacing:.2em;text-transform:uppercase;color:var(--acc);margin:0 0 8px}
.lede{color:#9fb0c4;font-size:15px;line-height:1.65;max-width:78ch;margin:0 0 22px}
.warn{background:rgba(255,176,32,.08);border:1px solid rgba(255,176,32,.28);border-radius:10px;padding:14px 16px;color:#e8d5a8;font-size:13.5px;line-height:1.6;max-width:92ch}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.card{background:var(--pan);border:1px solid var(--line);border-radius:12px;padding:20px;display:grid;gap:14px;align-content:start}
.card.hold{border-color:rgba(0,200,5,.45)}
.tag{font:700 10px/1 'JetBrains Mono';letter-spacing:.14em;text-transform:uppercase;color:var(--up)}
.big{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.big b{font:700 34px/1 'JetBrains Mono';letter-spacing:-1px}
.big span{color:#9fb0c4;font-size:13.5px}
.kv{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.kv div span{display:block;font-size:9.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--mut)}
.kv div b{font:600 16px/1.4 'JetBrains Mono'}
.note{color:#9fb0c4;font-size:13px;line-height:1.65;max-width:88ch;margin:0}
.note b{color:var(--tx)}
.odd{display:grid;grid-template-columns:56px 1fr 44px;gap:10px;align-items:center;font-size:13px}
.odd .bar{height:8px;background:var(--pan2);border-radius:4px;overflow:hidden}
.odd .bar i{display:block;height:100%;background:var(--up);border-radius:4px}
.odd .n{text-align:right}
.chip{font:700 9px/1 'JetBrains Mono';letter-spacing:.08em;text-transform:uppercase;color:#08090b;background:var(--up);padding:3px 5px;border-radius:3px;vertical-align:2px}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{text-align:left;font:700 9.5px/1 'JetBrains Mono';letter-spacing:.1em;text-transform:uppercase;color:var(--mut);padding:10px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:middle;white-space:nowrap}
th.n,td.n{text-align:right}
tr.lead td{background:rgba(0,200,5,.06)}
.tk{font:700 14px 'JetBrains Mono'}
.chart{height:380px;background:var(--pan);border:1px solid var(--line);border-radius:12px}
ol.rules{margin:0 0 18px;padding-left:20px;display:grid;gap:8px;max-width:80ch;color:#c6d1de}
ol.rules b{color:var(--tx)}
ul.cav{margin:0;padding-left:20px;display:grid;gap:9px;max-width:88ch;color:#9fb0c4;font-size:13.5px;line-height:1.6}
ul.cav b{color:var(--tx)}
footer{padding:26px 0;color:var(--mut);font-size:11.5px}
@media(max-width:820px){.cols{grid-template-columns:1fr}.kv{grid-template-columns:repeat(2,minmax(0,1fr))}
th,td{padding:8px 6px;font-size:11.5px}.chart{height:300px}.hide-m{display:none}}
__MOBILE_CSS__
</style></head><body>
<header><div class="wrap">
<div class="top"><div><div class="kick">● Momentum rotation · S&amp;P 500</div><h1>Last Year's Winner</h1></div>
<div class="asof">Prices <b class="mono" style="color:#fff">__ASOF__</b> · CBOE delayed<br>__LEFT__ sessions left in __Y__<br>
<a href="/">← Desk</a> · <a href="/map">Map</a> · <a href="/backtest">Backtest</a></div></div>
<div class="hero">__HERO__</div>
</div></header>

<section><div class="wrap">
<h2>What the rules hold</h2>
<p class="lede">Each January, put everything into the S&amp;P 500 stock that rose the most the year before and hold it for twelve months. Sell early only if it falls 35% below the price paid.</p>
<div class="cols">
<div class="card hold">
<div class="tag">__HOLD_TAG__</div>
<div class="big"><b>__HSYM__</b><span>__HNAME__, __PY__'s top S&amp;P 500 stock (__HPREV__)</span></div>
<div class="kv">
<div><span>Bought (Dec 31)</span><b>$__HBUY__</b></div>
<div><span>Last</span><b>$__HLAST__</b></div>
<div><span>__Y__ so far</span><b class="__HCLS__">__HYTD__</b></div>
<div><span>35% stop</span><b>$__HSTOP__</b></div>
</div>
<p class="note">__HNOTE__</p>
</div>
<div class="card">
<div class="tag" style="color:var(--acc)">Next buy · __NEXTJAN__</div>
<div class="big"><b>__LSYM__</b><span>__LNAME__, leading __Y__ at __LYTD__</span></div>
<div style="display:grid;gap:8px">__ODDS__</div>
<p class="note">Chance each stock finishes __Y__ first. __RACE__</p>
</div>
</div>
</div></section>

<section><div class="wrap">
<h2>The race for the __NY__ pick</h2>
<p class="lede">Every S&amp;P 500 member ranked by __Y__ price gain; first place at the Dec 31 close is the January buy. <b>Chance of #1</b> replays the last six months of real daily moves 4,000 times over the sessions left, with each stock's trend removed so nobody gets credit for momentum continuing.</p>
<div class="scroll"><table><thead><tr><th>#</th><th>Stock</th><th class="hide-m">Sector</th><th class="n">__Y__ gain</th><th>Path</th><th class="n">Low vs Jan</th><th class="n">Off high</th><th class="n">Chance of #1</th></tr></thead>
<tbody>__BOARD__</tbody></table></div>
</div></section>

<section><div class="wrap">
<h2>How it works</h2>
<ol class="rules">
<li><b>Pick.</b> On the first trading day of January, rank every stock in the S&amp;P 500 at the previous year-end by its calendar-year price gain. Buy the top one with the whole balance.</li>
<li><b>Protect.</b> Set a stop 35% below the purchase price (the Dec 31 close). If the stock trades there at any point in the year, sell at the stop and hold cash until next January.</li>
<li><b>Rotate.</b> Next January, sell and buy the new winner, even if it is the same stock.</li>
</ol>
<p class="lede"><b>Test period:</b> January 1997 to __ASOF__. <b>Benchmark:</b> SPY with dividends reinvested (__Y__ so far is price only). Returns are price-only through 2011 and total return from 2012, matching the source exhibits. No taxes or trading costs. The stop sold in __FIRED__, every time in a year the stock collapsed, and has not fired since.</p>
<div class="chart" id="growth"></div>
</div></section>

<section><div class="wrap">
<h2>Year by year</h2>
<p class="lede">The stock held each year and its return. Faded bars show the loss the stop avoided. Returns above +260% are cut off at the top.</p>
<div class="scroll"><div class="chart" id="bars" style="min-width:860px"></div></div>
</div></section>

<section><div class="wrap">
<h2>Why 35%</h2>
<p class="lede">Ending value of $100 at each stop level. Tighter stops sell winners on ordinary dips; looser ones ride each crash further down. 35% sits just past the deepest dip any non-collapse year produced (Reebok, −32.3% in 2001) and short of the shallowest collapse (Netflix, −64.5% in 2011). Faded segments: years without intraday data could pull a tight stop down to the low end.</p>
<div class="chart" id="sweep" style="height:400px"></div>
</div></section>

<section><div class="wrap">
<h2>Before trusting it</h2>
<ul class="cav">
<li><b>The 35% level was picked with hindsight.</b> It fits the four crashes in this sample almost perfectly.</li>
<li><b>One stock holds everything.</b> Without the stop, 2002 (Nvidia −83%) or 2008 (NOV −67%) would have wiped out most of the balance.</li>
<li><b>The stop stays at the January price.</b> It does not trail, so it protects none of a big gain made during the year.</li>
<li><b>Gaps.</b> A stock can open far below the stop on bad news. The backtest assumes a clean exit at exactly −35%.</li>
<li><b>Taxes.</b> Every sale is a short-term gain in a taxable account.</li>
<li><b>Data.</b> The race uses today's index members. Pre-2000 years and delisted names come from the source exhibits. The chance of finishing first is a rough estimate, not a forecast.</li>
</ul>
</div></section>

<footer><div class="wrap">Ten Themes · last year's winner · rules from @gurgavin's "Buying last year's winner" exhibits · prices CBOE delayed, shortlist from Nasdaq · __ASOF__ · not investment advice</div></footer>
<script>
const W = __PAYLOAD__;
const C = {stop:'#00c805', nostop:'#5b9cff', spy:'#8ea0b5', dn:'#ff5000', soft:'rgba(255,80,0,.28)', mut:'#7d8a9c', line:'#23272e'};
const fm = v => v>=1e6 ? '$'+(v/1e6).toFixed(2)+'M' : '$'+Math.round(v).toLocaleString('en-US');
const fp = v => (v>0?'+':v<0?'−':'')+Math.abs(v).toFixed(0)+'%';
const ax = {axisLine:{lineStyle:{color:C.line}}, axisLabel:{color:C.mut,fontSize:10}, splitLine:{lineStyle:{color:C.line}}};
const charts = [];
function mk(id){ const c = echarts.init(document.getElementById(id)); charts.push(c); return c; }

(function(){
  const x = ['1997', ...W.years.map(y => y.ytd ? 'Now' : String(y.year+1))];  // year-end points
  const s = k => [100, ...W.paths[k]];
  const stopPts = W.years.map((y,i) => y.stopped ? [i+1, W.paths.stop[i]] : null).filter(Boolean);
  const end = (k, c) => ({type:'line', name:{stop:'With 35% stop', nostop:'No stop', spy:'S&P 500'}[k], data:s(k), showSymbol:false,
    lineStyle:{width:k==='stop'?2.4:1.6,color:c}, itemStyle:{color:c},
    endLabel:{show:true,color:'#e8ecf1',fontFamily:'JetBrains Mono',fontSize:11,formatter:p=>fm(p.value)}});
  mk('growth').setOption({backgroundColor:'transparent', grid:{left:58,right:96,top:34,bottom:34},
    legend:{top:4,textStyle:{color:C.mut,fontSize:11}},
    tooltip:{trigger:'axis', formatter: ps => { const i = ps[0].dataIndex; const y = W.years[i-1];
      return (y ? '<b>'+(y.ytd?y.year+' to date':'End of '+y.year)+'</b> · held '+y.sym+' ('+fp(y.stopped?-35:y.ret)+(y.stopped?', stopped':'')+')<br>' : '<b>Jan 1997</b><br>')
        + ps.filter(p=>p.seriesType==='line').map(p => p.marker+p.seriesName+' '+fm(p.value)).join('<br>'); }},
    xAxis:{type:'category', data:x, boundaryGap:false, ...ax, splitLine:{show:false}, axisLabel:{color:C.mut,fontSize:10,interval:(i,v)=>v==='Now'||(i%5===0&&i<x.length-3)}},
    yAxis:{type:'log', min:10, max:1e7, ...ax, axisLabel:{color:C.mut,fontSize:10,formatter:v=>v>=1e6?'$'+v/1e6+'M':v>=1e3?'$'+v/1e3+'K':'$'+v}},
    series:[end('spy',C.spy), end('nostop',C.nostop), end('stop',C.stop),
      {type:'scatter', name:'Stop sold', data:stopPts, symbolSize:9, itemStyle:{color:C.dn, borderColor:'#111317', borderWidth:2}, z:5}]});
})();

(function(){
  const cap = 260, Y = W.years;
  const shown = Y.map(y => y.stopped ? -35 : y.ret);
  mk('bars').setOption({backgroundColor:'transparent', grid:{left:48,right:12,top:26,bottom:46},
    tooltip:{trigger:'axis', axisPointer:{type:'shadow'}, formatter: ps => { const y = Y[ps[0].dataIndex];
      return '<b>'+y.year+(y.ytd?' to date':'')+'</b> · '+y.name+' ('+y.sym+')<br>Return '+fp(y.ret)+(y.stopped?' → stopped at −35%':'')
        +' · S&P '+fp(y.spy)+(y.dip!=null?'<br>Deepest dip vs January '+fp(y.dip):''); }},
    xAxis:{type:'category', data:Y.map(y => "'"+String(y.year).slice(2)+'\\n'+y.sym), ...ax, splitLine:{show:false},
      axisLabel:{color:C.mut,fontSize:9,interval:0,lineHeight:13}},
    yAxis:{type:'value', min:-100, max:cap, interval:50, ...ax, axisLabel:{color:C.mut,fontSize:10,formatter:v=>(v>0?'+':'')+v+'%'}},
    series:[
      {type:'bar', stack:'a', barWidth:'62%', data:Y.map(y => y.stopped ? -35 : 0), itemStyle:{color:'transparent'}, silent:true},
      {type:'bar', stack:'a', barWidth:'62%', data:Y.map(y => y.stopped ? y.ret+35 : 0), itemStyle:{color:C.soft}, silent:true},
      {type:'bar', stack:'b', barGap:'-100%', barWidth:'62%', data:shown.map((v,i) => ({value:Math.min(v,cap),
        itemStyle:{color:v>=0?C.stop:C.dn, borderRadius:v>=0?[3,3,0,0]:[0,0,3,3]},
        label:{show:Math.abs(v)>=60||Y[i].stopped, position:v>=0?'top':'bottom', color:'#c6d1de', fontFamily:'JetBrains Mono', fontSize:10, formatter:()=>fp(v)}}))}]});
})();

(function(){
  const rows = W.sweep.slice().reverse();
  const lab = s => s.stop ? Math.round(s.stop*100)+'% stop' : 'No stop';
  mk('sweep').setOption({backgroundColor:'transparent', grid:{left:78,right:150,top:14,bottom:28},
    tooltip:{trigger:'axis', axisPointer:{type:'shadow'}, formatter: ps => { const s = rows[ps[0].dataIndex];
      return '<b>'+lab(s)+'</b><br>'+(Math.round(s.worst)===Math.round(s.best) ? fm(s.best) : fm(s.worst)+' to '+fm(s.best)); }},
    xAxis:{type:'value', splitNumber:innerWidth<640?2:5, ...ax, axisLabel:{color:C.mut,fontSize:10,formatter:v=>v>=1e6?'$'+v/1e6+'M':v?'$'+v/1e3+'K':'$0'}},
    yAxis:{type:'category', data:rows.map(lab), ...ax, splitLine:{show:false},
      axisLabel:{color:C.mut,fontSize:11,formatter:(v)=>v==='35% stop'?'{b|'+v+'}':v, rich:{b:{color:'#e8ecf1',fontWeight:700}}}},
    series:[
      {type:'bar', stack:'s', barWidth:'58%', data:rows.map(s => ({value:s.worst, itemStyle:{color:s.stop===W.stop?C.stop:'#5b9cff'}}))},
      {type:'bar', stack:'s', data:rows.map(s => ({value:Math.max(s.best-s.worst,0), itemStyle:{color:'rgba(91,156,255,.32)', borderRadius:[0,3,3,0]},
        label:{show:true, position:'right', color:'#e8ecf1', fontFamily:'JetBrains Mono', fontSize:11,
          formatter:()=>Math.round(s.worst)===Math.round(s.best) ? fm(s.best) : fm(s.worst)+' – '+fm(s.best)}}))}]});
})();
window.addEventListener('resize', () => charts.forEach(c => c.resize()));
</script>__MOBILE_JS__</body></html>"""

fill = {
    "__MOBILE_CSS__": mobile.CSS, "__MOBILE_JS__": mobile.JS,
    "__ASOF__": day(asof), "__LEFT__": str(W["trading_days_left"]), "__Y__": str(Y), "__NY__": str(Y + 1),
    "__PY__": str(Y - 1), "__HERO__": hero, "__HOLD_TAG__": hold_tag,
    "__HSYM__": e(P["sym"]), "__HNAME__": e(P["name"]), "__HPREV__": pct(P["prev_ret"], 0),
    "__HBUY__": f'{P["dec31"]:,.2f}', "__HLAST__": f'{P["last"]:,.2f}', "__HSTOP__": f'{P["stop_price"]:,.2f}',
    "__HYTD__": pct(P["year_ret"]), "__HCLS__": "up" if P["year_ret"] >= 0 else "dn", "__HNOTE__": hold_note,
    "__NEXTJAN__": day(next_jan.isoformat()), "__LSYM__": e(lead["sym"]), "__LNAME__": e(lead["name"]),
    "__LYTD__": pct(lead["ytd"], 0), "__ODDS__": odds_rows, "__RACE__": race_note,
    "__BOARD__": board_rows, "__FIRED__": fired, "__PAYLOAD__": payload,
}
for k, v in fill.items():
    HTML = HTML.replace(k, v)
open("winner.html", "w").write(HTML)
print("wrote winner.html", len(HTML), "bytes")
