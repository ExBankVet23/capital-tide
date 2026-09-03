# 🌊 Capital Tide

**An open-source demonstration of how much macro liquidity data is genuinely reconstructable from free, public sources — a daily regime-scoring desk, built to showcase the data, not to advise on trades.**

![status](https://img.shields.io/badge/data-55%2F58%20series%20live-2ECC71)
![license](https://img.shields.io/badge/license-MIT-blue)
![cost](https://img.shields.io/badge/data%20cost-%240%2Fmonth-brightgreen)
![build](https://img.shields.io/badge/build-open%20%26%20community--supported-9B8CFF)

Capital Tide is a demonstration of how much macro and market data is genuinely reconstructable from free, public sources — Fed liquidity, funding conditions, and cross-asset data, scored into a single daily regime read. It's built as an **open analytical showcase**, not a trading or investment tool: the point is exploring how far free, public data can go, not telling anyone what to do with it.

🔗 **[Open the live dashboard →](https://exbankvet23.github.io/capital-tide/liquidity_flow_dashboard.html)**

---

## Why this exists

Most macro liquidity dashboards live behind institutional paywalls or cost hundreds a month in data fees. Capital Tide asks a simple question: **how much of that is actually reconstructable for free, if you're willing to be honest about the gaps?** The answer, it turns out, is most of it — currently **55 of 58 tracked series run on live data**, pulled from FRED, Yahoo Finance, CoinGecko, CFTC, Binance, DefiLlama, Alternative.me, AAII, and Cboe. The handful that don't have a free equivalent are labeled exactly as such, in plain sight, not hidden.

## What it does

- **Core Desk** — a single Regime Score (−3 to +3), a "Trickle-Down Sequence" showing exactly how far liquidity has travelled through the system, a 7-bucket destination heatmap (Equities, Credit, Commodities, Rates, FX, Crypto, Derivatives), and an always-visible **Data Provenance panel** showing precisely what's live vs. synthetic, right now
- **PRO/MAX** — sector rotation scorecard, crypto sub-structure (BTC dominance, altseason index, funding rate, open interest), an impact-weighted economic calendar, COT futures positioning, and cross-asset correlation
- **Compare** — how today's regime stacks up against 1 day / 1 week / 1 month / 3 months / 1 year ago, each recalculated as it would have read on that date, not just restated backward
- **Evaluation** — a plain-English cycle-position read (Contraction → Trough → Recovery → Expansion → Late Cycle), an Accumulation Radar surfacing momentum before it's obvious, and a Focus List translating it all into concrete tickers worth researching further
- **Flow Guide** — hover any dotted-underlined element anywhere in the tool for a plain-English explanation *and* a live "right now" reading, so the tool teaches its own framework as you use it

## Data sources — all free

| Layer | Source |
|---|---|
| Fed balance sheet, TGA, RRP, yields, spreads, VIX | [FRED](https://fred.stlouisfed.org) |
| Equities, commodities, sector ETFs | Yahoo Finance (Stooq fallback) |
| Crypto (BTC, ETH), self-computed dominance & altseason | [CoinGecko](https://www.coingecko.com) |
| Stablecoin supply | [DefiLlama](https://defillama.com) |
| Futures positioning (COT) | [CFTC](https://www.cftc.gov) official Socrata API |
| Perp funding rate, open interest | Binance public API |
| Crypto sentiment | [Alternative.me](https://alternative.me/crypto/fear-and-greed-index/) |
| Retail sentiment | AAII weekly survey (free download) |
| Options tail-risk, vol term structure proxy | Cboe SKEW Index, VIX/VIX3M (via Yahoo Finance) |
| Fund manager cash proxy | Money market fund assets (Fed H.6 / FRED) |

Two series remain synthetic on principle, not laziness — the exact reason is shown live in the dashboard's Data Provenance panel:
- **BIS Global Liquidity Indicators** — a free endpoint exists but needs its exact query key hand-verified
- **Exchange net-flow** — genuinely proprietary wallet-clustering data (Glassnode/CryptoQuant-style); no free equivalent exists

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/capital-tide.git
cd capital-tide
pip install -r requirements.txt
cp .env.example .env    # add your free FRED + CoinGecko API keys
python fetch_data.py
python -m http.server 8000
```
Then open `http://localhost:8000/liquidity_flow_dashboard.html`.

Want it live and self-updating every day, for free, via GitHub Actions? See [`GITHUB_DEPLOYMENT_GUIDE.md`](GITHUB_DEPLOYMENT_GUIDE.md).

## Methodology

Every score in Capital Tide follows the same rule: **confirmation across layers matters more than any single number.** A bucket score blends level, trend, and relative strength; the composite regime score blends Liquidity, Funding, Credit, and Destination Breadth. Full formulas and the underlying data schema are documented in-app under "Methodology & Data Schema" — built to be read and checked, not just trusted.

## FAQ

**Is this financial advice?**
No. Capital Tide is an educational and research tool — see the in-app Legal & Disclaimer section for the full detail. Nothing here is a recommendation to buy, sell, or hold anything.

**Who is this for?**
Anyone curious about macro data, open data engineering, or how much of an institutional-style analytics stack is genuinely buildable for free. It's a showcase of what's possible with public data, not a tool aimed at traders or investors — if you're here for the data pipeline and the "how," you're the target audience.

**Why is some data still synthetic?**
Total honesty by design: any series without a genuine free source stays clearly labeled as synthetic rather than silently faked. Check the Data Provenance panel for the live breakdown at any time.

**Can I run my own copy with different data or styling?**
Yes — it's a single self-contained HTML file plus a Python data pipeline, MIT-licensed. Fork it, change it, make it yours.

**How is this funded?**
It isn't, beyond optional community support — see the ☕ Support panel in the dashboard. No paywall, no subscription, no ads.

## Support this project

Capital Tide is independently built and community-supported — free to use, no paywall. If it's useful to you, there's a BTC/USDT tip option in the dashboard itself. Genuinely appreciated, never required.

## Disclaimer

Capital Tide is an educational and research tool. Nothing here constitutes financial, investment, legal, or tax advice. Always do your own research and consult a licensed, independent advisor before making investment decisions. Full disclaimer in-app.

## License

MIT — see [`LICENSE`](LICENSE). Use it, fork it, learn from it.
