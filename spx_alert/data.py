# spx_alert/data.py
from __future__ import annotations

import datetime as dt
import time
from typing import Tuple, Optional

import pandas as pd
import yfinance as yf

from .config import INDEX_TICKER, LOOKBACK_DAYS
from .config import now_str


def fetch_series(ticker: str = INDEX_TICKER, days: int = LOOKBACK_DAYS) -> pd.Series:
    """Fetch daily close series for the given ticker."""
    end = dt.date.today()
    start = end - dt.timedelta(days=days + 10)
    last_err: Optional[Exception] = None

    for attempt in range(1, 4):
        try:
            df = yf.download(
                ticker,
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
        except Exception as e:
            last_err = e
        if attempt < 3:
            time.sleep(attempt * 2)

    raise RuntimeError(f"Data fetch failed: {last_err}")


def compute_drawdown(close: pd.Series) -> Tuple[float, float, float, pd.Timestamp]:
    """Return (current_price, peak_value, dd_pct, peak_date)."""
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, -1]

    rolling_max = close.cummax()
    dd_pct = (close / rolling_max - 1.0) * 100.0

    current = float(close.iat[-1])
    peak_value = float(rolling_max.iat[-1])
    dd = float(dd_pct.iat[-1])

    eq = (close.round(6) == rolling_max.round(6))
    peak_idx = eq[eq].index[-1]

    return current, peak_value, dd, pd.Timestamp(peak_idx)
