# main.py
from __future__ import annotations

import argparse

from spx_alert.buckets import DEFAULT_BUCKETS
from spx_alert.config import INDEXES, DEFAULT_INDEX_ID
from spx_alert.runner import run_from_args


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for the dip alert."""
    parser = argparse.ArgumentParser(
        description="Dip Alert — drawdown-based dip buying alerts."
    )
    parser.add_argument(
        "--index",
        choices=list(INDEXES.keys()) + ["all"],
        default=DEFAULT_INDEX_ID,
        help=(
            "Which index configuration to use "
            f"(default: {DEFAULT_INDEX_ID}). Use 'all' to run for all indices."
        )
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send a simple SMTP wiring test email and exit.",
    )
    parser.add_argument(
        "--test-bucket",
        choices=[b.id for b in DEFAULT_BUCKETS],
        help="Send a simulated bucket alert and exit (does not modify state).",
    )
    parser.add_argument(
        "--show-plot",
        action="store_true",
        help="Open the saved plot locally after generation (manual runs).",
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
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    run_from_args(args)


if __name__ == "__main__":
    main()
