"""Tests for data fetching and processing functions."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta
import pandas as pd
from src.data.data import (
    apply_peak_window,
    compute_drawdown,
    compute_trend_entry,
    compute_uranium_spot_from_sruuf,
)


class TestApplyPeakWindow(unittest.TestCase):
    """Test cases for apply_peak_window function."""

    def setUp(self):
        """Create sample price series for testing."""
        # Create 400 days of test data
        dates = pd.date_range(end=datetime.now(), periods=400, freq='D')
        self.series = pd.Series(
            range(100, 500),  # 100 to 499
            index=dates,
            name='Close'
        )

    def test_peak_window_1y(self):
        """Test 1-year window returns approximately last 365 days."""
        result = apply_peak_window(self.series, "1y")
        # Should have ~365 days
        self.assertGreater(len(result), 355)
        self.assertLessEqual(len(result), 375)

    def test_peak_window_all(self):
        """Test 'all' returns full series."""
        result = apply_peak_window(self.series, "all")
        self.assertEqual(len(result), len(self.series))

    def test_peak_window_ytd(self):
        """Test YTD window returns data from Jan 1."""
        result = apply_peak_window(self.series, "ytd")
        # Result should start at Jan 1 of current year
        jan_1 = pd.Timestamp(datetime.now().year, 1, 1)
        self.assertGreaterEqual(result.index.min(), jan_1)

    def test_peak_window_custom_date(self):
        """Test custom date format 'date:YYYY-MM-DD'."""
        # Use a date 100 days ago
        target_date = (datetime.now() - timedelta(days=100)).date().isoformat()
        result = apply_peak_window(self.series, f"date:{target_date}")
        # All dates should be >= target_date
        self.assertGreaterEqual(
            result.index.min(),
            pd.Timestamp(target_date)
        )

    def test_peak_window_invalid_date_fallback(self):
        """Test invalid date format falls back to 1-year window."""
        result = apply_peak_window(self.series, "date:invalid")
        # Should fall back to 1-year window
        self.assertGreater(len(result), 355)
        self.assertLessEqual(len(result), 375)

    def test_peak_window_none_defaults_to_1y(self):
        """Test None defaults to 1-year window."""
        result = apply_peak_window(self.series, None)
        self.assertGreater(len(result), 355)
        self.assertLessEqual(len(result), 375)

    def test_peak_window_empty_string_defaults_to_1y(self):
        """Test empty string defaults to 1-year window."""
        result = apply_peak_window(self.series, "")
        self.assertGreater(len(result), 355)
        self.assertLessEqual(len(result), 375)

    def test_peak_window_dataframe_input(self):
        """Test function handles DataFrame input."""
        df = self.series.to_frame()
        result = apply_peak_window(df, "1y")
        self.assertIsInstance(result, pd.Series)
        self.assertGreater(len(result), 355)

    def test_peak_window_handles_nan(self):
        """Test function handles NaN values."""
        series_with_nan = self.series.copy()
        series_with_nan.iloc[:10] = pd.NA
        result = apply_peak_window(series_with_nan, "all")
        # Should have fewer rows after NaN removal
        self.assertLess(len(result), len(self.series))


class TestComputeDrawdown(unittest.TestCase):
    """Test cases for compute_drawdown function."""

    def test_no_drawdown(self):
        """Test series with no drawdown (all-time high at end)."""
        series = pd.Series([100, 101, 102, 103, 104])
        current, peak, dd, peak_idx = compute_drawdown(series)
        self.assertEqual(current, 104)
        self.assertEqual(peak, 104)
        self.assertEqual(dd, 0.0)

    def test_simple_drawdown(self):
        """Test simple 10% drawdown."""
        series = pd.Series([100, 110, 99])  # Peak at 110, current at 99
        current, peak, dd, peak_idx = compute_drawdown(series)
        self.assertEqual(current, 99)
        self.assertEqual(peak, 110)
        self.assertAlmostEqual(dd, -10.0, places=1)

    def test_deep_drawdown(self):
        """Test deep 50% drawdown."""
        series = pd.Series([100, 200, 100])  # Peak at 200, current at 100 = -50%
        current, peak, dd, peak_idx = compute_drawdown(series)
        self.assertEqual(current, 100)
        self.assertEqual(peak, 200)
        self.assertAlmostEqual(dd, -50.0, places=1)

    def test_multiple_peaks_uses_latest(self):
        """Test with multiple peaks—should use the most recent one."""
        series = pd.Series([100, 150, 120, 150, 140])  # Two peaks at 150
        current, peak, dd, peak_idx = compute_drawdown(series)
        self.assertEqual(current, 140)
        self.assertEqual(peak, 150)
        self.assertAlmostEqual(dd, -6.67, places=1)

    def test_dataframe_input(self):
        """Test function handles DataFrame input."""
        df = pd.DataFrame({'Close': [100, 110, 99]})
        current, peak, dd, peak_idx = compute_drawdown(df)
        self.assertEqual(current, 99)
        self.assertEqual(peak, 110)


class TestComputeTrendEntry(unittest.TestCase):
    """Test cases for compute_trend_entry function."""

    def test_price_above_ma200(self):
        """Test price is above MA200."""
        # Create series where price crosses and stays above MA
        prices = list(range(100, 300))  # Steadily rising
        series = pd.Series(prices)
        c, m, pct, all_above, crossed, idx, ma, is_above = compute_trend_entry(series)
        # After rising steadily, price should be well above MA200
        self.assertGreater(c, m)
        self.assertGreater(pct, 0)
        self.assertTrue(all_above)

    def test_price_below_ma200(self):
        """Test price is below MA200."""
        # Create long series where price is below MA200
        # Need enough data: 200 for MA + 6 for hold_days+1
        prices = list(range(300, 100, -1))  # 200 points declining
        prices.extend([100] * 50)  # Add stable low prices
        series = pd.Series(prices)
        c, m, pct, all_above, crossed, idx, ma, is_above = compute_trend_entry(series, hold_days=5)
        # After declining and staying low, price should be below MA200
        self.assertLess(c, m)
        self.assertLess(pct, 0)

    def test_crossover_detection(self):
        """Test crossover from below to above MA200."""
        # Create series with enough points: 200 for MA calc + more for crossover
        # Start high, decline, then rise above MA200
        prices = list(range(250, 150, -1))  # 100 declining points
        prices.extend([150] * 50)  # 50 stable points below former high
        prices.extend(list(range(150, 250)))  # 100 rising points
        series = pd.Series(prices)
        c, m, pct, all_above, crossed, idx, ma, is_above = compute_trend_entry(series, hold_days=5)
        # Recent values should be above MA200
        self.assertTrue(all_above)

    def test_hold_days_parameter(self):
        """Test custom hold_days parameter."""
        prices = list(range(100, 350))  # Need 250+ points for stable MA
        series = pd.Series(prices)
        # With 10 hold days (needs last 11 points)
        c, m, pct, all_above, crossed, idx, ma, is_above = compute_trend_entry(
            series, ma_window=200, hold_days=10
        )
        self.assertTrue(all_above)

    def test_dataframe_input(self):
        """Test function handles DataFrame input."""
        df = pd.DataFrame({'Close': list(range(100, 300))})
        c, m, pct, all_above, crossed, idx, ma, is_above = compute_trend_entry(df)
        self.assertGreater(c, m)


class TestComputeUraniumSpot(unittest.TestCase):
    """Test cases for compute_uranium_spot_from_sruuf function."""

    def test_basic_computation(self):
        """Test basic uranium spot computation."""
        spot = compute_uranium_spot_from_sruuf(nav_per_unit=100.0, u3o8_lbs_per_unit=0.2)
        self.assertEqual(spot, 500.0)

    def test_sruuf_standard_ratio(self):
        """Test with SRUUF standard ratio (0.2404)."""
        nav = 50.0
        spot = compute_uranium_spot_from_sruuf(
            nav_per_unit=nav,
            u3o8_lbs_per_unit=0.2404
        )
        expected = nav / 0.2404
        self.assertAlmostEqual(spot, expected, places=1)

    def test_zero_u3o8_raises_error(self):
        """Test that zero u3o8_lbs_per_unit raises ValueError."""
        with self.assertRaises(ValueError):
            compute_uranium_spot_from_sruuf(nav_per_unit=100.0, u3o8_lbs_per_unit=0.0)

    def test_negative_u3o8_raises_error(self):
        """Test that negative u3o8_lbs_per_unit raises ValueError."""
        with self.assertRaises(ValueError):
            compute_uranium_spot_from_sruuf(nav_per_unit=100.0, u3o8_lbs_per_unit=-0.2)

    def test_positive_nav(self):
        """Test with positive NAV values."""
        for nav in [25.0, 50.0, 75.0, 100.0]:
            spot = compute_uranium_spot_from_sruuf(
                nav_per_unit=nav,
                u3o8_lbs_per_unit=0.25
            )
            self.assertGreater(spot, 0)
            self.assertAlmostEqual(spot, nav / 0.25, places=5)


if __name__ == '__main__':
    unittest.main()
