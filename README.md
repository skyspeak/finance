# Ten Themes

A weekly thematic equity + options research pipeline. Ten industry themes, 72 public tickers, 74 private-market competitors — scored into PICK / NEUTRAL / AVOID, sized into a model portfolio, and turned into defined-risk option trade tickets.

**Stack:** Railway Postgres + a Monday cron worker run the pipeline. Vercel serves the public desk at [ten-themes.vercel.app](https://ten-themes.vercel.app) and the macro map at [/map](https://ten-themes.vercel.app/map). Fetch scripts stay Python stdlib (Yahoo / CBOE / Treasury / EDGAR, no API keys). The job itself needs `psycopg` (`pip install -r requirements.txt`).

Data snapshot in `data/` is as of **2026-08-14** (market close), generated 2026-08-16.

---

## Quick start (local, no database)

```bash
cd pipeline
python3 prices.py        # -> prices.json
python3 enrich.py        # -> enrich.json
python3 tech.py          # -> tech.json, hist.json
python3 score.py         # -> data.json
python3 options.py       # -> options.json
python3 score2.py        # -> data2.json
python3 macro.py         # -> macro.json
python3 sectors.py       # -> sectors.json
python3 factors.py       # -> factors.json
python3 build_site2.py   # -> site2.html
python3 build_map.py     # -> map.html
python3 build_email2.py  # -> email2.html, email2_params.json
```

Or from the repo root:

```bash
./run_weekly.sh
```

`prices.py`, `enrich.py` and `tech.py` are independent and can run in any order. All three must finish before `score.py`.

The scripts read and write JSON in their working directory. To reproduce against the committed snapshot, copy `data/*.json` into `pipeline/` first (`run_weekly.sh` does this for you).

---

## Weekly on Railway (database + cron)

Vercel cannot run this job (timeouts, no disk). Railway can: long-running Python, attached Postgres, cron that starts the container, runs `job.py`, exits.

What the Monday job does:

1. Carries the latest research JSON out of Postgres (analysts, events, IPOs, 13F, privates, insiders, activists, layers).
2. Refetches prices, fundamentals, technicals, option chains, Treasury curve, and macro series.
3. Re-scores, diffs ratings vs last week, writes a mechanical strategy note (does not reuse last week's prose).
4. Builds factor betas, GICS cross-tabs, and the map-room HTML (value-chain layers come from `layers.json`).
5. Stores the full snapshot + per-ticker ratings in Postgres.
6. Publishes `public/*.html` by committing them to [skyspeak/industry](https://github.com/skyspeak/industry); Vercel's Git integration deploys every push to `main`.

It will **fail the deploy** if fewer than 60 prices come back or fewer than 8 option tickets clear the liquidity screen.

### Weekly email

After a successful publish the job emails a digest to **stuymusty@gmail.com**: the week's top world, economy and tech stories (`pipeline/world.py` — 12 outlets' RSS, ranked by how many outlets carried each story), a markets snapshot, then the Ten Themes desk. A failed run sends a short alert instead, so no email means the job didn't run.

Sending uses Gmail SMTP with an **App Password**, which doesn't expire (Google revokes it only on a password change or if 2-Step Verification is turned off):

1. Signed in as stuymusty@gmail.com, open https://myaccount.google.com/apppasswords (2-Step Verification must be on), create one named `ten-themes`.
2. Railway → fortunate-healing → finance → Variables: `GMAIL_APP_PASSWORD` = the 16 characters (spaces are fine).
3. Test without waiting for Monday: `railway ssh --service finance -- python3 mailer.py --test`.

`MAIL_TO` (comma-separated) and `MAIL_FROM` override the defaults. The Gmail API path (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`) also works, but only lasts if the OAuth consent screen is published to **Production** — in Testing, Google expires refresh tokens after 7 days.

### One-time setup

1. Create a Railway project, attach **Postgres**, deploy this repo as a service (Dockerfile + `railway.toml`).
2. Copy `.env.example` into Railway variables. `DATABASE_URL` is injected by the plugin. Add `GITHUB_TOKEN` — a fine-grained GitHub token with **Contents: read & write on `skyspeak/industry` only** — so the job can publish.
3. Seed the committed snapshot so week-over-week diffs have a baseline:

```bash
railway run python3 job.py --seed
```

4. Confirm the cron: Monday `02:00` UTC (`railway.toml`). Trigger once by hand with `railway run python3 job.py`.

Locally, with a Railway DATABASE_URL:

```bash
pip install -r requirements.txt
python3 job.py --seed
python3 job.py
```

Analyst coverage, events, and IPOs still need a human or agent pass when they go stale — the job carries them and dates that lag in the strategy note. 13F stays quarterly; private competitors monthly; secular theme scores quarterly.

---

## Repo layout

```
pipeline/       The weekly pipeline. Run in the order above.
  universe.py     10 themes -> 72 tickers. Single source of truth.
  prices.py       2y daily history, 52w range, 1w/1m/3m/1y returns
  enrich.py       Yahoo crumb handshake -> fundamentals, short interest, earnings dates
  tech.py         RSI, SMAs, realized vol, beta, Sharpe, drawdown, theme correlation matrix
  score.py        Five-factor composite -> PICK / NEUTRAL / AVOID
  options.py      CBOE chains -> IV/RV, flow, implied moves, defined-risk trade tickets
  score2.py       Merges everything -> squeeze scores, watchlist, model portfolio, risk
  macro.py        Treasury curve + Yahoo macro/sector/thematic series
  sectors.py      Yahoo GICS sector/industry per ticker
  factors.py      Univariate OLS factor betas, residual exposure, regimes
  backtest.py     Buy-and-hold of this week's picks vs SPY (not a walk-forward)
  build_site2.py  Generates the dashboard HTML (reads strategy.md if present)
  build_map.py    Generates the Macro & Market Map HTML
  build_backtest.py  Generates the backtest lab HTML
  build_email2.py Generates the email HTML + Gmail params (reads intro.md if present)
  strategy.py     Mechanical STRATEGY/INTRO from this week vs last week's ratings
  dates.py        today() / ASOF=YYYY-MM-DD replay

job.py          Railway entrypoint: fetch → score → Postgres → Vercel
db.py           snapshots + ratings schema
publish.py      Commits public/ to skyspeak/industry (Vercel deploys main)

research/       Scripts behind the research JSON that the pipeline consumes.
                EDGAR Form 4 / SC 13D screening. These produce insiders.json
                and activists.json. Analyst, private-company, event and IPO data
                were gathered by LLM research passes rather than scripts — see
                docs/DATA_SOURCES.md for the schemas they must satisfy.

data/           Committed snapshot of every input and intermediate file.
output/         Rendered dashboard.html and email.html from that snapshot.
public/         Vercel publish root — index.html (desk), map.html, backtest.html, email.html.
legacy/         The v1 light-themed generators, superseded by build_site2/build_email2.
docs/           METHODOLOGY.md, DATA_SOURCES.md, AGENT.md, CHANGELOG.md
```

---

## Publish the desk (Vercel)

The public desk is [https://ten-themes.vercel.app](https://ten-themes.vercel.app). The map room is [https://ten-themes.vercel.app/map](https://ten-themes.vercel.app/map). The pick backtest is [https://ten-themes.vercel.app/backtest](https://ten-themes.vercel.app/backtest). The site is served from [skyspeak/industry](https://github.com/skyspeak/industry), which Vercel deploys on every push to `main` — don't `vercel --prod` from here, the next push would overwrite it. The Railway job publishes all pages after each successful run. Manual publish:

```bash
GITHUB_TOKEN=... python3 -c 'from pathlib import Path; from publish import publish_public; publish_public(Path("public"))'
```

`/` is the desk, `/map` is the macro map, `/backtest` is the pick-book lab, `/email` is the digest.

---

## Data flow

```
universe.py
    |
    +-- prices.py ------> prices.json ---+
    +-- enrich.py ------> enrich.json ---|
    +-- tech.py --------> tech.json -----|
                          hist.json      |
                                         v
  research passes                    score.py --> data.json
    analysts_*.json ------------------->  |            |
    insiders.json --------------------->  |            v
    activists.json -------------------->  |       options.py --> options.json
    hedgefunds.json ------------------->  |            |
    private_*.json -------------------->  +            |
    events.json  ----------------------------------+   |
    ipos.json  ------------------------------------+   |
                                                   v   v
                                                 score2.py --> data2.json
                                                       |
                                          +------------+------------+
                                          v                         v
                                   build_site2.py           build_email2.py
                                   -> site2.html            -> email2.html
```

---

## Scoring in one table

Composite is a weighted 1–5 score. **PICK ≥ 3.70, AVOID < 3.05**, everything else NEUTRAL.

| Factor | Weight | How it's derived |
|---|---|---|
| Secular demand | 25% | Theme-level judgment call, hardcoded in `THEME` in `score.py`. The only deliberately subjective input. |
| Moat vs. private disruption | 20% | Mega-cap base 4.4 / other 3.4, minus 0.28 per tracked private challenger (floor −1.4) |
| Valuation | 20% | Upside to mean analyst target: >40%→5.0, >25%→4.3, >12%→3.5, >2%→2.8, >−10%→2.0, else 1.3 |
| Analyst momentum | 20% | Consensus base (Strong Buy 4.6 → Sell 1.4), +0.3 per upgrade/PT raise, −0.4 per downgrade/PT cut |
| Smart-money flow | 15% | Insider signal (buying 4.6 → heavy selling 2.0), ±0.7 for 13F accumulating/distributing, +0.4 for a known activist |

Weighted lowest on purpose: smart-money flow, because free 13F coverage is thin and 45 days stale.

**Squeeze score (0–100)**, separate from the composite: short % of float ×4 (cap 40) + days-to-cover ×4 (cap 20) + % over 50-day ÷2 (cap 15) + RSI above 55 (cap 10) + short-interest increase ÷2 (cap 15).

**Model portfolio:** picks only, weighted by composite ÷ realized vol, bucketed into Core / Contrarian / Tactical sleeves targeting 60/22/13%, then hard-capped at 12% per name. Overflow above the cap becomes **cash, not redistribution** — the leftover is the signal that the model wants more concentration than is prudent. Do not "fix" it by renormalising.

---

## Findings from the committed snapshot

- **13 picks, 52 neutrals, 7 avoids.** 82.9% invested, 17.1% cash.
- **Book beta 2.06.** Not a defensive portfolio.
- **67% of invested capital sits in three themes correlating 0.65–0.68** (AI Compute, Power & Grid, Enterprise Software). One trade at three layers of the stack.
- Cybersecurity and Enterprise Software correlate at **0.80** — the highest pair in the matrix, so the short side isn't a diversifier either.
- 17 of 28 shortlisted names produced a tradeable option ticket. The other 11 failed the liquidity screen and were left empty.

---

## Known limitations

Read `docs/DATA_SOURCES.md` for the full list. The ones that matter most:

- **13F is 45 days stale**, long US equity only, and position-level data was confirmable for only 27 of 72 tickers from free sources. "No data" appears throughout and is correct.
- **Short interest is up to two weeks stale** by construction — it mirrors FINRA's bi-monthly consolidated report.
- **Option quotes are delayed**, so real fills will differ from the mid prices in the tickets.
- **Insider signal conflates** open-market sales with grants and 10b5-1 exercises. Dollar values were parsed from Form 4 XML for 59 of 69 covered issuers; the rest are volume-based only.
- **Private valuations** are last disclosed post-money, press-reported, frequently stale and preference-laden.
- Event dates flagged `expected` or `rumored` are **not confirmed**.

---

## This is not investment advice

This repo generates research output. Nothing in it accounts for anyone's existing exposure, tax situation, time horizon, or risk tolerance. The option structures are illustrative and generated mechanically from delayed quotes; options can and do expire worthless. Max loss figures are per single lot.
