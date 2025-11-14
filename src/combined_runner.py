# spx_alert/combined_runner.py
from __future__ import annotations

from .alert_base import AlertBaseRunner
from .dip_runner import DipAlertRunner
from .trend_runner import TrendEntryRunner


class CombinedRunner(AlertBaseRunner):
    """Run dip + trend-entry logic on a shared price series."""

    def __init__(self, ix, peak_window: str | None = None) -> None:
        super().__init__(ix, peak_window=peak_window)
        self.dip = DipAlertRunner(ix, peak_window=peak_window)
        self.trend = TrendEntryRunner(ix)

    def run(self, show_plot: bool) -> None:
        series = self.fetch_series()
        # Dip uses the same series
        self.dip.run_with_series(series, show_plot=show_plot)
        # Trend uses the same series (no re-fetch)
        self.trend.run(series=series, is_test=False, show_plot=show_plot)
