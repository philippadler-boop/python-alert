# spx_alert/config.py
from __future__ import annotations

import os
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable, ignoring trailing comments.

    Allows values like "1095  # data lookback (days)" by stripping anything
    after a '#' and whitespace before converting to int. Falls back to the
    provided default on parse errors or empty values.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    # strip inline comments and whitespace
    cleaned = raw.split("#", 1)[0].strip()
    if cleaned == "":
        return default
    try:
        return int(cleaned)
    except (ValueError, TypeError):
        return default

# Root of the project (parent of this file's folder)
ROOT_DIR: Path = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------
# Core settings (global knobs)
# ---------------------------------------------------------------------

# Time windows (in days)
DAYS_PER_YEAR: int = 365
LOOKBACK_DAYS_DEFAULT: int = 1095  # 3 years
RETENTION_DAYS_DEFAULT: int = 30
DIP_PLOT_LOOKBACK_DAYS_DEFAULT: int = 180  # 6 months
TREND_PLOT_LOOKBACK_DAYS_DEFAULT: int = 30  # 1 month
MA_WINDOW_DEFAULT: int = 200  # Moving average window
TREND_HOLD_DAYS_DEFAULT: int = 5  # Days to hold above MA before alert

# Network settings
YFINANCE_TIMEOUT_SECONDS: int = 30
YFINANCE_RETRY_ATTEMPTS: int = 3
YFINANCE_RETRY_DELAY_SECONDS: int = 2

# How to define the "recent high" window for drawdown:
#  - "1y"            → last 365 days
#  - "ytd"           → since Jan 1 of current year
#  - "date:YYYY-MM-DD" → custom anchor date (e.g. investment start)
#  - anything else   → use full available history
PEAK_WINDOW_DEFAULT: str = os.getenv("PEAK_WINDOW", "1y").lower()

# Default SPX ticker (can be overridden via .env)
INDEX_TICKER: str = os.getenv("INDEX_TICKER", "^GSPC")

# Optional extra index ticker
NDX_TICKER: str = os.getenv("NDX_TICKER", "^NDX")

# How many calendar days of history to fetch
LOOKBACK_DAYS: int = _env_int("LOOKBACK_DAYS", LOOKBACK_DAYS_DEFAULT)

# Local timezone for timestamps
LOCAL_TZ: ZoneInfo = ZoneInfo(os.getenv("LOCAL_TZ", "Europe/Berlin"))

# If set, we log what would have happened but don't actually send emails
DRY_RUN: bool = os.getenv("DRY_RUN", "0") == "1"

# Whether to generate plots at all
SAVE_PLOTS: bool = os.getenv("SAVE_PLOTS", "1") == "1"

# HTML e-mail options
INLINE_IMAGE: bool = os.getenv("INLINE_IMAGE", "0") == "1"

# Attach plot also in test mode? (for future use / clarity)
ATTACH_PLOT_ON_TEST: bool = os.getenv("ATTACH_PLOT_ON_TEST", "1") == "1"

# How long to keep logs and plots
RETENTION_DAYS: int = _env_int("RETENTION_DAYS", RETENTION_DAYS_DEFAULT)

# Base directories
STATE_DIR: Path = (ROOT_DIR / "01_state").resolve()
LOGS_DIR: Path = (ROOT_DIR / "02_logs").resolve()
PLOTS_DIR: Path = (ROOT_DIR / "03_plots").resolve()

# Plot lookback window (shorter window than fetch horizon)
DIP_PLOT_LOOKBACK_DAYS = _env_int("DIP_PLOT_LOOKBACK_DAYS", DIP_PLOT_LOOKBACK_DAYS_DEFAULT)
TREND_PLOT_LOOKBACK_DAYS = _env_int("TREND_PLOT_LOOKBACK_DAYS", TREND_PLOT_LOOKBACK_DAYS_DEFAULT)

# Ensure base directories exist
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)

# How much U3O8 (in pounds) each SRUUF unit represents.
# Used to compute an implied uranium spot price from the SRUUF unit price.
SRUUF_U3O8_LBS_PER_UNIT: float = 0.2404


@dataclass(frozen=True)
class IndexConfig:
    """Configuration for a single index / ticker.

    This is the generic building block so we can easily add more tickers later.
    """

    id: str
    name: str
    ticker: str
    lookback_days: int
    state_file: Path
    log_csv: Path
    plots_dir: Path


