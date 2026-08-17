# -*- coding: utf-8 -*-
import json, html, datetime as dt, os
from pathlib import Path
from dates import today
D = json.load(open("data2.json"))
rows, watch, port, EV, IPO = D["rows"], D["watch"], D["portfolio"], D["events"], D["ipos"]
asof = D["asof"]; TODAY = today()
_lp = Path("link.txt")
LINK = _lp.read_text().strip() if _lp.exists() else os.environ.get("PUBLIC_URL", "https://ten-themes.vercel.app")
byT = {r["ticker"]: r for r in rows}
picks = [r for r in rows if r["rating"] == "PICK"]; avoids = [r for r in rows if r["rating"] == "AVOID"]
trades = [r for r in rows if r.get("trade")]
trades.sort(key=lambda r: ({"PICK":0,"NEUTRAL":1,"AVOID":2}[r["rating"]], -r["composite"]))
e = lambda s: html.escape(str(s if s is not None else ""))
M = "'SF Mono',SFMono-Regular,Consolas,monospace"
def sg(v, d=1):
    if v is None: return '<span style="color:#7d8a9c">—</span>'
    return f'<span style="color:{"#00c805" if v>0 else "#ff5000"};font-weight:600">{v:+.{d}f}%</span>'
def n(v, d=2, p="", s=""): return "—" if v is None else f"{p}{v:,.{d}f}{s}"

_FALLBACK_INTRO = """Thirteen picks, 82.9% invested, 17.1% cash. Book beta is 2.06 — twice the market, and 67% of invested capital
sits in three themes that correlate 0.65–0.68 with each other. That concentration is deliberate but it is one trade, not three.
The edge remains in power: VST scores top-quartile while trading 27% lower on the year, and the options market prices a ±24.6% move
into its next print. Seventeen defined-risk tickets are live below."""
_ip = Path("intro.md")
INTRO = _ip.read_text().strip() if _ip.exists() else _FALLBACK_INTRO

TD = f"padding:10px 11px;border-bottom:1px solid #23272e"
TH = f"padding:8px 11px;border-bottom:1px solid #3a4048;font:600 9.5px {M};letter-spacing:.09em;text-transform:uppercase;color:#7d8a9c;text-align:left"

def wrow(w, i):
    r = byT[w["ticker"]]; bg = "#111317" if i % 2 == 0 else "#0d0f12"
    kinds = " · ".join(s["kind"] for s in w["signals"])
    return f"""<tr style="background:{bg}"><td style="{TD}">
<b style="font-family:{M};font-size:13px;color:#e8ecf1">{e(w['ticker'])}</b>
<span style="font-size:9px;font-family:{M};color:{'#00c805' if r['rating']=='PICK' else '#ff5000' if r['rating']=='AVOID' else '#7d8a9c'};margin-left:6px">{r['rating']}</span>
<div style="font-size:10.5px;color:#5b9cff;margin-top:2px">{e(kinds)}</div>
<div style="font-size:11px;color:#9fb0c4;margin-top:3px;line-height:1.45">{e(w['signals'][0]['why'])}</div></td>
<td style="{TD};text-align:right;white-space:nowrap"><b style="font-family:{M};color:#e8ecf1">{n(r.get('last'),2,'$')}</b>
<div style="font-size:11px">{sg(r.get('chg_1w'))}</div></td></tr>"""

def trow(r, i):
    t = r["trade"]; bg = "#111317" if i % 2 == 0 else "#0d0f12"
    l = t["legs"]
    return f"""<tr style="background:{bg}"><td style="{TD}">
<b style="font-family:{M};font-size:13px;color:#e8ecf1">{e(r['ticker'])}</b>
<div style="font-size:10.5px;color:#5b9cff;margin-top:2px">{e(t['structure'])}</div>
<div style="font-family:{M};font-size:10.5px;color:#7d8a9c;margin-top:3px">
{l[0]['action']} {n(l[0]['strike'],0,'$')}{l[0]['cp']} / {l[1]['action']} {n(l[1]['strike'],0,'$')}{l[1]['cp']} · {e(t['expiry'])} · {t['dte']}d</div></td>
<td style="{TD};text-align:right;font-family:{M};font-size:11.5px;white-space:nowrap">
<div style="color:#00c805;font-weight:700">+{n(t['max_gain_1lot'],0,'$')}</div>
<div style="color:#ff5000">−{n(t['max_loss_1lot'],0,'$')}</div>
<div style="color:#7d8a9c;font-size:10px;margin-top:2px">BE {t['be_move_pct']:+.1f}%</div></td></tr>"""

def prow(p, i):
    bg = "#111317" if i % 2 == 0 else "#0d0f12"
    return f"""<tr style="background:{bg}">
<td style="{TD};font-family:{M};font-weight:700;color:#e8ecf1">{e(p['ticker'])}</td>
<td style="{TD};font-size:10px;color:#5b9cff">{e(p['sleeve'])}</td>
<td style="{TD};text-align:right;font-family:{M};font-weight:700;color:#e8ecf1">{p['weight']:.1f}%</td>
<td style="{TD};text-align:right">{sg(p.get('chg_1y'))}</td></tr>"""

