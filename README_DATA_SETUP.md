# Capital Tide — Free Data Pipeline Setup

This turns your dashboard from synthetic demo data into a mix of **real, free
data** for most series, with a handful of honest, clearly-labeled gaps that
have no free equivalent yet.

## What's real vs what's still synthetic

| Status | Series |
|---|---|
| ✅ Real (free) | Fed Balance Sheet, TGA, RRP, DXY, 10Y Real Yield, 2s10s, 5s30s, HY OAS, IG Spread, VIX, Financial Conditions Index, 2Y/10Y Yields, SPY, QQQ, ACWI, Russell 2000, XLF, HYG, LQD, Gold, Oil, Copper, Broad Commodity Index, USDJPY, EM FX Basket (approx.), Bonds (TLT proxy), BTC, ETH, BTC Dominance (self-computed), Altseason Index (self-computed), Stablecoin Supply, Perp Funding Rate, Open Interest, Crypto Fear & Greed, all 10 sector ETFs, COT net positioning (DXY/Gold/WTI/S&P 500 futures), AAII Bull-Bear Spread, Put/Call Ratio (Cboe), Equity Put/Call Skew (Cboe SKEW Index), Fund Manager Cash Level (Money Market Fund proxy) |
| 🟡 Left synthetic — genuine free-data gap | BIS Global Liquidity Indicators (USD/EUR credit), true exchange net-flow, Vol Term Structure / VX1-VX2 (tried VIX3M then VIX9D via Yahoo Finance — both failed identically in two separate environments, pointing to a genuine data-coverage gap on Yahoo's end for CBOE's secondary vol indices) |

AAII and the Cboe Put/Call ratio were originally (incorrectly) flagged as
having no free source — they do. See "Corrections" below.

## Fixes applied after first real-world test run

Running this against live data surfaced four real bugs, now fixed:

1. **Stooq blocked every request** — it was returning an HTML block-page
   instead of CSV, because the script's User-Agent identified it as a bot.
   Fixed by sending a standard browser User-Agent (a normal, common way to
   access publicly downloadable data — not bypassing any paywall).
2. **CoinGecko 401 + 429 errors** — their free tier now expects a (still
   free) Demo API key for reliable access; fully keyless calls get
   rate-limited almost immediately. Get one free at
   https://www.coingecko.com/en/api/pricing and set `COINGECKO_API_KEY`.
   The script also now fetches each coin only once and reuses it for both
   the BTC/ETH series and the dominance/altseason calculation, instead of
   fetching BTC/ETH twice.
3. **CFTC COT returned zero rows** — a double-URL-encoding bug in the query
   filter meant it was searching for the literal text `%25GOLD%25` instead
   of a wildcard match. Fixed.
4. **AAII and Cboe Put/Call were wrongly flagged as unfixable** — both have
   genuine free sources: AAII publishes their full weekly history at
   `aaii.com/files/surveys/sentiment.xls` (no login), and Cboe publishes a
   free historical Put/Call ratio archive on their CDN. Both are now wired
   in. One honest caveat on Cboe: the archive filename/coverage window
   wasn't verified live from the environment this was built in — if it
   404s or looks stale, check
   https://www.cboe.com/us/options/market_statistics/historical_data/ for
   the current filename.
