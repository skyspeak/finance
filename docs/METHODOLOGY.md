# Methodology

How a ticker becomes a rating, a portfolio weight, and a trade ticket.

---

## 1. The universe

`pipeline/universe.py` maps 10 themes to 72 tickers. It is the single source of truth — every other script imports `UNIVERSE` and `ALL` from it. Adding a name here is the only supported way to extend coverage.

Themes were chosen to span the industries where AI-era capital formation is actually happening, and each basket deliberately mixes large-cap anchors with mid-cap pure plays so the theme score isn't just a mega-cap proxy.

**Theme membership is a judgment call and should be sanity-checked.** ABBV was originally filed under *Robotics & Physical AI* — it is a pharmaceutical company and was moved to *Biotech & AI Drug Discovery*, with SERV (Serve Robotics) added to keep the robotics basket at seven names. That error changed the composite for both baskets.

---

## 2. The five-factor composite

Each factor is scored 1–5 and weighted. **PICK ≥ 3.70, AVOID < 3.05**, everything between is NEUTRAL. Implemented in `pipeline/score.py`.

### Secular demand — 25%

The only deliberately subjective input, assigned per theme in the `THEME` dict with a written thesis attached to each score. Every constituent inherits its theme's value. Revisit quarterly, not weekly — churning this destroys week-over-week comparability.

Current values run from 5.0 (AI Compute & Semiconductors) to 3.5 (Enterprise Software & AI Agents).

### Moat vs. private disruption — 20%

```
base  = 4.4 if mega-cap else 3.4
score = base - min(1.4, 0.28 × number_of_tracked_private_challengers)
```

A private company "challenges" a public name when that ticker appears in the private company's `competes_with` array. This is the mechanism that converts private-market intelligence into a public-market score: a well-funded startup attacking a public company's core revenue line mechanically lowers that company's moat rating.

The mega-cap set is hardcoded and represents names with genuine structural incumbency, not merely large market caps.

### Valuation — 20%

Upside to the mean analyst price target:

| Upside | Score |
|---|---|
| > 40% | 5.0 |
| > 25% | 4.3 |
| > 12% | 3.5 |
| > 2% | 2.8 |
| > −10% | 2.0 |
| else | 1.3 |

This is relative valuation, not absolute. It measures distance from consensus, not cheapness. A name can score 5.0 here purely because the sell side is bullish and the stock has fallen — which is a signal, but not the same as being cheap on cash flow. Read it alongside the fundamentals columns.

### Analyst momentum — 20%

Consensus base: Strong Buy 4.6, Buy/Outperform 3.8, Hold/Neutral 2.6, Sell 1.4. Then **+0.3** per recent upgrade, initiation or PT raise, and **−0.4** per downgrade or PT cut, clamped to 1–5. Downgrades are weighted more heavily than upgrades on the view that sell-side downgrades carry more information than upgrades.

### Smart-money flow — 15%

Insider signal sets the base: buying 4.6, quiet 3.4, moderate selling 2.9, heavy selling 2.0. Then ±0.7 for a 13F `accumulating`/`distributing` signal and +0.4 when a known activist has filed.

**Weighted lowest deliberately.** 13F data is 45 days stale, long-only, and confirmable for a minority of the universe; insider filing counts conflate open-market sales with grants and 10b5-1 exercises. The factor is included because it occasionally contradicts the other four loudly, which is informative — not because it is precise.

---

## 3. Squeeze score

Separate 0–100 score, computed in `score2.py`. Not part of the composite.

```
+ min(40, short_pct_float × 4)
+ min(20, days_to_cover × 4)
+ min(15, pct_above_50dma ÷ 2)      [only if positive]
+ min(10, (RSI − 55) ÷ 2)           [only if RSI > 55]
+ min(15, short_interest_change ÷ 2) [only if increasing]
```

Interpretation depends on the rating, which is the point:

- **High squeeze + PICK** → a setup. Crowded short against a thesis you believe.
- **High squeeze + AVOID** → confirmation. The market already agrees with the rating; no edge in piling on.
- **High squeeze + rising short interest + strong momentum** → shorts are adding into strength, which is where violent covering rallies come from.

---

## 4. Model portfolio construction

Picks only. Implemented at the end of `score2.py`.

**Step 1 — sleeve assignment.**
- `Contrarian` — 1-year return under +5% *and* composite ≥ 3.7. High conviction the price disagrees with.
- `Tactical` — 30-day realized vol above 55% *or* market cap under $30B.
- `Core` — everything else.

Contrarian is tested first, so a cheap high-conviction name lands there rather than in Tactical even if volatile.

**Step 2 — inverse-vol weighting within each sleeve.**

```
raw_weight ∝ composite ÷ max(realized_vol_30d, 15)
```

Conviction in the numerator, risk in the denominator. The 15% vol floor stops a very low-vol name from dominating.

**Step 3 — sleeve targets.** Core 60%, Contrarian 22%, Tactical 13%.

