from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict


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


# ---------------------------------------------------------------------
# Baseline buckets (for broad equity indices like SPX / NDX)
# ---------------------------------------------------------------------

DEFAULT_BUCKETS: List[Bucket] = [
    Bucket("B10", -10.0, -5.0, "Deploy 10% of Cash Bucket"),
    Bucket("B20", -20.0, -10.0, "Deploy 20% of Cash Bucket"),
    Bucket("B70", -999.0, -20.0, "Deploy remaining 70% in weekly tranches"),
]


# ---------------------------------------------------------------------
# Index-specific buckets for higher-volatility tickers
# ---------------------------------------------------------------------

# 1) Semiconductors (SOX) — more volatile than SPX, but still large-cap
SOX_BUCKETS: List[Bucket] = [
    Bucket("B10", -12.0, -7.0, "Deploy 10% of Cash Bucket (semis first buy)"),
    Bucket("B20", -25.0, -12.0, "Deploy 20% of Cash Bucket (semis second buy)"),
    Bucket(
        "B70",
        -999.0,
        -25.0,
        "Deploy remaining 70% in weekly tranches (deep semi drawdown)",
    ),
]

# 2) Data center REITs / digital infra (SRVR) — somewhat more volatile than SPX
SRVR_BUCKETS: List[Bucket] = [
    Bucket("B10", -12.0, -6.0, "Deploy 10% of Cash Bucket (data centers first buy)"),
    Bucket("B20", -25.0, -12.0, "Deploy 20% of Cash Bucket (data centers second buy)"),
    Bucket(
        "B70",
        -999.0,
        -25.0,
        "Deploy remaining 70% in weekly tranches (deep REIT drawdown)",
    ),
]

# 3) Sprott Physical Uranium (SRUUF) — very high volatility, deep swings are normal
SRUUF_BUCKETS: List[Bucket] = [
    Bucket("B10", -20.0, -10.0, "Deploy 10% of Cash Bucket (uranium first buy)"),
    Bucket("B20", -40.0, -20.0, "Deploy 20% of Cash Bucket (uranium second buy)"),
    Bucket(
        "B70",
        -999.0,
        -40.0,
        "Deploy remaining 70% in weekly tranches (deep uranium drawdown)",
    ),
]

# 4) Transition metals / rare earths (REMX) — also very volatile
REMX_BUCKETS: List[Bucket] = [
    Bucket("B10", -20.0, -10.0, "Deploy 10% of Cash Bucket (metals first buy)"),
    Bucket("B20", -40.0, -20.0, "Deploy 20% of Cash Bucket (metals second buy)"),
    Bucket(
        "B70",
        -999.0,
        -40.0,
        "Deploy remaining 70% in weekly tranches (deep metals drawdown)",
    ),
]


# 5) Procure Space ETF (UFO) — similar deep-drawdown behavior to REMX but handled separately
UFO_BUCKETS: List[Bucket] = [
    Bucket("B10", -20.0, -10.0, "Deploy 10% of Cash Bucket (space ETF first buy)"),
    Bucket("B20", -40.0, -20.0, "Deploy 20% of Cash Bucket (space ETF second buy)"),
    Bucket(
        "B70",
        -999.0,
        -40.0,
        "Deploy remaining 70% in weekly tranches (deep space ETF drawdown)",
    ),
]

# 6) Bitcoin (BTC-USD) — very high volatility, deep swings are normal
BTC_BUCKETS: List[Bucket] = [
    Bucket("B10", -30.0, -20.0, "Deploy 10% of Cash Bucket (Bitcoin first buy)"),
    Bucket("B20", -45.0, -30.0, "Deploy 20% of Cash Bucket (Bitcoin second buy)"),
    Bucket(
        "B70",
        -999.0,
        -45.0,
        "Deploy remaining 70% in weekly tranches (deep Bitcoin drawdown)",
    ),
]


# Registry mapping index ids (config.id) → bucket set
BUCKETS_BY_INDEX_ID: Dict[str, List[Bucket]] = {
    # Baseline: SPX / NDX (and similar broad equity indices)
    "spx": DEFAULT_BUCKETS,
    "ndx": DEFAULT_BUCKETS,
    "sxxp": DEFAULT_BUCKETS,
    "awdpacxj": DEFAULT_BUCKETS,
    "msci_imi": DEFAULT_BUCKETS,

    # New higher-vol names
    "sox": SOX_BUCKETS,
    "srvr": SRVR_BUCKETS,
    "sruuf": SRUUF_BUCKETS,
    "remx": REMX_BUCKETS,
    "ufo": UFO_BUCKETS,
    "btc": BTC_BUCKETS,
}


def get_buckets_for_index(ix_id: str) -> List[Bucket]:
    """Return bucket list for a given index id, defaulting to baseline."""
    return BUCKETS_BY_INDEX_ID.get(ix_id, DEFAULT_BUCKETS)


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
