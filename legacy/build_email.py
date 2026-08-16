# -*- coding: utf-8 -*-
import json, html
D = json.load(open("data.json"))
rows, themes, privates, activists = D["rows"], D["themes"], D["privates"], D["activists"]
asof = D["asof"]
LINK = open("link.txt").read().strip()
picks  = [r for r in rows if r["rating"]=="PICK"]
avoids = [r for r in rows if r["rating"]=="AVOID"]
e = lambda s: html.escape(str(s if s is not None else ""))
def sg(v, bold=False):
    if v is None: return "—"
    c = "#0a7d4f" if v > 0 else "#c62828"
    w = "600" if bold else "500"
    return f'<span style="color:{c};font-weight:{w}">{v:+.1f}%</span>'

INTRO = """The book is long the layers where AI demand is contracted and physically constrained, and short the layers where
software margins are exposed to substitution. Nine of fourteen picks sit in compute and power. Every avoid sits in cybersecurity,
application software, or card rails. The most interesting setup in the data is power: a top-quartile theme score paired with
negative one-year performance — VST is down 27% against a demand curve that has not bent."""

def prow(r, i):
    bg = "#ffffff" if i % 2 == 0 else "#f7fafd"
    return f"""<tr style="background:{bg}">
<td style="padding:9px 10px;border-bottom:1px solid #e7eef6"><b style="font-family:'SF Mono',Consolas,monospace;font-size:13px">{e(r['ticker'])}</b>
<div style="font-size:10.5px;color:#6b7c93">{e(r['theme'][:30])}</div></td>
<td style="padding:9px 10px;border-bottom:1px solid #e7eef6;text-align:right;font-family:'SF Mono',Consolas,monospace;font-weight:700;color:#0b5cd5">{r['composite']:.2f}</td>
<td style="padding:9px 10px;border-bottom:1px solid #e7eef6;text-align:right;font-family:'SF Mono',Consolas,monospace">${r.get('last',0):,.2f}</td>
<td style="padding:9px 10px;border-bottom:1px solid #e7eef6;text-align:right">{sg(r.get('chg_1y'))}</td>
<td style="padding:9px 10px;border-bottom:1px solid #e7eef6;text-align:right">{sg(r.get('pct_off_high'))}</td>
<td style="padding:9px 10px;border-bottom:1px solid #e7eef6;font-size:11px;color:#42546b">{e(r.get('consensus') or '—')} · {('$%.0f' % r['pt_mean']) if r.get('pt_mean') else '—'}</td>
<td style="padding:9px 10px;border-bottom:1px solid #e7eef6;font-size:11px;color:#42546b">{e(r.get('insider_signal') or '—')}</td></tr>"""

theme_rows = "".join(f"""<tr style="background:{'#ffffff' if i%2==0 else '#f7fafd'}">
<td style="padding:8px 10px;border-bottom:1px solid #e7eef6;font-family:'SF Mono',monospace;color:#6b7c93;font-size:11px">{i+1}</td>
<td style="padding:8px 10px;border-bottom:1px solid #e7eef6;font-size:13px"><b>{e(t['theme'])}</b></td>
<td style="padding:8px 10px;border-bottom:1px solid #e7eef6;text-align:right;font-family:'SF Mono',monospace;font-weight:600;color:#0b5cd5">{t['score']:.2f}</td>
<td style="padding:8px 10px;border-bottom:1px solid #e7eef6;text-align:right">{sg(t['med_1y'])}</td>
<td style="padding:8px 10px;border-bottom:1px solid #e7eef6;text-align:right;font-size:12px"><span style="color:#0a7d4f;font-weight:600">{len(t['picks'])}</span> / <span style="color:#c62828;font-weight:600">{len(t['avoids'])}</span></td>
</tr>""" for i, t in enumerate(themes))

