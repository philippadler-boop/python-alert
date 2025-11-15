
from __future__ import annotations
import datetime as dt, time
from typing import Tuple
import pandas as pd, yfinance as yf
from ..config.config import SPX_INDEX, IndexConfig, now_str, YFINANCE_TIMEOUT_SECONDS, YFINANCE_RETRY_ATTEMPTS, YFINANCE_RETRY_DELAY_SECONDS
from ..logging import logger

def fetch_series(ix: IndexConfig = SPX_INDEX) -> pd.Series:
    lookback_days = getattr(ix, "lookback_days", 1095)

    end = dt.date.today()
    start = end - dt.timedelta(days=int(lookback_days))

    last_exc = None
    for attempt in range(1, YFINANCE_RETRY_ATTEMPTS + 1):
        try:
            logger.info(f"Fetching {ix.ticker} (attempt {attempt}) from {start} to {end}...")
            data = yf.download(ix.ticker, start=start, end=end, progress=False, auto_adjust=False, timeout=YFINANCE_TIMEOUT_SECONDS)

            if data is None or data.empty:
                raise RuntimeError("Empty result")

            # SAFE SELECTION — no 'or' anymore
            close = data.get("Adj Close")
            if close is None or close.empty:
                close = data.get("Close")

            if close is None or close.empty:
                raise RuntimeError("Close price not found in downloaded data")

            close = close.dropna()
            close.index = pd.to_datetime(close.index)
            close = close.sort_index()

            logger.info(f"Fetched {len(close)} points for {ix.id} (last date: {close.index[-1].date()})")
            return close

        except Exception as e:
            last_exc = e
            time.sleep(YFINANCE_RETRY_DELAY_SECONDS)

    raise RuntimeError(f"Failed to fetch data for {ix.ticker}") from last_exc

def apply_peak_window(
    close: pd.Series,
    peak_window: str | None,
) -> pd.Series:
    """
    Restrict the series used for the peak calculation based on a window spec.

    Expected peak_window values (after runner precedence resolution):
      - None or ""        → use default window ("1y")
      - "all"             → no restriction (full series)
      - "1y"              → last 365 days
      - "ytd"             → from Jan 1 of the current year
      - "date:YYYY-MM-DD" → from that date onward

    Note:
      The runner ensures that None/"" are replaced by "1y" *before* calling this.
      This function implements the actual windowing logic.
    """

    # Ensure correct type/shape
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, -1]

    close = close.dropna().sort_index()
    if close.empty:
        return close

    # If peak_window is None or "", treat it as "1y"
    if not peak_window:
        peak_window = "1y"

    # CASE 1 — no restriction
    if peak_window == "all":
        return close

    last_date = close.index.max().normalize()

    # CASE 2 — 1-year window
    if peak_window == "1y":
        cutoff = last_date - pd.DateOffset(years=1)
        return close.loc[close.index >= cutoff]

    # CASE 3 — year-to-date
    if peak_window == "ytd":
        year_start = last_date.replace(month=1, day=1)
        return close.loc[close.index >= year_start]

    # CASE 4 — custom start date
    if peak_window.startswith("date:"):
        try:
            date_str = peak_window.split(":", 1)[1]
            cutoff = pd.to_datetime(date_str)
            return close.loc[close.index >= cutoff]
        except Exception:
            # Bad format → fall back to 1-year window
            cutoff = last_date - pd.DateOffset(years=1)
            return close.loc[close.index >= cutoff]

    # CASE 5 — unknown spec → fall back to 1-year window
    cutoff = last_date - pd.DateOffset(years=1)
    return close.loc[close.index >= cutoff]

def compute_drawdown(close: pd.Series):
    if isinstance(close,pd.DataFrame): close=close.iloc[:,-1]
    close=close.dropna().sort_index()
    rolling_max=close.cummax()
    dd_pct=(close/rolling_max-1)*100
    current=float(close.iat[-1]); peak=float(rolling_max.iat[-1]); dd=float(dd_pct.iat[-1])
    eq=(close.round(6)==rolling_max.round(6))
    peak_idx=eq[eq].index[-1]
    return current, peak, dd, peak_idx

def compute_trend_entry(close: pd.Series, ma_window=200, hold_days=5):
    if isinstance(close,pd.DataFrame): close=close.iloc[:,-1]
    close=close.dropna().sort_index()
    ma=close.rolling(ma_window).mean().dropna()
    close=close.loc[ma.index]
    is_above=close>ma
    last=is_above.iloc[-(hold_days+1):]
    all_above=bool(last.iloc[1:].all())
    crossed = (last.iloc[0] == False) and all_above
    idx=last.index[-1]
    c=float(close.loc[idx]); m=float(ma.loc[idx])
    pct=(c/m-1)*100
    return c,m,pct,all_above,crossed,idx,ma,is_above

def compute_uranium_spot_from_sruuf(
    nav_per_unit: float,
    u3o8_lbs_per_unit: float,
) -> float:
    """
    Compute an implied uranium spot price (USD/lb) from SRUUF.

    We approximate:
        spot ≈ NAV_per_unit / U3O8_lbs_per_unit

    In practice, we use the SRUUF "close" price as a proxy for NAV.
    """
    if u3o8_lbs_per_unit <= 0:
        raise ValueError("u3o8_lbs_per_unit must be positive")
    return nav_per_unit / u3o8_lbs_per_unit

