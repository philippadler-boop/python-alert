
from __future__ import annotations
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from ..config.config import now_str, DIP_PLOT_LOOKBACK_DAYS, TREND_PLOT_LOOKBACK_DAYS
from ..logging.logger import logger

def _make_path(ix, prefix):
    ts=now_str().replace(':','').replace('-','').replace('T','_')
    p=ix.plots_dir/f"{ix.id}_{prefix}_{ts}.png"
    p.parent.mkdir(parents=True,exist_ok=True)
    return p


def _coerce_series(data):
    """Return a clean pandas Series (dropna + sorted) or None for missing data."""
    if data is None:
        return None
    if isinstance(data, pd.DataFrame):
        data = data.iloc[:, -1]
    if not isinstance(data, pd.Series):
        raise TypeError("Plotting expects pandas Series inputs")
    return data.dropna().sort_index()


def _trim_to_window(series: pd.Series, cutoff: pd.Timestamp) -> pd.Series:
    """Trim a series to dates greater than or equal to the cutoff."""
    return series.loc[series.index >= cutoff]


def _prepare_optional_series(base_index: pd.Index, data):
    series = _coerce_series(data)
    if series is None or series.empty:
        return None
    overlap = base_index.intersection(series.index)
    if overlap.empty:
        return None
    return series.loc[overlap]


def _plot_rsi_panel(ax, rsi: pd.Series | None, opt_b: bool):
    """Render the RSI subplot (with Option B highlight when requested)."""
    ax.set_ylabel("RSI")
    ax.set_ylim(0, 100)
    ax.axhline(50, linestyle="--", color="#999999", linewidth=0.8)
    ax.axhline(40, linestyle=":", color="#d62728", linewidth=0.8)

    if rsi is None or rsi.empty:
        ax.text(0.5, 0.5, "No RSI data", ha="center", va="center", transform=ax.transAxes, fontsize=9, color="#666666")
        return

    ax.plot(rsi.index, rsi, color="#9467bd")
    ax.fill_between(rsi.index, rsi, 40, where=(rsi < 40), color="#d62728", alpha=0.12)

    if opt_b:
        today = rsi.index[-1]
        val = rsi.iloc[-1]
        scalar = val.item() if hasattr(val, "item") else float(val)
        ax.scatter([today], [scalar], s=70, color="#d62728", edgecolor="k")

def make_alert_plot(ix, series, title: str | None = None) -> Path | None:
    """
    Dip alert plot:
    - Left y-axis: price
    - Right y-axis: % of recent high (recent high = 100%)
    - Rolling recent high line.
    - Dashed horizontal line at last close with ticks on both axes.
    """
    try:
        from matplotlib.ticker import FuncFormatter

        # Handle Series/DataFrame
        if isinstance(series, pd.DataFrame):
            close = series.iloc[:, -1]
        else:
            close = series

        close = close.dropna().sort_index()
        if close.empty:
            raise ValueError("No data for plotting.")

        # Rolling recent high on full series
        recent_high_full = close.cummax()

        # Apply shorter lookback for plotting
        cutoff = close.index.max() - pd.Timedelta(days=DIP_PLOT_LOOKBACK_DAYS)
        close = close.loc[close.index >= cutoff]
        recent_high = recent_high_full.loc[recent_high_full.index >= cutoff]

        if close.empty or recent_high.empty:
            raise ValueError("Not enough data in plotting window.")

        out = _make_path(ix, "dip_alert")

        # Reference values
        max_recent_high = float(recent_high.max())
        last_close = float(close.iloc[-1])

        fig, ax = plt.subplots(figsize=(10, 5))

        # Price & recent-high lines on left axis
        ax.plot(close.index, close, label="Close")
        ax.plot(recent_high.index, recent_high, "--", label="Recent high")

        # Dashed horizontal line at last close (left axis coordinates)
        ax.axhline(last_close, linestyle="--", linewidth=1)

        ax.set_title(title or f"{ix.name} — Close vs Recent High")
        ax.set_ylabel("Price")
        ax.xaxis.set_major_locator(MaxNLocator(nbins=8))

        # Gridlines
        ax.grid(True, which="major", axis="both", alpha=0.25)

        # Make sure both recent high and last close are in the left ticks
        left_ticks = list(ax.get_yticks())
        left_ticks.extend([max_recent_high])
        left_ticks = sorted(set(left_ticks))
        ax.set_yticks(left_ticks)

        # Right axis: same limits, but format as % of recent high
        ax2 = ax.twinx()
        y_min, y_max = ax.get_ylim()
        ax2.set_ylim(y_min, y_max)

        # Ensure same tick positions on right axis
        ax2.set_yticks(left_ticks)

        def pct_formatter(v, _pos):
            pct = (v / max_recent_high) * 100.0
            return f"{pct:.0f}%"

        ax2.yaxis.set_major_formatter(FuncFormatter(pct_formatter))
        ax2.set_ylabel("% of recent high (100% = max)")

        # Annotate last close with price and % (optional but nice)
        last_close_pct = (last_close / max_recent_high) * 100.0
        ax.text(
            close.index[-1],
            last_close,
            f"  {last_close:.2f}",
            va="bottom",
            ha="left",
            fontsize=8,
        )
        ax2.text(
            close.index[-1],
            last_close,
            f"  {last_close_pct:.1f}%",
            va="top",
            ha="left",
            fontsize=8,
        )

        # Legend & layout
        ax.legend(loc="upper left")
        fig.autofmt_xdate()
        plt.tight_layout()
        fig.savefig(out)
        plt.close(fig)
        return out

    except Exception as e:  # noqa: BLE001
        logger.error(f"[{now_str()}] Dip plot error: {e}")
        return None


