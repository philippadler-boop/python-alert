from __future__ import annotations

import argparse

from src import DEFAULT_BUCKETS, INDEXES, DEFAULT_INDEX_ID, run_from_args


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for the alert tool."""
    parser = argparse.ArgumentParser(
        prog="Alert Tool",
        description=(
            "Dip Alert / Trend Entry — drawdown-based dip alerts and "
            "MA200-based trend-entry alerts with email notifications and plot generation."
        ),
        epilog=(
            "Examples:\n"
            "  python main.py --index all --both-modes          # Run both dip + trend in combined mode\n"
            "  python main.py --index sox --dip-entry           # Dip alerts only\n"
            "  python main.py --index srvr --trend-entry --test # Test trend email\n"
            "  python main.py --index spx --test-bucket B20     # Simulate dip bucket\n"
            "  python main.py --help                            # Show this help"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
            "Not supported together with combined both-modes execution."
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
        help="Open the saved plot locally after generation (dip or trend runs).",
    )

    parser.add_argument(
        "--peak-window",
        metavar="WINDOW",
        help=(
            "Peak window for dip mode drawdown calculation: "
            "'1y' (365 days), 'ytd' (year-to-date), 'all', or 'date:YYYY-MM-DD'. "
            "Precedence: CLI > env PEAK_WINDOW > default '1y'"
        ),
    )

    # --- Mode selection ---
    mode_group = parser.add_mutually_exclusive_group()

    mode_group.add_argument(
        "--dip-entry",
        action="store_true",
        help=(
            "Run dip alerts only (no trend-entry checks). "
            "Required when using --test-bucket."
        ),
    )

    mode_group.add_argument(
        "--trend-entry",
        action="store_true",
        help=(
            "Run MA200-based trend-entry checks only (no dip alerts). "
            "Sends an alert when price has crossed from below to above the "
            "200-day MA and stayed above for the configured number of "
            "trading days (default 5)."
        ),
    )

    mode_group.add_argument(
        "--both-modes",
        action="store_true",
        help=(
            "Run both dip + trend checks in one pass (default if no mode specified). "
            "Optimized: fetches price data once, computes MA200 once (with caching). "
            "Not compatible with --test-bucket"
        ),
    )

    return parser.parse_args()


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    run_from_args(args)


if __name__ == "__main__":
    main()
