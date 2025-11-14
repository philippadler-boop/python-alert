# Python Alert System (Dip Alerts + Trend Entry Alerts)

This tool monitors multiple market indices and sends alerts under two independent conditions:

1. **Dip Alerts** – Triggered when drawdown reaches predefined buckets (e.g., -5%, -10%, -20%).
2. **Trend Entry Alerts** – Triggered when price crosses from **below to above the 200-day MA** and remains above for **5 consecutive trading days**, serving as a reminder to review sector fundamentals before entering positions.

---

## 🚀 Features

### ✅ Dip Alerts (Bucket-based)
- Computes drawdown relative to a configurable peak window:
  - `1y` (last 365 days)
  - `ytd`
  - `date:YYYY-MM-DD` (e.g., investment start)
- Bucket triggers configurable per index.
- Email includes:
  - Drawdown %
  - Recent high
  - Bucket plan
  - Chart (inline or attached)

### ✅ Trend Entry Alerts (MA200-based)
- Detects:
  - MA200 cross **from below**
  - **AND** stays above MA200 for 5 consecutive trading days.
- Uses **checklist reminders** stored externally in:
  ```
  spx_alert/trend_checklists.json
  ```
- Emails contain:
  - Price vs. MA200
  - % distance above MA200
  - Fundamentals checklist (TSMC CAPEX, PMI, AWS/Azure/Google CAPEX, etc.)

---

## 📁 Supported Index Proxies

| Index ID | Proxy Ticker | Sector / ETF |
|----------|--------------|---------------|
| `spx`    | ^GSPC        | S&P 500 |
| `ndx`    | ^NDX         | Nasdaq 100 |
| `sox`    | ^SOX         | Semiconductors (VanEck Semiconductor UCITS ETF) |
| `srvr`   | SRVR         | Data Center REITs (Global X Data Center & Digital Infrastructure ETF) |
| `ura`    | URA          | Uranium (WisdomTree Uranium & Nuclear Energy ETF) |
| `remx`   | REMX         | Rare Earths & Strategic Metals ETF |

---

## ⚙ Setup

### 1. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate    # macOS/Linux
venv\Scripts\activate     # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 📦 Environment Variables (`.env`)

```env
# Email / SMTP
FROM_EMAIL=your@gmail.com
TO_EMAIL=your@gmail.com
APP_PASSWORD=your_app_password

# Behavior toggles
DRY_RUN=0
SAVE_PLOTS=1
INLINE_IMAGE=0
ATTACH_PLOT_ON_TEST=1

# Timezone & retention
LOCAL_TZ=Europe/Berlin
RETENTION_DAYS=30

# Index settings (optional overrides)
LOOKBACK_DAYS=1095
PLOT_LOOKBACK_DAYS=180

# Peak window (dip alert mode)
# Options: 1y, ytd, date:YYYY-MM-DD
PEAK_WINDOW=1y

# Optional custom dirs
PLOTS_DIR=plots
LOGS_DIR=logs
STATE_DIR=state
```

---

## 🧪 Running the Tool

### **Dip Alerts**

Run dip alert for a single index:

```bash
python main.py --index spx
```

Run dip alerts for all indices:

```bash
python main.py --index all
```

Simulate a bucket (no state persistence):

```bash
python main.py --index spx --test-bucket B20
```

SMTP wiring test:

```bash
python main.py --index spx --test
```

Custom peak window:

```bash
python main.py --index sox --peak-window date:2023-04-01
```

---

### **Trend Entry Alerts**

Run for one:

```bash
python main.py --index sox --trend-entry
```

Run for all indices:

```bash
python main.py --index all --trend-entry
```

---

## 🧩 Trend Checklist Configuration

Edit:
```
spx_alert/trend_checklists.json
```

Example:

```json
{
  "sox": [
    "Check TSMC CAPEX guidance for 2026 (TSMC IR: https://investor.tsmc.com)",
    "Check Samsung CAPEX guidance for 2026 (Samsung IR: https://www.samsung.com/global/ir/)",
    "Check Electronics PMI ≥ 50 for 2 consecutive months (https://www.spglobal.com/marketintelligence/en/news-insights/latest-pmi)"
  ]
}
```

You may add: `srvr`, `ura`, `remx`, etc.

---

## 🧹 Git Ignore Recommendations

```
# Environment
.env

# Runtime files
state/
logs/
plots/

# OS garbage
.DS_Store
Thumbs.db
```

---

## 📡 GitHub Actions

To run all dip alerts daily:

```yaml
run: python main.py --index all
```

Trend entry daily check:

```yaml
run: python main.py --index all --trend-entry
```

Artifacts include logs & plots.

---

## 📊 Output

- Email alert (dip or trend entry)
- Optional attached chart
- CSV log entries
- Plots saved locally or uploaded by GitHub Actions

---

## 🧠 Future Additions

- Cooldown window for trend entries  
- Trend entry support for REMX  
- Telegram/Slack integration  
- Multi-timeframe trend checks  

---

## ✅ Summary

Your system now supports **automated dip alerts + structured trend-entry signals**, including JSON-based fundamental checklists.  
This enables consistent, rules-based staged entries into:

- Semiconductors  
- Data centers  
- Uranium  
- Rare earths  
- Index ETFs (SPX, NDX)

Ready for disciplined long-term allocation 🚀
