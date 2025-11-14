# spx_alert/runner.py
from __future__ import annotations

import os
import platform
import subprocess
import sys
import smtplib
import socket
from dataclasses import dataclass
from typing import Optional

from .config import (
    INDEXES,
    DEFAULT_INDEX_ID,
    IndexConfig,
    SAVE_PLOTS,
    ATTACH_PLOT_ON_TEST,
    now_str,
    PEAK_WINDOW_DEFAULT,
)
from .buckets import DEFAULT_BUCKETS, pick_bucket, Bucket, get_buckets_for_index
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


@dataclass
class AlertContext:
    """Values needed to construct an alert for a given index snapshot."""

    series: object
    close: float
    peak: float
    dd: float
    peak_date: object  # pandas.Timestamp-like, but we keep it generic


class DipAlertRunner:
    """Encapsulates the main dip-alert logic for a given index."""

    def __init__(self, ix: IndexConfig, peak_window: str) -> None:
        self.ix = ix
        self.peak_window = peak_window
        # use index-specific bucket set (spx, ndx, sox, srvr, ura, remx, ...)
        self.buckets = get_buckets_for_index(ix.id)

    # ----------------- internal helpers -----------------

    def _build_context(self) -> AlertContext:
        """Fetch latest series and compute drawdown context."""
        series = fetch_series(self.ix)
        close, peak, dd, peak_date = compute_drawdown(series, self.peak_window)
        return AlertContext(
            series=series,
            close=close,
            peak=peak,
            dd=dd,
            peak_date=peak_date,
        )

    def _make_plot(self, ctx: AlertContext, *, title: str, show_plot: bool):
        """Create plot (if enabled) and optionally open it."""
        plot_path: Optional[object] = None
        if SAVE_PLOTS:
            plot_path = make_alert_plot(self.ix, ctx.series, title=title)

        if show_plot:
            open_plot(plot_path)

        return plot_path

    def _send_and_log(
        self,
        *,
        ctx: AlertContext,
        bucket: Bucket,
        plot_path,
        is_test: bool,
        extra_note: str = "",
    ) -> None:
        """Compose email from context + bucket, send it, and log the event."""
        subject = make_email_subject(self.ix, bucket, ctx.dd)
        body = make_email_body(
            self.ix,
            ctx.close,
            ctx.peak,
            ctx.dd,
            ctx.peak_date,
            bucket,
            note=extra_note,
        )
        html_kwargs = dict(
            ix=self.ix,
            close=ctx.close,
            peak=ctx.peak,
            dd=ctx.dd,
            peak_date=ctx.peak_date,
            bucket=bucket,
        )

        # Attach plot only if:
        # - we have a plot, AND
        # - it's a live alert, OR test alerts are configured to attach
        attachments = None
        if plot_path and (not is_test or ATTACH_PLOT_ON_TEST):
            attachments = [plot_path]

        try:
            send_email(
                subject,
                body_text=body,
                html_kwargs=html_kwargs,
                attachments=attachments,
                inline_path=plot_path,
            )
            tag = "TEST" if is_test else "LIVE"
            print(f"[{now_str()}] [{self.ix.id}] {tag} alert sent.")
        except (smtplib.SMTPException, socket.timeout) as e:
            print(f"[{now_str()}] [{self.ix.id}] ERROR sending email: {e}")
            # In test mode we just log to console; in live mode the caller
            # will decide whether to proceed with state updates.
            if not is_test:
                raise

        append_csv_log(
            self.ix,
            now_str(),
            bucket,
            ctx.dd,
            ctx.close,
            ctx.peak,
            str(ctx.peak_date.date()),
            plot_path,
            self.ix.ticker,
            is_test=is_test,
        )

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
        ctx = self._build_context()

        bucket = next((b for b in self.buckets if b.id == bucket_id), None)
        if bucket is None:
            print(f"[{now_str()}] Unknown bucket {bucket_id}")
            return

        plot_path = self._make_plot(
            ctx,
            title=f"{self.ix.name} — Close vs Recent High (TEST)",
            show_plot=show_plot,
        )

        # Simulated alert, state not touched
        self._send_and_log(
            ctx=ctx,
            bucket=bucket,
            plot_path=plot_path,
            is_test=True,
            extra_note="(SIMULATED ALERT)",
        )
        print(f"[{now_str()}] Test bucket email sent for {bucket.id}.")

    # ----------------- Normal run -----------------

    def run_normal(self, show_plot: bool) -> None:
        """Perform a normal run: check current drawdown and alert if needed."""
        state = load_state(self.ix)
        ctx = self._build_context()
        bucket = pick_bucket(ctx.dd, self.buckets)

        if not bucket:
            print(
                f"[{now_str()}] No alert. [{self.ix.id}] DD {ctx.dd:.2f}% "
                f"(close {ctx.close:.2f}, peak {ctx.peak:.2f})."
            )
            return

        peak_key = str(ctx.peak_date.date())
        already = state.get("fired_buckets", {}).get(peak_key, [])
        if bucket.id in already:
            print(
                f"[{now_str()}] [{self.ix.id}] Bucket {bucket.id} "
                f"already fired for this peak."
            )
            return

        plot_path = self._make_plot(
            ctx,
            title=f"{self.ix.name} — Close vs Recent High",
            show_plot=show_plot,
        )

        try:
            self._send_and_log(
                ctx=ctx,
                bucket=bucket,
                plot_path=plot_path,
                is_test=False,
            )
        except Exception:
            # Email failed; do not update state or log as fired.
            return

        # Only mark bucket as fired if email was successfully sent
        state.setdefault("fired_buckets", {}).setdefault(peak_key, []).append(
            bucket.id
        )
        save_state(state, self.ix)
        print(f"[{now_str()}] [{self.ix.id}] Logged and state updated.")


def _run_single_index(ix: IndexConfig, args, peak_window: str) -> None:
    """Run the alert logic for a single index (including housekeeping)."""
    # housekeeping (per run, per index)
    clean_old_plots(ix.plots_dir)
    clean_old_log_rows(ix)

    runner = DipAlertRunner(ix, peak_window=peak_window)

    if args.test:
        runner.run_test_email()
    elif args.test_bucket:
        runner.run_test_bucket(args.test_bucket, args.show_plot)
    else:
        runner.run_normal(args.show_plot)


def run_from_args(args) -> None:
    """Entry point used by main.py to dispatch based on CLI args."""
    ix_id = getattr(args, "index", None) or DEFAULT_INDEX_ID

    from .config import INDEXES  # avoid circular imports at module load

    # Determine peak window: CLI overrides env/DEFAULT
    peak_window = getattr(args, "peak_window", None) or PEAK_WINDOW_DEFAULT

    if ix_id == "all":
        # For safety, we do not support --test / --test-bucket with 'all'
        if args.test or args.test_bucket:
            print(
                f"[{now_str()}] '--index all' cannot be combined with "
                "--test or --test-bucket. Please choose a specific index."
            )
            return

        # Run normal mode for all configured indices
        for ix_key, ix in INDEXES.items():
            print(f"[{now_str()}] Running alert for index '{ix_key}'...")
            _run_single_index(ix, args, peak_window=peak_window)

        return

    # Single-index mode (existing behavior)
    ix = INDEXES.get(ix_id)
    if not ix:
        available = ", ".join(INDEXES.keys())
        print(f"[{now_str()}] Unknown index '{ix_id}'. Available: {available}")
        return

    _run_single_index(ix, args, peak_window=peak_window)
