"""Tests for email formatting functions."""
from __future__ import annotations

import unittest
import math
from datetime import datetime
import pandas as pd
from src.email.email_utils import make_email_subject, make_email_body, build_html_email
from src.alerts.buckets import Bucket
from src.config.config import SPX_INDEX, SOX_INDEX


class TestMakeEmailSubject(unittest.TestCase):
    """Test cases for make_email_subject function."""

    def test_subject_format_with_finite_range(self):
        """Test subject line with finite bucket range."""
        bucket = Bucket("B10", -10.0, -5.0, "Deploy 10%")
        subject = make_email_subject(SPX_INDEX, bucket, -7.5)
        
        # Check required components
        self.assertIn("SPX", subject)
        self.assertIn("DIP ALERT", subject)
        self.assertIn("-5%", subject)
        self.assertIn("-10%", subject)
        self.assertIn("-7.50%", subject)

    def test_subject_format_with_deep_range(self):
        """Test subject with deep range (large negative lo bound)."""
        bucket = Bucket("B70", -999.0, -20.0, "Deploy 70%")
        subject = make_email_subject(SPX_INDEX, bucket, -50.0)
        
        self.assertIn("SPX", subject)
        # -999 is treated as finite, so it shows: "to -999%"
        self.assertIn("-20%", subject)
        self.assertIn("-999%", subject)
        self.assertIn("-50.00%", subject)

    def test_subject_includes_index_id_uppercase(self):
        """Test subject includes uppercase index ID."""
        bucket = Bucket("B20", -20.0, -10.0, "Deploy 20%")
        subject = make_email_subject(SOX_INDEX, bucket, -15.0)
        
        self.assertIn("SOX", subject)

    def test_subject_includes_drawdown_percentage(self):
        """Test subject includes formatted drawdown percentage."""
        bucket = Bucket("B10", -10.0, -5.0, "Deploy")
        subject = make_email_subject(SPX_INDEX, bucket, -6.234)
        
        self.assertIn("-6.23%", subject)

    def test_subject_with_small_drawdown(self):
        """Test subject with very small drawdown."""
        bucket = Bucket("B10", -10.0, -5.0, "Deploy")
        subject = make_email_subject(SPX_INDEX, bucket, -5.001)
        
        self.assertIn("-5.00%", subject)

    def test_subject_with_extreme_drawdown(self):
        """Test subject with extreme drawdown."""
        bucket = Bucket("B70", -999.0, -20.0, "Deploy")
        subject = make_email_subject(SPX_INDEX, bucket, -95.5)
        
        self.assertIn("-95.50%", subject)


class TestMakeEmailBody(unittest.TestCase):
    """Test cases for make_email_body function."""

    def test_body_includes_required_fields(self):
        """Test body includes required information."""
        bucket = Bucket("B10", -10.0, -5.0, "Deploy 10%")
        peak_date = pd.Timestamp(datetime.now())
        
        body = make_email_body(
            SPX_INDEX,
            close=100.0,
            peak=110.0,
            dd=-9.09,
            peak_date=peak_date,
            bucket=bucket,
        )
        
        self.assertIn("100.00", body)      # Close
        self.assertIn("110.00", body)      # Peak
        self.assertIn("-9.09", body)       # Drawdown
        self.assertIn("Deploy 10%", body)  # Bucket note
        self.assertIn("^GSPC", body)       # Ticker

    def test_body_with_custom_note(self):
        """Test body with custom note appended."""
        bucket = Bucket("B20", -20.0, -10.0, "Deploy 20%")
        peak_date = pd.Timestamp(datetime.now())
        custom_note = "This is a test alert (SIMULATED)"
        
        body = make_email_body(
            SPX_INDEX,
            close=95.0,
            peak=115.0,
            dd=-17.39,
            peak_date=peak_date,
            bucket=bucket,
            note=custom_note,
        )
        
        self.assertIn(custom_note, body)

    def test_body_formats_currency(self):
        """Test body formats prices as currency."""
        bucket = Bucket("B10", -10.0, -5.0, "Deploy 10%")
        peak_date = pd.Timestamp(datetime.now())
        
        body = make_email_body(
            SPX_INDEX,
            close=4567.89,
            peak=5000.00,
            dd=-8.65,
            peak_date=peak_date,
            bucket=bucket,
        )
        
        self.assertIn("4567.89", body)
        self.assertIn("5000.00", body)

    def test_body_includes_peak_date(self):
        """Test body includes peak date."""
        bucket = Bucket("B10", -10.0, -5.0, "Deploy")
        peak_date = pd.Timestamp("2025-11-15")
        
        body = make_email_body(
            SPX_INDEX,
            close=100.0,
            peak=110.0,
            dd=-9.09,
            peak_date=peak_date,
            bucket=bucket,
        )
        
        self.assertIn("2025-11-15", body)


