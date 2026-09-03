# Capital Tide — GitHub Deployment & Daily Auto-Fetch Guide

*Since you already have a GitHub account (MarketWall's home), this skips account setup and goes straight to getting Capital Tide live with a self-updating daily data feed.*

---

## What you're setting up

Right now, you run `fetch_data.py` by hand every time you want fresh data. After this guide:
- The dashboard lives at a real URL (free, via GitHub Pages)
- A robot (GitHub Actions) runs `fetch_data.py` for you **automatically, once a day, for free, forever**
- You never touch the terminal again unless you're changing the code itself

---

## Step 1 — Create the repository

1. Go to https://github.com/new
2. Repository name: `capital-tide` (or whatever you like)
3. **Public** (required for free GitHub Actions minutes and free GitHub Pages on a personal account)
4. Don't initialize with a README — you're uploading existing files
5. Click **Create repository**

---

## Step 2 — Upload your files

You have two options. Pick whichever you're comfortable with.

### Option A — Web upload (no command line, easiest)

1. On your new repo's page, click **"uploading an existing file"**
2. Drag in these files from your `capital_tide_data` folder:
   - `fetch_data.py`
   - `requirements.txt`
   - `liquidity_flow_dashboard.html` *(the public/community build — this is the one that goes live)*
   - `.gitignore`
   - `.env.example`
   - `README.md` *(GitHub shows this automatically on your repo's front page)*
   - `LICENSE`
   - `DISCLAIMER.md`
   - `CONTRIBUTING.md`
   - `LIVE_SITE.md`
   - `README_DATA_SETUP.md`
   - `DAILY_CHEATSHEET.md`
3. **Do NOT upload `.env`** (your real keys) or `data.json` yet — `.gitignore` already protects `.env` if you're using git directly, but the web upload tool doesn't check that, so just don't drag it in.
4. For the `.github/workflows/update-data.yml` file specifically: GitHub's drag-and-drop won't create the folder structure automatically. Instead:
   - Click **"Add file" → "Create new file"**
   - In the filename box, type: `.github/workflows/update-data.yml` (typing the slashes creates the folders)
   - Paste in the workflow file's contents
   - Commit

5. Keep `liquidity_flow_dashboard_personal.html` **off GitHub entirely** — that's your private daily-use copy with no gate. Keep it locally on your own machine only.

### Option B — Git command line (if you're comfortable with it)

```cmd
cd c:\temp\capital_tide_data
git init
git add fetch_data.py requirements.txt liquidity_flow_dashboard.html .gitignore .env.example README.md LICENSE DISCLAIMER.md CONTRIBUTING.md LIVE_SITE.md README_DATA_SETUP.md DAILY_CHEATSHEET.md .github
git commit -m "Initial Capital Tide deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/capital-tide.git
git push -u origin main
```
(Replace `YOUR_USERNAME` with your actual GitHub username.)

---

## Step 3 — Add your API keys as repository secrets

This is the **critical security step** — your keys must never appear in the actual code, only as encrypted secrets GitHub injects at run-time.

1. In your repo, go to **Settings → Secrets and variables → Actions**
2. Click **"New repository secret"**
3. Name: `FRED_API_KEY`, Value: your real FRED key → **Add secret**
4. Click **"New repository secret"** again
5. Name: `COINGECKO_API_KEY`, Value: your real CoinGecko key → **Add secret**

You should now see both listed (values hidden, names visible) under Repository secrets.

---

## Step 4 — Trigger the first data fetch manually

The workflow runs automatically once a day, but let's not wait — let's get real `data.json` live right now.

1. Go to the **Actions** tab in your repo
2. You should see **"Update Capital Tide data"** listed on the left
3. Click it, then click **"Run workflow"** (dropdown button on the right) → **"Run workflow"** again to confirm
4. Wait ~30–60 seconds, refresh the page — you should see a green checkmark
5. Click into that run to see the same log output you're used to seeing locally (all the `[ok]`/`[fail]` lines)
6. If it went green, check your repo's file list — `data.json` should now exist, auto-committed by the bot

If it fails: click into the run, expand the failing step, and the error will look identical to what you'd see locally — same fixes apply.

---

## Step 5 — Turn on GitHub Pages (this makes the site live)

1. Go to **Settings → Pages**
2. Under "Build and deployment" → Source: **Deploy from a branch**
3. Branch: **main**, folder: **/ (root)** → **Save**
4. Wait ~1 minute, then refresh — GitHub will show you the live URL, something like:
   ```
   https://YOUR_USERNAME.github.io/capital-tide/liquidity_flow_dashboard.html
   ```
5. Open that URL — this is now your **public, live, real-data dashboard**, no terminal required, viewable from any device.

---

## Step 6 — Confirm the daily schedule is live

The workflow (`.github/workflows/update-data.yml`) is already set to run once a day at **21:30 UTC** (30 minutes after the US market close). You don't need to do anything else — but to double check it's scheduled correctly:

1. Actions tab → "Update Capital Tide data" → you'll see past runs listed
2. Come back tomorrow and confirm a new run appeared automatically overnight
3. If you want a different time, edit the `cron` line in the workflow file (GitHub web editor works fine for this — click the file, pencil icon to edit)

---

## Your new daily reality

| Before | After |
|---|---|
| Open terminal, `python fetch_data.py`, wait, `python -m http.server` | Nothing — it already ran overnight |
| Open `localhost:8000/...` | Open your real `github.io` URL from anywhere, any device |
| Only you can see it | Anyone with the link can see the public/demo build |

Your **personal ungated copy** (`liquidity_flow_dashboard_personal.html`) stays local — just point it at the same `data.json` your GitHub repo generates. Two easy ways to do that:
- **Simplest**: after each Action run, download the fresh `data.json` from your repo and drop it next to your local personal HTML file.
- **Better**: host the personal copy locally but have it fetch `data.json` directly from your live GitHub Pages URL instead of a local file — ask me and I'll wire that in, it's a one-line change.

---

## Quick troubleshooting

| Symptom | Fix |
|---|---|
| Actions tab shows nothing to run | Confirm `.github/workflows/update-data.yml` uploaded with the exact folder path (case-sensitive) |
| Workflow run is red/failed | Click in, read the log — usually a missing/mistyped secret name |
| Pages URL 404s | Wait a minute after enabling Pages, then hard-refresh; confirm branch/folder settings match Step 5 |
| Dashboard loads but shows synthetic data | `data.json` isn't in the same folder as the HTML, or the Action hasn't run yet — check Step 4 |

---

*Once this is live, MarketWall and Capital Tide sit side by side on your GitHub profile — two real, working, daily-updating tools. Nice portfolio to have.*
