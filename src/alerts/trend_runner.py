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

    def run(
        self,
        series: Optional[pd.Series] = None,
        *,
        is_test: bool = False,
        show_plot: bool = False,
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

        # --- Plot building unchanged ---
        plot_path: Path | None = None
        hold_indices = None
        cross_idx = None
        try:
            flags = is_above_flags
            last_dates = flags.index[-(profile.hold_days + 1):]
            hold_indices = last_dates[-profile.hold_days:]
            cross_idx = hold_indices[0]
        except Exception:
            hold_indices = None
            cross_idx = None

        if SAVE_PLOTS:
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

        # --- Load state ---
        state = load_state(self.ix)
        trend_state = state.get("trend_entry", {})
        last_alert_date = trend_state.get("last_alert_date")

        is_above_today = pct_diff >= 0.0
        trend_state["last_status"] = "above" if is_above_today else "below"

        today_iso = str(today_idx.date())

        # --- Load fundamentals checklist from JSON ---
        checklists = load_trend_checklists()
        checklist = checklists.get(
            self.ix.id,
            ["(No specific fundamentals checklist configured for this index.)"]
        )

        # ============================================================
        # 🔥 SRUUF-only: Prepend implied uranium spot to checklist
        # ============================================================
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

        # ============================
        # TEST MODE
        # ============================
        if is_test:
            subject = make_trend_entry_subject(self.ix, is_test=True)
            body = make_trend_entry_body(
                self.ix,
                close_today,
                ma_today,
                pct_diff,
                profile.hold_days,
                checklist,        # <-- includes SRUUF spot if applicable
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
            return

        # ============================
        # LIVE MODE
        # ============================

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
            checklist,        # <-- includes SRUUF spot if applicable
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

