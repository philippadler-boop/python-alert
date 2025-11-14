from __future__ import annotations

import argparse

from src import DEFAULT_BUCKETS, INDEXES, DEFAULT_INDEX_ID, run_from_args


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for the alert tool."""
    parser = argparse.ArgumentParser(
        description=(
            "Dip Alert / Trend Entry — drawdown-based dip alerts and "
            "MA200-based trend-entry alerts."
        )
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
        help=(
            "Dip mode: send a simple SMTP wiring test email and exit. "
            "Trend mode: send a trend-entry test email (no state change). "
            "Not supported with --both-modes."
        ),
    )

    parser.add_argument(
        "--test-bucket",
        choices=[b.id for b in DEFAULT_BUCKETS],
        help=(
            "Send a simulated dip bucket alert and exit (does not modify state). "
            "Only valid in dip mode (no --trend-entry / --both-modes)."
        ),
    )

    parser.add_argument(
        "--show-plot",
        action="store_true",
        help="Open the saved plot locally after generation (dip runs).",
    )

    parser.add_argument(
        "--peak-window",
        metavar="WINDOW",
        help=(
            "Recent-high window for drawdown in dip mode: "
            "'1y' (last 365 days), 'ytd' (year-to-date), "
            "or 'date:YYYY-MM-DD' for a custom anchor date. "
            "If omitted, uses PEAK_WINDOW_DEFAULT from config."
        ),
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--trend-entry",
        action="store_true",
        help=(
            "Run MA200-based trend entry checks instead of dip alerts. "
            "Sends an alert when price has crossed from below to above the "
            "200-day MA and stayed above for 5 trading days."
        ),
    )
    mode_group.add_argument(
        "--both-modes",
        action="store_true",
        help=(
            "Run both dip alerts and trend-entry checks in a single pass, "
            "reusing the same fetched price series per index. "
            "Not compatible with --test or --test-bucket."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    run_from_args(args)


if __name__ == "__main__":
    main()
