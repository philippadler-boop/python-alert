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

Create a `.env` file in the project root:

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

# Optional custom dirs (defaults shown in config.py)
# PLOTS_DIR=plots
# STATE_DIR=state
# LOGS_DIR=logs
.env is not committed (ignored by .gitignore) so secrets stay local.

🖥️ Running Locally
1️⃣ Create and activate virtualenv
bash
Code kopieren
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
2️⃣ Install dependencies
bash
Code kopieren
pip install -r requirements.txt
3️⃣ Run a normal check
Use the CLI entry main.py:

bash
Code kopieren
# Default index (spx)
python main.py

# Explicit index
python main.py --index spx
python main.py --index ndx
Useful CLI flags
bash
Code kopieren
# Send a simple SMTP wiring test (no buckets, no state)
python main.py --test

# Simulate a bucket alert (does NOT modify state)
python main.py --index spx --test-bucket B10
python main.py --index spx --test-bucket B20
python main.py --index spx --test-bucket B70

# Show plot after generation (local only, opens image viewer)
python main.py --index spx --test-bucket B10 --show-plot
python main.py --show-plot          # on a normal run
Behavior in test mode is controlled by:

DRY_RUN – if 1, emails are not actually sent

ATTACH_PLOT_ON_TEST – controls if the PNG is attached for simulated bucket alerts

🧪 How Alerts Work
On each run (per index):

Fetch historical daily closes from yfinance

Compute rolling high and current drawdown

Pick the matching bucket (if any) based on drawdown

Check state to avoid firing the same bucket for the same peak twice

Generate a plot (if SAVE_PLOTS=1)

Send email (or log only in DRY_RUN)

Append to CSV log

Update JSON state file

🧬 Project Structure
Typical layout:

text
Code kopieren
python-alert/
│
├── main.py                     # CLI entrypoint
├── requirements.txt
├── README.md
├── .env                        # local secrets (ignored by git)
│
├── spx_alert/
│   ├── __init__.py
│   ├── config.py               # env & index configuration
│   ├── exceptions.py           # custom exception classes
│   ├── buckets.py              # dip buckets
│   ├── data.py                 # fetching & drawdown
│   ├── email_utils.py          # email composition + sending
│   ├── logging_utils.py        # CSV & cleanup
│   ├── plotting.py             # plot generation
│   ├── runner.py               # main orchestration
│   └── state.py                # JSON state for fired buckets
│
├── logs/                       # per-index CSV logs
├── plots/                      # per-index PNG plots
├── state/                      # per-index JSON state
└── .github/
    └── workflows/
        └── alert.yml           # GitHub Actions workflow
🚀 GitHub Actions Automation
The workflow file lives at:

text
Code kopieren
.github/workflows/alert.yml
It typically:

Scheduled: runs Monday–Friday at a specific UTC time (configured via cron)

Manual: can be triggered via the Run workflow button in GitHub Actions

Inside the workflow you’d usually run:

bash
Code kopieren
python -m pip install -r requirements.txt
python main.py --index spx
(or with --index ndx, or multiple runs for multiple indices).

🔐 Required GitHub Secrets
Set these in:

Repo → Settings → Secrets and variables → Actions

Secret Name	Value
FROM_EMAIL	Your Gmail address
TO_EMAIL	Where alerts are sent
APP_PASSWORD	Gmail App Password (16 chars)

GitHub will expose them as environment variables during the workflow.

📊 Outputs
📈 Plot
Each alert can include a plot showing:

Recent close prices

Rolling recent high

Current price marker

Plots are saved under:

text
Code kopieren
plots/<index-id>/
Example:

text
Code kopieren
plots/spx/SPX_2024-01-02T16-30-00.png
🗂️ CSV Log
Per-index CSV logs live under:

text
Code kopieren
logs/
Each row tracks:

Timestamp (ts_iso)

Bucket (B10 / B20 / B70)

Drawdown %

Close

Peak

Peak date

Note / plan

Ticker

Test vs real flag

Plot path

🧹 Automatic Cleanup
On each run the script:

Deletes plot PNGs older than RETENTION_DAYS

Removes old rows from log CSVs older than RETENTION_DAYS

(Default retention: 30 in code, override via .env.)

🧠 Troubleshooting
“Email not sending”
Check:

DRY_RUN is 0

FROM_EMAIL, TO_EMAIL, and APP_PASSWORD are set correctly

The app password belongs to the FROM_EMAIL account

SMTP is not blocked by a firewall

“No alerts fire”
Possible reasons:

Drawdown does not fall into any bucket range

Bucket already fired for the current peak (state prevents duplicates)

Data fetch failed (see console logs / DataFetchError)

“Cron time is off”
Remember GitHub cron uses UTC.
If you want “16:30 Berlin” you must convert to the correct UTC time depending on DST.

🔒 Security
.env ignored via .gitignore

Gmail App Password used instead of your main password

GitHub Secrets encrypted in transit & at rest

SMTP connection uses TLS

Logs and state kept locally or in private repos