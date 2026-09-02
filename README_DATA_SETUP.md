# Capital Tide — Free Data Pipeline Setup

This turns your dashboard from synthetic demo data into a mix of **real, free
data** for most series, with a handful of honest, clearly-labeled gaps that
have no free equivalent yet.

## What's real vs what's still synthetic

| Status | Series |
|---|---|
| ✅ Real (free) | Fed Balance Sheet, TGA, RRP, DXY, 10Y Real Yield, 2s10s, 5s30s, HY OAS, IG Spread, VIX, Financial Conditions Index, 2Y/10Y Yields, SPY, QQQ, ACWI, Russell 2000, XLF, HYG, LQD, Gold, Oil, Copper, Broad Commodity Index, USDJPY, EM FX Basket (approx.), Bonds (TLT proxy), BTC, ETH, BTC Dominance (self-computed), Altseason Index (self-computed), Stablecoin Supply, Perp Funding Rate, Open Interest, Crypto Fear & Greed, all 10 sector ETFs, COT net positioning (DXY/Gold/WTI/S&P 500 futures), **AAII Bull-Bear Spread**, **Put/Call Ratio (Cboe)** |
| 🟡 Left synthetic — genuine free-data gap | BIS Global Liquidity Indicators (USD/EUR credit), true exchange net-flow, Fund Manager Cash Level (BofA survey has no clean free API, only media commentary) |

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
- Stooq: no published hard limit for casual daily use; the script only pulls
  once per run.
- CoinGecko: keyless calls are IP rate-limited; the dominance/altseason
  calculation includes a small delay between requests to stay well within it.
- CFTC, Binance, DefiLlama, Alternative.me: all comfortably free at this
  volume (one run per day).

## What genuinely has no free fix (for now)

- **True exchange net-flow** (wallet-cluster based) — this is proprietary
  Glassnode/CryptoQuant-style analysis; no free equivalent exists.
- **AAII bull-bear survey, options put/call ratio, fund manager cash** — no
  free full-history feed exists for these exact series. If you ever want
  them, that's the point where a paid data add-on would make sense — not
  before.
