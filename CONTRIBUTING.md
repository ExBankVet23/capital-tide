# Contributing to Capital Tide

Thanks for even considering it — this started as a solo build and any help is genuinely welcome.

## Ways to contribute

- **Found a bug in a data fetcher?** Open an issue with the exact error output from `fetch_data.py` — that's usually enough to diagnose and fix quickly (see the commit history for examples of exactly this pattern).
- **Know a free data source for one of the current gaps?** Check the Data Provenance panel in the dashboard, or the `errors` object in `data.json`, for the current honest list of what's still synthetic and why. A genuinely free, reliable source for any of those is a very welcome PR.
- **Design/UX improvements** — the dashboard is a single self-contained HTML file (`liquidity_flow_dashboard.html`), styled with plain CSS variables (see the `:root` block at the top). No build step, no framework — easy to fork and experiment with.
- **Documentation** — if something in the setup guides was unclear, a PR fixing it helps the next person more than you'd think.

## Ground rules

- **Keep the honesty principle intact.** If you add a new data source, always provide a clean synthetic fallback and be explicit in code comments and the Data Provenance panel about exactly what it is and isn't (see any existing `*_proxy()` function in `fetch_data.py` for the pattern).
- **No paid API dependencies** for anything in the core pipeline — the whole point of this project is that it runs for $0/month. If you want to add an optional paid-tier enhancement, gate it clearly behind an environment variable and document the free fallback.
- **Test before submitting.** `fetch_data.py` is designed so one failing series never breaks the whole run — if you add a new fetcher, wrap it the same way (see the `safe()` helper).

## Getting set up

See [`README.md`](README.md) for the quick start and [`README_DATA_SETUP.md`](README_DATA_SETUP.md) for the full data pipeline walkthrough.

## Questions

Open an issue, or use the contact details in the dashboard's Support section.
