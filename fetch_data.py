#!/usr/bin/env python3
"""
Capital Tide — free data fetch pipeline
=========================================
Pulls real series from free sources and writes data.json in the shape the
dashboard (liquidity_flow_dashboard.html) expects. Run this on a schedule
(see .github/workflows/update-data.yml) — it's designed to run for free
forever on GitHub Actions.

FREE SOURCES USED (all confirmed free-tier / keyless as of build time):
  - FRED (api.stlouisfed.org)        — needs a free API key, sign up at
                                        https://fredaccount.stlouisfed.org
                                        (also used for the Fund Manager Cash
                                        Level proxy — see mmf_cash_proxy())
  - Yahoo Finance chart endpoint      — no key (primary equity/commodity/FX
                                        source; Stooq kept only as a fallback
                                        since it's proven unreliable — likely
                                        blocking automated requests outright)
  - Stooq (stooq.com)                — no key, fallback only
  - CoinGecko (api.coingecko.com)    — free Demo API key required now for
                                        reliable access (sign up free, see
                                        README_DATA_SETUP.md)
  - DefiLlama (stablecoins.llama.fi) — no key
  - CFTC Socrata (publicreporting.cftc.gov) — no key
  - Binance public futures API       — no key (market data endpoints only)
  - Alternative.me (api.alternative.me) — no key
  - AAII (aaii.com/files/surveys/sentiment.xls) — no key, no login
  - Cboe (cdn.cboe.com)               — no key

Keys persist across runs via a ".env" file in this folder (loaded
automatically via python-dotenv) — see README_DATA_SETUP.md.

HONEST GAPS (left synthetic on purpose — see README_DATA_SETUP.md):
  - BIS Global Liquidity Indicators (USD/EUR credit) — a real free SDMX
    endpoint exists (dataflow BIS,GLI_E1,1.0 at stats.bis.org) but needs its
    exact series key confirmed via the interactive API docs before it can be
    wired in reliably. Left as a clearly-flagged TODO.
  - True exchange net-flow (on-chain wallet clustering) — no free
    equivalent exists; this is proprietary Glassnode/CryptoQuant-style data.

NOTE on Fund Manager Cash Level: this is now a genuine free PROXY, not the
BofA survey itself. It uses weekly Retail + Institutional Money Market Fund
assets (Fed H.6 release data, on FRED as WRMFSL/WIMFSL) — ICI and the Fed
both describe MMF asset changes as a real directional signal for cash
flows into cash-like instruments. Detrended into an oscillator so it reads
like every other series here. It will track BofA's actual survey directionally
at times and diverge at others — treat it as "a" cash-preference signal,
not "the" one.

NOTE on Equity Put/Call Skew: this is CBOE's own SKEW Index (^SKEW on Yahoo
Finance), not a literal 25-delta put/call skew calculation — a closely
related, well-established tail-risk measure, not an identical one.

NOTE on Vol Term Structure (VX1-VX2): this is VIX vs VIX3M (both CBOE spot
volatility indices, free via Yahoo Finance), not literal VIX futures
term structure. Building the real VX1-VX2 futures spread requires
contract-roll logic against CFE settlement files with no clean,
verifiable-from-here download URL — a much bigger undertaking than
anything else here. VIX/VIX3M carries the same conceptual signal
(contango vs backwardation) without that fragility.

Every fetch is wrapped so one failing series never breaks the whole run —
you'll always get a data.json, just with some series flagged as unavailable
and left for the dashboard to fall back to synthetic data for that one
series only.
"""

import os
import json
import time
from datetime import datetime, timezone

import requests

# Load a .env file if present, so you don't have to re-export your keys in
# every new terminal session (this is the #1 cause of "FRED_API_KEY not set"
# errors that show up even after you've set the key once before).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — fall back to real env vars only

FRED_API_KEY = os.environ.get("FRED_API_KEY", "").strip()
COINGECKO_API_KEY = os.environ.get("COINGECKO_API_KEY", "").strip()

# --- Loud, impossible-to-miss startup diagnostic ---------------------------
print("=== Capital Tide data fetch — key check ===")
print(f"  FRED_API_KEY:      {'set (' + FRED_API_KEY[:4] + '...)' if FRED_API_KEY else 'NOT SET — every FRED series below will fail'}")
print(f"  COINGECKO_API_KEY: {'set (' + COINGECKO_API_KEY[:4] + '...)' if COINGECKO_API_KEY else 'NOT SET — CoinGecko calls will 401/429 almost immediately'}")
if not FRED_API_KEY or not COINGECKO_API_KEY:
    print("""
  --------------------------------------------------------------------
  Missing key(s) detected. Easiest fix: create a file named ".env" in
  this same folder (next to fetch_data.py) containing:

      FRED_API_KEY=your_fred_key_here
      COINGECKO_API_KEY=your_coingecko_key_here

  This persists across every future run — no need to re-export in each
  new terminal. Get keys free at:
      FRED:       https://fredaccount.stlouisfed.org
      CoinGecko:  https://www.coingecko.com/en/api/pricing
  --------------------------------------------------------------------
""")
print("=== Starting fetch ===\n")

