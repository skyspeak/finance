# Data sources, endpoints, and their failure modes

Everything is free and unauthenticated. This document records what worked, what broke, and the exact schemas the LLM-gathered research files must satisfy.

---

## 1. Prices and history — Yahoo v8 chart

```
GET https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}?range=2y&interval=1d
```

- **No auth.** Still open as of 2026-08-16. This is the endpoint the whole price and technicals layer rests on.
- Requires a **browser User-Agent** header; a default Python UA gets refused.
- Rate limit politely — 0.35s between calls is comfortable for 72 tickers.
- Returns `chart.result[0]` with `timestamp[]`, `indicators.quote[0].close[]`, `volume[]`, plus a `meta` block carrying `regularMarketPrice`, `fiftyTwoWeekHigh/Low`, `chartPreviousClose`.
- Close arrays contain `None` holes on halted/no-trade days. Filter before computing anything.

**Failure mode:** a ticker that 404s has almost certainly been renamed or delisted. `SQ` → `XYZ` (Block) broke a run. Check the rename before assuming the endpoint is down.

---

## 2. Fundamentals, short interest, earnings dates — Yahoo v10 quoteSummary

```
GET https://query2.finance.yahoo.com/v10/finance/quoteSummary/{TICKER}
      ?modules=defaultKeyStatistics,calendarEvents,financialData,summaryDetail&crumb={CRUMB}
```

**This endpoint is crumb-gated.** Without the handshake it returns:

```json
{"finance":{"result":null,"error":{"code":"Unauthorized","description":"Invalid Crumb"}}}
```

The v7 options endpoint (`/v7/finance/options/{TICKER}`) is gated the same way. The v8 chart endpoint is **not** — which is why prices kept working while these failed.

### The handshake (implemented in `pipeline/enrich.py`)

