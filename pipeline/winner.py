"""Last Year's Winner: hold the prior year's best S&P 500 stock, with a 35% stop.

Rules (from the @gurgavin "Buying last year's winner" exhibits):
  1. First trading day of January: put the whole balance into the S&P 500 member with the
     highest price gain over the previous calendar year.
  2. Stop-loss 35% below the purchase price (the prior Dec 31 close). If it trades there,
     sell at the stop and hold cash until next January.
  3. Repeat every year.

Writes winner.json: the stock held now and its stop, the race for next January's pick
(with a bootstrap estimate of who finishes the year first), and a 1997-to-date backtest.

Data (all reachable from Railway):
  * winner_base_<year>.json - every member's Dec 31 close and that year's gain. Read from
    data/, then from the published site, else rebuilt from CBOE (slow, once a year in January)
    and written here so job.py publishes it next to the pages.
  * Nasdaq screener - one call for every US last sale; only used to shortlist candidates
    (it can carry after-hours prints).
  * CBOE daily history - official closes and intraday lows for the shortlist, the held
    stock and SPY.
"""
from __future__ import annotations

import datetime as dt
import html as htmllib
import json
import math
import os
import random
import re
import urllib.request

import market_data as md

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
PUBLIC_URL = (open(os.path.join(HERE, "link.txt")).read().strip() if os.path.exists(os.path.join(HERE, "link.txt"))
              else os.environ.get("PUBLIC_URL", "https://ten-themes.vercel.app")).rstrip("/")
STOP = 0.35
SHORTLIST = 15
SIMS = 4000
NASDAQ = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&download=true"
WIKI = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# Stock held each year, its calendar-year return and its deepest intraday low vs the January
# price (None = no intraday data). Yahoo Finance where the ticker still trades, the exhibits
# otherwise. Price returns through 2011, total returns from 2012, as in the exhibits.
HISTORY = [
    (1997, "DELL", "Dell", 216.0, None), (1998, "DELL", "Dell", 249.0, None),
    (1999, "DELL", "Dell", 39.3, None), (2000, "QCOM", "Qualcomm", -53.3, -70.8),
    (2001, "RBK", "Reebok", -3.0, -32.3), (2002, "NVDA", "Nvidia", -82.8, -89.2),
    (2003, "PVN", "Providian Financial", 79.0, None), (2004, "AV", "Avaya", 33.0, None),
    (2005, "ADSK", "Autodesk", 13.2, -31.0), (2006, "VLO", "Valero Energy", -0.9, -9.2),
    (2007, "ATI", "Allegheny Technologies", -4.7, -11.8), (2008, "NOV", "National Oilwell Varco", -66.7, -76.0),
    (2009, "FDO", "Family Dollar", 6.0, None), (2010, "XL", "XL Group", 19.0, None),
    (2011, "NFLX", "Netflix", -60.6, -64.5), (2012, "COG", "Cabot Oil & Gas", 31.0, None),
    (2013, "PHM", "PulteGroup", 13.1, -21.6), (2014, "NFLX", "Netflix", -7.2, -18.7),
    (2015, "LUV", "Southwest Airlines", 2.4, -25.9), (2016, "NFLX", "Netflix", 8.2, -30.1),
    (2017, "NVDA", "Nvidia", 82.0, -10.8), (2018, "NRG", "NRG Energy", 39.6, -16.6),
    (2019, "AMD", "AMD", 148.4, -8.2), (2020, "AMD", "AMD", 100.0, -19.9),
    (2021, "TSLA", "Tesla", 49.8, -23.5), (2022, "DVN", "Devon Energy", 50.9, -2.7),
    (2023, "OXY", "Occidental Petroleum", -4.1, -12.5), (2024, "NVDA", "Nvidia", 171.2, -4.4),
    (2025, "PLTR", "Palantir", 135.0, -16.2),
]
# SPY total return by year (Yahoo adjusted closes).
SPY_TR = {1997: 33.5, 1998: 28.7, 1999: 20.4, 2000: -9.7, 2001: -11.8, 2002: -21.6, 2003: 28.2, 2004: 10.7,
          2005: 4.8, 2006: 15.8, 2007: 5.1, 2008: -36.8, 2009: 26.4, 2010: 15.1, 2011: 1.9, 2012: 16.0,
          2013: 32.3, 2014: 13.5, 2015: 1.2, 2016: 12.0, 2017: 21.7, 2018: -4.6, 2019: 31.2, 2020: 18.3,
          2021: 28.7, 2022: -18.2, 2023: 26.2, 2024: 24.9, 2025: 17.7}