# Stooq (and some other free endpoints) block requests that identify as a
# script/bot. A standard browser User-Agent is a normal, widely-used way to
# access public, freely-downloadable data endpoints like this — it's not
# bypassing any paywall or authentication, just avoiding basic bot
# fingerprinting on a page that's meant for free public downloads anyway.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
})
# NOTE: the CoinGecko key is deliberately NOT added to SESSION.headers here —
# it's only attached per-request inside coingecko_market_chart(), so it's
# never sent to FRED/Stooq/CFTC/etc.

SERIES = {}      # flat map: series name -> list[float] (chronological)
COT = {}         # map: display name -> list[float] (net position, chronological)
CRYPTO_EXTRA = {}  # BTC Dominance / Altseason Index / Stablecoin Supply / Perp Funding Rate
SECTORS = {}     # ticker -> list[float]
ERRORS = {}      # name -> reason string, for transparency


def log_ok(label, n):
    print(f"[ok]   {label}: {n} points")


def log_fail(label, err):
    print(f"[fail] {label}: {err}")
    ERRORS[label] = str(err)


# ---------------------------------------------------------------------------
# FRED
# ---------------------------------------------------------------------------
def fred_series(series_id, start="2023-01-01"):
    if not FRED_API_KEY:
        raise RuntimeError("FRED_API_KEY not set (get a free key at fredaccount.stlouisfed.org)")
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start,
    }
    r = SESSION.get(url, params=params, timeout=20)
    r.raise_for_status()
    payload = r.json()
    # FRED returns a 200 OK even for a bad series_id, with an error_message
    # field instead of "observations" — surface that directly rather than
    # letting it fall through to a generic "insufficient data" message that
    # hides the actual cause (e.g. a renamed/discontinued series ID).
    if "error_message" in payload:
        raise RuntimeError(f"FRED error for {series_id!r}: {payload['error_message']}")
    obs = payload.get("observations", [])
    vals = [float(o["value"]) for o in obs if o.get("value") not in (".", "", None)]
    if len(vals) < 10:
        raise RuntimeError(f"insufficient data returned for {series_id!r} ({len(vals)} usable points)")
    return vals


# ---------------------------------------------------------------------------
# Stooq — free daily OHLC, no key
# ---------------------------------------------------------------------------
def stooq_series(ticker, keep_last=500):
    url = f"https://stooq.com/q/d/l/?s={ticker}&i=d"
    r = SESSION.get(url, timeout=20)
    r.raise_for_status()
    lines = r.text.strip().splitlines()
    if len(lines) < 10 or "Date" not in lines[0]:
        raise RuntimeError(f"unexpected stooq response for {ticker}: {lines[0][:80]!r}")
    closes = []
    for row in lines[1:]:
        parts = row.split(",")
        if len(parts) < 5:
            continue
        try:
            closes.append(float(parts[4]))
        except ValueError:
            continue
    if len(closes) < 10:
        raise RuntimeError("insufficient data returned")
    return closes[-keep_last:]


# ---------------------------------------------------------------------------
# Yahoo Finance chart endpoint — free, no key, no login. Used as the primary
# source below because Stooq has proven unreliable in practice (it appears
# to be blocking automated requests outright — likely a Cloudflare-style
# challenge that no amount of header-tweaking can satisfy from a plain HTTP
# client, rather than something fixable by request headers alone).
# ---------------------------------------------------------------------------
def yahoo_chart_series(symbol, keep_last=500):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    r = SESSION.get(url, params={"range": "2y", "interval": "1d"}, timeout=20)
    r.raise_for_status()
    data = r.json()
    result = (data.get("chart") or {}).get("result")
    if not result:
        raise RuntimeError(f"unexpected Yahoo response shape for {symbol}")
    closes = result[0]["indicators"]["quote"][0]["close"]
    closes = [c for c in closes if c is not None]
    if len(closes) < 10:
        raise RuntimeError("insufficient data returned")
    return closes[-keep_last:]


def equity_series(yahoo_symbol, stooq_ticker, keep_last=500):
    """Tries Yahoo first (more reliable in practice), falls back to Stooq."""
    try:
        return yahoo_chart_series(yahoo_symbol, keep_last)
    except Exception as e_yahoo:
        try:
            return stooq_series(stooq_ticker, keep_last)
        except Exception as e_stooq:
            raise RuntimeError(f"Yahoo failed ({e_yahoo}); Stooq also failed ({e_stooq})")


