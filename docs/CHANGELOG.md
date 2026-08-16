# Changelog

## v3 — 2026-08-16 (dashboard render fixes)

Verified the published dashboard in a real browser rather than assuming it rendered, which surfaced two defects.

**Fixed**
- **Literal asterisks in the strategy note.** The markdown helper handled `**bold**` but not single-asterisk italics, so `*down*` rendered as visible asterisks. `md()` now does a second pass for `*italic*` after the bold pass.
- **Strategy panel layout.** The panel was full-width with paragraphs capped at `92ch`, leaving roughly a third of a 1440px viewport empty inside a bordered box — it read as broken rather than deliberate. Panel now capped at 1020px so it presents as an intentional reading column.

**Discovered**
- The published artifact URL is **session-authenticated**. Fetched without an authenticated session it returns `{"error":"Not authenticated"}` and renders nothing. Consequence: the "Open the trading desk" button in the email digest silently fails anywhere the reader isn't signed in — most likely on mobile. Documented in `docs/AGENT.md`; the fix is to publish a genuinely public share link for email use.
- Public share links serve a cached snapshot taken at publish time. Re-saving the underlying file does **not** update an existing share URL; a fresh publish is required to verify a change.

---

## v2 — 2026-08-16 (trading layer)

Added the four data layers that turn the research product into something actionable, and rebuilt the interface from an institutional research register into a dark trading-desk register.

**Added**
- **Options** (`options.py`). CBOE delayed chains with full greeks. IV vs realized vol, put/call ratios by volume and OI, unusual-activity ranking by volume÷OI, earnings implied move from the ATM straddle, and liquidity-screened defined-risk trade tickets. 17 tradeable tickets from a 28-name shortlist.
- **Short interest and squeeze scoring**. Short % of float, days to cover, and change since prior settlement across all 72 names, folded into a 0–100 squeeze score.
- **Event calendar**. 58 forward non-earnings catalysts with confidence flags, direction, and sources, plus confirmed earnings dates for every name and an options-implied move for each.
- **IPO pipeline**. 32 companies across priced / pending / rumored, each with a read-across naming the public tickers it reprices.
- **Fundamentals and technicals** (`enrich.py`, `tech.py`). Market cap, forward P/E, EV/revenue, margins, revenue growth, FCF yield; RSI, 20/50/200-day SMAs, golden cross, realized vol at three horizons, max drawdown, 12-1 momentum, beta and correlation vs SPY, Sharpe, dollar volume.
- **Watchlist** (`score2.py`). Nine rules firing on signal conflicts, ranked by priority-weighted signal count. 42 names flagged.
- **Model portfolio**. Inverse-vol weighting inside Core / Contrarian / Tactical sleeves with a hard 12% single-name cap.
- **Theme correlation matrix** and cluster-concentration analysis.
- Sparklines, sortable universe table, and a dark mobile-first layout throughout.

**Fixed**
- **ABBV was misclassified** under *Robotics & Physical AI*. It is a pharmaceutical company; moved to *Biotech & AI Drug Discovery*. SERV (Serve Robotics) added to keep the robotics basket at seven names. Both theme composites changed.
- **Options expiry selection was picking thin weeklies.** The target expiry was chosen as the median of the DTE window, which for NVDA landed on an expiry with 780 total open interest instead of the monthly with 511,344. Every strike then failed the OI screen and tradeable tickets silently collapsed from 18 to 1. Expiries are now ranked by total open interest, which naturally selects monthlies.
- **The 12% position cap was not binding.** It capped relative weights and then renormalised to the sleeve target, which re-inflated everything straight back — four core names splitting a 60% sleeve is 15% each regardless of any cap. Changed to a hard truncate with the overflow falling to cash, which also makes the cash balance meaningful.

**Investigated and rejected**
- **FINRA's consolidated short interest API.** Free and official, but the bulk endpoint truncates at the row limit across all listed and OTC symbols — a 5,000-row pull covered 16 of 72 tickers with stale settlement dates. `sortFields` returns HTTP 400 on that endpoint. Yahoo's key-statistics module mirrors the same FINRA report with full coverage, so that is used instead. Recorded in `docs/DATA_SOURCES.md` so it isn't re-attempted.

---

## v1 — 2026-08-16 (initial build)

**Added**
- 10 themes, 71 tickers, 74 private-market competitors with funding, valuation, backers and threat rationale.
- Price pipeline over Yahoo's v8 chart endpoint: last close, 52-week range, 1w/1m/3m/1y returns.
- Five-factor composite scoring into PICK / NEUTRAL / AVOID.
- EDGAR research: Form 4 insider activity across 69 issuers with dollar values parsed from XML for 59; SC 13D activist screen returning 22 positions.
- 13F positioning for 27 of 71 tickers across 6 funds, with explicit limitations recorded.
- Analyst consensus, targets and recent actions for all 71 names.
- Light institutional-register dashboard and email digest.

**Notable findings**
- No classic activist (Elliott, Starboard, ValueAct, Jana, Trian) opened a new position in the universe in twelve months. What the 13D screen surfaced was strategic and sponsor ownership instead — Cerberus at ~31% of EOSE, SoftBank and Walmart at SYM, American Tower and Vodafone at ASTS.
- **EDGAR full-text search only indexes filings through ~2024-12-17.** A naive full-text screen of recent periods returns a false empty. Quarterly `crawler.idx` files are the correct source for recent filings.
- Ticker rename `SQ` → `XYZ` (Block) broke the first price run.
