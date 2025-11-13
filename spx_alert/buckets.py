# spx_alert/buckets.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List


@dataclass(frozen=True)
class Bucket:
    id: str
    lo: float
    hi: float
    note: str


DEFAULT_BUCKETS: List[Bucket] = [
    Bucket("B10", -8.0, -5.0, "Deploy 10% of Cash Bucket"),
    Bucket("B20", -15.0, -10.0, "Deploy 20% of Cash Bucket"),
    Bucket("B70", -999.0, -20.0, "Deploy remaining 70% in weekly tranches"),
]


def pick_bucket(dd: float, buckets: List[Bucket] = DEFAULT_BUCKETS) -> Optional[Bucket]:
    for b in buckets:
        if b.lo <= dd <= b.hi:
            return b
    return None