class TestBuildHtmlEmail(unittest.TestCase):
    """Test cases for build_html_email function."""

    def test_html_email_has_required_structure(self):
        """Test HTML email has required HTML structure."""
        bucket = Bucket("B10", -10.0, -5.0, "Deploy 10%")
        peak_date = pd.Timestamp(datetime.now())
        
        html = build_html_email(
            SPX_INDEX,
            close=100.0,
            peak=110.0,
            dd=-9.09,
            peak_date=peak_date,
            bucket=bucket,
            cid=None,
        )
        
        self.assertIn("<html>", html.lower())
        self.assertIn("<body", html.lower())
        self.assertIn("</body>", html.lower())
        self.assertIn("</html>", html.lower())

    def test_html_email_includes_table_data(self):
        """Test HTML email includes table with data."""
        bucket = Bucket("B10", -10.0, -5.0, "Deploy 10%")
        peak_date = pd.Timestamp(datetime.now())
        
        html = build_html_email(
            SPX_INDEX,
            close=100.0,
            peak=110.0,
            dd=-9.09,
            peak_date=peak_date,
            bucket=bucket,
            cid=None,
        )
        
        self.assertIn("<table", html.lower())
        self.assertIn("100.00", html)
        self.assertIn("110.00", html)
        self.assertIn("Drawdown", html)

    def test_html_email_with_image_cid(self):
        """Test HTML email includes image when cid provided."""
        bucket = Bucket("B10", -10.0, -5.0, "Deploy 10%")
        peak_date = pd.Timestamp(datetime.now())
        cid_value = "image_001"
        
        html = build_html_email(
            SPX_INDEX,
            close=100.0,
            peak=110.0,
            dd=-9.09,
            peak_date=peak_date,
            bucket=bucket,
            cid=cid_value,
        )
        
        self.assertIn(f"cid:{cid_value}", html)
        self.assertIn("<img", html.lower())

    def test_html_email_without_image_cid(self):
        """Test HTML email without image when cid is None."""
        bucket = Bucket("B10", -10.0, -5.0, "Deploy 10%")
        peak_date = pd.Timestamp(datetime.now())
        
        html = build_html_email(
            SPX_INDEX,
            close=100.0,
            peak=110.0,
            dd=-9.09,
            peak_date=peak_date,
            bucket=bucket,
            cid=None,
        )
        
        # Image HTML should not be present
        self.assertNotIn("<img", html)

    def test_html_email_bucket_range_finite(self):
        """Test HTML email displays bucket range with finite bounds."""
        bucket = Bucket("B10", -10.0, -5.0, "Deploy 10%")
        peak_date = pd.Timestamp(datetime.now())
        
        html = build_html_email(
            SPX_INDEX,
            close=100.0,
            peak=110.0,
            dd=-9.09,
            peak_date=peak_date,
            bucket=bucket,
            cid=None,
        )
        
        # Should show "-5% to -10%"
        self.assertIn("-5%", html)
        self.assertIn("-10%", html)

    def test_html_email_bucket_range_infinite(self):
        """Test HTML email displays bucket range with large negative bound."""
        bucket = Bucket("B70", -999.0, -20.0, "Deploy 70%")
        peak_date = pd.Timestamp(datetime.now())
        
        html = build_html_email(
            SPX_INDEX,
            close=100.0,
            peak=120.0,
            dd=-16.67,
            peak_date=peak_date,
            bucket=bucket,
            cid=None,
        )
        
        # Should show the range with -999% (large bounds)
        self.assertIn("-20%", html)
        self.assertIn("-999%", html)


if __name__ == '__main__':
    unittest.main()
