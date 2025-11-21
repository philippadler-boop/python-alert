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
from ..logging import logger


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
    "btc": TrendEntryProfile(id="btc", hold_days=3, ma_window=200),
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
        logger.warning(
            f"Unable to load trend_checklists.json from {CHECKLIST_FILE!s} ({e}). Falling back to empty checklists."
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
        logger.debug(f"Trend align debug: series index dtype={series.index.dtype}, ma index dtype={ma_series.index.dtype}")
        logger.debug(f"Trend align debug: series idx head={series.index[:3]}, ma idx head={ma_series.index[:3]}")
        logger.debug(f"Trend align debug: lengths series={len(series)}, ma={len(ma_series)}")
        logger.debug(f"Trend align debug: types: series={type(series)}, ma={type(ma_series)}")
        
        # Align series and MA using pandas.align to preserve the datetime index
        # and avoid misaligned operand errors when comparing the two.
        series_aligned, ma_aligned = series.align(ma_series, join="inner")
        
        if series_aligned.empty or ma_aligned.empty:
            raise ValueError("No overlapping data between series and MA")
        
        # Compute above/below flags (handle unexpected alignment errors gracefully)
        try:
            is_above = series_aligned > ma_aligned
        except Exception as e:  # alignment problem, try re-aligning
            logger.debug(f"Trend comparison error: {e}; attempting explicit align")
            series_aligned, ma_aligned = series_aligned.align(ma_aligned, join="inner")
            if series_aligned.empty or ma_aligned.empty:
                raise ValueError("No overlapping data between series and MA after align")
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
            logger.info(f"Trend entry profile not enabled for index '{self.ix.id}'.")
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
            logger.warning(f"[{self.ix.id}] Trend entry not evaluated: {e}")
            return

        # Alias MA200 series for later Option checks
        ma200_series = ma_series if ma_series is not None else None

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

        # --- Additional indicators for Options A/B ---
        # MA50
        try:
            ma50 = series.rolling(50, min_periods=1).mean().dropna()
        except Exception:
            ma50 = None

        # RSI(14)
        def compute_rsi(s: pd.Series, window: int = 14) -> pd.Series:
            delta = s.diff()
            up = delta.clip(lower=0.0)
            down = -delta.clip(upper=0.0)
            ma_up = up.ewm(alpha=1/window, adjust=False).mean()
            ma_down = down.ewm(alpha=1/window, adjust=False).mean()
            rs = ma_up / ma_down
            rsi = 100 - (100 / (1 + rs))
            return rsi

        try:
            rsi14 = compute_rsi(series, window=14)
        except Exception:
            rsi14 = None

        # Option A: price previously dropped below MA200, now closes above MA50 while MA50 rising
        opt_a = False
        try:
            if ma50 is not None and ma200_series is not None:
                # lookback window to detect prior below-200 condition
                lookback_days = 60
                lookback_idx = series.index[-lookback_days:] if len(series.index) >= lookback_days else series.index
                past_below = (series.reindex(lookback_idx) < ma200_series.reindex(lookback_idx)).any()
                idx = today_idx
                if idx in ma50.index and len(ma50.index) > 1:
                    pos = ma50.index.get_loc(idx)
                    if pos > 0:
                        ma50_today = float(ma50.iloc[pos])
                        ma50_prev = float(ma50.iloc[pos - 1])
                        close_now = float(series.loc[idx])
                        if close_now > ma50_today and ma50_today > ma50_prev and past_below:
                            opt_a = True
        except Exception:
            opt_a = False

        # Option B: RSI dip below 40 then break above 50
        opt_b = False
        try:
            if rsi14 is not None and today_idx in rsi14.index:
                lookback = 30
                rsi_window = rsi14.dropna()
                recent = rsi_window.iloc[-lookback:] if len(rsi_window) >= lookback else rsi_window
                dipped = (recent < 40).any()

                # Robustly get the last occurrence position for today_idx (handles duplicate indices)
                idx_positions = [i for i, x in enumerate(rsi14.index) if x == today_idx]
                if idx_positions:
                    pos = idx_positions[-1]
                    v = rsi14.iloc[pos]
                    curr_rsi = float(v.item() if hasattr(v, "item") else v)
                    if pos > 0:
                        pv = rsi14.iloc[pos - 1]
                        prev_rsi = float(pv.item() if hasattr(pv, "item") else pv)
                    else:
                        prev_rsi = None
                else:
                    # Fallback: try to coerce via .loc then take first element
                    vals = rsi14.loc[today_idx]
                    if isinstance(vals, pd.Series):
                        curr_rsi = float(vals.iloc[-1])
                    else:
                        curr_rsi = float(vals)
                    prev_rsi = None

                if dipped and curr_rsi > 50 and (prev_rsi is None or prev_rsi <= 50):
                    opt_b = True
        except Exception:
            opt_b = False

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
                logger.warning(f"SRUUF spot computation failed (trend): {e}")

        # -------------- TEST MODE: always send email, optional plot --------------
        plot_path: Path | None = None

        # Prepare scalar indicator values for emails/plots
        ma50_today: float | None = None
        if ma50 is not None and today_idx in ma50.index:
            try:
                v = ma50.loc[today_idx]
                val = v.item() if hasattr(v, "item") else (v.iloc[-1] if isinstance(v, pd.Series) else v)
                ma50_today = float(val)
            except Exception:
                ma50_today = None

        rsi_today: float | None = None
        if rsi14 is not None and today_idx in rsi14.index:
            try:
                v = rsi14.loc[today_idx]
                val = v.item() if hasattr(v, "item") else (v.iloc[-1] if isinstance(v, pd.Series) else v)
                rsi_today = float(val)
            except Exception:
                rsi_today = None

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
                    ma50=ma50,
                    rsi=rsi14,
                    opt_a=opt_a,
                    opt_b=opt_b,
                    title=plot_title,
                )
                if show_plot:
                    self.open_plot(plot_path)

            # For TEST emails we want to demonstrate both Option A and B
            test_opt_a = True
            test_opt_b = True

            subject = make_trend_entry_subject(self.ix, is_test=True)
            body = make_trend_entry_body(
                self.ix,
                close_today,
                ma_today,
                pct_diff,
                profile.hold_days,
                checklist,
                is_test=True,
                ma50=ma50_today,
                rsi=rsi_today,
                include_condition=True,
                opt_a=test_opt_a,
                opt_b=test_opt_b,
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
                logger.info(
                    f"[{self.ix.id}] Trend-entry TEST email sent (close {close_today:.2f}, MA{profile.ma_window} {ma_today:.2f})."
                )
            except (smtplib.SMTPException, socket.timeout) as e:
                logger.error(f"[{self.ix.id}] ERROR sending trend test email: {e}")
            # Do not touch state in test mode
            return

        # -------------- LIVE MODE: only create plot when useful --------------

        # Alert when Option A (MA200 drop then MA50 reclaim + rising) or Option B (RSI dip/reclaim)
        cond_met = bool(opt_a) or bool(opt_b)

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
                    ma50=ma50,
                    rsi=rsi14,
                    opt_a=opt_a,
                    opt_b=opt_b,
                    title=plot_title,
                )
                self.open_plot(plot_path)

            state["trend_entry"] = trend_state
            save_state(state, self.ix)
            logger.info(
                f"No trend entry alert for '{self.ix.id}'. (all_above={all_above}, crossed_from_below={crossed_from_below})"
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
                    ma50=ma50,
                    rsi=rsi14,
                    opt_a=opt_a,
                    opt_b=opt_b,
                    title=plot_title,
                )
                self.open_plot(plot_path)

            state["trend_entry"] = trend_state
            save_state(state, self.ix)
            logger.info(f"Trend entry for '{self.ix.id}' already alerted today.")
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
                ma50=ma50,
                rsi=rsi14,
                opt_a=opt_a,
                opt_b=opt_b,
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
            ma50=ma50_today,
            rsi=rsi_today,
            include_condition=True,
            opt_a=opt_a,
            opt_b=opt_b,
        )

        attachments_live = [plot_path] if plot_path is not None else None

        try:
            send_email(
                subject,
                body_text=body,
                attachments=attachments_live,
                inline_path=plot_path,
            )
            logger.info(
                f"[{self.ix.id}] Trend entry alert sent (close {close_today:.2f}, MA{profile.ma_window} {ma_today:.2f})."
            )
        except (smtplib.SMTPException, socket.timeout) as e:
            logger.error(f"[{self.ix.id}] ERROR sending trend email: {e}")
            state["trend_entry"] = trend_state
            save_state(state, self.ix)
            return

        trend_state["last_alert_date"] = today_iso
        state["trend_entry"] = trend_state
        save_state(state, self.ix)

