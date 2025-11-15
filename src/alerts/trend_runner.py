# spx_alert/trend_runner.py
from __future__ import annotations

import json
import smtplib
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from .alert_base import AlertBaseRunner
from ..config.config import SAVE_PLOTS, ATTACH_PLOT_ON_TEST, now_str, SRUUF_U3O8_LBS_PER_UNIT
from ..data import compute_trend_entry, compute_uranium_spot_from_sruuf, load_state, save_state

from ..email.email_utils import (
    send_email,
    make_trend_entry_subject,
    make_trend_entry_body,
)
from ..plotting.plotting import make_trend_plot


@dataclass(frozen=True)
class TrendEntryProfile:
    """Configuration for MA-based trend entry alerts for a given index."""

    id: str
    hold_days: int = 5
    ma_window: int = 200
    enabled: bool = True


TREND_PROFILES: dict[str, TrendEntryProfile] = {
    "sox": TrendEntryProfile(id="sox"),
    "srvr": TrendEntryProfile(id="srvr"),
    "sruuf": TrendEntryProfile(id="sruuf"),
    # Add "remx": TrendEntryProfile(id="remx") if you want REMX trend-entry as well.
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


class TrendEntryRunner(AlertBaseRunner):
    """MA-based trend-entry alerts (e.g. 200-day MA cross + hold)."""

    def __init__(self, ix) -> None:
        super().__init__(ix, peak_window=None)
        self.profile = TREND_PROFILES.get(ix.id)

    def is_enabled(self) -> bool:
        return self.profile is not None and self.profile.enabled

    @staticmethod
    def _compute_trend_from_ma(
        series: pd.Series,
        ma_series: pd.Series,
        profile: TrendEntryProfile,
    ) -> tuple:
        """Compute trend entry metrics from pre-computed MA series.
        
        Returns:
            (close_today, ma_today, pct_diff, all_above, crossed_from_below, today_idx, is_above_flags)
        """
        # Align series with MA
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, -1]
        
        series = series.dropna().sort_index()
        ma_series = ma_series.dropna().sort_index()
        
        common = series.index.intersection(ma_series.index)
        series_aligned = series.loc[common]
        ma_aligned = ma_series.loc[common]
        
        if series_aligned.empty or ma_aligned.empty:
            raise ValueError("No overlapping data between series and MA")
        
        # Compute above/below flags
        is_above = series_aligned > ma_aligned
        
        # Get last N+1 days (hold_days + 1 for crossover detection)
        last = is_above.iloc[-(profile.hold_days + 1):]
        all_above = bool(last.iloc[1:].all())
        crossed_from_below = (last.iloc[0] == False) and all_above
        
        idx = last.index[-1]
        c = float(series_aligned.loc[idx])
        m = float(ma_aligned.loc[idx])
        pct = (c / m - 1) * 100
        
        return c, m, pct, all_above, crossed_from_below, idx, is_above

    def run(
        self,
        series: Optional[pd.Series] = None,
        *,
        is_test: bool = False,
        show_plot: bool = False,
        _cached_ma: Optional[pd.Series] = None,
    ) -> None:
        if not self.is_enabled():
            print(
                f"[{now_str()}] Trend entry profile not enabled for index '{self.ix.id}'."
            )
            return

        profile = self.profile
        assert profile is not None

        if series is None:
            series = self.fetch_series()

        try:
            # Use cached MA200 if provided (from combined mode), otherwise compute it
            if _cached_ma is not None:
                # Cached MA provided; use it directly
                ma_series = _cached_ma
                close_today, ma_today, pct_diff, all_above, crossed_from_below, today_idx, is_above_flags = \
                    self._compute_trend_from_ma(series, ma_series, profile)
            else:
                # Standard path: compute trend entry with fresh MA200
                (
                    close_today,
                    ma_today,
                    pct_diff,
                    all_above,
                    crossed_from_below,
                    today_idx,
                    ma_series,
                    is_above_flags,
                ) = compute_trend_entry(
                    series,
                    ma_window=profile.ma_window,
                    hold_days=profile.hold_days,
                )
        except ValueError as e:
            print(f"[{now_str()}] [{self.ix.id}] Trend entry not evaluated: {e}")
            return

        # Determine hold window indices (last N days used in compute_trend_entry)
        hold_indices = None
        cross_idx = None
        try:
            flags = is_above_flags
            last_dates = flags.index[-(profile.hold_days + 1) :]
            hold_indices = last_dates[-profile.hold_days :]
            cross_idx = hold_indices[0]
        except Exception:
            hold_indices = None
            cross_idx = None

        # Load state
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

        # SRUUF-only: prepend implied uranium spot to checklist
        if self.ix.id == "sruuf":
            try:
                spot = compute_uranium_spot_from_sruuf(
                    nav_per_unit=close_today,
                    u3o8_lbs_per_unit=SRUUF_U3O8_LBS_PER_UNIT,
                )
                spot_line = (
                    f"Implied uranium spot (via SRUUF unit price): "
                    f"{spot:.2f} USD/lb (approx.)."
                )
                checklist = [spot_line] + checklist
            except Exception as e:
                print(f"[{now_str()}] SRUUF spot computation failed (trend): {e}")

        # -------------- TEST MODE: always send email, optional plot --------------
        plot_path: Path | None = None

        if is_test:
            # In test mode we almost always want a plot (for inspection and attachments)
            if SAVE_PLOTS or show_plot or ATTACH_PLOT_ON_TEST:
                plot_title = f"{self.ix.name} — Close vs MA{profile.ma_window}"
                plot_path = make_trend_plot(
                    self.ix,
                    series,
                    ma_series,
                    hold_indices=hold_indices,
                    cross_idx=cross_idx,
                    title=plot_title,
                )
                if show_plot:
                    self.open_plot(plot_path)

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

            attachments = None
            if plot_path and ATTACH_PLOT_ON_TEST:
                attachments = [plot_path]

            try:
                send_email(
                    subject,
                    body_text=body,
                    attachments=attachments,
                    inline_path=plot_path,
                )
                print(
                    f"[{now_str()}] [{self.ix.id}] Trend-entry TEST email sent "
                    f"(close {close_today:.2f}, MA{profile.ma_window} {ma_today:.2f})."
                )
            except (smtplib.SMTPException, socket.timeout) as e:
                print(
                    f"[{now_str()}] [{self.ix.id}] ERROR sending trend test email: {e}"
                )
            # Do not touch state in test mode
            return

        # -------------- LIVE MODE: only create plot when useful --------------

        cond_met = all_above and crossed_from_below

        if not cond_met:
            # No alert; only create a plot if user explicitly asked to see it
            if SAVE_PLOTS and show_plot:
                plot_title = f"{self.ix.name} — Close vs MA{profile.ma_window}"
                plot_path = make_trend_plot(
                    self.ix,
                    series,
                    ma_series,
                    hold_indices=hold_indices,
                    cross_idx=cross_idx,
                    title=plot_title,
                )
                self.open_plot(plot_path)

            state["trend_entry"] = trend_state
            save_state(state, self.ix)
            print(
                f"[{now_str()}] No trend entry alert for '{self.ix.id}'. "
                f"(all_above={all_above}, crossed_from_below={crossed_from_below})"
            )
            return

        if last_alert_date == today_iso:
            # Already alerted today; again, only build a plot if show_plot is requested
            if SAVE_PLOTS and show_plot:
                plot_title = f"{self.ix.name} — Close vs MA{profile.ma_window}"
                plot_path = make_trend_plot(
                    self.ix,
                    series,
                    ma_series,
                    hold_indices=hold_indices,
                    cross_idx=cross_idx,
                    title=plot_title,
                )
                self.open_plot(plot_path)

            state["trend_entry"] = trend_state
            save_state(state, self.ix)
            print(
                f"[{now_str()}] Trend entry for '{self.ix.id}' already alerted today."
            )
            return

        # Condition met and not yet alerted today → build plot (if enabled) and send
        if SAVE_PLOTS or show_plot:
            plot_title = f"{self.ix.name} — Close vs MA{profile.ma_window}"
            plot_path = make_trend_plot(
                self.ix,
                series,
                ma_series,
                hold_indices=hold_indices,
                cross_idx=cross_idx,
                title=plot_title,
            )
            if show_plot:
                self.open_plot(plot_path)

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

        attachments_live = [plot_path] if plot_path is not None else None

        try:
            send_email(
                subject,
                body_text=body,
                attachments=attachments_live,
                inline_path=plot_path,
            )
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

