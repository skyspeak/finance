"""Fundamentals from SEC EDGAR XBRL company facts — used when Yahoo quoteSummary is blocked.

Produces the enrich.json fields the pipeline consumes (market cap, valuation ratios,
margins, growth, cash/debt, FCF yield) from each company's own 10-K/10-Q filings plus
this week's price. Only US-GAAP / USD filers are computed; IFRS filers (TSM, NVO, ...)
return None and the caller carries last week's values forward.

SEC asks for a descriptive User-Agent with a contact address (SEC_USER_AGENT) and
<10 requests/second.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.request

SEC_UA = os.environ.get("SEC_USER_AGENT", "TenThemes/1.0 research@example.com")
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FRESH_DAYS = 200  # a figure older than this (vs today) is treated as unavailable

REVENUE = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
           "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet"]
NET_INCOME = ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]
GROSS_PROFIT = ["GrossProfit"]
COST_OF_REVENUE = ["CostOfRevenue", "CostOfGoodsAndServicesSold"]
OP_INCOME = ["OperatingIncomeLoss"]
OCF = ["NetCashProvidedByUsedInOperatingActivities",
       "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]
CAPEX = ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets",
         "PaymentsForCapitalImprovements"]
DA = ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
      "DepreciationAmortizationAndAccretionNet", "Depreciation"]
CASH = ["CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]
ST_INVEST = ["ShortTermInvestments", "MarketableSecuritiesCurrent",
             "AvailableForSaleSecuritiesDebtSecuritiesCurrent"]
DEBT_TOTAL = ["LongTermDebt", "DebtAndCapitalLeaseObligations"]
DEBT_NONCURRENT = ["LongTermDebtNoncurrent"]
DEBT_CURRENT = ["LongTermDebtCurrent", "DebtCurrent"]
EQUITY = ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
DILUTED = ["WeightedAverageNumberOfDilutedSharesOutstanding"]


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": SEC_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def _days(e: dict) -> int | None:
    return (_d(e["end"]) - _d(e["start"])).days if e.get("start") else None


def _fresh(end: str) -> bool:
    return (dt.date.today() - _d(end)).days <= FRESH_DAYS


def _entries(gaap: dict, concept: str, unit: str = "USD") -> list[dict]:
    """10-K/10-Q facts for one concept, one value per period (latest filing wins)."""
    raw = (gaap.get(concept) or {}).get("units", {}).get(unit) or []
    best: dict[tuple, dict] = {}
    for e in raw:
        if e.get("form") not in ("10-K", "10-Q", "10-K/A", "10-Q/A"):
            continue
        k = (e.get("start"), e["end"])
        if k not in best or e.get("filed", "") > best[k].get("filed", ""):
            best[k] = e
    return sorted(best.values(), key=lambda e: e["end"])


def _pick(gaap: dict, concepts: list[str], unit: str = "USD") -> list[dict]:
    """Entries of whichever concept was reported most recently (filers switch tags)."""
    cands = [_entries(gaap, c, unit) for c in concepts]
    cands = [c for c in cands if c]
    return max(cands, key=lambda es: es[-1]["end"]) if cands else []


def _near(es: list[dict], end: dt.date, days: int) -> dict | None:
    """Entry of ~`days` duration ending within 12 days of `end`."""
    for e in es:
        dd = _days(e)
        if dd is not None and abs(dd - days) <= 12 and abs((_d(e["end"]) - end).days) <= 12:
            return e
    return None


def ttm(gaap: dict, concepts: list[str]) -> float | None:
    """Trailing twelve months for a flow concept: FY, or FY + YTD - prior-year YTD."""
    es = _pick(gaap, concepts)
    annual = [e for e in es if 350 <= (_days(e) or 0) <= 380]
    if not annual:
        return None
    fy = annual[-1]
    ytd = [e for e in es if e.get("start") and _d(e["start"]) > _d(fy["end"]) and (_days(e) or 0) < 350]
    if ytd:
        cur = max(ytd, key=lambda e: e["end"])
        prior = _near(es, _d(cur["end"]) - dt.timedelta(days=364), _days(cur))
        if prior and _fresh(cur["end"]):
            return fy["val"] + cur["val"] - prior["val"]
    return fy["val"] if _fresh(fy["end"]) else None


def yoy_quarter(gaap: dict, concepts: list[str]) -> float | None:
    """Latest discrete quarter vs the same quarter a year earlier, as a fraction."""
    es = _pick(gaap, concepts)
    qs = [e for e in es if 80 <= (_days(e) or 0) <= 100]
    if not qs or not _fresh(qs[-1]["end"]):
        return None
    cur = qs[-1]
    prior = _near(qs, _d(cur["end"]) - dt.timedelta(days=364), _days(cur))
    if not prior or not prior["val"]:
        return None
    return (cur["val"] - prior["val"]) / abs(prior["val"])


def instant(gaap: dict, concepts: list[str], unit: str = "USD") -> tuple[float, str] | None:
    es = [e for e in _pick(gaap, concepts, unit) if not e.get("start")]
    if not es or not _fresh(es[-1]["end"]):
        return None
    return es[-1]["val"], es[-1]["end"]


def shares_outstanding(facts: dict) -> float | None:
    dei = (facts.get("dei") or {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares") or []
    if dei:
        last = max(e["end"] for e in dei)
        if _fresh(last):
            # multi-class issuers (GOOGL) report one row per class for the same date
            latest_filed = max(e.get("filed", "") for e in dei if e["end"] == last)
            return float(sum(e["val"] for e in dei if e["end"] == last and e.get("filed", "") == latest_filed))
    es = [e for e in _pick(facts.get("us-gaap") or {}, DILUTED, "shares") if e.get("start")]
    return float(es[-1]["val"]) if es and _fresh(es[-1]["end"]) else None


def compute(facts: dict, price: float | None, shares_fallback: float | None = None) -> dict | None:
    """enrich.json fields from one company's facts; None if not a US-GAAP USD filer.

    shares_fallback (last week's share count) covers issuers that tag no usable share
    count, e.g. Visa's multi-class structure."""
    gaap = facts.get("facts", {}).get("us-gaap")
    if not gaap or not price:
        return None
    f = facts.get("facts", {})
    out: dict = {}
    shares = shares_outstanding(f) or shares_fallback
    rev, ni, op = ttm(gaap, REVENUE), ttm(gaap, NET_INCOME), ttm(gaap, OP_INCOME)
    gp = ttm(gaap, GROSS_PROFIT)
    if gp is None and rev is not None:
        cor = ttm(gaap, COST_OF_REVENUE)
        gp = rev - cor if cor is not None else None
    ocf, capex, da = ttm(gaap, OCF), ttm(gaap, CAPEX), ttm(gaap, DA)
    cash = instant(gaap, CASH)
    sti = instant(gaap, ST_INVEST)
    debt = instant(gaap, DEBT_TOTAL)
    if debt is None:
        nc, cu = instant(gaap, DEBT_NONCURRENT), instant(gaap, DEBT_CURRENT)
        debt = ((nc[0] if nc else 0) + (cu[0] if cu else 0), (nc or cu)[1]) if (nc or cu) else None
    eq = instant(gaap, EQUITY)

    mcap = price * shares if shares else None
    total_cash = (cash[0] if cash else 0) + (sti[0] if sti else 0) if (cash or sti) else None
    total_debt = debt[0] if debt else None
    ev = mcap + (total_debt or 0) - (total_cash or 0) if mcap else None
    fcf = ocf - capex if (ocf is not None and capex is not None) else None
    ebitda = op + da if (op is not None and da is not None) else None

    def ratio(a, b, positive=True):
        if a is None or not b or (positive and b <= 0):
            return None
        return round(a / b, 4)

    out.update({
        "market_cap": round(mcap) if mcap else None,
        "shares_out": shares,
        "enterprise_value": round(ev) if ev else None,
        "trail_pe": ratio(mcap, ni),
        "ps": ratio(mcap, rev),
        "pb": ratio(mcap, eq[0] if eq else None),
        "ev_rev": ratio(ev, rev),
        "ev_ebitda": ratio(ev, ebitda),
        "profit_margin": ratio(ni, rev, positive=True),
        "gross_margin": ratio(gp, rev, positive=True),
        "op_margin": ratio(op, rev, positive=True),
        "rev_growth": yoy_quarter(gaap, REVENUE),
        "earn_growth": yoy_quarter(gaap, NET_INCOME),
        "fcf": fcf,
        "total_cash": total_cash,
        "total_debt": total_debt,
        "roe": ratio(ni, eq[0] if eq else None),
    })
    if fcf is not None and mcap:
        out["fcf_yield"] = round(fcf / mcap * 100, 2)
    for k in ("rev_growth", "earn_growth"):
        if out[k] is not None:
            out[k] = round(out[k], 4)
    return {k: v for k, v in out.items() if v is not None}


class Edgar:
    """Ticker -> company facts, with SEC's ~10 req/s courtesy limit."""

    def __init__(self):
        self._ciks = None

    def cik(self, ticker: str) -> int | None:
        if self._ciks is None:
            data = _get_json(TICKERS_URL)
            self._ciks = {v["ticker"].upper(): int(v["cik_str"]) for v in data.values()}
        return self._ciks.get(ticker.upper())

    def facts(self, ticker: str) -> dict | None:
        c = self.cik(ticker)
        if not c:
            return None
        time.sleep(0.15)
        return _get_json(FACTS_URL.format(cik=c))
