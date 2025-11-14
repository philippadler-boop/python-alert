# main.py
from __future__ import annotations

import argparse

from spx_alert.buckets import DEFAULT_BUCKETS
from spx_alert.config import INDEXES, DEFAULT_INDEX_ID
from spx_alert.runner import run_from_args


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for the alert tool."""
    parser = argparse.ArgumentParser(
        description="Dip Alert / Trend Entry — drawdown-based dip alerts and MA200-based entry alerts."
    )

    parser.add_argument(
        "--index",
        choices=list(INDEXES.keys()) + ["all"],
        default=DEFAULT_INDEX_ID,
        help=(
            "Which index configuration to use "
            f"(default: {DEFAULT_INDEX_ID}). Use 'all' to run for all indices."
        ),
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Send a simple SMTP wiring test email and exit (dip-alert mode only).",
    )

    parser.add_argument(
        "--test-bucket",
        choices=[b.id for b in DEFAULT_BUCKETS],
        help=(
            "Send a simulated bucket alert and exit (does not modify state). "
            "Dip-alert mode only."
        ),
    )

    parser.add_argument(
        "--show-plot",
        action="store_true",
        help="Open the saved plot locally after generation (dip-alert runs).",
    )

    parser.add_argument(
        "--peak-window",
        metavar="WINDOW",
        help=(
            "Recent-high window for drawdown: "
            "'1y' (last 365 days), 'ytd' (year-to-date), "
            "or 'date:YYYY-MM-DD' for a custom anchor date. "
            "If omitted, uses PEAK_WINDOW_DEFAULT from config."
        ),
    )

    parser.add_argument(
        "--trend-entry",
        action="store_true",
        help=(
            "Run MA200-based trend entry checks instead of dip alerts. "
            "For each index, send an email when price has crossed from below "
            "to above the 200-day MA and stayed above for 5 trading days."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    run_from_args(args)


if __name__ == "__main__":
    main()
