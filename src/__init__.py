# spx_alert/__init__.py
"""SPX Dip Alert package.

Provides utilities for:
- fetching SPX data from yfinance
- computing drawdowns from recent highs
- defining dip buckets
- generating plots
- sending email alerts
- logging alerts and cleaning up old data
- simple JSON state tracking to avoid duplicate alerts
"""
