# main.py
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import smtplib
import socket

from spx_alert.config import (
    INDEX_TICKER,
    LOOKBACK_DAYS,
    SAVE_PLOTS,
    PLOTS_DIR,
    now_str,
)
from spx_alert.buckets import DEFAULT_BUCKETS, pick_bucket
from spx_alert.data import fetch_series, compute_drawdown
from spx_alert.state import load_state, save_state
from spx_alert.plotting import make_alert_plot
from spx_alert.logging_utils import (
    append_csv_log,
    clean_old_plots,
    clean_old_log_rows,
)
from spx_alert.email_utils import (
    send_email,
    make_email_subject,
    make_email_body,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for the alert script."""
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


def open_plot(plot_path) -> None:
    """Open the given plot file using the default image viewer, if possible."""
    if not plot_path:
        return
    try:
        if os.name == "nt":
            os.startfile(str(plot_path))  # type: ignore[attr-defined]
        elif sys.platform.startswith("darwin"):
            subprocess.run(["open", str(plot_path)], check=False)
        else:
            subprocess.run(["xdg-open", str(plot_path)], check=False)
    except Exception as e:  # noqa: BLE001
        print(f"[{now_str()}] Unable to open plot viewer: {e}")


class DipAlertRunner:
    """Encapsulates the main alert logic for test and normal runs."""

    def __init__(self) -> None:
        self.ticker = INDEX_TICKER

    # ----------------- Test email -----------------

    def run_test_email(self) -> None:
        """Send a simple SMTP wiring test email."""
        subject = "TEST — SPX Dip Alert wiring OK"
        body = (
            "[SPX Dip Alert — TEST]\n"
            f"Host: {platform.node()}\n"
            f"Time: {now_str()}\n"
            "✓ SMTP connection successful."
        )
        send_email(subject, body)
        print(f"[{now_str()}] Test email sent.")

    # ----------------- Test bucket -----------------

    def run_test_bucket(self, bucket_id: str, show_plot: bool) -> None:
        """Simulate a bucket being triggered without altering state."""
        series = fetch_series(self.ticker, LOOKBACK_DAYS)
        close, peak, dd, peak_date = compute_drawdown(series)

        bucket = next((b for b in DEFAULT_BUCKETS if b.id == bucket_id), None)
        if bucket is None:
            print(f"[{now_str()}] Unknown bucket {bucket_id}")
            return

        plot_path = (
            make_alert_plot(
                series,
                title=f"{self.ticker} — Close vs Recent High (TEST)",
            )
            if SAVE_PLOTS
            else None
        )

        if show_plot:
            open_plot(plot_path)

        subject = make_email_subject(bucket, dd)
        body = make_email_body(
            self.ticker,
            close,
            peak,
            dd,
            peak_date,
            bucket,
            "(SIMULATED ALERT)",
        )
        html_kwargs = dict(
            ticker=self.ticker,
            close=close,
            peak=peak,
            dd=dd,
            peak_date=peak_date,
            bucket=bucket,
        )

        send_email(
            subject,
            body_text=body,
            html_kwargs=html_kwargs,
            attachments=[plot_path] if plot_path else None,
            inline_path=plot_path,
        )

        append_csv_log(
            now_str(),
            bucket,
            dd,
            close,
            peak,
            str(peak_date.date()),
            plot_path,
            self.ticker,
            is_test=True,
        )
        print(f"[{now_str()}] Test bucket email sent for {bucket.id}.")

    # ----------------- Normal run -----------------

    def run_normal(self, show_plot: bool) -> None:
        """Perform a normal run: check current drawdown and alert if needed."""
        state = load_state()
        series = fetch_series(self.ticker, LOOKBACK_DAYS)
        close, peak, dd, peak_date = compute_drawdown(series)
        bucket = pick_bucket(dd, DEFAULT_BUCKETS)

        if not bucket:
            print(
                f"[{now_str()}] No alert. DD {dd:.2f}% "
                f"(close {close:.2f}, peak {peak:.2f})."
            )
            return

        peak_key = str(peak_date.date())
        if bucket.id in state.get("fired_buckets", {}).get(peak_key, []):
            print(f"[{now_str()}] Bucket {bucket.id} already fired for this peak.")
            return

        plot_path = (
            make_alert_plot(
                series,
                title=f"{self.ticker} — Close vs Recent High",
            )
            if SAVE_PLOTS
            else None
        )

        if show_plot:
            open_plot(plot_path)

        subject = make_email_subject(bucket, dd)
        body = make_email_body(
            self.ticker,
            close,
            peak,
            dd,
            peak_date,
            bucket,
        )
        html_kwargs = dict(
            ticker=self.ticker,
            close=close,
            peak=peak,
            dd=dd,
            peak_date=peak_date,
            bucket=bucket,
        )

        try:
            send_email(
                subject,
                body_text=body,
                html_kwargs=html_kwargs,
                attachments=[plot_path] if plot_path else None,
                inline_path=plot_path,
            )
            print(f"[{now_str()}] Alert sent.")
        except (smtplib.SMTPException, socket.timeout) as e:
            print(f"[{now_str()}] ERROR sending email: {e}")
            return

        append_csv_log(
            now_str(),
            bucket,
            dd,
            close,
            peak,
            str(peak_date.date()),
            plot_path,
            self.ticker,
            is_test=False,
        )
        state.setdefault("fired_buckets", {}).setdefault(peak_key, []).append(bucket.id)
        save_state(state)
        print(f"[{now_str()}] Logged and state updated.")


def main() -> None:
    args = parse_args()

    # housekeeping
    clean_old_plots(PLOTS_DIR)
    clean_old_log_rows()

    runner = DipAlertRunner()

    if args.test:
        runner.run_test_email()
    elif args.test_bucket:
        runner.run_test_bucket(args.test_bucket, args.show_plot)
    else:
        runner.run_normal(args.show_plot)


if __name__ == "__main__":
    main()
