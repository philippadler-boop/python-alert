# 📉 SPX Dip Alert — Automated Drawdown Email Notifications

This project monitors stock indices like the **S&P 500 (^GSPC)** and **NASDAQ 100 (^NDX)** and automatically sends email alerts whenever the market hits predefined **drawdown (“dip”) levels**.  
It works both **locally** and fully **automated in GitHub Actions**, meaning alerts continue even when your PC is off.

Alerts include:

- Drawdown % from the most recent high  
- Current index price  
- Recent high + date  
- Bucket triggered (–5%, –10%, –20%)  
- Your dip-buying plan instructions  
- Attached price chart  
- CSV logging of all alerts  

---

## 🚨 Dip Trigger Levels

By default (see `spx_alert/buckets.py`):

| Drawdown Range | Bucket | Action |
|----------------|--------|--------|
| –5% to –8%     | B10    | Deploy **10%** of cash bucket |
| –10% to –15%   | B20    | Deploy **20%** |
| –20% or more   | B70    | Deploy remaining **70%** in weekly tranches |

You can change these in `DEFAULT_BUCKETS`.

---

## 📦 Features

### ✔️ Drawdown Detection
- Fetches daily data via `yfinance`
- Computes drawdown from the latest rolling high
- Robust retries + errors surfaced via `DataFetchError`

### ✔️ Email Alerts (Gmail SMTP)
- Sends a formatted alert email (plain-text + HTML)
- Optional inline chart image (CID) and/or PNG attachment
- Uses Gmail App Password (secure OAuth alternative)
- `DRY_RUN` mode that prints instead of sending

### ✔️ Logging
- Per-index CSV log of all alerts  
- Automatic cleanup of logs & plots older than `RETENTION_DAYS`

### ✔️ GitHub Actions Automation
- Runs automatically **Monday–Friday** at a fixed time (cron in UTC)  
- Continues running even when your PC is off  
- Supports manual test runs using `--test-bucket` or `--test`

---

# 🔧 Configuration

Configuration is centralized in **`spx_alert/config.py`** and environment variables (usually via `.env`).

### Core environment variables

```env
# Email / SMTP
FROM_EMAIL=your@gmail.com
TO_EMAIL=your@gmail.com
APP_PASSWORD=your_app_password   # Gmail App Password (16 chars)

# Behavior toggles
DRY_RUN=0                        # 1 = log only, no emails
SAVE_PLOTS=1                     # 1 = generate plots, 0 = skip
INLINE_IMAGE=0                   # 1 = embed chart inline via CID
ATTACH_PLOT_ON_TEST=1            # 1 = attach plot in test-bucket mode

# Timezone & retention
LOCAL_TZ=Europe/Berlin
RETENTION_DAYS=365

# Index settings (optional overrides)
INDEX_TICKER=^GSPC               # default SPX ticker
NDX_TICKER=^NDX                  # default NDX ticker
LOOKBACK_DAYS=1095               # data lookback (days)
PLOT_LOOKBACK_DAYS=180           # shorter window for plots

# How to determine the "recent high" for drawdown
# 1y  = last 365 days
# ytd = since Jan 1 of current year
# date:YYYY-MM-DD = custom anchor date (e.g. when you started investing)
PEAK_WINDOW=1y

# Optional custom dirs (defaults shown in config.py)
# PLOTS_DIR=plots
# STATE_DIR=state
# LOGS_DIR=logs
```

> `.env` is **not committed** (ignored by `.gitignore`) so secrets stay local.

---

# 🖥️ Running Locally

## 1️⃣ Create and activate virtualenv

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

## 2️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

## 3️⃣ Run a normal check

```bash
python main.py
python main.py --index spx
python main.py --index ndx
```

### Useful CLI flags

```bash
python main.py --test
python main.py --index spx --test-bucket B10
python main.py --show-plot

# Use default window from PEAK_WINDOW (e.g. 1y)
python main.py --index remx

# Explicit 1-year peak window
python main.py --index remx --peak-window 1y

# Year-to-date peak
python main.py --index remx --peak-window ytd

# From a specific investment date
python main.py --index remx --peak-window date:2023-04-01

```

---

# 🧪 How Alerts Work

1. Fetch historical daily closes  
2. Compute drawdown  
3. Pick a bucket  
4. Check state  
5. Generate a plot  
6. Send email  
7. Log CSV  
8. Update state  

---

# 🧬 Project Structure

```text
python-alert/
├── main.py
├── requirements.txt
├── README.md
├── .env
├── spx_alert/
│   ├── config.py
│   ├── exceptions.py
│   ├── buckets.py
│   ├── data.py
│   ├── email_utils.py
│   ├── logging_utils.py
│   ├── plotting.py
│   ├── runner.py
│   └── state.py
├── logs/
├── plots/
├── state/
└── .github/
    └── workflows/
        └── alert.yml
```

---

# 🔐 GitHub Secrets

| Secret | Value |
|--------|--------|
| FROM_EMAIL | Gmail address |
| TO_EMAIL | Alert destination |
| APP_PASSWORD | Gmail App Password |

---

# 📊 Outputs

Plots → `plots/<index>/`  
Logs → `logs/<index>.csv`  

---

# 🔒 Security

- `.env` ignored by git  
- Gmail App Passwords  
- Encrypted GitHub Secrets  
