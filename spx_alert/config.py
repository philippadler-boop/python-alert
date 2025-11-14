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

# Root of the project (parent of this file's folder)
ROOT_DIR: Path = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------
# Core settings (global knobs)
# ---------------------------------------------------------------------

# Default SPX ticker (can be overridden via .env)
INDEX_TICKER: str = os.getenv("INDEX_TICKER", "^GSPC")

# How many calendar days of history to fetch
LOOKBACK_DAYS: int = int(os.getenv("LOOKBACK_DAYS", "1095"))

# Local timezone for timestamps
LOCAL_TZ: ZoneInfo = ZoneInfo(os.getenv("LOCAL_TZ", "Europe/Berlin"))

# If set, we log what would have happened but don't actually send emails
DRY_RUN: bool = os.getenv("DRY_RUN", "0") == "1"

# Whether to generate plots at all
SAVE_PLOTS: bool = os.getenv("SAVE_PLOTS", "1") == "1"

# Base directories
PLOTS_DIR: Path = Path(os.getenv("PLOTS_DIR", ROOT_DIR / "plots")).resolve()
LOGS_DIR: Path = (ROOT_DIR / "logs").resolve()
STATE_DIR: Path = (ROOT_DIR / "state").resolve()

# Plot lookback window (shorter window than fetch horizon)
PLOT_LOOKBACK_DAYS: int = int(os.getenv("PLOT_LOOKBACK_DAYS", "180"))

# HTML e-mail options
INLINE_IMAGE: bool = os.getenv("INLINE_IMAGE", "0") == "1"

# How long to keep logs and plots
RETENTION_DAYS: int = int(os.getenv("RETENTION_DAYS", "30"))

# Ensure base directories exist
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class IndexConfig:
    """Configuration for a single index / ticker.

    This is the generic building block so we can easily add more tickers later.
    """

    id: str
    name: str
    ticker: str
    lookback_days: int
    plot_lookback_days: int
    state_file: Path
    log_csv: Path
    plots_dir: Path


# ---------------------------------------------------------------------
# Concrete index configurations
# ---------------------------------------------------------------------

SPX_INDEX: IndexConfig = IndexConfig(
    id="spx",
    name="S&P 500",
    ticker=INDEX_TICKER,
    lookback_days=LOOKBACK_DAYS,
    plot_lookback_days=PLOT_LOOKBACK_DAYS,
    state_file=STATE_DIR / "spx_alert_state.json",
    log_csv=LOGS_DIR / "spx_dip_alert_log.csv",
    plots_dir=PLOTS_DIR / "spx",
)

NDX_INDEX: IndexConfig = IndexConfig(
    id="ndx",
    name="NASDAQ 100",
    ticker=os.getenv("NDX_TICKER", "^NDX"),
    lookback_days=LOOKBACK_DAYS,
    plot_lookback_days=PLOT_LOOKBACK_DAYS,
    state_file=STATE_DIR / "ndx_alert_state.json",
    log_csv=LOGS_DIR / "ndx_dip_alert_log.csv",
    plots_dir=PLOTS_DIR / "ndx",
)

# Registry of available indices
INDEXES: Dict[str, IndexConfig] = {
    "spx": SPX_INDEX,
    "ndx": NDX_INDEX,
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
