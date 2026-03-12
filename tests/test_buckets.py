"""Tests for bucket selection logic."""
from __future__ import annotations

import unittest
from src.alerts.buckets import (
    Bucket,
    pick_bucket,
    get_buckets_for_index,
    DEFAULT_BUCKETS,
    SOX_BUCKETS,
    SRVR_BUCKETS,
    SRUUF_BUCKETS,
    REMX_BUCKETS,
)


class TestPickBucket(unittest.TestCase):
    """Test cases for pick_bucket function."""

    def test_pick_bucket_in_first_range(self):
        """Test drawdown falls in first bucket."""
        # B10: -10.0 to -5.0
        bucket = pick_bucket(-7.5, DEFAULT_BUCKETS)
        self.assertIsNotNone(bucket)
        self.assertEqual(bucket.id, "B10")

    def test_pick_bucket_in_second_range(self):
        """Test drawdown falls in second bucket."""
        # B20: -20.0 to -10.0
        bucket = pick_bucket(-15.0, DEFAULT_BUCKETS)
        self.assertIsNotNone(bucket)
        self.assertEqual(bucket.id, "B20")

    def test_pick_bucket_in_deep_range(self):
        """Test drawdown falls in deep range (B70)."""
        # B70: -999.0 to -20.0
        bucket = pick_bucket(-50.0, DEFAULT_BUCKETS)
        self.assertIsNotNone(bucket)
        self.assertEqual(bucket.id, "B70")

    def test_pick_bucket_at_boundary_lower(self):
        """Test drawdown at lower boundary of range."""
        # B10 lower bound: -10.0
        bucket = pick_bucket(-10.0, DEFAULT_BUCKETS)
        self.assertIsNotNone(bucket)
        self.assertEqual(bucket.id, "B10")

    def test_pick_bucket_at_boundary_upper(self):
        """Test drawdown at upper boundary of range."""
        # B10 upper bound: -5.0
        bucket = pick_bucket(-5.0, DEFAULT_BUCKETS)
        self.assertIsNotNone(bucket)
        self.assertEqual(bucket.id, "B10")

    def test_pick_bucket_no_match(self):
        """Test drawdown outside all ranges returns None."""
        bucket = pick_bucket(-2.0, DEFAULT_BUCKETS)  # Above -5.0
        self.assertIsNone(bucket)

    def test_pick_bucket_zero_drawdown(self):
        """Test zero drawdown (no loss) returns None."""
        bucket = pick_bucket(0.0, DEFAULT_BUCKETS)
        self.assertIsNone(bucket)

    def test_pick_bucket_positive_drawdown(self):
        """Test positive drawdown (gain) returns None."""
        bucket = pick_bucket(5.0, DEFAULT_BUCKETS)
        self.assertIsNone(bucket)

    def test_pick_bucket_extreme_drawdown(self):
        """Test extreme drawdown falls in B70."""
        bucket = pick_bucket(-99.0, DEFAULT_BUCKETS)
        self.assertIsNotNone(bucket)
        self.assertEqual(bucket.id, "B70")