# Unknown dips are bounded by "never fell" and "fell like Reebok 2001"; only stops under 35% care.
UNKNOWN_WORST_DIP = -32.3


def http_json(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": md.UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _row(day, close, high, low):
    # A low under half the same day's close is a bad print, not a trade; it would fake a stop-out.
    low = low if low and low >= close * 0.5 else close
    high = high if high and high >= close else close
    return (day, close, high, low)


def cboe_rows(sym: str, quote: bool = True) -> list[tuple]:
    """[(date, close, high, low)] ascending, split-adjusted. The history file lags a session, so
    the quote's official close (its `close` field, not `current_price`) is appended. CBOE spells
    class shares with a dot (BRK.B)."""
    s = sym.replace("-", ".")
    data = json.loads(md._get(md.CBOE_HIST.format(s=s))).get("data") or []
    rows = [(d["date"], md._num(d.get("close")), md._num(d.get("high")), md._num(d.get("low"))) for d in data]
    rows = [_row(*r) for r in rows if r[1]]
    if not quote:
        return rows
    try:
        q = json.loads(md._get(md.CBOE_QUOTE.format(s=s), tries=2)).get("data") or {}
        day, px = (q.get("last_trade_time") or "")[:10], md._num(q.get("close")) or md._num(q.get("current_price"))
        if day and px and rows and day > rows[-1][0]:
            rows.append(_row(day, px, md._num(q.get("high")), md._num(q.get("low"))))
    except Exception:
        pass
    return rows


def year_close(rows, year):
    yr = [r for r in rows if r[0][:4] == str(year)]
    return yr[-1][1] if yr else None


def start_price(rows, year):
    """Purchase basis for `year`: the prior Dec 31 close, or the first close for a stock that
    listed during the year (how the exhibits count Sandisk's 2025)."""
    return year_close(rows, year - 1) or next((r[1] for r in rows if r[0][:4] == str(year)), None)


# ---------------------------------------------------------------- base files
def sp500_members() -> list[dict]:
    req = urllib.request.Request(WIKI, headers={"User-Agent": md.UA})
    page = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    table = page[page.index('id="constituents"'):]
    table = table[:table.index("</table>")]
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S)[1:]:
        cells = [htmllib.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) >= 3:
            out.append({"sym": cells[0].replace(".", "-"), "name": cells[1], "sector": cells[2]})
    return out


def build_base(year: int, prev_base: dict | None) -> dict:
    """Every member's Dec 31 close for `year` and its gain that year, plus how last year's
    pick did. Runs once, on the first trading day of the following January."""
    print(f"winner: building winner_base_{year}.json from CBOE (once a year)", flush=True)
    members = []
    for i, m in enumerate(sp500_members()):
        try:
            rows = cboe_rows(m["sym"], quote=False)
        except Exception as e:
            print(f"  skip {m['sym']}: {str(e)[:60]}", flush=True)
            continue
        end, start = year_close(rows, year), start_price(rows, year)
        if end and start:
            members.append({**m, "close": round(end, 4), "prev_ret": round((end / start - 1) * 100, 2)})
        if i % 50 == 0:
            print(f"  {i} members fetched", flush=True)
    base = {"year": year, "asof": f"{year}-12-31", "source": "CBOE delayed history",
            "held": max(members, key=lambda m: m["prev_ret"])["sym"], "members": members}
    if len(members) < 400:
        raise SystemExit(f"winner: only {len(members)} members priced for {year}; not saving a base")
    if prev_base:  # record how the stock held during `year` finished, for the backtest
        sym = prev_base["held"]
        held_m = next(m for m in prev_base["members"] if m["sym"] == sym)
        all_rows = cboe_rows(sym, quote=False)
        p0 = year_close(all_rows, year - 1) or held_m["close"]
        rows = [r for r in all_rows if r[0][:4] == str(year)]
        spy = cboe_rows("SPY", quote=False)
        base["completed"] = {
            "year": year, "sym": sym, "name": held_m["name"],
            "ret": round((rows[-1][1] / p0 - 1) * 100, 1),
            "dip": round((min(r[3] for r in rows) / p0 - 1) * 100, 1),
            "spy": round((year_close(spy, year) / year_close(spy, year - 1) - 1) * 100, 1),  # price only
        }
    json.dump(base, open(os.path.join(HERE, f"winner_base_{year}.json"), "w"), separators=(",", ":"))
    return base


