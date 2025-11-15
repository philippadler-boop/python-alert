# spx_alert/combined_runner.py
from __future__ import annotations

import pandas as pd

from .alert_base import AlertBaseRunner
from .dip_runner import DipAlertRunner
from .trend_runner import TrendEntryRunner
from ..config.config import MA_WINDOW_DEFAULT, TREND_HOLD_DAYS_DEFAULT


class CombinedRunner(AlertBaseRunner):
    """Run dip + trend-entry logic on a shared price series with cached MA200."""

    def __init__(self, ix, peak_window: str | None = None) -> None:
        super().__init__(ix, peak_window=peak_window)
        self.dip = DipAlertRunner(ix, peak_window=peak_window)
        self.trend = TrendEntryRunner(ix)

    def run(self, show_plot: bool) -> None:
        series = self.fetch_series()
        
        # Dip uses the same series
        self.dip.run_with_series(series, show_plot=show_plot)
        
        # Pre-compute MA200 to avoid recalculation in trend runner
        if self.trend.is_enabled():
            try:
                profile = self.trend.profile
                assert profile is not None
                
                # Cache MA200 so trend runner doesn't recompute it
                ma = series.rolling(profile.ma_window).mean().dropna()
                # Ensure the moving average is a Series (not a DataFrame)
                if isinstance(ma, pd.DataFrame):
                    logger.debug("CombinedRunner: MA computed as DataFrame; selecting last column for trend.")
                    ma = ma.iloc[:, -1]
                
                # Pass pre-computed MA to avoid redundant calculation
                self.trend.run(
                    series=series,
                    is_test=False,
                    show_plot=show_plot,
                    _cached_ma=ma
                )
            except Exception:
                # Fall back to standard trend run if caching fails
                self.trend.run(series=series, is_test=False, show_plot=show_plot)
        else:
            # Trend not enabled, just run trend with series (will skip early)
            self.trend.run(series=series, is_test=False, show_plot=show_plot)
