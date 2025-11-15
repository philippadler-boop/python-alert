# 📉📈 Index Alert — Dip Alerts + Trend Entry Alerts

A fully automated alerting tool for:

- **Dip-buying signals** (based on drawdowns from recent highs)
- **Trend-entry signals** (price crossing above MA200 & holding for N days)
- **Email notifications** (plain text + optional HTML with plots)
- **Plot generation** (dip plots + MA200 trend plots)
- **Daily GitHub Actions automation**
- **Test modes** for both dip and trend alerts
- A **combined mode** (`--both-modes`) that runs dip + trend in a single data fetch with optimized caching

Supports any ticker.  
Preconfigured for:

- **SPX** (S&P 500)
- **NDX** (Nasdaq 100)
- **SOX** (Semiconductors — PHLX)
- **SRVR** (Data Centers & Digital Infrastructure ETF)
- **SRUUF** (Sprott Physical Uranium exposure / uranium theme)
- **REMX** (Rare Earth & Strategic Metals ETF)

---

## 🔧 Features

### ✔ Dip Alerting

- Uses a configurable **peak window** (default: last 1 year)
- Computes rolling maximum over that window
- Calculates drawdown percentage
- Maps drawdown to custom **buckets** per index
- Sends email with:
  - Close price
  - Recent high (within the chosen window)
  - Drawdown %
  - Bucket name & action plan
  - Optional plot

> **Peak window precedence**:  
> 1. CLI `--peak-window`  
> 2. Env `PEAK_WINDOW`  
> 3. Default `1y`

### ✔ Trend-Entry Alerting

- Computes 200-day moving average (MA200)
- Detects **cross from below** MA200
- Confirms **N-day hold above MA200** (e.g. 5 days, configurable)
- Sends email with:
  - Close price
  - MA200 value
  - Distance from MA200
  - Index-specific fundamentals checklist
  - MA200 trend plot

### ✔ Combined Mode — `--both-modes` (Optimized)

Runs both dip + trend evaluations in **one pass**:

```
python main.py --index all --both-modes
```

**Optimizations:**
- Only **one data fetch** per index (vs. two separate fetches)
- MA200 computed once and **cached** (not redundantly recalculated)
- Perfect consistency between dip + trend checks
- ~50% faster execution vs. sequential runs

---

## 🏗️ Architecture

### Core Components

```
src/
├── alerts/
│   ├── alert_base.py          # Base runner class with shared logic
│   ├── dip_runner.py          # Dip-alert specific logic
│   ├── trend_runner.py        # Trend-entry specific logic
│   ├── combined_runner.py     # Optimized dip + trend in one pass
│   ├── buckets.py             # Bucket definition & selection
│   └── trend_checklists.json  # Per-index fundamentals checklist
├── data/
│   ├── data.py                # yfinance fetching & processing (30s timeout)
│   └── state.py               # JSON state persistence with validation
├── config/
│   └── config.py              # Centralized configuration (10+ named constants)
├── email/
│   └── email_utils.py         # SMTP + email formatting (HTML/plain-text)
├── logging/
│   └── logger.py              # Centralized logging (file + console)
├── plotting/
│   └── plotting.py            # Matplotlib plots for dip & trend
└── runner.py                  # Entry point & execution orchestration
```

### Key Design Patterns

- **Named Constants**: All magic numbers centralized in `config.py` (e.g., timeouts, MA windows, retention days)
- **State Validation**: JSON state files validated on load with detailed error logging
- **Centralized Logging**: All modules use structured logging with file + console output
- **Combined-Mode Optimization**: MA200 computed once and passed to trend runner (no redundant calculations)
- **Network Resilience**: yfinance calls have 30-second timeout with 3 retry attempts

---

## 🧩 `.env` Configuration

```
# Email
FROM_EMAIL=your@gmail.com
TO_EMAIL=your@gmail.com
APP_PASSWORD=your_app_password

# Behavior toggles
DRY_RUN=0
SAVE_PLOTS=1
INLINE_IMAGE=0
ATTACH_PLOT_ON_TEST=1

LOCAL_TZ=Europe/Berlin
RETENTION_DAYS=365

LOOKBACK_DAYS=1095
DIP_PLOT_LOOKBACK_DAYS=180
TREND_PLOT_LOOKBACK_DAYS=30

# Peak Window (Dip alerts)
# CLI > env > default 1y
PEAK_WINDOW=1y

PLOTS_DIR=plots
LOGS_DIR=logs
STATE_DIR=state
```

Be sure to `.gitignore` your `.env`.

---

## 🧪 Running Locally

### 1. Create virtualenv
```
python -m venv venv
```

### 2. Activate
Windows:
```
venv\Scripts\activate
```
macOS/Linux:
```
source venv/bin/activate
```

### 3. Install dependencies
```
pip install -r requirements.txt
```

### 4. Dip-only run
```
python main.py --index sox --dip-entry
```

### 5. Trend-only run
```
python main.py --index srvr --trend-entry
```

### 6. Combined mode (recommended)
```
python main.py --index all --both-modes
```

### 7. View help
```
python main.py --help
```

