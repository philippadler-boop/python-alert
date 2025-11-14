# main.py
from __future__ import annotations

import argparse

from spx_alert.buckets import DEFAULT_BUCKETS
from spx_alert.runner import run_from_args


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for the SPX dip alert."""
    parser = argparse.ArgumentParser(
        description="SPX Dip Alert — drawdown-based dip buying alerts."
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
    return parser.parse_args()


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    run_from_args(args)


if __name__ == "__main__":
    main()