def make_trend_plot(
    ix,
    close,
    ma,
    *,
    hold_indices=None,
    cross_idx=None,
    ma50=None,
    rsi=None,
    opt_a: bool = False,
    opt_b: bool = False,
    title: str | None = None,
) -> Path | None:
    """
    Trend plot:
    - Close vs MA (e.g., 200d)
    - Shading above MA
    - Shading for hold window
    - Marker for cross point
    - Vertical line for every day in the series window.
    """
    try:
        close = _coerce_series(close)
        ma = _coerce_series(ma)
        if close is None or close.empty or ma is None or ma.empty:
            raise ValueError("No data for trend plotting.")

        common = close.index.intersection(ma.index)
        close = close.loc[common]
        ma = ma.loc[common]
        if close.empty:
            raise ValueError("No overlapping data for trend plotting.")

        cutoff = close.index.max() - pd.Timedelta(days=TREND_PLOT_LOOKBACK_DAYS)
        close = _trim_to_window(close, cutoff)
        ma = _trim_to_window(ma, cutoff)
        common = close.index.intersection(ma.index)
        close = close.loc[common]
        ma = ma.loc[common]
        if close.empty or ma.empty:
            raise ValueError("Not enough data in trend plotting window.")

        window_index = close.index
        ma50_series = _prepare_optional_series(window_index, ma50)
        rsi_series = _prepare_optional_series(window_index, rsi)

        out = _make_path(ix, "trend")

        fig, (ax, ax_rsi) = plt.subplots(
            2,
            1,
            figsize=(10, 6),
            dpi=300,
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1]},
        )

        ma_label = ma.name or "MA"
        ax.plot(window_index, close, label="Close")
        ax.plot(ma.index, ma, "--", label=ma_label)

        if ma50_series is not None:
            ax.plot(ma50_series.index, ma50_series, "-.", label="MA50", color="#2ca02c")

        above = close > ma
        ax.fill_between(window_index, close, ma, where=above, alpha=0.12)

        if hold_indices is not None:
            hold_idx = pd.to_datetime(list(hold_indices))
            hold_mask = window_index.isin(hold_idx)
            if hold_mask.any():
                ax.fill_between(window_index, close, ma, where=hold_mask, alpha=0.25)

        if cross_idx is not None:
            cross_idx = pd.to_datetime(cross_idx)
            if cross_idx in window_index:
                price_at_cross = close.loc[cross_idx]
                ax.scatter([cross_idx], [price_at_cross], s=80, zorder=5, edgecolor="k")
                if opt_a:
                    ax.scatter([cross_idx], [price_at_cross], s=140, marker="*", color="#ff7f0e", zorder=6, edgecolor="k")

        ax.set_title(title or f"{ix.name} — Trend vs MA")
        ax.set_ylabel("Price")
        for ts in window_index:
            ax.axvline(ts, linestyle="-", linewidth=0.35, alpha=0.12)
        ax.grid(True, which="major", axis="y", alpha=0.2)

        _plot_rsi_panel(ax_rsi, rsi_series, opt_b)

        ax.legend(loc="upper left")
        fig.autofmt_xdate()
        fig.subplots_adjust(hspace=0.25)
        fig.savefig(out)
        plt.close(fig)
        return out

    except Exception as e:  # noqa: BLE001
        logger.error(f"[{now_str()}] Trend plot error: {e}")
        return None