earn = sorted([r for r in rows if r.get("days_to_earnings") is not None and 0 <= r["days_to_earnings"] <= 30],
              key=lambda r: r["days_to_earnings"])[:10]
erow = "".join(f"""<tr style="background:{'#111317' if i%2==0 else '#0d0f12'}">
<td style="{TD};font-family:{M};font-weight:700;color:#e8ecf1">{e(r['ticker'])}</td>
<td style="{TD};font-family:{M};color:#5b9cff">{r['days_to_earnings']}d</td>
<td style="{TD};font-size:11px;color:#9fb0c4">{e(r.get('earnings_next'))}</td>
<td style="{TD};text-align:right;font-family:{M};color:#ffb020;font-weight:700">{('±'+str((r.get('opt') or {}).get('imp_move_pct'))+'%') if (r.get('opt') or {}).get('imp_move_pct') else '—'}</td></tr>"""
 for i, r in enumerate(earn))

sq = sorted([r for r in rows if r.get("short_pct_float")], key=lambda r: -r["squeeze"])[:8]
sqrow = "".join(f"""<tr style="background:{'#111317' if i%2==0 else '#0d0f12'}">
<td style="{TD};font-family:{M};font-weight:700;color:#e8ecf1">{e(r['ticker'])}</td>
<td style="{TD};font-family:{M};color:#ffb020;font-weight:700">{r['squeeze']}</td>
<td style="{TD};text-align:right;font-family:{M};color:#9fb0c4">{n(r.get('short_pct_float'),1,'','% float')}</td>
<td style="{TD};text-align:right;font-family:{M};color:#9fb0c4">{n(r.get('short_ratio'),1)}d cover</td></tr>"""
 for i, r in enumerate(sq))

ipo_hot = [p for p in IPO if p.get("status") in ("pending", "rumored")][:8]
irow = "".join(f"""<tr style="background:{'#111317' if i%2==0 else '#0d0f12'}">
<td style="{TD}"><b style="color:#e8ecf1;font-size:12.5px">{e(p['name'])}</b>
<div style="font-size:10.5px;color:#7d8a9c">{e(p.get('expected_date') or 'date TBD')} · {e(p.get('status'))}</div></td>
<td style="{TD};text-align:right;font-family:{M};color:#00c805;font-weight:700;white-space:nowrap">{('$%.0fB'%p['valuation_b']) if isinstance(p.get('valuation_b'),(int,float)) else '—'}</td></tr>"""
 for i, p in enumerate(ipo_hot))

STAT = "".join(
  f'<td align="center" style="padding:13px 3px;border-right:1px solid #23272e">'
  f'<div style="color:{c};font-size:20px;font-weight:700;font-family:{M}">{v}</div>'
  f'<div style="color:#7d8a9c;font-size:8.5px;letter-spacing:.1em;text-transform:uppercase;margin-top:3px">{l}</div></td>'
  for v, l, c in [(len(picks),"Picks","#00c805"),(len(avoids),"Avoid","#ff5000"),(len(trades),"Trades","#e8ecf1"),
                  (len(watch),"Flagged","#e8ecf1"),(D["port_beta"],"Beta","#ffb020")])

H = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#08090b">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#08090b"><tr><td align="center" style="padding:20px 8px">
<table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;background:#0d0f12;border:1px solid #23272e;border-radius:12px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif">

<tr><td style="padding:24px 26px 20px;background:linear-gradient(180deg,#12161b,#0d0f12)">
<div style="color:#00c805;font-size:10px;letter-spacing:.2em;text-transform:uppercase;font-weight:700;margin-bottom:7px">● Live desk · weekly</div>
<div style="color:#fff;font-size:29px;font-weight:800;letter-spacing:-.8px">Ten Themes</div>
<div style="color:#7d8a9c;font-size:11.5px;margin-top:6px">Market data {asof} · CBOE delayed options · 13F Q2 2026</div></td></tr>

<tr><td style="background:#111317;border-top:1px solid #23272e;border-bottom:1px solid #23272e">
<table width="100%" cellpadding="0" cellspacing="0"><tr>{STAT}</tr></table></td></tr>

<tr><td style="padding:22px 26px 4px">
<div style="color:#5b9cff;font-size:10px;letter-spacing:.2em;text-transform:uppercase;font-weight:700;margin-bottom:10px">This Week</div>
<div style="font-size:14.5px;line-height:1.7;color:#c3cede;background:#111317;border-left:3px solid #00c805;padding:15px 17px;border-radius:8px">{INTRO}</div></td></tr>