ins = [r for r in rows if r.get("insider_signal") == "heavy selling"]
ins_li = "".join(f"<li style='margin-bottom:5px'><b style=\"font-family:'SF Mono',monospace\">{e(r['ticker'])}</b> — {r.get('n_form4',0)} Form 4s in 90 days · rated {e(r['rating'])}</li>" for r in sorted(ins, key=lambda r: -(r.get('n_form4') or 0))[:8])
act_li = "".join(f"<li style='margin-bottom:5px'><b style=\"font-family:'SF Mono',monospace\">{e(a['ticker'])}</b> — {e(a.get('filer_name'))} ({e(a.get('form_type'))}, {e(a.get('filing_date'))})</li>" for a in sorted(activists, key=lambda x: x.get('filing_date') or '', reverse=True)[:8])
ipo = [p for p in privates if p.get("ipo_watch")]
ipo_li = "".join(f"<li style='margin-bottom:5px'><b>{e(p['name'])}</b> — {('$%.1fB' % p['valuation']) if isinstance(p.get('valuation'),(int,float)) else 'undisclosed'} · {e(p.get('theme'))}</li>" for p in sorted(ipo, key=lambda p: -(p.get('valuation') or 0))[:10])

MONO = "'SF Mono',Consolas,monospace"
STATS = "".join(
  f'<td align="center" style="padding:14px 4px;border-right:1px solid rgba(255,255,255,.12)">'
  f'<div style="color:{c};font-size:22px;font-weight:700;font-family:{MONO}">{v}</div>'
  f'<div style="color:#8fa9c9;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;margin-top:3px">{l}</div></td>'
  for v, l, c in [(10,"Themes","#fff"),(len(rows),"Public","#fff"),(len(privates),"Private","#fff"),
                  (len(picks),"Picks","#5fd39a"),(len(avoids),"Avoid","#ff8a8a")])

H = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#eef2f7">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:22px 10px">
<table width="700" cellpadding="0" cellspacing="0" style="max-width:700px;background:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#0b1220">

<tr><td style="background:#08183a;padding:26px 30px">
<div style="color:#7fb0ff;font-size:10px;letter-spacing:.18em;text-transform:uppercase;font-weight:600;margin-bottom:7px">Weekly Thematic Intelligence</div>
<div style="color:#fff;font-size:27px;font-weight:700;letter-spacing:-.4px">Ten Themes</div>
<div style="color:#9fb6d4;font-size:12px;margin-top:6px">Market data as of {asof} · 13F Q2 2026 · Form 4 trailing 90 days</div>
</td></tr>

<tr><td style="background:#0b2350;padding:0">
<table width="100%" cellpadding="0" cellspacing="0"><tr>
{STATS}
</tr></table></td></tr>

<tr><td style="padding:26px 30px 6px">
<div style="font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;color:#0b5cd5;font-weight:700;margin-bottom:10px">This Week's Read</div>
<div style="font-size:15px;line-height:1.68;color:#26374d;background:#f6f9fc;border-left:3px solid #0b5cd5;padding:16px 18px">{INTRO}</div>
</td></tr>

<tr><td style="padding:24px 30px 6px">
<div style="font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;color:#0b5cd5;font-weight:700;margin-bottom:10px">Theme Ranking</div>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:12px">
<tr><th align="left" style="padding:7px 10px;border-bottom:2px solid #0b1220;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#6b7c93">#</th>
<th align="left" style="padding:7px 10px;border-bottom:2px solid #0b1220;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#6b7c93">Theme</th>
<th align="right" style="padding:7px 10px;border-bottom:2px solid #0b1220;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#6b7c93">Score</th>
<th align="right" style="padding:7px 10px;border-bottom:2px solid #0b1220;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#6b7c93">Med 1Y</th>
<th align="right" style="padding:7px 10px;border-bottom:2px solid #0b1220;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#6b7c93">P / A</th></tr>
{theme_rows}</table></td></tr>

