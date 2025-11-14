# spx_alert/data.py
from __future__ import annotations

import datetime as dt
import time
from typing import Tuple, Optional

import pandas as pd
import yfinance as yf

from .config import SPX_INDEX, IndexConfig, now_str
from .exceptions import DataFetchError


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


def compute_drawdown(close: pd.Series, peak_window: str) -> Tuple[float, float, float, pd.Timestamp]:
    """Compute the current drawdown relative to a configurable recent high.

    peak_window options:
        "1y"              → last 365 days
        "ytd"             → since January 1 of the current year
        "date:YYYY-MM-DD" → explicit anchor date (e.g. investment date)
        anything else     → use full available history
    """

    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, -1]

    if close.empty:
        raise ValueError("Cannot compute drawdown on empty series")

    # Ensure series is sorted by date
    close = close.sort_index()

    # Ensure we have a DatetimeIndex
    if not isinstance(close.index, pd.DatetimeIndex):
        try:
            close.index = pd.to_datetime(close.index)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"Unable to convert index to DatetimeIndex: {e}")

    idx = close.index
    peak_window = (peak_window or "").lower()

    # ----------------- determine cutoff -----------------
    cutoff: pd.Timestamp

    if peak_window == "1y":
        cutoff = idx[-1] - dt.timedelta(days=365)

    elif peak_window == "ytd":
        year = idx[-1].year
        # preserve timezone if present
        if idx.tz is not None:
            cutoff = pd.Timestamp(year=year, month=1, day=1, tz=idx.tz)
        else:
            cutoff = pd.Timestamp(year=year, month=1, day=1)

    elif peak_window.startswith("date:"):
        _, date_str = peak_window.split(":", 1)
        try:
            cutoff = pd.Timestamp(date_str.strip())
            if cutoff.tzinfo is None and idx.tz is not None:
                cutoff = cutoff.tz_localize(idx.tz)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"Invalid PEAK_WINDOW value '{peak_window}': {e}")
    else:
        # Fallback: use full history
        cutoff = idx[0]

    # ----------------- restrict to window -----------------
    window = close[close.index >= cutoff]

    # If the window is empty (e.g. cutoff after last data), fall back to full series
    if window.empty:
        window = close

    # Peak within the window
    peak_value = float(window.max())
    peak_idx = window.idxmax()

    current = float(window.iloc[-1])
    dd = (current / peak_value - 1.0) * 100.0

    return current, peak_value, dd, pd.Timestamp(peak_idx)

