# spx_alert/buckets.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List


@dataclass(frozen=True)
class Bucket:
    """Range of drawdown that triggers a specific deployment rule.

    lo and hi are expressed as percentages (negative values),
    e.g. -8.0 to -5.0 for a 5–8% drawdown from the peak.
    """

    id: str
    lo: float  # lower bound of drawdown (e.g. -8.0)
    hi: float  # upper bound of drawdown (e.g. -5.0)
    note: str  # human-readable deployment rule


# Default SPX buckets for dip buying
DEFAULT_BUCKETS: List[Bucket] = [
    Bucket("B10", -8.0, -5.0, "Deploy 10% of Cash Bucket"),
    Bucket("B20", -15.0, -10.0, "Deploy 20% of Cash Bucket"),
    Bucket("B70", -999.0, -20.0, "Deploy remaining 70% in weekly tranches"),
]


def pick_bucket(dd: float, buckets: List[Bucket] = DEFAULT_BUCKETS) -> Optional[Bucket]:
    """Return the bucket that matches the current drawdown, or None.

    Args:
        dd: Current drawdown in percent (negative values).
        buckets: Bucket definitions to use.

    Returns:
        The matching Bucket or None if no range contains dd.
    """
    for b in buckets:
        if b.lo <= dd <= b.hi:
            return b
    return None
