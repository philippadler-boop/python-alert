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
    # Semiconductors — VanEck Semiconductor UCITS ETF (SOX proxy)
    "sox": TrendEntryProfile(id="sox"),
    # Data Centers — Global X Data Center REITs & Digital Infrastructure (SRVR proxy)
    "srvr": TrendEntryProfile(id="srvr"),
    # Uranium — WisdomTree Uranium & Nuclear Energy (URA proxy)
    "ura": TrendEntryProfile(id="ura"),
    # You can add "remx" later if you want a trend entry for rare earths as well.
}


CHECKLIST_FILE = Path(__file__).with_name("trend_checklists.json")


def load_trend_checklists() -> dict[str, list[str]]:
    """Load trend entry checklists from JSON; return {} on error."""
    try:
        with CHECKLIST_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure it's a dict[str, list[str]]
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
        # index-specific bucket set (spx, ndx, sox, srvr, ura, remx, ...)
        self.buckets = get_buckets_for_index(ix.id)

    # ----------------- internal helpers (dip) -----------------

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

    # ----------------- Test email -----------------

    def run_test_email(self) -> None:
        """Send a simple SMTP wiring test email (dip-alert mode)."""
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

    # ----------------- Normal dip run -----------------

    def run_normal(self, show_plot: bool) -> None:
        """Perform a normal run: check current drawdown and alert if needed."""
        state = load_state(self.ix)
        ctx = self._build_context()
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
            # Email failed; do not update state or log as fired.
            return

        # Only mark bucket as fired if email was successfully sent
        state.setdefault("fired_buckets", {}).setdefault(peak_key, []).append(
            bucket.id
        )
        save_state(state, self.ix)
        print(f"[{now_str()}] [{self.ix.id}] Dip alert logged and state updated.")

    # ----------------- MA200 Trend Entry -----------------

    def run_trend_entry(self) -> None:
        """Check MA200-based trend entry rule and email if newly satisfied.

        Rule:
          - Price crosses from BELOW to ABOVE 200-day MA
          - AND stays above for `hold_days` consecutive trading days.
        """
        profile = TREND_PROFILES.get(self.ix.id)
        if not profile or not profile.enabled:
            print(
                f"[{now_str()}] Trend entry profile not enabled for index '{self.ix.id}'."
            )
            return

        hold_days = profile.hold_days
        ma_window = profile.ma_window

        series = fetch_series(self.ix)
        s = series.dropna()
        if len(s) < ma_window + hold_days + 1:
            print(
                f"[{now_str()}] Not enough data for trend entry on '{self.ix.id}' "
                f"(need at least {ma_window + hold_days + 1} points)."
            )
            return

        ma = s.rolling(ma_window).mean()
        ma = ma.dropna()
        if ma.empty:
            print(f"[{now_str()}] MA{ma_window} series empty for '{self.ix.id}'.")
            return

        # Align lengths (use intersection of indices)
        s = s.loc[ma.index]
        is_above = s > ma

        if len(is_above) < hold_days + 1:
            print(
                f"[{now_str()}] Not enough data for trend entry window on '{self.ix.id}'."
            )
            return

        # Last N+1 days
        last_dates = is_above.index[-(hold_days + 1) :]
        flags = is_above.loc[last_dates]

        # last day is the evaluation day
        today_idx = last_dates[-1]
        last_n = flags.iloc[-hold_days:]  # last N days that must be above
        prev_flag = flags.iloc[0]  # flag at day before the last N

        all_above = bool(last_n.all())
        crossed_from_below = (prev_flag is False) and all_above

        close_today = float(s.loc[today_idx])
        ma_today = float(ma.loc[today_idx])
        pct_diff = (close_today / ma_today - 1.0) * 100.0

        # Load & update state
        state = load_state(self.ix)
        trend_state = state.get("trend_entry", {})
        last_alert_date = trend_state.get("last_alert_date")  # ISO string or None

        # For informational purposes, track last status (above/below)
        is_above_today = bool(is_above.loc[today_idx])
        trend_state["last_status"] = "above" if is_above_today else "below"

        # Decide whether to send a new alert
        if not crossed_from_below:
            # Condition not newly met today
            state["trend_entry"] = trend_state
            save_state(state, self.ix)
            print(
                f"[{now_str()}] No trend entry alert for '{self.ix.id}'. "
                f"(all_above={all_above}, crossed_from_below={crossed_from_below})"
            )
            return

        # Avoid sending twice on the same day if the script is re-run
        today_iso = str(today_idx.date())
        if last_alert_date == today_iso:
            state["trend_entry"] = trend_state
            save_state(state, self.ix)
            print(
                f"[{now_str()}] Trend entry for '{self.ix.id}' already alerted today."
            )
            return

        # Build checklist from JSON
        all_checklists = load_trend_checklists()
        checklist = all_checklists.get(
            self.ix.id,
            ["(No specific fundamentals checklist configured for this index.)"],
        )

        subject = make_trend_entry_subject(self.ix)
        body = make_trend_entry_body(
            self.ix,
            close_today,
            ma_today,
            pct_diff,
            hold_days,
            checklist,
        )

        try:
            send_email(subject, body_text=body)
            print(
                f"[{now_str()}] [{self.ix.id}] Trend entry alert sent "
                f"(close {close_today:.2f}, MA{ma_window} {ma_today:.2f})."
            )
        except (smtplib.SMTPException, socket.timeout) as e:
            print(f"[{now_str()}] [{self.ix.id}] ERROR sending trend email: {e}")
            # Do not update alert date on failure
            state["trend_entry"] = trend_state
            save_state(state, self.ix)
            return

        # Mark as alerted for today
        trend_state["last_alert_date"] = today_iso
        state["trend_entry"] = trend_state
        save_state(state, self.ix)


# ----------------- Job orchestration -----------------


def _run_single_index(ix: IndexConfig, args, peak_window: str, *, mode: str) -> None:
    """Run the alert logic for a single index (including housekeeping)."""
    # housekeeping (per run, per index)
    clean_old_plots(ix.plots_dir)
    clean_old_log_rows(ix)

    runner = DipAlertRunner(ix, peak_window=peak_window)

    if mode == "trend":
        runner.run_trend_entry()
        return

    # dip-alert mode
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

    # Determine peak window: CLI overrides env/DEFAULT (dip mode only)
    peak_window = getattr(args, "peak_window", None) or PEAK_WINDOW_DEFAULT

    mode = "trend" if getattr(args, "trend_entry", False) else "dip"

    if ix_id == "all":
        # For safety, we do not support --test / --test-bucket with 'all'
        if mode == "dip" and (args.test or args.test_bucket):
            print(
                f"[{now_str()}] '--index all' cannot be combined with "
                "--test or --test-bucket. Please choose a specific index."
            )
            return
        if mode == "trend" and (args.test or args.test_bucket):
            print(
                f"[{now_str()}] '--trend-entry' cannot be combined with "
                "--test or --test-bucket."
            )
            return

        # Run for all configured indices
        for ix_key, ix in INDEXES.items():
            print(f"[{now_str()}] Running {mode} mode for index '{ix_key}'...")
            _run_single_index(ix, args, peak_window=peak_window, mode=mode)

        return

    # Single-index mode
    ix = INDEXES.get(ix_id)
    if not ix:
        available = ", ".join(INDEXES.keys())
        print(f"[{now_str()}] Unknown index '{ix_id}'. Available: {available}")
        return

    _run_single_index(ix, args, peak_window=peak_window, mode=mode)
