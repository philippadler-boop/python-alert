# spx_alert/dip_runner.py
from __future__ import annotations

import platform
from pathlib import Path

import pandas as pd

from .alert_base import AlertBaseRunner
from .buckets import Bucket, pick_bucket, get_buckets_for_index
from .config import SAVE_PLOTS, ATTACH_PLOT_ON_TEST, now_str
from .data import compute_drawdown
from .email_utils import send_email, make_email_subject, make_email_body
from .logging_utils import append_csv_log
from .plotting import make_alert_plot
from .state import load_state, save_state


class DipAlertRunner(AlertBaseRunner):
    """Dip-based drawdown alerts using configured buckets."""

    def __init__(self, ix, peak_window: str | None = None) -> None:
        super().__init__(ix, peak_window=peak_window)
        self.buckets = get_buckets_for_index(ix.id)

    # -------- test helpers --------

    def run_test_email(self) -> None:
        """Send a simple SMTP wiring test email for this index."""
        subject = f"TEST — {self.ix.name} Dip Alert wiring OK"
        body = (
            f"[{self.ix.name} Dip Alert — TEST]\n"
            f"Host: {platform.node()}\n"
            f"Time: {now_str()}\n"
            "✓ SMTP connection successful."
        )
        send_email(subject, body_text=body)
        print(f"[{now_str()}] Dip test email sent.")

    def run_test_bucket(self, bucket_id: str, show_plot: bool) -> None:
        """Simulate a bucket alert without touching state."""
        series = self.fetch_series()
        close, peak, dd, peak_date = compute_drawdown(series)

        bucket = next((b for b in self.buckets if b.id == bucket_id), None)
        if bucket is None:
            print(f"[{now_str()}] Unknown bucket {bucket_id}")
            return

        plot_path: Path | None = None
        if SAVE_PLOTS:
            plot_path = make_alert_plot(
                self.ix,
                series,
                title=f"{self.ix.name} — Close vs Recent High (TEST)",
            )
        if show_plot:
            self.open_plot(plot_path)

        subject = make_email_subject(self.ix, bucket, dd)
        body = make_email_body(
            self.ix,
            close,
            peak,
            dd,
            peak_date,
            bucket,
            note="(SIMULATED ALERT)",
        )
        html_kwargs = dict(
            ix=self.ix,
            close=close,
            peak=peak,
            dd=dd,
            peak_date=peak_date,
            bucket=bucket,
        )

        attachments = None
        if plot_path and ATTACH_PLOT_ON_TEST:
            attachments = [plot_path]

        send_email(
            subject,
            body_text=body,
            html_kwargs=html_kwargs,
            attachments=attachments,
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

    # -------- normal dip run --------

    def run_with_series(self, series: pd.Series, show_plot: bool) -> None:
        """Perform a dip alert run using a pre-fetched series."""
        state = load_state(self.ix)
        close, peak, dd, peak_date = compute_drawdown(series)
        bucket = pick_bucket(dd, self.buckets)

        if not bucket:
            print(
                f"[{now_str()}] No dip alert. [{self.ix.id}] DD {dd:.2f}% "
                f"(close {close:.2f}, peak {peak:.2f})."
            )
            return

        peak_key = str(peak_date.date())
        already = state.get("fired_buckets", {}).get(peak_key, [])
        if bucket.id in already:
            print(
                f"[{now_str()}] [{self.ix.id}] Bucket {bucket.id} "
                f"already fired for this peak."
            )
            return

        plot_path: Path | None = None
        if SAVE_PLOTS:
            plot_path = make_alert_plot(
                self.ix,
                series,
                title=f"{self.ix.name} — Close vs Recent High",
            )
        if show_plot:
            self.open_plot(plot_path)

        subject = make_email_subject(self.ix, bucket, dd)
        body = make_email_body(
            self.ix,
            close,
            peak,
            dd,
            peak_date,
            bucket,
        )
        html_kwargs = dict(
            ix=self.ix,
            close=close,
            peak=peak,
            dd=dd,
            peak_date=peak_date,
            bucket=bucket,
        )

        attachments = [plot_path] if plot_path is not None else None

        try:
            send_email(
                subject,
                body_text=body,
                html_kwargs=html_kwargs,
                attachments=attachments,
                inline_path=plot_path,
            )
            print(f"[{now_str()}] [{self.ix.id}] LIVE dip alert sent.")
        except Exception:
            # Do not update state on failure
            return

        state.setdefault("fired_buckets", {}).setdefault(peak_key, []).append(
            bucket.id
        )
        save_state(state, self.ix)
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
        print(f"[{now_str()}] [{self.ix.id}] Dip alert logged and state updated.")

    def run(self, show_plot: bool) -> None:
        """Normal dip run: fetch series and evaluate buckets."""
        series = self.fetch_series()
        self.run_with_series(series, show_plot)