@dataclass(frozen=True)
class EmailConfig:
    """SMTP email settings loaded from environment variables."""

    from_email: str
    to_email: str
    app_password: str


def get_email_config() -> EmailConfig:
    """Load email config from environment in a centralized place.

    Raises:
        RuntimeError: if any required variable is missing.
    """
    from_email = os.getenv("FROM_EMAIL")
    to_email = os.getenv("TO_EMAIL")
    app_pass = os.getenv("APP_PASSWORD")

    if not (from_email and to_email and app_pass):
        raise RuntimeError(
            "Missing FROM_EMAIL / TO_EMAIL / APP_PASSWORD in environment"
        )

    # Strip spaces just once here; Gmail app passwords often have spaces
    app_pass = app_pass.replace(" ", "")
    return EmailConfig(from_email=from_email, to_email=to_email, app_password=app_pass)


# ---------------------------------------------------------------------
# Concrete index configurations
# ---------------------------------------------------------------------

SPX_INDEX: IndexConfig = IndexConfig(
    id="spx",
    name="S&P 500",
    ticker=INDEX_TICKER,
    lookback_days=LOOKBACK_DAYS,    
    state_file=STATE_DIR / "spx_alert_state.json",
    log_csv=LOGS_DIR / "spx_dip_alert_log.csv",
    plots_dir=PLOTS_DIR / "spx",
)

NDX_INDEX: IndexConfig = IndexConfig(
    id="ndx",
    name="NASDAQ 100",
    ticker=NDX_TICKER,
    lookback_days=LOOKBACK_DAYS,    
    state_file=STATE_DIR / "ndx_alert_state.json",
    log_csv=LOGS_DIR / "ndx_dip_alert_log.csv",
    plots_dir=PLOTS_DIR / "ndx",
)
SOX_INDEX: IndexConfig = IndexConfig(
    id="sox",
    name="PHLX Semiconductor",
    ticker="^SOX",
    lookback_days=LOOKBACK_DAYS,    
    state_file=STATE_DIR / "sox_alert_state.json",
    log_csv=LOGS_DIR / "sox_dip_alert_log.csv",
    plots_dir=PLOTS_DIR / "sox",
)

SRVR_INDEX: IndexConfig = IndexConfig(
    id="srvr",
    name="Pacer Benchmark Data & Infrastructure Real Estate",
    ticker="SRVR",
    lookback_days=LOOKBACK_DAYS,    
    state_file=STATE_DIR / "srvr_alert_state.json",
    log_csv=LOGS_DIR / "srvr_dip_alert_log.csv",
    plots_dir=PLOTS_DIR / "srvr",
)

SRUUF_INDEX: IndexConfig = IndexConfig(
    id="sruuf",
    name="Sprott Physical Uranium",
    ticker="SRUUF",
    lookback_days=LOOKBACK_DAYS,    
    state_file=STATE_DIR / "sruuf_alert_state.json",
    log_csv=LOGS_DIR / "sruuf_dip_alert_log.csv",
    plots_dir=PLOTS_DIR / "sruuf",
)

REMX_INDEX: IndexConfig = IndexConfig(
    id="remx",
    name="Rare Earth and Strategic Metals",
    ticker="REMX",
    lookback_days=LOOKBACK_DAYS,    
    state_file=STATE_DIR / "remx_alert_state.json",
    log_csv=LOGS_DIR / "remx_dip_alert_log.csv",
    plots_dir=PLOTS_DIR / "remx",
)


# Registry of available indices
INDEXES: Dict[str, IndexConfig] = {
    "spx": SPX_INDEX,
    "ndx": NDX_INDEX,
    "sox": SOX_INDEX,
    "srvr": SRVR_INDEX,
    "sruuf": SRUUF_INDEX,
    "remx": REMX_INDEX,
}

# Default index id
DEFAULT_INDEX_ID: str = "spx"

# Ensure per-index directories exist
for ix in INDEXES.values():
    ix.plots_dir.mkdir(parents=True, exist_ok=True)
    ix.state_file.parent.mkdir(parents=True, exist_ok=True)
    ix.log_csv.parent.mkdir(parents=True, exist_ok=True)


def now(tz: ZoneInfo | None = None) -> dt.datetime:
    """Return current datetime in our local timezone (or provided tz)."""
    tz = tz or LOCAL_TZ
    return dt.datetime.now(tz=tz)


def now_str() -> str:
    """Shortcut for current timestamp as ISO string with seconds."""
    return now().isoformat(timespec="seconds")
