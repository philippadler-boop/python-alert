# spx_alert/exceptions.py
from __future__ import annotations


class DataFetchError(RuntimeError):
    """Raised when price data cannot be fetched or is unusable."""
    pass