class TestGetBucketsForIndex(unittest.TestCase):
    """Test cases for get_buckets_for_index function."""

    def test_spx_buckets(self):
        """Test SPX uses DEFAULT_BUCKETS."""
        buckets = get_buckets_for_index("spx")
        self.assertEqual(buckets, DEFAULT_BUCKETS)
        self.assertEqual(len(buckets), 3)

    def test_ndx_buckets(self):
        """Test NDX uses DEFAULT_BUCKETS."""
        buckets = get_buckets_for_index("ndx")
        self.assertEqual(buckets, DEFAULT_BUCKETS)

    def test_sxxp_buckets(self):
        """Test STOXX600 (SXXP) uses DEFAULT_BUCKETS."""
        buckets = get_buckets_for_index("sxxp")
        self.assertEqual(buckets, DEFAULT_BUCKETS)

    def test_awdpacxj_buckets(self):
        """Test AWDPACXJ (FGI) uses DEFAULT_BUCKETS."""
        buckets = get_buckets_for_index("awdpacxj")
        self.assertEqual(buckets, DEFAULT_BUCKETS)

    def test_sox_buckets(self):
        """Test SOX uses custom SOX_BUCKETS."""
        buckets = get_buckets_for_index("sox")
        self.assertEqual(buckets, SOX_BUCKETS)
        # SOX should have tighter ranges (more aggressive buying)
        self.assertTrue(buckets[0].hi >= -7.0)

    def test_srvr_buckets(self):
        """Test SRVR uses custom SRVR_BUCKETS."""
        buckets = get_buckets_for_index("srvr")
        self.assertEqual(buckets, SRVR_BUCKETS)

    def test_sruuf_buckets(self):
        """Test SRUUF uses custom SRUUF_BUCKETS (high volatility)."""
        buckets = get_buckets_for_index("sruuf")
        self.assertEqual(buckets, SRUUF_BUCKETS)
        # SRUUF should have wider ranges (more volatile)
        self.assertTrue(buckets[0].hi <= -10.0)

    def test_remx_buckets(self):
        """Test REMX uses custom REMX_BUCKETS."""
        buckets = get_buckets_for_index("remx")
        self.assertEqual(buckets, REMX_BUCKETS)

    def test_unknown_index_defaults_to_default_buckets(self):
        """Test unknown index ID returns DEFAULT_BUCKETS."""
        buckets = get_buckets_for_index("unknown")
        self.assertEqual(buckets, DEFAULT_BUCKETS)

    def test_all_buckets_have_required_fields(self):
        """Test all bucket definitions have required fields."""
        all_bucket_sets = [
            DEFAULT_BUCKETS,
            SOX_BUCKETS,
            SRVR_BUCKETS,
            SRUUF_BUCKETS,
            REMX_BUCKETS,
        ]
        for bucket_set in all_bucket_sets:
            for bucket in bucket_set:
                self.assertIsInstance(bucket, Bucket)
                self.assertIsNotNone(bucket.id)
                self.assertIsInstance(bucket.lo, (int, float))
                self.assertIsInstance(bucket.hi, (int, float))
                self.assertIsNotNone(bucket.note)


class TestBucketLogic(unittest.TestCase):
    """Test bucket logic and consistency."""

    def test_bucket_ranges_are_consistent(self):
        """Test that bucket ranges don't overlap incorrectly."""
        for bucket_set in [DEFAULT_BUCKETS, SOX_BUCKETS, SRVR_BUCKETS, SRUUF_BUCKETS, REMX_BUCKETS]:
            for i, bucket in enumerate(bucket_set[:-1]):  # All but the last
                # Each bucket's lo should be <= next bucket's hi
                next_bucket = bucket_set[i + 1]
                self.assertLessEqual(bucket.lo, next_bucket.hi)

    def test_bucket_ranges_logical(self):
        """Test that lo <= hi for all buckets."""
        for bucket_set in [DEFAULT_BUCKETS, SOX_BUCKETS, SRVR_BUCKETS, SRUUF_BUCKETS, REMX_BUCKETS]:
            for bucket in bucket_set:
                self.assertLessEqual(bucket.lo, bucket.hi)

    def test_bucket_has_b70_deep_bucket(self):
        """Test each bucket set has a B70 for extreme drawdowns."""
        for bucket_set in [DEFAULT_BUCKETS, SOX_BUCKETS, SRVR_BUCKETS, SRUUF_BUCKETS, REMX_BUCKETS]:
            b70 = next((b for b in bucket_set if b.id == "B70"), None)
            self.assertIsNotNone(b70, f"B70 not found in {bucket_set}")

    def test_volatility_tier_logic(self):
        """Test that higher-volatility indices have wider bucket ranges."""
        # Get first bucket (B10) from each set
        default_b10 = DEFAULT_BUCKETS[0]  # -10 to -5
        sox_b10 = SOX_BUCKETS[0]          # -12 to -7
        sruuf_b10 = SRUUF_BUCKETS[0]      # -20 to -10

        # Volatility tier should have wider ranges
        self.assertGreater(abs(sruuf_b10.lo), abs(default_b10.lo))
        self.assertGreater(abs(sox_b10.lo), abs(default_b10.lo))


if __name__ == '__main__':
    unittest.main()