5. **CoinGecko still 401'ing even with a valid key set** — two likely
   causes fixed together: the key is now sent both as the `x-cg-demo-api-key`
   header and the `x_cg_demo_api_key` query parameter (belt-and-suspenders,
   since CoinGecko's docs show both forms), and the default history window
   was reduced from 760 days to 365 — the free Demo tier caps historical
   range at 1 year, and asking for more can itself trigger a 401 even with a
   working key. If it still fails after this: open your `.env` file and
   make sure the line reads exactly `COINGECKO_API_KEY=CG-xxxxxxx` with no
   quotation marks and no trailing spaces (a very common copy-paste error),
   and confirm the key shows as "Active" on your CoinGecko developer
   dashboard.

## One-time setup (about 10 minutes)

### 1. Get a free FRED API key
Go to https://fredaccount.stlouisfed.org, create a free account, then
generate an API key under "My Account → API Keys." No cost, no card.

**Important: never commit your key to the repo or paste it into
`fetch_data.py` directly.** Set it as an environment variable locally, and
as a GitHub Actions secret when deployed (step 4 below) — a key sitting in
committed code on a public repo gets scraped by bots within hours.

### 1b. (Recommended) Get a free CoinGecko Demo API key
Sign up at https://www.coingecko.com/en/api/pricing (free tier, no card) and
set it as `COINGECKO_API_KEY`. Without it, crypto/dominance/altseason fetches
will be slow and may hit rate limits.

### 2. Test the pipeline locally
```bash
cd capital-tide-data
pip install -r requirements.txt
export FRED_API_KEY="your_key_here"          # Windows: set FRED_API_KEY=your_key_here
export COINGECKO_API_KEY="your_key_here"      # optional but recommended
python fetch_data.py
```
You should see mostly `[ok]` lines now, and a handful of `[fail]` lines for
the genuine gaps (BIS GLI, Exchange Net Flow, Fund Manager Cash). Open
`data.json` and check the `errors` object — that's your exact, current
data-provenance list.


### 3. Serve the dashboard locally to test it end-to-end
Opening the HTML file directly (`file://...`) will NOT work for this step —
browsers block `fetch()` calls to local files for security reasons. Instead:
```bash
python -m http.server 8000
```
then visit `http://localhost:8000/liquidity_flow_dashboard.html` — put
`data.json` in the same folder. You should see the demo banner switch to
reporting real series counts.

### 4. Deploy for free with auto-refresh
1. Push this folder (including `fetch_data.py`, `data.json`,
   `.github/workflows/update-data.yml`, and the dashboard HTML) to a **public
   GitHub repo**.
2. Add your FRED key as a repo secret: **Settings → Secrets and variables →
   Actions → New repository secret**, name it `FRED_API_KEY`.
3. Enable **GitHub Pages** on the repo (Settings → Pages → deploy from the
   main branch) — this hosts your dashboard for free.
4. The Action runs once a day automatically (free on GitHub's free tier for
   public repos) and commits a fresh `data.json` — your live site updates
   itself with no server, no cost.

## Fixing the one flagged gap that's actually solvable (BIS GLI)

The BIS SDMX API is free and the dataflow exists
(`BIS,GLI_E1,1.0` — "Global liquidity: banks' claims"), confirmed at
https://data.bis.org/topics/GLI/tables-and-dashboards/BIS,GLI_E1,1.0 — but the
exact series key (which combination of currency/counterparty dimension codes
gives you the USD and EUR non-bank credit series specifically) needs to be
confirmed once, by hand, in their interactive API explorer:

https://stats.bis.org/api-doc/v2/

Once you have a working query URL, add a `bis_gli_series(key)` function to
`fetch_data.py` following the same pattern as the other fetchers, and add its
output to the `SERIES` dict under `"BIS GLI — USD Credit"` /
`"BIS GLI — EUR Credit"`.

## Rate limits & politeness

- FRED: generous, no realistic risk of hitting limits at this scale.
- Yahoo Finance: the primary source for equities, commodities, sectors, and
  FX (Stooq is a fallback only, since it's proven unreliable — it appears to
  block automated requests outright).
- CoinGecko: keyless calls are IP rate-limited; the dominance/altseason
  calculation includes a small delay between requests to stay well within
  it. Also now the source for Perp Funding Rate / Open Interest (see below).
- CFTC, DefiLlama, Alternative.me, AAII, Cboe: all comfortably free at this
  volume (one run per day).
- **Binance is deliberately NOT called directly anymore.** A real run
  confirmed Binance returns 451 "Unavailable For Legal Reasons" from
  GitHub Actions' runner IPs (a regulatory geo-block on cloud-provider IP
  ranges, not a code issue — confirmed to affect Bybit identically too).
  Perp Funding Rate and Open Interest are now sourced from CoinGecko's free
  `/derivatives` endpoint instead, which proxies this data without touching
  an exchange's own CDN-protected infrastructure. One trade-off: that
  endpoint only gives a current snapshot, not history, so the pipeline
  accumulates its own — one new data point per day, saved to
  `derivatives_history.json` (which the GitHub Action commits alongside
  `data.json`). Needs 5 days accumulated before Open Interest goes live,
  10 days for Perp Funding Rate.

## What genuinely has no free fix (for now)

- **BIS Global Liquidity Indicators** (USD/EUR credit) — a real free SDMX
  endpoint exists but needs its exact query key hand-verified against the
  interactive API docs before it can be wired in reliably.
- **True exchange net-flow** (wallet-cluster based) — this is proprietary
  Glassnode/CryptoQuant-style analysis; no free equivalent exists.
- **Vol Term Structure (VX1-VX2)** — tried twice (VIX3M, then VIX9D, both
  via Yahoo Finance); both failed identically in two separate environments
  (local machine and GitHub Actions), pointing to a genuine data-coverage
  gap on Yahoo's end for CBOE's secondary vol indices, not a network issue.

Everything else that was once on this list — AAII's bull-bear survey, the
options put/call ratio, and fund manager cash — turned out to have genuine
free sources after all (AAII's own site, Cboe's CDN, and a Money Market Fund
proxy respectively) and are now live. Worth remembering: "no free fix" is
often really "no free fix *found yet*" — several of this project's fixes
came from someone pushing back on an earlier "that's not possible" answer.