<tr><td style="padding:24px 26px 4px">
<div style="color:#5b9cff;font-size:10px;letter-spacing:.2em;text-transform:uppercase;font-weight:700;margin-bottom:10px">Pay Attention — top {min(8,len(watch))} of {len(watch)}</div>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">{''.join(wrow(w,i) for i,w in enumerate(watch[:8]))}</table></td></tr>

<tr><td style="padding:24px 26px 4px">
<div style="color:#5b9cff;font-size:10px;letter-spacing:.2em;text-transform:uppercase;font-weight:700;margin-bottom:10px">Trade Tickets — {len(trades)} live</div>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
<tr><th style="{TH}">Structure</th><th style="{TH};text-align:right">Gain / Loss per lot</th></tr>
{''.join(trow(r,i) for i,r in enumerate(trades[:10]))}</table>
<div style="font-size:10.5px;color:#7d8a9c;margin-top:8px;line-height:1.5">Defined-risk only. Delayed quotes — fills will differ. Full chains and greeks on the dashboard.</div></td></tr>

<tr><td style="padding:24px 26px 4px">
<div style="color:#5b9cff;font-size:10px;letter-spacing:.2em;text-transform:uppercase;font-weight:700;margin-bottom:10px">Earnings Runway — next 30 days</div>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
<tr><th style="{TH}">Ticker</th><th style="{TH}">In</th><th style="{TH}">Date</th><th style="{TH};text-align:right">Implied move</th></tr>{erow}</table></td></tr>

<tr><td style="padding:24px 26px 4px">
<div style="color:#5b9cff;font-size:10px;letter-spacing:.2em;text-transform:uppercase;font-weight:700;margin-bottom:10px">Squeeze Board</div>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">{sqrow}</table></td></tr>

<tr><td style="padding:24px 26px 4px">
<div style="color:#5b9cff;font-size:10px;letter-spacing:.2em;text-transform:uppercase;font-weight:700;margin-bottom:10px">IPO Pipeline</div>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">{irow}</table></td></tr>

<tr><td style="padding:24px 26px 4px">
<div style="color:#5b9cff;font-size:10px;letter-spacing:.2em;text-transform:uppercase;font-weight:700;margin-bottom:10px">Model Portfolio — {round(sum(p['weight'] for p in port),1)}% invested</div>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">{''.join(prow(p,i) for i,p in enumerate(port))}
<tr style="background:#0d0f12"><td style="{TD};font-family:{M};color:#7d8a9c">CASH</td><td style="{TD}"></td>
<td style="{TD};text-align:right;font-family:{M};font-weight:700;color:#7d8a9c">{D['cash']}%</td><td style="{TD}"></td></tr></table>
<div style="background:rgba(255,80,0,.08);border:1px solid rgba(255,80,0,.3);border-radius:8px;padding:13px 15px;margin-top:12px;font-size:11.5px;color:#f0c0aa;line-height:1.6">
<b style="color:#ff5000">Concentration warning.</b> {D['cluster_w']}% of invested capital sits in three themes correlating 0.65–0.68. Book beta {D['port_beta']}. A hyperscaler capex guide-down breaks all of it at once.</div></td></tr>

<tr><td style="padding:26px" align="center">
<a href="{LINK}" style="display:inline-block;background:#00c805;color:#08090b;text-decoration:none;padding:15px 34px;font-size:14px;font-weight:700;border-radius:8px">Open the trading desk →</a>
<div style="font-size:10.5px;color:#7d8a9c;margin-top:10px">{len(rows)} names · {len(D['privates'])} private competitors · {len(EV)} catalysts · {len(IPO)} IPOs</div></td></tr>

<tr><td style="background:#0a0b0d;padding:16px 26px;border-top:1px solid #23272e">
<div style="font-size:10px;color:#7d8a9c;line-height:1.6">
<b style="color:#c3cede">Method.</b> Composite = secular 25%, moat 20%, valuation 20%, analyst momentum 20%, smart-money flow 15%. PICK ≥ 3.70, AVOID &lt; 3.05.
<b style="color:#c3cede">Caveats.</b> 13F is a 45-day-lagged Q2 2026 snapshot confirmable for 27 of 71 names. Short interest mirrors FINRA's bi-monthly report and is up to two weeks stale. Options quotes are delayed. Event dates flagged expected or rumored are unconfirmed.
<b style="color:#c3cede">This is research, not investment advice.</b></div></td></tr>
</table></td></tr></table></body></html>"""
open("email2.html", "w").write(H)
json.dump({"to": "stuymusty@gmail.com",
 "subject": f"Ten Themes — {asof} · {len(trades)} trade tickets, {len(watch)} names flagged, beta {D['port_beta']}",
 "htmlBody": H,
 "textBody": f"Ten Themes weekly, data as of {asof}. {len(picks)} picks / {len(avoids)} avoids. {len(trades)} defined-risk option tickets. {len(watch)} names flagged. Book beta {D['port_beta']}, {D['cluster_w']}% in three correlated themes. Dashboard: {LINK}"},
 open("email2_params.json", "w"))
print("wrote email2.html", len(H))
