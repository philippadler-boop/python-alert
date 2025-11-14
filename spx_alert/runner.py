# spx_alert/runner.py
from __future__ import annotations

import json
import os
import platform
import smtplib
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd

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
from .data import fetch_series, compute_drawdown, compute_trend_entry
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
    make_trend_entry_subject,
    make_trend_entry_body,
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
    """Values needed to construct a dip alert for a given index snapshot."""

    series: pd.Series
    close: float
    peak: float
    dd: float
    peak_date: Any  # pandas.Timestamp-like


# ----------------- Trend-entry profiles & checklist loading -----------------


@dataclass(frozen=True)
class TrendEntryProfile:
    """Configuration for MA200-based trend entry alerts for a given index."""

    id: str
    hold_days: int = 5
    ma_window: int = 200
    enabled: bool = True


TREND_PROFILES: Dict[str, TrendEntryProfile] = {
    "sox": TrendEntryProfile(id="sox"),
    "srvr": TrendEntryProfile(id="srvr"),
    "ura": TrendEntryProfile(id="ura"),
    # Add "remx": TrendEntryProfile(id="remx") if you want a REMX trend-entry as well.
}


CHECKLIST_FILE = Path(__file__).with_name("trend_checklists.json")


def load_trend_checklists() -> dict[str, list[str]]:
    """Load trend entry checklists from JSON; return {} on error."""
    try:
        with CHECKLIST_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        norm: dict[str, list[str]] = {}
        for k, v in data.items():
            if isinstance(v, list):
                norm[k] = [str(item) for item in v]
        return norm
    except Exception as e:  # noqa: BLE001
        print(
            f"[{now_str()}] [WARN] Unable to load trend_checklists.json "
            f"from {CHECKLIST_FILE!s} ({e}). Falling back to empty checklists."
        )
        return {}


