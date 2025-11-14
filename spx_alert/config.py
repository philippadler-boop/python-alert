# spx_alert/config.py
from __future__ import annotations

import os
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# Root of the project (parent of this file's folder)
ROOT_DIR: Path = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------
# Core settings
# ---------------------------------------------------------------------

# Which index to track (SPX by default)
INDEX_TICKER: str = os.getenv("INDEX_TICKER", "^GSPC")

# How many calendar days of history to fetch
LOOKBACK_DAYS: int = int(os.getenv("LOOKBACK_DAYS", "1095"))

# Local timezone for timestamps
LOCAL_TZ: ZoneInfo = ZoneInfo(os.getenv("LOCAL_TZ", "Europe/Berlin"))

# If set, we log what would have happened but don't actually send e-mails
DRY_RUN: bool = os.getenv("DRY_RUN", "0") == "1"

# Whether to generate plots at all
SAVE_PLOTS: bool = os.getenv("SAVE_PLOTS", "1") == "1"

# Base directories
PLOTS_DIR: Path = Path(os.getenv("PLOTS_DIR", ROOT_DIR / "plots")).resolve()
LOGS_DIR: Path = (ROOT_DIR / "logs").resolve()
STATE_DIR: Path = (ROOT_DIR / "state").resolve()

# Derived paths
LOG_CSV = (LOGS_DIR / "spx_dip_alert_log.csv").resolve()

PLOT_LOOKBACK_DAYS: int = int(os.getenv("PLOT_LOOKBACK_DAYS", "180"))

# HTML e-mail options
INLINE_IMAGE: bool = os.getenv("INLINE_IMAGE", "0") == "1"

# How long to keep logs and plots
RETENTION_DAYS: int = int(os.getenv("RETENTION_DAYS", "30"))

# Simple state file to track which buckets fired for which peak
STATE_FILE: Path = Path(
    os.getenv("STATE_FILE", STATE_DIR / "spx_alert_state.json")
).resolve()

# Ensure directories exist
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)


def now(tz: ZoneInfo | None = None) -> dt.datetime:
    """Return current datetime in our local timezone (or provided tz)."""
    tz = tz or LOCAL_TZ
    return dt.datetime.now(tz=tz)


def now_str() -> str:
    """Shortcut for current timestamp as ISO string with seconds."""
    return now().isoformat(timespec="seconds")
