# spx_alert/config.py
from __future__ import annotations

import os
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# Root of the project (parent of this file's folder)
ROOT_DIR = Path(__file__).resolve().parent.parent

INDEX_TICKER = os.getenv("INDEX_TICKER", "^GSPC")
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "1095"))

LOCAL_TZ = ZoneInfo(os.getenv("LOCAL_TZ", "Europe/Berlin"))
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"

SAVE_PLOTS = os.getenv("SAVE_PLOTS", "1") == "1"
PLOTS_DIR = Path(os.getenv("PLOTS_DIR", ROOT_DIR / "plots")).resolve()
LOG_CSV = Path(os.getenv("LOG_CSV", ROOT_DIR / "spx_dip_alert_log.csv")).resolve()
PLOT_LOOKBACK_DAYS = int(os.getenv("PLOT_LOOKBACK_DAYS", "180"))

INLINE_IMAGE = os.getenv("INLINE_IMAGE", "0") == "1"
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))

STATE_FILE = Path(os.getenv("STATE_FILE", ROOT_DIR / ".spx_alert_state.json")).resolve()

PLOTS_DIR.mkdir(parents=True, exist_ok=True)


def now(tz: ZoneInfo | None = None) -> dt.datetime:
    tz = tz or LOCAL_TZ
    return dt.datetime.now(tz=tz)


def now_str() -> str:
    return now().isoformat(timespec="seconds")