<tr><td style="padding:26px 30px 6px">
<div style="font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;color:#0a7d4f;font-weight:700;margin-bottom:10px">The Picks — {len(picks)} names</div>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:12px">
<tr><th align="left" style="padding:7px 10px;border-bottom:2px solid #0b1220;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#6b7c93">Name</th>
<th align="right" style="padding:7px 10px;border-bottom:2px solid #0b1220;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#6b7c93">Score</th>
<th align="right" style="padding:7px 10px;border-bottom:2px solid #0b1220;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#6b7c93">Last</th>
<th align="right" style="padding:7px 10px;border-bottom:2px solid #0b1220;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#6b7c93">1Y</th>
<th align="right" style="padding:7px 10px;border-bottom:2px solid #0b1220;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#6b7c93">Off high</th>
<th align="left" style="padding:7px 10px;border-bottom:2px solid #0b1220;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#6b7c93">Consensus</th>
<th align="left" style="padding:7px 10px;border-bottom:2px solid #0b1220;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:#6b7c93">Insiders</th></tr>
{''.join(prow(r,i) for i,r in enumerate(picks))}</table></td></tr>

<tr><td style="padding:26px 30px 6px">
<div style="font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;color:#c62828;font-weight:700;margin-bottom:10px">The Avoids — {len(avoids)} names</div>
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:12px">
{''.join(prow(r,i) for i,r in enumerate(avoids))}</table></td></tr>

<tr><td style="padding:26px 30px 6px">
<div style="font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;color:#0b5cd5;font-weight:700;margin-bottom:10px">Signals</div>
<div style="font-size:12.5px;color:#26374d;line-height:1.6">
<b style="font-size:11px;text-transform:uppercase;letter-spacing:.06em">Heaviest insider selling</b>
<ul style="margin:7px 0 16px;padding-left:19px">{ins_li}</ul>
<b style="font-size:11px;text-transform:uppercase;letter-spacing:.06em">13D filers, trailing 12 months</b>
<div style="font-size:11.5px;color:#6b7c93;margin-top:5px">No classic activist (Elliott, Starboard, ValueAct, Jana, Trian) opened a new position in this universe. What the screen found is strategic and sponsor ownership.</div>
<ul style="margin:7px 0 16px;padding-left:19px">{act_li}</ul>
<b style="font-size:11px;text-transform:uppercase;letter-spacing:.06em">Private names on IPO watch</b>
<ul style="margin:7px 0 0;padding-left:19px">{ipo_li}</ul>
</div></td></tr>

<tr><td style="padding:26px 30px 30px" align="center">
<a href="{LINK}" style="display:inline-block;background:#0b5cd5;color:#fff;text-decoration:none;padding:14px 30px;font-size:13.5px;font-weight:600;letter-spacing:.02em;border-radius:3px">Open the full dashboard →</a>
<div style="font-size:11px;color:#6b7c93;margin-top:11px">71 public names · 74 private competitors · full filing detail and sources</div>
</td></tr>

<tr><td style="background:#f6f9fc;padding:18px 30px;border-top:1px solid #e7eef6">
<div style="font-size:10.5px;color:#6b7c93;line-height:1.6">
<b style="color:#0b1220">Method.</b> Composite = secular demand 25%, moat vs. private disruption 20%, valuation vs. mean analyst target 20%, analyst momentum 20%, smart-money flow 15%. PICK ≥ 3.70, AVOID &lt; 3.05.
<b style="color:#0b1220">Caveats.</b> 13F data is a 45-day-lagged Q2 2026 snapshot, long US equity only, confirmable for 27 of 71 tickers. Insider signal conflates open-market sales with grants and 10b5-1 exercises. Private valuations are last disclosed post-money, press-reported. Prices from Yahoo Finance, analyst data from stockanalysis.com / S&amp;P Global.
<b style="color:#0b1220">This is research, not investment advice.</b>
</div></td></tr>
</table></td></tr></table></body></html>"""
open("email.html","w").write(H)
print("wrote email.html", len(H))
json.dump({"to":"stuymusty@gmail.com",
 "subject":f"Ten Themes — weekly read, {asof} · {len(picks)} picks, {len(avoids)} avoids",
 "htmlBody":H,
 "textBody":f"Ten Themes weekly. Data as of {asof}. {len(picks)} picks, {len(avoids)} avoids across 10 themes, 71 public names, 74 private competitors. Top themes: "
   + "; ".join(f"{t['theme']} {t['score']:.2f}" for t in themes[:3]) + f". Dashboard: {LINK}"},
 open("email_params.json","w"))
print("wrote email_params.json")