def load_base(year: int, build: bool = False) -> dict | None:
    name = f"winner_base_{year}.json"
    for path in (os.path.join(DATA, name), os.path.join(HERE, name)):
        if os.path.exists(path):
            return json.load(open(path))
    try:
        base = http_json(f"{PUBLIC_URL}/{name}")
        json.dump(base, open(os.path.join(HERE, name), "w"), separators=(",", ":"))  # republish as-is
        return base
    except Exception:
        pass
    return build_base(year, load_base(year - 1)) if build else None


# ---------------------------------------------------------------- helpers
def trading_days_left(asof: dt.date) -> int:
    y = asof.year

    def nth(month, weekday, n):  # nth weekday of month (n=-1: last)
        d = dt.date(y, month, 1) if n > 0 else dt.date(y, month + 1, 1) - dt.timedelta(days=1)
        step = 1 if n > 0 else -1
        while d.weekday() != weekday:
            d += dt.timedelta(days=step)
        return d + dt.timedelta(weeks=(n - 1) if n > 0 else 0)

    def observed(d):
        return d - dt.timedelta(days=1) if d.weekday() == 5 else d + dt.timedelta(days=1) if d.weekday() == 6 else d

    a, b, c = y % 19, y // 100, y % 100  # Gregorian Easter (anonymous algorithm)
    dd, e, f = b // 4, b % 4, (b + 8) // 25
    h = (19 * a + b - dd - (b - f + 1) // 3 + 15) % 30
    l = (32 + 2 * e + 2 * (c // 4) - h - c % 4) % 7
    m = (a + 11 * h + 22 * l) // 451
    easter = dt.date(y, (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1)
    hol = {observed(dt.date(y, 1, 1)), nth(1, 0, 3), nth(2, 0, 3), easter - dt.timedelta(days=2),
           nth(5, 0, -1), observed(dt.date(y, 6, 19)), observed(dt.date(y, 7, 4)), nth(9, 0, 1),
           nth(11, 3, 4), observed(dt.date(y, 12, 25))}
    d, n = asof + dt.timedelta(days=1), 0
    while d.year == y:
        if d.weekday() < 5 and d not in hol:
            n += 1
        d += dt.timedelta(days=1)
    return n


def backtest(years, stop, case="known"):  # case: known | best | worst
    bal, path, fired = 100.0, [], []
    for y in years:
        # No intraday data: assume it never dipped, except in the "worst" bound of the stop sweep.
        dip = y["dip"] if y["dip"] is not None else (UNKNOWN_WORST_DIP if case == "worst" else 0.0)
        hit = stop is not None and dip <= -stop * 100
        bal *= 1 + (-stop * 100 if hit else y["ret"]) / 100
        path.append(round(bal, 2))
        if hit:
            fired.append(y["year"])
    return path, fired


def main():
    spy = cboe_rows("SPY")
    asof = dt.date.fromisoformat(spy[-1][0])
    Y = asof.year
    base = load_base(Y - 1, build=True)
    held = base["held"]
    mem = {m["sym"]: dict(m) for m in base["members"]}

    # The race counts stocks in the index at year-end, so rank today's members. Stocks added
    # since the base was saved (including spinoffs that listed this year) get their basis from CBOE.
    try:
        current = {m["sym"]: m for m in sp500_members()}
        if len(current) < 450:
            raise ValueError(f"only {len(current)} rows parsed")
    except Exception as e:
        print(f"winner: S&P list unavailable ({str(e)[:60]}); ranking last Dec 31's members", flush=True)
        current = {s: m for s, m in mem.items()}
    for s in [s for s in current if s not in mem]:
        try:
            p0 = start_price(cboe_rows(s, quote=False), Y)
        except Exception as e:
            print(f"  new member {s}: {str(e)[:60]}", flush=True)
            continue
        if p0:
            mem[s] = {**current[s], "close": p0, "prev_ret": None}
            print(f"winner: added {s} (joined the index after the base was saved)", flush=True)
    ranked_pool = [s for s in mem if s in current]

    # Shortlist: top of the Nasdaq last-sale ranking, last run's leaders (covers a split that
    # makes a leader look like a loser) and the held stock.
    short = set()
    try:
        rows = http_json(NASDAQ)["data"]["rows"]
        last = {r["symbol"].replace("/", "-"): md._num((r.get("lastsale") or "").lstrip("$")) for r in rows}
        ranked = sorted((s for s in ranked_pool if last.get(s)), key=lambda s: last[s] / mem[s]["close"], reverse=True)
        short.update(ranked[:SHORTLIST])
        print(f"winner: nasdaq priced {len(ranked)} of {len(ranked_pool)} members", flush=True)
    except Exception as e:
        print(f"winner: nasdaq screener failed ({str(e)[:80]}); using last run's leaders", flush=True)
    try:
        prev = http_json(f"{PUBLIC_URL}/winner.json")
        if prev.get("year") == Y:
            short.update(r["sym"] for r in prev.get("screen", [])[:SHORTLIST] if r["sym"] in current)
    except Exception:
        pass
    short.add(held)
    if len(short) < 5:
        raise SystemExit("winner: no candidate list (nasdaq and last run both unavailable)")

    board, series = [], {}
    for s in sorted(short):
        if s not in mem:
            continue
        try:
            rows = cboe_rows(s)
        except Exception as e:
            print(f"  {s}: {str(e)[:60]}", flush=True)
            continue
        yr = [r for r in rows if r[0][:4] == str(Y)]
        p0 = start_price(rows, Y) or mem[s]["close"]
        if not yr or not p0:
            continue
        lastpx = yr[-1][1]
        stop_hit = next((r[0] for r in yr if r[3] <= p0 * (1 - STOP)), None)
        series[s] = [r[1] for r in rows]
        board.append({
            "sym": s, "name": mem[s]["name"], "sector": mem[s]["sector"],
            "dec31": round(p0, 2), "last": round(lastpx, 2), "ytd": round((lastpx / p0 - 1) * 100, 1),
            "low": round((min(r[3] for r in yr) / p0 - 1) * 100, 1),
            "stop_date": stop_hit, "listed": year_close(rows, Y - 1) is None,
            "offhigh": round((lastpx / max(r[2] for r in yr) - 1) * 100, 1),
            "spark": [round(r[1] / p0, 3) for r in yr[::3]] + [round(lastpx / p0, 3)],
            "in_index": s in current,
        })
    if not any(r["sym"] == held for r in board):
        raise SystemExit(f"winner: no CBOE prices for the held stock {held}")
    held_row = next(r for r in board if r["sym"] == held)
    # The race only counts current members; the held stock stays on the board for its own card.
    board = sorted((r for r in board if r["in_index"]), key=lambda r: r["ytd"], reverse=True)
    if len(board) < 2:
        raise SystemExit(f"winner: only {len(board)} candidates priced")

    # Who finishes the year first? Bootstrap whole days from the last six months (keeps
    # correlation and fat tails), each stock's drift removed so trend isn't projected forward.
    left = trading_days_left(asof)
    top = board[:10]
    rets = {}
    for r in top:
        c = series[r["sym"]][-127:]
        lr = [math.log(c[i] / c[i - 1]) for i in range(1, len(c))]
        mu = sum(lr) / len(lr) if lr else 0.0
        rets[r["sym"]] = [x - mu for x in lr] or [0.0]
    # Days are drawn by position from the end so all stocks share the same session; a stock with
    # a shorter history (a recent listing) wraps around its own days.
    n = max(len(v) for v in rets.values())
    wins = {r["sym"]: 0 for r in top}
    rng = random.Random(7)
    start = {r["sym"]: math.log(1 + r["ytd"] / 100) for r in top}
    for _ in range(SIMS if left else 1):
        days = [rng.randrange(n) for _ in range(left)]
        best = max(top, key=lambda r: start[r["sym"]] + sum(rets[r["sym"]][-1 - d % len(rets[r["sym"]])] for d in days))
        wins[best["sym"]] += 1
    tot = sum(wins.values())
    for r in board:
        r["p_win"] = round(wins.get(r["sym"], 0) / tot * 100, 1)

    # Position
    h = held_row
    h.setdefault("p_win", 0.0)
    stop_px = round(h["dec31"] * (1 - STOP), 2)
    stopped = h["stop_date"] is not None
    position = {**{k: h[k] for k in ("sym", "name", "dec31", "last", "ytd", "low", "stop_date", "offhigh", "spark")},
                "prev_ret": mem[held]["prev_ret"], "stop_price": stop_px, "stopped": stopped,
                "year_ret": -STOP * 100 if stopped else h["ytd"]}

    # Backtest: the hard-coded history, completed years from later base files, then this year.
    years = [dict(year=y, sym=s, name=nm, ret=r, dip=d, spy=SPY_TR[y]) for y, s, nm, r, d in HISTORY]
    for yr in range(HISTORY[-1][0] + 1, Y):
        b = load_base(yr)
        if b and b.get("completed"):
            years.append(dict(b["completed"]))
    spy_ytd = round((spy[-1][1] / year_close(spy, Y - 1) - 1) * 100, 1)
    years.append(dict(year=Y, sym=held, name=h["name"], ret=h["ytd"], dip=min(h["low"], 0.0), spy=spy_ytd, ytd=True))

    spy_path, b = [], 100.0
    for y in years:
        b *= 1 + y["spy"] / 100
        spy_path.append(round(b, 2))
    nostop, _ = backtest(years, None)
    withstop, fired = backtest(years, STOP)
    for y in years:
        y["stopped"] = y["year"] in fired
    t_years = (asof - dt.date(1997, 1, 1)).days / 365.25
    cagr = lambda v: round(((v / 100) ** (1 / t_years) - 1) * 100, 1)
    sweep = []
    for st in (None, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50):
        sweep.append(dict(stop=st, best=backtest(years, st, "best")[0][-1], worst=backtest(years, st, "worst")[0][-1]))

    out = dict(
        asof=asof.isoformat(), year=Y, trading_days_left=left, stop=STOP, spy_ytd=spy_ytd,
        position=position, screen=board[:SHORTLIST], years=years,
        paths=dict(stop=withstop, nostop=nostop, spy=spy_path),
        summary=dict(stop_end=withstop[-1], nostop_end=nostop[-1], spy_end=spy_path[-1],
                     stop_cagr=cagr(withstop[-1]), nostop_cagr=cagr(nostop[-1]), spy_cagr=cagr(spy_path[-1]),
                     fired=fired),
        sweep=sweep,
    )
    json.dump(out, open(os.path.join(HERE, "winner.json"), "w"), indent=1)
    print(f"winner: asof {asof}, holding {held} {h['ytd']:+.1f}% (stop {stop_px}{', STOPPED' if stopped else ''}); "
          f"leader {board[0]['sym']} {board[0]['ytd']:+.1f}% ({board[0]['p_win']}% to finish first); "
          f"$100 since 1997 -> {withstop[-1]:,.0f}", flush=True)


if __name__ == "__main__":
    main()
