# spx_alert/data.py
from __future__ import annotations

import datetime as dt
import time
from typing import Tuple, Optional

import pandas as pd
import yfinance as yf

from .config import SPX_INDEX, IndexConfig, now_str


class DataFetchError(RuntimeError):
    """Raised when price data cannot be fetched or is unusable."""


def _normalize_close_series(df: pd.DataFrame) -> pd.Series:
    """Extract and normalize the Close series from a yfinance DataFrame.

    Handles:
    - Single-column or multi-column DataFrames
    - Missing / NaN-only columns
    """
    if "Close" not in df:
        raise DataFetchError("Missing 'Close' column in fetched data")

    s = df["Close"].dropna()

    # yfinance sometimes returns multi-index/multi-column data; reduce to 1D
    if isinstance(s, pd.DataFrame):
        # Drop columns that are entirely NaN
        s = s.dropna(axis=1, how="all")
        if s.shape[1] == 0:
            raise DataFetchError("All 'Close' columns are empty after dropna")
        # Take the first non-empty column
        s = s.iloc[:, 0]

    if not isinstance(s, pd.Series) or s.empty:
        raise DataFetchError("Close series is empty or invalid")

    # Ensure we have a DatetimeIndex (as typical for yfinance)
    if not isinstance(s.index, pd.DatetimeIndex):
        try:
            s.index = pd.to_datetime(s.index)
        except Exception as e:  # noqa: BLE001
            raise DataFetchError(f"Unable to convert index to DatetimeIndex: {e}")

    return s.sort_index()


def fetch_series(ix: IndexConfig = SPX_INDEX) -> pd.Series:
    """Fetch daily adjusted close series for the given index config.

    Retries a few times with small backoff. Raises DataFetchError on failure.
    """
    end = dt.date.today()
    # Fetch a bit more than needed to be robust against holidays / gaps
    start = end - dt.timedelta(days=ix.lookback_days + 10)
    last_err: Optional[Exception] = None

    for attempt in range(1, 4):
        try:
            print(
                f"[{now_str()}] Fetching {ix.ticker} "
                f"(attempt {attempt}) from {start} to {end}..."
            )
            df = yf.download(
                ix.ticker,
                start=start,
                end=end,
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False,
            )

            if df is None or df.empty:
                raise DataFetchError("No data returned from yfinance")

            s = _normalize_close_series(df)
            # Trim to requested lookback
            cutoff = end - dt.timedelta(days=ix.lookback_days)
            s = s[s.index.date >= cutoff]
            if s.empty:
                raise DataFetchError("Series empty after applying lookback window")

            print(
                f"[{now_str()}] Fetched {len(s)} points for {ix.id} "
                f"(last date: {s.index[-1].date()})"
            )
            return s

        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < 3:
                print(
                    f"[{now_str()}] Fetch attempt {attempt} for {ix.ticker} "
                    f"failed: {e}; retrying..."
                )
                time.sleep(attempt * 2)
            else:
                print(
                    f"[{now_str()}] Fetch attempt {attempt} for {ix.ticker} "
                    f"failed: {e}; giving up."
                )

    # If we get here, all attempts failed
    raise DataFetchError(f"Data fetch failed for {ix.ticker}: {last_err}")


def compute_drawdown(close: pd.Series) -> Tuple[float, float, float, pd.Timestamp]:
    """Compute the current drawdown relative to the rolling max.

    Returns:
        current_close, peak_value, drawdown_pct, peak_date
    """
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, -1]

    if close.empty:
        raise ValueError("Cannot compute drawdown on empty series")

    # Ensure series is sorted by date
    close = close.sort_index()

    rolling_max = close.cummax()
    dd_pct = (close / rolling_max - 1.0) * 100.0

    current = float(close.iat[-1])
    peak_value = float(rolling_max.iat[-1])
    dd = float(dd_pct.iat[-1])

    # Last occurrence of the rolling max
    eq = (close.round(6) == rolling_max.round(6))
    peak_idx = eq[eq].index[-1]

    return current, peak_value, dd, pd.Timestamp(peak_idx)