1. Build an opener with a cookie jar and a browser User-Agent.
2. Hit a seed URL to acquire cookies — `https://fc.yahoo.com` (returns 404, that's fine, the cookie is what matters) or `https://finance.yahoo.com/quote/NVDA`.
3. `GET https://query2.finance.yahoo.com/v1/test/getcrumb` with those cookies → an ~11-character token.
4. Append `&crumb={token}` to every quoteSummary call, reusing the same cookie jar.

The crumb is short-lived. **Fetch a fresh one at the start of every run**; don't cache it across runs.

### Fields used

| Module | Fields |
|---|---|
| `defaultKeyStatistics` | enterpriseValue, floatShares, sharesOutstanding, sharesShort, sharesShortPriorMonth, shortRatio, shortPercentOfFloat, dateShortInterest, beta, forwardPE, pegRatio, priceToBook, enterpriseToRevenue, enterpriseToEbitda |
| `summaryDetail` | marketCap, trailingPE, priceToSalesTrailing12Months, dividendYield |
| `financialData` | profitMargins, grossMargins, operatingMargins, revenueGrowth, earningsGrowth, freeCashflow, totalCash, totalDebt, returnOnEquity, recommendationKey |
| `calendarEvents` | earnings.earningsDate[] (epoch → next confirmed report), earningsAverage, revenueAverage |

Values arrive as `{"raw": x, "fmt": "..."}` — unwrap `raw`.

**Short-interest staleness:** `dateShortInterest` is the FINRA settlement date, so this data is up to two weeks old by construction. Always surface that.

---

## 3. Option chains — CBOE delayed quotes

```
GET https://cdn.cboe.com/api/global/delayed_quotes/options/{TICKER}.json
```

- **Free, no auth, no crumb.** The best free options source found.
- ~1.6 MB per underlying; ~3,600 contracts for a name like NVDA.
- `data.close` is the underlying price; `data.iv30` is a convenience 30-day IV.
- Each contract carries: `bid`, `ask`, `bid_size`, `ask_size`, `iv`, `open_interest`, `volume`, `delta`, `gamma`, `vega`, `theta`, `rho`, `theo`, `last_trade_price`, `prev_day_close`.
- Option symbols parse as `ROOT + YYMMDD + C|P + strike×1000`, e.g. `NVDA260817C00110000` → NVDA, 2026-08-17, call, $110.00 strike.
- `iv` is a decimal (0.376 = 37.6%). Deep-ITM contracts return nonsense IV (4.06) — exclude them from any ATM IV average.

### The expiry-selection trap — read this before touching `options.py`

Selecting the *median* expiry inside a DTE window lands on **thin weeklies**. Concretely, in the 35–80 DTE window for NVDA:

| Expiry | Total call OI |
|---|---|
| 2026-09-25 | 74,909 |
| 2026-10-02 | **780** ← median pick |
| 2026-10-16 | **511,344** ← monthly |

The median picked 2026-10-02, every strike then failed the `open_interest >= 100` screen, and tradeable tickets silently collapsed from 18 to 1. **Always rank candidate expiries by total open interest.** That naturally selects monthlies.

---

## 4. SEC EDGAR — insider and activist filings

Base: `https://data.sec.gov` and `https://www.sec.gov`. A descriptive **User-Agent is mandatory** or requests are refused. Keep under ~8 requests/second.

- **CIK lookup:** `https://www.sec.gov/files/company_tickers.json`
- **Filing history:** `https://data.sec.gov/submissions/CIK{10-digit-zero-padded}.json`
- **Form 4 (insider):** filter submissions by `form == "4"` and a date window. Dollar values require fetching and parsing the individual Form 4 XML — transaction codes matter: `P`/`S` are open-market purchase/sale, while `A` (grant), `M` (option exercise), `G` (gift) and `F` (tax withholding) are **not** open-market and carry no meaningful price.

**Critical EDGAR limitation:** full-text search (EFTS, `efts.sec.gov/LATEST/search-index?q=`) **only indexes filings through approximately 2024-12-17.** Anything more recent will not appear, and a naive full-text screen returns a false empty. For recent periods, screen the quarterly crawler indexes instead:

```
https://www.sec.gov/Archives/edgar/full-index/{YEAR}/QTR{1-4}/crawler.idx
```

Match subject companies **by CIK, never by ticker string** — short tickers like `S`, `V`, `AI`, `MP` produce large numbers of false positives against company names.

---

## 5. FINRA short interest — a documented dead end

```
POST https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest
Content-Type: application/json
{"limit": 5000, "dateRangeFilters": [{"fieldName":"settlementDate","startDate":"...","endDate":"..."}]}
```

Free, no auth, returns CSV. **But** the bulk endpoint truncates at the row limit across *all* listed and OTC symbols, so a 5,000-row pull covered only **16 of 72** tickers and returned settlement dates months stale. `{"limit": 5000, "sortFields": ["-settlementDate"]}` returns HTTP 400 — `sortFields` is not accepted on this endpoint.

Per-symbol `compareFilters` queries do work and would require 72 requests. Not worth it: **Yahoo's `shortPercentOfFloat` / `shortRatio` / `sharesShortPriorMonth` mirror the same FINRA bi-monthly report with full coverage in one call per ticker.** Use Yahoo; keep this note so nobody re-litigates it.

---

## 6. Analyst coverage — stockanalysis.com

```
https://stockanalysis.com/stocks/{ticker}/forecast/
```

Fetches cleanly and carries S&P Global-aggregated consensus, analyst count, mean/high/low targets, and a recent-actions table. Batch 8–10 URLs per fetch call. OTC ADRs have no page here — `FANUY` fell back to investing.com, with no analyst count available.

Short interest, valuation and margin data also appear in the embedded JSON on `https://stockanalysis.com/stocks/{ticker}/statistics/` as a usable cross-check against Yahoo.

---

## 7. LLM-gathered research files — required schemas

These are produced by research passes, not scripts. `score.py` and `score2.py` will fail or silently degrade if the shapes drift.

### `analysts_1.json` / `analysts_2.json` — object keyed by ticker
```json
{"NVDA": {"consensus": "Strong Buy", "num_analysts": 61, "pt_mean": 302.83,
  "pt_high": 500.0, "pt_low": 180.0,
  "recent_actions": [{"firm": "UBS", "action": "reiterate", "to": "$280", "date": "2026-08-14"}],
  "source_url": "https://..."}}
```

### `insiders.json` — object keyed by ticker
```json
{"NVDA": {"ticker": "NVDA", "cik": "1045810", "company_name": "NVIDIA CORP",
  "n_form4": 23, "signal": "quiet",
  "notable": [{"insider": "...", "role": "Director", "date": "2026-08-12", "note": "...", "filing_url": "..."}],
  "method": "how dollar values were or weren't obtained"}}
```
`signal` must be one of: `buying`, `quiet`, `moderate selling`, `heavy selling`.

### `activists.json` — array
```json
[{"ticker": "EOSE", "subject_company": "...", "subject_cik": "...",
  "filer_name": "Cerberus Capital", "filer_cik": "...",
  "form_type": "SCHEDULE 13D", "filing_date": "2026-03-11",
  "accession_url": "https://...", "is_known_activist": false,
  "activist_agenda": "one sentence"}]
```

### `hedgefunds.json`
```json
{"as_of_quarter": "Q2 2026", "limitations": "...",
 "moves": [{"fund": "Coatue", "ticker": "NVDA", "action": "added",
            "quarter": "Q2 2026", "size": "...", "source_url": "..."}],
 "by_ticker": {"NVDA": {"net_signal": "accumulating", "notable_holders": [],
                        "evidence": "...", "source_url": "..."}}}
```
`net_signal` must be one of: `accumulating`, `mixed`, `distributing`, `no data`.

### `private_1.json` / `private_2.json` — arrays
```json
[{"name": "OpenAI", "theme": "AI Compute & Semiconductors", "description": "...",
  "stage": "private established, pre-IPO", "last_round": "$122B, Mar 2026",
  "valuation": 852, "total_raised": "$300B+",
  "key_backers": ["SoftBank"], "competes_with": ["NVDA", "AMD"],
  "threat": "one sentence", "ipo_watch": true, "source_url": "https://..."}]
```
`valuation` is in **$B as a number**, or `null`. `competes_with` tickers must exist in `universe.py` — that's how private-market pressure attaches to a public name and lowers its moat score.

### `events.json` — array
```json
[{"date": "2026-09-30", "date_confidence": "confirmed",
  "tickers": ["NVO"], "theme": "Biotech & AI Drug Discovery",
  "event_type": "regulatory", "title": "...", "description": "...",
  "direction": "binary", "why_it_matters": "...", "source_url": "https://..."}]
```
`date` accepts `YYYY-MM-DD`, `YYYY-MM`, or a quarter string. `date_confidence`: `confirmed` | `expected` | `rumored`. `direction`: `bullish_if_hit` | `bearish_risk` | `binary` | `informational`. `event_type`: `product` | `conference` | `regulatory` | `clinical` | `energy_market` | `contract` | `investor_day` | `lockup` | `index` | `other`.

### `ipos.json` — array
```json
[{"name": "Cerebras Systems", "theme": "AI Compute & Semiconductors",
  "status": "priced", "expected_date": "2026-05-14", "ticker": "CBRS",
  "price_range": "$185", "valuation_b": 66, "raise_b": 5.5,
  "underwriters": ["..."], "last_private_valuation_b": null,
  "description": "...", "read_across": "which public tickers this reprices and why",
  "source_url": "https://..."}]
```
`status`: `priced` | `pending` | `rumored`. `score2.py` scans `read_across` + `description` for ticker symbols to build the IPO→public-name linkage, so **name the affected tickers explicitly in that prose**.

### `layers.json` — object
Editorial value-chain taxonomy for the map room. Not fetched.

```json
{"public": [{"ticker": "NVDA", "theme": "AI Compute & Semiconductors",
  "layer": "Accelerators & Custom Silicon", "layer_index": 3,
  "also": ["Interconnect & Networking"], "note": "...",
  "is_pure_play": false, "spans_stack": true}],
 "private": [...],
 "layer_gaps": [{"theme": "...", "observation": "..."}]}
```

---

## 8. Macro series — Treasury + Yahoo

```
GET https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv
GET https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}?range=2y&interval=1d
```

`macro.py` pulls the par yield curve (2s10s lives here; `^TNX` on Yahoo is too sparse) and the same v8 chart endpoint used for prices, for VIX, DXY, WTI, gold, copper, TLT, HYG, LQD, BTC, SPX/NDX/RUT, GICS SPDRs, and thematic ETFs. `sectors.py` uses the crumb-gated quoteSummary `assetProfile` module. `factors.py` is local OLS on `hist.json` + `macro.json`.

**Hard macro is absent.** CPI, payrolls, and ISM are not fetched. Everything on the map is market-priced and daily.

---

## Anti-fabrication rule

Every numeric claim in the output must trace to a retrieved source. `null` is a valid and expected value. A partially covered dataset honestly labelled is worth more than a complete one that is partly invented — this is why `hedgefunds.json` ships with an explicit `limitations` string and why "no data" appears on 45 of 72 tickers in the flow column.