class DipAlertRunner:
    """Encapsulates the main alert logic for a given index."""

    def __init__(self, ix: IndexConfig, peak_window: str) -> None:
        self.ix = ix
        self.peak_window = peak_window
        self.buckets = get_buckets_for_index(ix.id)

    # ----------------- dip helpers -----------------

    def _build_context_from_series(self, series: pd.Series) -> AlertContext:
        """Compute dip-alert context given a pre-fetched series."""
        close, peak, dd, peak_date = compute_drawdown(series)
        return AlertContext(
            series=series,
            close=close,
            peak=peak,
            dd=dd,
            peak_date=peak_date,
        )

    def _build_context(self) -> AlertContext:
        """Fetch latest series and compute drawdown context."""
        series = fetch_series(self.ix)
        return self._build_context_from_series(series)

    def _make_plot(self, ctx: AlertContext, *, title: str, show_plot: bool):
        """Create plot (if enabled) and optionally open it."""
        plot_path: Optional[Path] = None
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
        plot_path: Optional[Path],
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

        attachments: Optional[list[Path]] = None
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
            print(f"[{now_str()}] [{self.ix.id}] {tag} dip alert sent.")
        except (smtplib.SMTPException, socket.timeout) as e:
            print(f"[{now_str()}] [{self.ix.id}] ERROR sending dip email: {e}")
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

    # ----------------- dip test & normal runs -----------------

    def run_test_email(self) -> None:
        """Send a simple SMTP wiring test email (dip-alert mode)."""
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

        self._send_and_log(
            ctx=ctx,
            bucket=bucket,
            plot_path=plot_path,
            is_test=True,
            extra_note="(SIMULATED ALERT)",
        )
        print(f"[{now_str()}] Test bucket email sent for {bucket.id}.")

    def run_normal_with_series(self, series: pd.Series, show_plot: bool) -> None:
        """Normal dip alert run using a pre-fetched series."""
        state = load_state(self.ix)
        ctx = self._build_context_from_series(series)
        bucket = pick_bucket(ctx.dd, self.buckets)

        if not bucket:
            print(
                f"[{now_str()}] No dip alert. [{self.ix.id}] DD {ctx.dd:.2f}% "
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
            return

        state.setdefault("fired_buckets", {}).setdefault(peak_key, []).append(
            bucket.id
        )
        save_state(state, self.ix)
        print(f"[{now_str()}] [{self.ix.id}] Dip alert logged and state updated.")

    def run_normal(self, show_plot: bool) -> None:
        """Normal dip alert run (fetches its own series)."""
        series = fetch_series(self.ix)
        self.run_normal_with_series(series, show_plot)

    # ----------------- trend-entry runs -----------------

    def run_trend_entry(self, series: Optional[pd.Series] = None, *, is_test: bool = False) -> None:
        """Check MA200-based trend entry and email if conditions are met.

        Uses compute_trend_entry() from data.py. If `series` is None,
        fetches prices first.
        """
        profile = TREND_PROFILES.get(self.ix.id)
        if not profile or not profile.enabled:
            print(
                f"[{now_str()}] Trend entry profile not enabled for index '{self.ix.id}'."
            )
            return

        if series is None:
            series = fetch_series(self.ix)

        try:
            (
                close_today,
                ma_today,
                pct_diff,
                all_above,
                crossed_from_below,
                today_idx,
            ) = compute_trend_entry(
                series,
                ma_window=profile.ma_window,
                hold_days=profile.hold_days,
            )
        except ValueError as e:
            print(f"[{now_str()}] [{self.ix.id}] Trend entry not evaluated: {e}")
            return

        # Load & update state
        state = load_state(self.ix)
        trend_state = state.get("trend_entry", {})
        last_alert_date = trend_state.get("last_alert_date")  # ISO string or None

        # Track last status (above/below) for info
        is_above_today = pct_diff >= 0.0
        trend_state["last_status"] = "above" if is_above_today else "below"

        today_iso = str(today_idx.date())

        # Build checklist from JSON
        checklists = load_trend_checklists()
        checklist = checklists.get(
            self.ix.id,
            ["(No specific fundamentals checklist configured for this index.)"],
        )

        # For test mode: always send a test email with current metrics, no state change
        if is_test:
            subject = make_trend_entry_subject(self.ix, is_test=True)
            body = make_trend_entry_body(
                self.ix,
                close_today,
                ma_today,
                pct_diff,
                profile.hold_days,
                checklist,
                is_test=True,
            )
            try:
                send_email(subject, body_text=body)
                print(
                    f"[{now_str()}] [{self.ix.id}] Trend-entry TEST email sent "
                    f"(close {close_today:.2f}, MA{profile.ma_window} {ma_today:.2f})."
                )
            except (smtplib.SMTPException, socket.timeout) as e:
                print(f"[{now_str()}] [{self.ix.id}] ERROR sending trend test email: {e}")
            # Do not modify trend_state on test
            return

        # Live mode: only send when a new confirmed cross has occurred
        if not (all_above and crossed_from_below):
            state["trend_entry"] = trend_state
            save_state(state, self.ix)
            print(
                f"[{now_str()}] No trend entry alert for '{self.ix.id}'. "
                f"(all_above={all_above}, crossed_from_below={crossed_from_below})"
            )
            return

        if last_alert_date == today_iso:
            state["trend_entry"] = trend_state
            save_state(state, self.ix)
            print(
                f"[{now_str()}] Trend entry for '{self.ix.id}' already alerted today."
            )
            return

        subject = make_trend_entry_subject(self.ix, is_test=False)
        body = make_trend_entry_body(
            self.ix,
            close_today,
            ma_today,
            pct_diff,
            profile.hold_days,
            checklist,
            is_test=False,
        )

        try:
            send_email(subject, body_text=body)
            print(
                f"[{now_str()}] [{self.ix.id}] Trend entry alert sent "
                f"(close {close_today:.2f}, MA{profile.ma_window} {ma_today:.2f})."
            )
        except (smtplib.SMTPException, socket.timeout) as e:
            print(f"[{now_str()}] [{self.ix.id}] ERROR sending trend email: {e}")
            state["trend_entry"] = trend_state
            save_state(state, self.ix)
            return

        trend_state["last_alert_date"] = today_iso
        state["trend_entry"] = trend_state
        save_state(state, self.ix)

    # ----------------- combined mode -----------------

    def run_both(self, show_plot: bool) -> None:
        """Run dip + trend-entry logic on the same fetched series."""
        series = fetch_series(self.ix)
        # Run dip alerts on this series
        self.run_normal_with_series(series, show_plot)
        # Run trend-entry check on the same data
        self.run_trend_entry(series=series, is_test=False)


# ----------------- Job orchestration -----------------


def _run_single_index(ix: IndexConfig, args, peak_window: str, *, mode: str) -> None:
    """Run the alert logic for a single index (including housekeeping)."""
    clean_old_plots(ix.plots_dir)
    clean_old_log_rows(ix)

    runner = DipAlertRunner(ix, peak_window=peak_window)

    if mode == "dip":
        if args.test:
            runner.run_test_email()
        elif args.test_bucket:
            runner.run_test_bucket(args.test_bucket, args.show_plot)
        else:
            runner.run_normal(args.show_plot)
        return

    if mode == "trend":
        if args.test:
            runner.run_trend_entry(is_test=True)
        else:
            runner.run_trend_entry(is_test=False)
        return

    if mode == "both":
        # Test / test-bucket not allowed in combined mode (validated earlier)
        runner.run_both(args.show_plot)
        return


def run_from_args(args) -> None:
    """Entry point used by main.py to dispatch based on CLI args."""
    ix_id = getattr(args, "index", None) or DEFAULT_INDEX_ID

    from .config import INDEXES  # avoid circular imports at module load

    peak_window = getattr(args, "peak_window", None) or PEAK_WINDOW_DEFAULT

    # Determine mode: dip (default), trend-only, or both
    trend_flag = getattr(args, "trend_entry", False)
    both_flag = getattr(args, "both_modes", False)

    if both_flag and trend_flag:
        print(
            f"[{now_str()}] Cannot use --trend-entry and --both-modes together. "
            "Choose one mode."
        )
        return

    if both_flag:
        mode = "both"
    elif trend_flag:
        mode = "trend"
    else:
        mode = "dip"

    # Validate incompatible combinations
    if mode in ("trend", "both") and getattr(args, "test_bucket", None):
        print(
            f"[{now_str()}] --test-bucket is only valid in dip mode "
            "(no --trend-entry / --both-modes)."
        )
        return

    if mode == "both" and getattr(args, "test", False):
        print(
            f"[{now_str()}] --test is not supported in combined mode (--both-modes). "
            "Use dip-only or trend-only for testing."
        )
        return

    if ix_id == "all":
        if getattr(args, "test", False) or getattr(args, "test_bucket", None):
            print(
                f"[{now_str()}] '--index all' cannot be combined with --test or "
                "--test-bucket. Choose a specific index."
            )
            return

        for ix_key, ix in INDEXES.items():
            print(f"[{now_str()}] Running {mode} mode for index '{ix_key}'...")
            _run_single_index(ix, args, peak_window=peak_window, mode=mode)
        return

    ix = INDEXES.get(ix_id)
    if not ix:
        available = ", ".join(INDEXES.keys())
        print(f"[{now_str()}] Unknown index '{ix_id}'. Available: {available}")
        return

    _run_single_index(ix, args, peak_window=peak_window, mode=mode)