# ---------------------------------------------------------------------------
# CoinGecko — free tier, no key required for these endpoints
# ---------------------------------------------------------------------------
def coingecko_market_chart(coin_id, days=365, max_retries=3):
    """Returns (prices, market_caps) as parallel chronological lists.
    Uses the free Demo API key if COINGECKO_API_KEY is set (sign up free at
    coingecko.com/en/api/pricing) — fully keyless calls are rate-limited very
    aggressively and will 429 quickly if you're fetching more than a couple
    of coins in a run.

    Two things changed here after a real 401-despite-valid-key report:
    1. The key is now sent BOTH as the `x-cg-demo-api-key` header and as the
       `x_cg_demo_api_key` query parameter — CoinGecko's docs show both forms
       and one has been more reliable than the other depending on the exact
       endpoint/plan, so sending both is a safe belt-and-suspenders fix.
    2. `days` is capped at 365 by default (was 760) — CoinGecko's free Demo
       tier restricts historical range to 1 year; requesting more than that
       can itself trigger a 401 even with a valid key. This does mean the
       "1 year ago" crypto comparison will have thinner history, but the
       front-end already clamps gracefully when a lookback window exceeds
       available data.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    headers = {}
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    if COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = COINGECKO_API_KEY
        params["x_cg_demo_api_key"] = COINGECKO_API_KEY
    for attempt in range(max_retries):
        r = SESSION.get(url, params=params, headers=headers, timeout=25)
        if r.status_code == 429:
            wait = 15 * (attempt + 1)
            print(f"  (rate limited on {coin_id}, waiting {wait}s before retry {attempt+1}/{max_retries})")
            time.sleep(wait)
            continue
        if r.status_code == 401:
            raise RuntimeError(
                "401 Unauthorized even with a key set — double-check your "
                ".env file has no extra quotes or spaces around the key "
                "(should be exactly: COINGECKO_API_KEY=CG-xxxxxxx, no "
                "quotation marks), and confirm the key shows as 'Active' on "
                "https://www.coingecko.com/en/developers/dashboard"
            )
        r.raise_for_status()
        data = r.json()
        prices = [p[1] for p in data.get("prices", [])]
        mcaps = [m[1] for m in data.get("market_caps", [])]
        if len(prices) < 10:
            raise RuntimeError("insufficient data returned")
        return prices, mcaps
    raise RuntimeError(f"gave up after {max_retries} retries (rate limited) — "
                        f"set COINGECKO_API_KEY for a much higher free limit")


# Basket used to self-compute BTC dominance & an altcoin-season proxy for
# free, since CoinGecko's free tier only gives *current* dominance, not
# history. This is an approximation (misses the very long tail of small
# coins) but tracks direction/trend accurately, which is what the
# dashboard's z-scores actually need.
DOMINANCE_BASKET = [
    "bitcoin", "ethereum", "tether", "binancecoin", "solana", "usd-coin",
    "ripple", "cardano", "dogecoin", "tron", "avalanche-2", "chainlink",
    "polkadot", "the-open-network", "litecoin",
]


def fetch_coin_basket():
    """Fetches price + market-cap history once for the whole basket (used for
    both the plain BTC/ETH series and the dominance/altseason calc below) —
    avoids hitting CoinGecko twice for the same coins."""
    basket_mcaps, basket_prices = {}, {}
    for coin_id in DOMINANCE_BASKET:
        try:
            prices, mcaps = coingecko_market_chart(coin_id)
            basket_mcaps[coin_id] = mcaps
            basket_prices[coin_id] = prices
            time.sleep(1.5 if COINGECKO_API_KEY else 7)  # keyless tier is rate-limited hard
        except Exception as e:
            print(f"  (basket coin {coin_id} skipped: {e})")
    return basket_prices, basket_mcaps


def compute_dominance_and_altseason(basket_prices, basket_mcaps):
    if "bitcoin" not in basket_mcaps:
        raise RuntimeError("could not fetch BTC market cap — basket calc aborted")

    n = min(len(v) for v in basket_mcaps.values())
    total = [sum(v[-n + i] for v in basket_mcaps.values()) for i in range(n)]
    btc_dom = [100.0 * basket_mcaps["bitcoin"][-n + i] / total[i] for i in range(n)]

    # Altseason index: for each day, % of basket (excluding BTC & stablecoins)
    # whose trailing-90-day return beats BTC's trailing-90-day return.
    alt_ids = [c for c in basket_prices if c not in ("bitcoin", "tether", "usd-coin")]
    window = 90
    altseason = []
    btc_p = basket_prices["bitcoin"]
    m = min(len(btc_p), *(len(basket_prices[c]) for c in alt_ids)) if alt_ids else 0
    for i in range(window, m):
        btc_ret = (btc_p[-m + i] / btc_p[-m + i - window]) - 1
        beating = 0
        for c in alt_ids:
            p = basket_prices[c]
            alt_ret = (p[-m + i] / p[-m + i - window]) - 1
            if alt_ret > btc_ret:
                beating += 1
        altseason.append(100.0 * beating / len(alt_ids))

    return btc_dom, altseason


# ---------------------------------------------------------------------------
# DefiLlama — free, no key
# ---------------------------------------------------------------------------
def defillama_stablecoin_supply():
    url = "https://stablecoins.llama.fi/stablecoincharts/all"
    r = SESSION.get(url, timeout=25)
    r.raise_for_status()
    rows = r.json()
    vals = []
    for row in rows:
        usd = (row.get("totalCirculating") or {}).get("peggedUSD")
        if usd is not None:
            vals.append(float(usd) / 1e9)  # in $B
    if len(vals) < 10:
        raise RuntimeError("insufficient data returned")
    return vals[-500:]


# ---------------------------------------------------------------------------
# CFTC — official Socrata API, free, no key
# ---------------------------------------------------------------------------
def cftc_cot_net_position(name_filter, limit=250):
    """Net non-commercial (speculator) position = long - short, weekly,
    chronological. `name_filter` is matched against market_and_exchange_names
    with a case-insensitive LIKE.

    NOTE: field names below (noncomm_positions_long_all /
    noncomm_positions_short_all) match the standard CFTC Legacy Combined
    report schema at the time this was written. If CFTC renames columns,
    this will raise and simply fall back to synthetic for COT — verify
    against https://publicreporting.cftc.gov/resource/jun7-fc8e.json if it
    ever stops working.
    """
    url = "https://publicreporting.cftc.gov/resource/jun7-fc8e.json"
    # NOTE: pass a plain '%' wildcard here — requests/urllib will percent-encode
    # the whole string exactly once when building the query string. Manually
    # writing '%25' here (an earlier bug) caused double-encoding, so Socrata
    # searched for the literal text "%25GOLD%25" instead of a wildcard match,
    # which is why it returned zero rows.
    params = {
        "$where": f"market_and_exchange_names like '%{name_filter}%'",
        "$order": "report_date_as_yyyy_mm_dd ASC",
        "$limit": limit,
    }
    r = SESSION.get(url, params=params, timeout=25)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise RuntimeError(f"no rows returned for filter {name_filter!r}")

    # A loose LIKE filter (e.g. "%GOLD%" or "%WTI%") can match MULTIPLE
    # distinct CFTC-listed contracts at once (e.g. regular vs micro
    # contracts). A real test run caught this: values were alternating
    # between two completely different scales because rows from two
    # different markets were interleaved by date. Fix: group by the exact
    # market_and_exchange_names string and keep only whichever single
    # market has the most reports (almost always the main, most-traded
    # contract) — discard the rest.
    by_market = {}
    for row in rows:
        name = row.get("market_and_exchange_names", "")
        by_market.setdefault(name, []).append(row)
    dominant_name = max(by_market, key=lambda k: len(by_market[k]))
    if len(by_market) > 1:
        print(f"  (note: '{name_filter}' matched {len(by_market)} distinct markets — "
              f"using '{dominant_name}' with {len(by_market[dominant_name])} rows, discarding the rest)")
    rows = sorted(by_market[dominant_name], key=lambda r: r.get("report_date_as_yyyy_mm_dd", ""))

    vals = []
    for row in rows:
        try:
            long_ = float(row["noncomm_positions_long_all"])
            short_ = float(row["noncomm_positions_short_all"])
            vals.append(long_ - short_)
        except (KeyError, ValueError):
            continue
    if len(vals) < 10:
        raise RuntimeError("insufficient parsable rows")
    return vals


# ---------------------------------------------------------------------------
# Binance public futures API — free, no key, market data only
# ---------------------------------------------------------------------------
def binance_funding_rate_history(symbol="BTCUSDT", limit=500):
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    r = SESSION.get(url, params={"symbol": symbol, "limit": limit}, timeout=20)
    r.raise_for_status()
    rows = r.json()
    vals = [float(x["fundingRate"]) for x in rows]
    if len(vals) < 10:
        raise RuntimeError("insufficient data returned")
    return vals


def binance_open_interest_hist(symbol="BTCUSDT", period="1d", limit=30):
    """Free tier only exposes the trailing ~1 month — this will build up
    real depth over time as the pipeline runs daily and results get
    appended by the GitHub Action (see README)."""
    url = "https://fapi.binance.com/futures/data/openInterestHist"
    r = SESSION.get(url, params={"symbol": symbol, "period": period, "limit": limit}, timeout=20)
    r.raise_for_status()
    rows = r.json()
    vals = [float(x["sumOpenInterestValue"]) / 1e9 for x in rows]  # $B
    if len(vals) < 5:
        raise RuntimeError("insufficient data returned")
    return vals


# ---------------------------------------------------------------------------
# Alternative.me — free crypto Fear & Greed Index, full history
# ---------------------------------------------------------------------------
def alternative_me_fear_greed():
    url = "https://api.alternative.me/fng/"
    r = SESSION.get(url, params={"limit": 0, "format": "json"}, timeout=20)
    r.raise_for_status()
    rows = r.json().get("data", [])
    vals = [float(x["value"]) for x in reversed(rows)]  # API returns newest-first
    if len(vals) < 10:
        raise RuntimeError("insufficient data returned")
    return vals[-500:]


# ---------------------------------------------------------------------------
# AAII — free, full-history Bull-Bear spread, no login required
# ---------------------------------------------------------------------------
def aaii_sentiment_history():
    """AAII publishes their full weekly Investor Sentiment Survey history for
    free, no login, at https://www.aaii.com/files/surveys/sentiment.xls —
    this was previously (incorrectly) flagged as having no free source.

    Requires the `xlrd` package (pinned to 1.2.0 in requirements.txt, since
    newer xlrd versions dropped .xls support).

    A real test run hit a 403 Forbidden here — same bot-blocking pattern as
    Stooq. Fixed the same way: a real Referer header plus a warm-up GET of
    the survey's normal landing page first, so the file request looks like
    it came from someone who actually browsed there, not a bare script hit.

    NOTE: the exact column layout is parsed defensively below (it scans for
    a header row mentioning "Bullish"/"Bearish" rather than hardcoding a
    column index), but this hasn't been run against a live copy of the file
    from this environment — if AAII changes their sheet layout, this will
    raise cleanly and just fall back to synthetic for this one series.
    """
    import xlrd
    import time as _time
    landing_url = "https://www.aaii.com/sentimentsurvey"
    file_url = "https://www.aaii.com/files/surveys/sentiment.xls"
    r = None
    last_err = None
    for attempt in range(3):
        try:
            try:
                SESSION.get(landing_url, timeout=15)  # warm-up: picks up any session cookie AAII sets
            except Exception:
                pass  # non-fatal — proceed to the file request either way
            r = SESSION.get(file_url, timeout=25, headers={"Referer": landing_url})
            r.raise_for_status()
            break
        except Exception as e:
            last_err = e
            r = None
            if attempt < 2:
                wait = 8 * (attempt + 1)
                print(f"  (AAII fetch blocked/failed, waiting {wait}s before retry {attempt+1}/2: {e})")
                _time.sleep(wait)
    if r is None:
        raise RuntimeError(f"AAII fetch failed after 3 attempts (likely a transient block, not a code issue): {last_err}")
    book = xlrd.open_workbook(file_contents=r.content)
    sheet = book.sheet_by_index(0)

    header_row, bull_col, bear_col = None, None, None
    for row_idx in range(min(20, sheet.nrows)):
        row_vals = [str(c).strip().lower() for c in sheet.row_values(row_idx)]
        if any("bullish" in v for v in row_vals) and any("bearish" in v for v in row_vals):
            header_row = row_idx
            bull_col = next(i for i, v in enumerate(row_vals) if "bullish" in v)
            bear_col = next(i for i, v in enumerate(row_vals) if "bearish" in v)
            break
    if header_row is None:
        raise RuntimeError("could not locate Bullish/Bearish header row — AAII may have changed their sheet layout")

    EMPTY_TYPES = (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK)
    vals = []
    for row_idx in range(header_row + 1, sheet.nrows):
        bull_cell = sheet.cell(row_idx, bull_col)
        bear_cell = sheet.cell(row_idx, bear_col)
        # A real test run showed the previous value-based guess ("skip if
        # both == 0.0") didn't actually catch the trailing bad rows — the
        # output was byte-identical before and after that fix, meaning
        # whatever's in those rows isn't a clean (0.0, 0.0) pair. This is
        # the technically correct fix instead: check xlrd's actual cell
        # type. A genuinely blank/empty Excel cell has ctype EMPTY or
        # BLANK regardless of what "value" it coerces to — this can't be
        # fooled the way a value-based guess can.
        if bull_cell.ctype in EMPTY_TYPES or bear_cell.ctype in EMPTY_TYPES:
            continue
        try:
            bull = float(bull_cell.value)
            bear = float(bear_cell.value)
        except (ValueError, TypeError):
            continue
        spread = (bull - bear) * 100.0
        # Belt-and-suspenders: a real AAII weekly reading landing on an
        # exact 0.00000% tie is vanishingly unlikely — if it happens, it's
        # far more likely a formatting artifact than genuine data.
        if spread == 0.0:
            continue
        vals.append(spread)
    if len(vals) < 10:
        raise RuntimeError("insufficient parsable rows")
    return vals[-500:]


# ---------------------------------------------------------------------------
# CBOE — free historical Total Put/Call ratio archive, no key
# ---------------------------------------------------------------------------
def cboe_put_call_ratio_history():
    """Cboe publishes free put/call ratio archives on their own CDN.
    NOTE: the exact filename below (totalpc.csv) follows the same naming
    pattern as their confirmed indexpcarchive.csv / equitypc.csv files, but
    hasn't been verified live from this environment — if it 404s, check
    https://www.cboe.com/us/options/market_statistics/historical_data/ for
    the current filename and update the URL below. Also note Cboe's archive
    files have historically lagged the present by some years; for the most
    recent data you may need Cboe's live daily-stats page instead.
    """
    url = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv"
    r = SESSION.get(url, timeout=25)
    r.raise_for_status()
    vals = []
    for line in r.text.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        try:
            vals.append(float(parts[-1]))  # last column is the P/C ratio
        except ValueError:
            continue
    if len(vals) < 10:
        raise RuntimeError("insufficient parsable rows — verify CDN filename against the live Cboe page")
    return vals[-500:]


# ---------------------------------------------------------------------------
# Equity Put/Call Skew — free proxy via CBOE's own SKEW Index (Yahoo Finance)
# ---------------------------------------------------------------------------
def skew_index_series():
    """Not literally a 25-delta put/call skew calculation — that's CBOE's own
    published SKEW Index instead, a closely related, well-established
    tail-risk measure, freely available via Yahoo Finance (ticker ^SKEW).
    Same conceptual signal (elevated = more tail-risk hedging demand in
    options pricing), different exact methodology.
    """
    return equity_series("^SKEW", "^skew")


# ---------------------------------------------------------------------------
# Vol Term Structure — free proxy via VIX vs VIX3M (both CBOE spot indices)
# ---------------------------------------------------------------------------
def vol_term_structure_proxy():
    """Not literally VX1-VX2 futures term structure — building that requires
    contract-roll logic against CFE futures settlement files with no clean,
    verifiable-from-here download URL, which is a much bigger and shakier
    undertaking than anything else in this pipeline. This is a cleaner,
    equally valid proxy instead: CBOE's own VIX (30-day) vs VIX3M (93-day)
    spot volatility indices, both freely available via Yahoo Finance. Same
    conceptual signal as futures term structure — contango (ratio < 1,
    calm) vs backwardation (ratio > 1, stress) — without needing to track
    individual futures contract expirations.
    """
    vix = yahoo_chart_series("^VIX", keep_last=500)
    vix3m = yahoo_chart_series("^VIX3M", keep_last=500)
    n = min(len(vix), len(vix3m))
    ratio = [vix[-n + i] / vix3m[-n + i] for i in range(n) if vix3m[-n + i] != 0]
    if len(ratio) < 10:
        raise RuntimeError("insufficient data returned")
    return ratio


# ---------------------------------------------------------------------------
# Fund Manager Cash Level — free proxy via weekly Money Market Fund assets
# (Fed H.6 release, sourced from the same underlying ICI data, on FRED)
# ---------------------------------------------------------------------------
def mmf_cash_proxy():
    """Not the BofA Global Fund Manager Survey — that stays behind a paywall.
    This is a genuine, well-established directional proxy instead: ICI and
    the Fed both describe money market fund asset changes as a proxy for
    net new cash flows into cash-like instruments. When investors/managers
    get defensive, MMF assets tend to build faster than trend; when they
    lean into risk, MMF growth lags or reverses.

    A real test run confirmed WRMFSL/WIMFSL are discontinued — FRED's own
    page for WRMFSL names its replacement as RMFSL. IMFSL (institutional) is
    inferred by the same naming pattern (the "W" dropped), not independently
    confirmed — if this fails too, that inference was wrong and needs a
    manual FRED search for the institutional counterpart specifically.

    The replacement series may also run at a different frequency (monthly
    rather than weekly) since the "W" convention is gone — so this pulls a
    much longer history and sizes the detrending window adaptively instead
    of assuming a fixed 90 points.
    """
    try:
        retail = fred_series("RMFSL", start="2010-01-01")
    except Exception as e:
        raise RuntimeError(f"Retail MMF series (RMFSL) failed: {e}")
    try:
        inst = fred_series("IMFSL", start="2010-01-01")
    except Exception as e:
        raise RuntimeError(f"Institutional MMF series (IMFSL, inferred ID) failed: {e}")
    n = min(len(retail), len(inst))
    total = [retail[-n + i] + inst[-n + i] for i in range(n)]
    # Adaptive window: ~1/4 of available history, floor 6, ceiling 90 — works
    # whether this turns out to be weekly or monthly data.
    window = max(6, min(90, n // 4))
    if len(total) <= window:
        raise RuntimeError(f"insufficient combined history for a {window}-point detrending window ({len(total)} points available)")
    oscillator = []
    for i in range(window, len(total)):
        ma = sum(total[i - window:i]) / window
        oscillator.append(100.0 * (total[i] - ma) / ma)
    if len(oscillator) < 10:
        raise RuntimeError(f"insufficient oscillator output ({len(oscillator)} points after detrending)")
    return oscillator


# =============================================================================
# RUN THE PIPELINE
# =============================================================================

def safe(label, store, fn, *args, **kwargs):
    try:
        val = fn(*args, **kwargs)
        store[label] = val
        log_ok(label, len(val))
    except Exception as e:
        log_fail(label, e)


print("=== Capital Tide data fetch starting ===\n")

# ---- LIQUIDITY (FRED) ----
safe("Fed Balance Sheet", SERIES, fred_series, "WALCL")
safe("TGA Balance", SERIES, fred_series, "WTREGEN")
safe("RRP Facility", SERIES, fred_series, "RRPONTSYD")
ERRORS["BIS GLI — USD Credit"] = (
    "BIS SDMX API (dataflow BIS,GLI_E1,1.0) exists and is free, but needs its "
    "exact series key confirmed at https://stats.bis.org/api-doc/v2/ before "
    "wiring in — left synthetic. See README_DATA_SETUP.md."
)
ERRORS["BIS GLI — EUR Credit"] = ERRORS["BIS GLI — USD Credit"]

# ---- FUNDING (FRED) ----
safe("DXY", SERIES, fred_series, "DTWEXBGS")
safe("10Y Real Yield", SERIES, fred_series, "DFII10")
safe("2s10s Curve", SERIES, fred_series, "T10Y2Y")
safe("HY OAS", SERIES, fred_series, "BAMLH0A0HYM2")
safe("IG Spread", SERIES, fred_series, "BAMLC0A0CM")
safe("VIX", SERIES, fred_series, "VIXCLS")
safe("Financial Conditions Idx", SERIES, fred_series, "NFCI")
try:
    d5 = fred_series("DGS5")
    d30 = fred_series("DGS30")
    n = min(len(d5), len(d30))
    SERIES["5s30s Curve"] = [d30[-n + i] - d5[-n + i] for i in range(n)]
    log_ok("5s30s Curve", n)
except Exception as e:
    log_fail("5s30s Curve", e)

# ---- RATES (FRED) ----
safe("2Y Yield", SERIES, fred_series, "DGS2")
safe("10Y Yield", SERIES, fred_series, "DGS10")

# ---- EQUITIES (Yahoo, falls back to Stooq) ----
safe("SPY", SERIES, equity_series, "SPY", "spy.us")
safe("QQQ", SERIES, equity_series, "QQQ", "qqq.us")
safe("ACWI", SERIES, equity_series, "ACWI", "acwi.us")
safe("Russell 2000", SERIES, equity_series, "IWM", "iwm.us")
safe("XLF (Financials)", SERIES, equity_series, "XLF", "xlf.us")

# ---- CREDIT (Yahoo, falls back to Stooq) ----
safe("HYG", SERIES, equity_series, "HYG", "hyg.us")
safe("LQD", SERIES, equity_series, "LQD", "lqd.us")

# ---- COMMODITIES (Yahoo, falls back to Stooq) ----
safe("Gold", SERIES, equity_series, "GC=F", "xauusd")
safe("Oil (WTI)", SERIES, equity_series, "CL=F", "cl.f")
safe("Copper", SERIES, equity_series, "HG=F", "hg.f")
safe("Broad Commodity Idx", SERIES, equity_series, "DBC", "dbc.us")

# ---- FX (Yahoo, falls back to Stooq) ----
safe("USDJPY", SERIES, equity_series, "JPY=X", "usdjpy")
safe("EM FX Basket", SERIES, equity_series, "CEW", "cew.us")  # approximation — see README

# ---- BONDS PROXY (for cross-asset correlation panel) ----
safe("Bonds (TLT proxy)", SERIES, equity_series, "TLT", "tlt.us")

# ---- CRYPTO (CoinGecko) — fetch the basket once, reuse for everything ----
_basket_prices, _basket_mcaps = {}, {}
try:
    _basket_prices, _basket_mcaps = fetch_coin_basket()
    if "bitcoin" in _basket_prices:
        SERIES["BTC"] = _basket_prices["bitcoin"]
        log_ok("BTC", len(_basket_prices["bitcoin"]))
    else:
        log_fail("BTC", "not present in basket fetch results")
    if "ethereum" in _basket_prices:
        SERIES["ETH"] = _basket_prices["ethereum"]
        log_ok("ETH", len(_basket_prices["ethereum"]))
    else:
        log_fail("ETH", "not present in basket fetch results")
except Exception as e:
    log_fail("BTC", e)
    log_fail("ETH", e)

# ---- BTC Dominance + Altseason (self-computed from the same basket, free) ----
try:
    dom, alt = compute_dominance_and_altseason(_basket_prices, _basket_mcaps)
    CRYPTO_EXTRA["BTC Dominance"] = dom
    CRYPTO_EXTRA["Altseason Index"] = alt
    log_ok("BTC Dominance (self-computed)", len(dom))
    log_ok("Altseason Index (self-computed)", len(alt))
except Exception as e:
    log_fail("BTC Dominance / Altseason Index", e)

# ---- Stablecoin supply (DefiLlama) ----
safe("Stablecoin Supply", CRYPTO_EXTRA, defillama_stablecoin_supply)

# ---- Perp funding rate + Open Interest (Binance) ----
safe("Perp Funding Rate (BTC)", CRYPTO_EXTRA, binance_funding_rate_history, "BTCUSDT")
safe("Open Interest ($B)", CRYPTO_EXTRA, binance_open_interest_hist, "BTCUSDT")

ERRORS["Exchange Net Flow"] = (
    "No free equivalent exists for real wallet-cluster exchange net-flow "
    "(this is proprietary Glassnode/CryptoQuant-style data) — left synthetic."
)

# ---- Crypto sentiment proxy (Alternative.me Fear & Greed) ----
safe("Crypto Fear & Greed", CRYPTO_EXTRA, alternative_me_fear_greed)

# ---- Equity sentiment: AAII (confirmed free, full-history, no login) ----
safe("AAII Bull-Bear Spread", SERIES, aaii_sentiment_history)

# ---- Put/Call ratio: Cboe free archive (confirmed free; see function docstring for the one caveat) ----
safe("Put/Call Ratio (total)", SERIES, cboe_put_call_ratio_history)

# ---- Fund Manager Cash Level: free MMF-based proxy (NOT the BofA survey
# itself — see mmf_cash_proxy()'s docstring for exactly what this is and isn't) ----
safe("Fund Manager Cash Level", SERIES, mmf_cash_proxy)

# ---- Derivatives bucket: SKEW proxy + VIX/VIX3M term structure proxy ----
safe("Equity Put/Call Skew", SERIES, skew_index_series)
safe("Vol Term Structure (VX1-VX2)", SERIES, vol_term_structure_proxy)

# ---- SECTORS (Stooq) ----
SECTOR_TICKERS = {
    "XLK": "xlk.us", "XLE": "xle.us", "XLF": "xlf.us", "XLI": "xli.us",
    "XLV": "xlv.us", "XLY": "xly.us", "XLP": "xlp.us", "XLU": "xlu.us",
    "XLB": "xlb.us", "XLRE": "xlre.us",
}
for tkr, sym in SECTOR_TICKERS.items():
    safe(tkr, SECTORS, equity_series, tkr, sym)  # Yahoo ticker == sector symbol itself

# ---- COT positioning (CFTC Socrata) ----
COT_FILTERS = {
    "DXY Futures": "DOLLAR INDEX",
    "Gold Futures": "GOLD",
    "WTI Crude Futures": "WTI",
    "S&P 500 E-mini": "E-MINI S&P 500",
}
for label, filt in COT_FILTERS.items():
    safe(label, COT, cftc_cot_net_position, filt)

# =============================================================================
# WRITE OUTPUT
# =============================================================================
output = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "series": SERIES,
    "cot": COT,
    "cryptoExtra": CRYPTO_EXTRA,
    "sectors": SECTORS,
    "errors": ERRORS,
}

with open("data.json", "w") as f:
    json.dump(output, f)

n_ok = len(SERIES) + len(COT) + len(CRYPTO_EXTRA) + len(SECTORS)
n_fail = len(ERRORS)
print(f"\n=== Done. {n_ok} series fetched live, {n_fail} flagged (see errors in data.json) ===")
