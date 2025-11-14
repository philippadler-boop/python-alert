# spx_alert/runner.py
from __future__ import annotations

import os
import platform
import subprocess
import sys
import smtplib
import socket

from .config import SPX_INDEX, IndexConfig, SAVE_PLOTS, now_str
from .buckets import DEFAULT_BUCKETS, pick_bucket
from .data import fetch_series, compute_drawdown
from .state import load_state, save_state
from .plotting import make_alert_plot
from .logging_utils import (
    append_csv_log,
    clean_old_plots,
    clean_old_log_rows,
)
from .email_utils import (
    send_email,
    make_email_subject,
    make_email_body,
)


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
    """Encapsulates the main dip-alert logic for a given index."""

    def __init__(self, ix: IndexConfig = SPX_INDEX) -> None:
        self.ix = ix

    # ----------------- Test email -----------------

    def run_test_email(self) -> None:
        """Send a simple SMTP wiring test email."""
        subject = f"TEST — {self.ix.name} Dip Alert wiring OK"
        body = (
            f"[{self.ix.name} Dip Alert — TEST]\n"
            f"Host: {platform.node()}\n"
            f"Time: {now_str()}\n"
            "✓ SMTP connection successful."
        )
        send_email(subject, body)
        print(f"[{now_str()}] Test email sent.")

    # ----------------- Test bucket -----------------

    def run_test_bucket(self, bucket_id: str, show_plot: bool) -> None:
        """Simulate a bucket being triggered without altering state."""
        series = fetch_series(self.ix)
        close, peak, dd, peak_date = compute_drawdown(series)

        bucket = next((b for b in DEFAULT_BUCKETS if b.id == bucket_id), None)
        if bucket is None:
            print(f"[{now_str()}] Unknown bucket {bucket_id}")
            return

        plot_path = (
            make_alert_plot(
                self.ix,
                series,
                title=f"{self.ix.name} — Close vs Recent High (TEST)",
            )
            if SAVE_PLOTS
            else None
        )

        if show_plot:
            open_plot(plot_path)

        subject = make_email_subject(bucket, dd)
        body = make_email_body(
            self.ix.ticker,
            close,
            peak,
            dd,
            peak_date,
            bucket,
            "(SIMULATED ALERT)",
        )
        html_kwargs = dict(
            ticker=self.ix.ticker,
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
            self.ix,
            now_str(),
            bucket,
            dd,
            close,
            peak,
            str(peak_date.date()),
            plot_path,
            self.ix.ticker,
            is_test=True,
        )
        print(f"[{now_str()}] Test bucket email sent for {bucket.id}.")

    # ----------------- Normal run -----------------

    def run_normal(self, show_plot: bool) -> None:
        """Perform a normal run: check current drawdown and alert if needed."""
        state = load_state(self.ix)
        series = fetch_series(self.ix)
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
                self.ix,
                series,
                title=f"{self.ix.name} — Close vs Recent High",
            )
            if SAVE_PLOTS
            else None
        )

        if show_plot:
            open_plot(plot_path)

        subject = make_email_subject(bucket, dd)
        body = make_email_body(
            self.ix.ticker,
            close,
            peak,
            dd,
            peak_date,
            bucket,
        )
        html_kwargs = dict(
            ticker=self.ix.ticker,
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
            self.ix,
            now_str(),
            bucket,
            dd,
            close,
            peak,
            str(peak_date.date()),
            plot_path,
            self.ix.ticker,
            is_test=False,
        )
        state.setdefault("fired_buckets", {}).setdefault(peak_key, []).append(bucket.id)
        save_state(state, self.ix)
        print(f"[{now_str()}] Logged and state updated.")


def run_from_args(args) -> None:
    """Entry point used by main.py to dispatch based on CLI args."""
    ix = SPX_INDEX  # single index for now, but ready to extend

    # housekeeping (per run, per index)
    clean_old_plots(ix.plots_dir)
    clean_old_log_rows(ix)

    runner = DipAlertRunner(ix)

    if args.test:
        runner.run_test_email()
    elif args.test_bucket:
        runner.run_test_bucket(args.test_bucket, args.show_plot)
    else:
        runner.run_normal(args.show_plot)
