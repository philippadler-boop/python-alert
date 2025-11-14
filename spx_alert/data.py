# spx_alert/data.py
from __future__ import annotations

import datetime as dt
import time
from typing import Tuple

import pandas as pd
import yfinance as yf

from .config import SPX_INDEX, IndexConfig, now_str


def fetch_series(ix: IndexConfig = SPX_INDEX) -> pd.Series:
    """Fetch daily adjusted close series for the given index config.

    Uses yfinance with a simple retry loop. Returns a pandas Series of
    adjusted close prices indexed by date (DatetimeIndex).
    """
    # Determine lookback horizon in calendar days
    lookback_days = getattr(ix, "lookback_days", 365 * 3)
    end = dt.date.today()
    start = end - dt.timedelta(days=int(lookback_days))

    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            print(
                f"[{now_str()}] Fetching {ix.ticker} (attempt {attempt}) "
                f"from {start} to {end}..."
            )
            data = yf.download(
                ix.ticker,
                start=start,
                end=end,
                progress=False,
                auto_adjust=False,
            )
            if data is None or data.empty:
                raise RuntimeError("Empty result from yfinance")
            # Prefer Adj Close if available, otherwise Close
            if "Adj Close" in data.columns:
                close = data["Adj Close"].copy()
            elif "Close" in data.columns:
                close = data["Close"].copy()
            else:
                raise RuntimeError("No Close/Adj Close column in data")
            close = close.dropna()
            close.index = pd.to_datetime(close.index)
            close = close.sort_index()
            print(
                f"[{now_str()}] Fetched {len(close)} points for {ix.id} "
                f"(last date: {close.index[-1].date()})"
            )
            return close
        except Exception as e:  # noqa: BLE001
            last_exc = e
            print(f"[{now_str()}] Error fetching {ix.ticker}: {e}")
            time.sleep(2.0)

    raise RuntimeError(f"Failed to fetch data for {ix.ticker}") from last_exc


def compute_drawdown(close: pd.Series) -> Tuple[float, float, float, pd.Timestamp]:
    """Compute the current drawdown relative to the rolling max.

    Returns:
        current_close, peak_value, drawdown_pct, peak_date
    """
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, -1]

    if close.empty:
        raise ValueError("Cannot compute drawdown on empty series")

    # Ensure series is sorted by date and has a DatetimeIndex
    close = close.sort_index()
    if not isinstance(close.index, pd.DatetimeIndex):
        close.index = pd.to_datetime(close.index)

    rolling_max = close.cummax()
    dd_pct = (close / rolling_max - 1.0) * 100.0

    current = float(close.iat[-1])
    peak_value = float(rolling_max.iat[-1])
    dd = float(dd_pct.iat[-1])

    # Last occurrence of the rolling max
    eq = (close.round(6) == rolling_max.round(6))
    peak_idx = eq[eq].index[-1]

    return current, peak_value, dd, pd.Timestamp(peak_idx)


def compute_trend_entry(
    close: pd.Series,
    ma_window: int = 200,
    hold_days: int = 5,
) -> Tuple[float, float, float, bool, bool, pd.Timestamp]:
    """Compute MA-based trend entry metrics.

    Encapsulates the logic for:

      - Building a `ma_window` moving average
      - Determining whether the last `hold_days` are all above the MA
      - Detecting if this run was *preceded* by a day below the MA
        (i.e., a cross from below to above + confirmation)

    Args:
        close: Price series (e.g. daily closes), indexed by DatetimeIndex.
        ma_window: Moving average window (default 200).
        hold_days: Number of consecutive days price must be above MA
                   *after* crossing from below (default 5).

    Returns:
        (close_today, ma_today, pct_diff, all_above, crossed_from_below, today_idx)

        - close_today: latest close
        - ma_today: latest moving average value
        - pct_diff: percentage difference (close_today / ma_today - 1) * 100
        - all_above: True if the last `hold_days` are all above MA
        - crossed_from_below: True if the day before that sequence was below MA
        - today_idx: Timestamp of the evaluation day
    """
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, -1]

    close = close.dropna()
    if close.empty:
        raise ValueError("Cannot compute trend entry on empty series")

    # Ensure sorted and DateTime index
    close = close.sort_index()
    if not isinstance(close.index, pd.DatetimeIndex):
        close.index = pd.to_datetime(close.index)

    if len(close) < ma_window + hold_days + 1:
        raise ValueError(
            f"Not enough data for trend entry: need at least {ma_window + hold_days + 1} points"
        )

    ma = close.rolling(ma_window).mean().dropna()
    if ma.empty:
        raise ValueError("MA series empty in compute_trend_entry")

    # Align
    close = close.loc[ma.index]
    is_above = close > ma

    if len(is_above) < hold_days + 1:
        raise ValueError(
            f"Not enough aligned data for trend entry window: need {hold_days + 1} flags"
        )

    last_dates = is_above.index[-(hold_days + 1) :]
    flags = is_above.loc[last_dates]

    today_idx = last_dates[-1]
    last_n = flags.iloc[-hold_days:]
    prev_flag = flags.iloc[0]

    all_above = bool(last_n.all())
    crossed_from_below = (prev_flag is False) and all_above

    close_today = float(close.loc[today_idx])
    ma_today = float(ma.loc[today_idx])
    pct_diff = (close_today / ma_today - 1.0) * 100.0

    return close_today, ma_today, pct_diff, all_above, crossed_from_below, pd.Timestamp(
        today_idx
    )