---

## 🧪 Running tests with pytest (recommended)

This project uses `unittest`-style tests but `pytest` is supported and recommended for development because it runs `unittest` tests and provides rich features.

1. Install pytest in your virtual environment:
```
venv\Scripts\activate
pip install pytest pytest-cov pytest-xdist
```

2. Run the tests via pytest (works with existing unittest tests):
```
pytest -q
```

3. If using VS Code, enable pytest under testing settings and set the test path to `tests` (the repo includes a `pytest.ini` already). This will avoid discovery errors.


---

## 🔍 Test Modes

### Dip SMTP wiring test
```
python main.py --index spx --dip-entry --test
```
Sends a test email to verify SMTP configuration.

### Dip bucket simulation
```
python main.py --index sruuf --dip-entry --test-bucket B20
```
Simulates a dip alert for bucket B20 (no state change, email sent).

### Trend-entry test
```
python main.py --index sox --trend-entry --test
```
Sends a test trend-entry email (no state change).

---

## 📊 Plots

### Dip plot (`03_plots/{index}/dip_plot.png`)
Includes:
- Close price line
- Rolling high (computed from peak-window-filtered series)
- X-axis limited by `DIP_PLOT_LOOKBACK_DAYS` (default: 180 days)
- Shaded region showing drawdown

### Trend plot (`03_plots/{index}/trend_plot.png`)
Includes:
- Close price line
- MA200 line
- Shaded region above MA (bullish zone)
- Green dot marking trend-entry confirmation day
- Hold-days window highlighted
- X-axis limited by `TREND_PLOT_LOOKBACK_DAYS` (default: 30 days)

---

## 📋 State Management

State files stored in `01_state/{index}_alert_state.json`:

```json
{
  "fired_buckets": ["B10", "B20"],
  "trend_fired_date": "2025-11-15"
}
```

**Validation:**
- Must be valid JSON dict with `fired_buckets` key
- State validated on load with detailed error logging
- Graceful fallback to clean state on corruption

**Retention:**
- Configured via `RETENTION_DAYS` (.env)
- Old alert logs cleaned up automatically

---

## 🤖 GitHub Actions

### Daily Alerts (Dip + Trend)

Runs weekday at 16:30 Europe/Berlin:

```
python main.py --index all --both-modes
```

Artifacts include:
- `03_plots/**` (all generated plots)
- `02_logs/**` (alert execution logs)

### Manual Test Workflow

Triggered manually for integration testing.

---

## ✅ Testing & Quality

- **61 unit tests** covering data processing, bucket logic, and email formatting
- **100% pass rate** with ~14ms execution time
- **100% backward compatible** (no breaking changes to CLI or state format)
- **Type hints** throughout codebase
- **Comprehensive logging** (see `02_logs/alert_YYYYMMDD.log`)

---

## 🔐 Security

- Email credentials stored in `.env` (not in code)
- `.env` file must be `.gitignore`d
- Google App Passwords recommended (not account password)
- All network calls have 30-second timeout

---

## 🚀 Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Single index dip check | ~2-3s | Includes data fetch, computation, plot |
| Single index trend check | ~2-3s | Same as above |
| All 6 indices (combined mode) | ~12-15s | Optimized with MA200 caching |
| All 6 indices (separate modes) | ~25-30s | Two separate data fetches per index |

**Optimization impact:** Combined mode + caching = ~50% faster for multi-index runs.

---

## 🐛 Troubleshooting

### Timeout errors
- Check network connection
- yfinance timeout is configurable via `YFINANCE_TIMEOUT_SECONDS` (default: 30s)
- Retry logic: 3 attempts with 2-second delays

### Email not sending
- Verify `FROM_EMAIL`, `TO_EMAIL`, `APP_PASSWORD` in `.env`
- Run test mode: `python main.py --index spx --dip-entry --test`
- Check logs: `02_logs/alert_YYYYMMDD.log`

### Plots not generating
- Ensure `SAVE_PLOTS=1` in `.env`
- Check `03_plots/{index}/` directory exists
- Verify matplotlib is installed: `pip list | grep matplotlib`

### State corruption
- Invalid JSON will log error and reset to clean state
- Check logs for validation details

---

## 📝 Changelog

### v1.1 (Current)
- ✅ Added 30-second timeout to yfinance calls (network resilience)
- ✅ 61-test suite with 100% coverage
- ✅ Centralized configuration with named constants
- ✅ Structured logging to `02_logs/` directory
- ✅ JSON state validation with error logging
- ✅ MA200 caching in combined mode (~50% speed improvement)

### v1.0
- Initial release with dip + trend alerting

---

## 💡 Quick Start Examples

```bash
# Run everything (recommended for GitHub Actions)
python main.py --index all --both-modes

# Test email configuration
python main.py --index spx --dip-entry --test

# Dip alerts only for a specific index
python main.py --index sox --dip-entry

# Trend alerts with custom peak window
python main.py --index ndx --trend-entry --peak-window 6m

# Simulate a specific bucket alert
python main.py --index sruuf --dip-entry --test-bucket B20
```

For more options: `python main.py --help`