**Step 4 — hard 12% single-name cap.** Weights are truncated at 12%, and **the overflow becomes cash.** It is not redistributed.

This last decision matters and is easy to get wrong. An earlier version capped relative weights and then renormalised to the sleeve target — which re-inflated every position straight back to 15% when a sleeve had only four members. Four names splitting 60% is 15% each by construction; no cap survives renormalisation. Truncating to cash means the cash balance carries information: **it is the amount by which the model wanted to be more concentrated than the risk limit allows.**

---

## 5. Risk analytics

**Book beta** — portfolio-weighted 1-year daily beta vs SPY. Reported prominently because a reader will otherwise assume roughly 1. The committed snapshot is **2.06**.

**Theme correlation matrix** — `tech.py` builds an equal-weighted daily return series per theme over the trailing year and computes the full pairwise correlation matrix. This is the diversification the book *actually* has, as opposed to what ten distinct theme labels imply.

**Cluster concentration** — invested weight in AI Compute + Power & Grid + Enterprise Software. In the snapshot this is **67%** across themes correlating 0.65–0.68, i.e. one trade expressed at three layers of the stack. Reported as an explicit warning rather than buried.

---

## 6. Watchlist generation

`score2.py` fires a rule per signal and ranks names by `sum(4 − priority)` across all signals fired. Priority 1 is most urgent.

| Signal | Trigger | Priority |
|---|---|---|
| Contrarian | PICK with negative 1-year return | 1 |
| Conflict | PICK with heavy insider selling | 1 |
| Earnings | Reports within 21 days | 1 if rated, else 3 |
| Squeeze | Squeeze ≥ 45 and not AVOID | 2 |
| Rich vol | IV/RV ≥ 1.30 | 2 |
| Cheap vol | IV/RV ≤ 0.60 | 2 |
| Overextended | RSI ≥ 75 on an AVOID | 2 |
| Put flow | Put/call volume ≥ 2.0 | 3 |
| IPO read-across | A tracked IPO names this ticker | 3 |

A name on the watchlist is explicitly **not** a buy recommendation. It is where the data stopped agreeing with itself, which is where the analyst should spend attention.

---

## 7. Options analytics and trade tickets

Implemented in `pipeline/options.py` over CBOE chains.

**Shortlist:** all PICKs, all AVOIDs, plus the 8 NEUTRALs with the largest gap between valuation score and analyst score — i.e. the names where consensus and price disagree most.

**IV/RV** — average implied vol of contracts within 6% of spot on the most liquid 21–45 DTE expiry, divided by 30-day realized vol. Above ~1.3, options are expensive relative to how the stock has actually been moving and selling premium is favoured. Below ~0.7, leverage is cheap and long options are favoured.

**Implied move** — the at-the-money straddle (call mid + put mid) ÷ spot, on the most liquid expiry *after* the next confirmed earnings date. This is the market's own forecast of the earnings reaction.

**Unusual activity** — contracts with OI > 200 and volume > 300, ranked by volume ÷ OI. A high ratio means today's flow is large relative to existing positioning.

### Liquidity screen — non-negotiable

```
open_interest >= 100  AND  bid >= $0.05  AND  bid_ask_spread <= 30% of mid
```

A name that fails gets **no ticket**. Never widen the screen to force one out; an untradeable ticket is worse than no ticket. In the snapshot, 11 of 28 shortlisted names produced nothing, and that is the screen working correctly.

### Structures

| Rating | Structure | Strike selection |
|---|---|---|
| PICK | Bull call debit spread | Long ~0.42 delta, short ~0.20 delta |
| AVOID | Bear put debit spread | Long ~−0.42 delta, short ~−0.20 delta |
| NEUTRAL | Bull put credit spread | Short ~−0.25 delta, long wing ~6% below |

Target expiry is the **most liquid** expiry in 35–80 DTE — ranked by total open interest, never by position in the list. See `DATA_SOURCES.md` §3 for why this matters.

### Ticket arithmetic

Every ticket carries net debit/credit, max gain, max loss, breakeven, breakeven move %, reward:risk, and both max figures **in dollars per single lot** (×100). Invariants worth asserting in any refactor:

- Debit spread: `max_gain == width − debit` and `max_loss == debit`
- Credit spread: `max_gain == credit` and `max_loss == width − credit`
- Breakeven: long strike ± net price, in the direction of the trade

---

## 8. The weekly narrative

The strategy note in `build_site2.py` (`STRATEGY`) and the short read in `build_email2.py` (`INTRO`) are prose, written fresh each week from what actually changed — rating flips, new 13D filings, insider clusters, squeeze setups forming, IV/RV dislocations, new private rounds.

**Shipping last week's narrative over this week's numbers is the primary failure mode of this product.** The tables will look current and the analysis will be stale, which is worse than an obviously old report.

The note should lead with factor disagreement rather than with whatever scored highest, because the highest scorer is usually already consensus and therefore already priced.
