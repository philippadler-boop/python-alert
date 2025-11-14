# spx_alert/data.py
from __future__ import annotations

import datetime as dt
import time
from typing import Tuple, Optional

import pandas as pd
import yfinance as yf

from .config import SPX_INDEX, IndexConfig, now_str


def fetch_series(ix: IndexConfig = SPX_INDEX) -> pd.Series:
    """Fetch daily adjusted close series for the given index config.

    Args:
        ix: IndexConfig describing ticker and lookback horizon.

    Returns:
        A pandas Series of closing prices indexed by date.

    Raises:
        RuntimeError: If data cannot be fetched after retries.
    """
    end = dt.date.today()
    start = end - dt.timedelta(days=ix.lookback_days + 10)
    last_err: Optional[Exception] = None

    for attempt in range(1, 4):
        try:
            df = yf.download(
                ix.ticker,
                start=start,
                end=end,
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False,
            )
            if df is not None and not df.empty and "Close" in df:
                s = df["Close"].dropna()
                if isinstance(s, pd.DataFrame):
                    s = s.dropna(axis=1, how="all")
                    if s.shape[1] > 0:
                        s = s.iloc[:, 0]
                if isinstance(s, pd.Series) and not s.empty:
                    return s

            last_err = RuntimeError("No data fetched or missing Close column")
        except Exception as e:  # noqa: BLE001
            last_err = e

        if attempt < 3:
            print(f"[{now_str()}] Fetch attempt {attempt} failed: {last_err}; retrying...")
            time.sleep(attempt * 2)

    raise RuntimeError(f"Data fetch failed for {ix.ticker}: {last_err}")


def compute_drawdown(close: pd.Series) -> Tuple[float, float, float, pd.Timestamp]:
    """Compute the current drawdown relative to the rolling max.

    Args:
        close: Series of closing prices.

    Returns:
        Tuple of (current_price, peak_value, drawdown_pct, peak_date).
        - drawdown_pct is negative when below the peak.
        - peak_date is the last date where the rolling max equals the close.
    """
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, -1]

    rolling_max = close.cummax()
    dd_pct = (close / rolling_max - 1.0) * 100.0

    current = float(close.iat[-1])
    peak_value = float(rolling_max.iat[-1])
    dd = float(dd_pct.iat[-1])

    # last peak date
    eq = (close.round(6) == rolling_max.round(6))
    peak_idx = eq[eq].index[-1]

    return current, peak_value, dd, pd.Timestamp(peak_idx)
