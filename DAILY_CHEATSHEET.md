# Capital Tide — Daily Cheat Sheet

*Keep this open in a tab. Two modes: **Manual** (what you're doing right now, testing locally) and <b>Automated</b> (once deployed — you barely touch it).*

\---

## 🖥️ MODE 1: Manual daily routine (local testing, right now)

Run these commands **in this exact order**, in `cmd.exe`, from your `capital\_tide\_data` folder:

```cmd
cd c:\\temp\\capital\_tide\_data
venv\\Scripts\\activate
python fetch\_data.py
```

**What that does:** activates your Python environment, then runs the pipeline — pulls fresh data from FRED/Yahoo/CoinGecko/CFTC/etc., computes the scores, and writes a new `data.json`.

**Then, to actually view the dashboard with that fresh data:**

```cmd
python -m http.server 8000
```

Open your browser to:

```
http://localhost:8000/liquidity\_flow\_dashboard.html
```

**When you're done looking:** go back to the terminal running the server and press `Ctrl+C` to stop it. You don't need to stop/restart anything for `fetch\_data.py` — it just runs once and exits each time.

### The 4-step daily loop, summarized

1. `venv\\Scripts\\activate`
2. `python fetch\_data.py` → wait for "Done. X series fetched live"
3. `python -m http.server 8000`
4. Refresh `http://localhost:8000/liquidity\_flow\_dashboard.html` in your browser

\---

## 🤖 MODE 2: Automated routine (once deployed to GitHub)

This is the end goal — once it's live, **your daily routine becomes "open the site."** Nothing to run.

**One-time deployment steps** (do these once, not daily):

1. Push the whole folder to a **public GitHub repo**.
2. Add `FRED\_API\_KEY` and `COINGECKO\_API\_KEY` as repo secrets: **Settings → Secrets and variables → Actions → New repository secret.**
3. Enable **GitHub Pages** (Settings → Pages → deploy from main branch).
4. Confirm the Action is enabled (Actions tab → "Update Capital Tide data").

**After that**, GitHub runs `fetch\_data.py` for you automatically once a day (free, no server needed) and commits a fresh `data.json`. Your dashboard reads whatever's latest every time someone visits.

**You only manually re-run anything if:**

* You want to force a refresh right now → go to the **Actions tab → "Update Capital Tide data" → Run workflow** (the manual trigger button)
* You changed `fetch\_data.py` itself and want to test the change

\---

## ✅ Quick sanity checklist after any run

|Check|Where|
|-|-|
|Did it say "X series fetched live" at the end?|Terminal output|
|How many are still `\[fail]`?|Terminal output — compare to last run|
|Does the demo banner say "N of M series are LIVE"?|Top of dashboard|
|Is "Data last fetched" recent?|Legal \& Disclaimer → Live data provenance|
|Any new/unexpected `\[fail]` lines?|Paste them to me — same process as always|

\---

## 🩹 Fast troubleshooting reference

|Symptom|Likely cause|Fix|
|-|-|-|
|`FRED\_API\_KEY not set`|`.env` file missing or has a typo|Check `.env` exists in the same folder, no quotes around the key|
|`401 Unauthorized` (CoinGecko)|Key not active yet, or extra quotes/spaces in `.env`|Check CoinGecko dashboard shows key as "Active"; re-check `.env` formatting|
|`403 Forbidden` (Stooq/AAII/any site)|Site's bot-blocking|Usually already handled with fallbacks — if a *new* one appears, paste me the exact error|
|Dashboard shows all synthetic data even after a good run|`data.json` not in the same folder as the HTML file, or browser cache|Confirm both files sit together; hard-refresh the browser (Ctrl+F5)|
|`python -m http.server` shows nothing at localhost:8000|Server not actually running, or wrong port already in use|Re-run the command; try port 8001 if 8000 is busy|

\---

## 🔑 Where things live (reminders)

* **Your keys**: `.env` file, never committed to GitHub (already in `.gitignore`)
* **Your wallet addresses**: hardcoded in `liquidity\_flow\_dashboard.html` (Support panel) — only touch these if you're changing wallets
* **Full setup instructions**: `README\_DATA\_SETUP.md`
* **What's live vs synthetic right now**: Legal \& Disclaimer section → "Live data provenance" box, inside the dashboard itself

\---

*Print this, pin it, or just keep it in the repo — either way, this is the whole operational loop in one page.*

