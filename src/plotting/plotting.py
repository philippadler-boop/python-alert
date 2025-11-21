
from __future__ import annotations
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, PercentFormatter
from ..config.config import now_str, DIP_PLOT_LOOKBACK_DAYS, TREND_PLOT_LOOKBACK_DAYS
from ..logging import logger

def _make_path(ix, prefix):
    ts=now_str().replace(':','').replace('-','').replace('T','_')
    p=ix.plots_dir/f"{ix.id}_{prefix}_{ts}.png"
    p.parent.mkdir(parents=True,exist_ok=True)
    return p

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
        # Handle DataFrame/Series
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, -1]

        close = close.dropna().sort_index()
        ma = ma.dropna().sort_index()

        if close.empty or ma.empty:
            raise ValueError("No data for trend plotting.")

        # Align indices
        common = close.index.intersection(ma.index)
        close = close.loc[common]
        ma = ma.loc[common]

        if close.empty:
            raise ValueError("No overlapping data for trend plotting.")

        # Apply shorter lookback for trend plot
        cutoff = close.index.max() - pd.Timedelta(days=TREND_PLOT_LOOKBACK_DAYS)
        close = close.loc[close.index >= cutoff]
        ma = ma.loc[ma.index >= cutoff]

        if close.empty or ma.empty:
            raise ValueError("Not enough data in trend plotting window.")

        out = _make_path(ix, "trend")

        # Create two-row layout: price (with MA50) and RSI
        fig = plt.figure(figsize=(10, 6), dpi=300)
        gs = fig.add_gridspec(nrows=2, ncols=1, height_ratios=[3, 1], hspace=0.25)

        ax = fig.add_subplot(gs[0, 0])
        ax_rsi = fig.add_subplot(gs[1, 0], sharex=ax)

        # PRICE PANEL: main close and MA
        ax.plot(close.index, close, label="Close")
        ax.plot(ma.index, ma, "--", label=f"MA{len(ma)}" if hasattr(ma, "shape") else "MA")

        # Optional 50MA overlay
        if ma50 is not None:
            try:
                ma50 = ma50.dropna().sort_index()
                common50 = close.index.intersection(ma50.index)
                ax.plot(ma50.loc[common50].index, ma50.loc[common50], "-.", label="MA50", color="#2ca02c")
            except Exception:
                pass

        # Shading above MA
        above = close > ma
        ax.fill_between(close.index, close, ma, where=above, alpha=0.12)

        # Shading for hold window (last N days)
        if hold_indices is not None:
            hold_set = set(pd.to_datetime(list(hold_indices)))
            mask = close.index.isin(hold_set)
            ax.fill_between(close.index, close, ma, where=mask, alpha=0.25)

        # Marker for cross point and Option A
        if cross_idx is not None:
            cross_idx = pd.to_datetime(cross_idx)
            if cross_idx in close.index:
                ax.scatter([cross_idx], [close.loc[cross_idx]], s=80, zorder=5, edgecolor="k")
                if opt_a:
                    # highlight with star
                    ax.scatter([cross_idx], [close.loc[cross_idx]], s=140, marker="*", color="#ff7f0e", zorder=6, edgecolor="k")

        ax.set_title(title or f"{ix.name} — Trend vs MA")
        ax.set_ylabel("Price")

        # Vertical line for every day in the series
        for ts in close.index:
            ax.axvline(ts, linestyle="-", linewidth=0.35, alpha=0.12)

        ax.grid(True, which="major", axis="y", alpha=0.2)

        # RSI PANEL — always present; if data missing show placeholder axes
        try:
            ax_rsi.set_ylabel("RSI")
            ax_rsi.set_ylim(0, 100)
            ax_rsi.axhline(50, linestyle="--", color="#999999", linewidth=0.8)
            ax_rsi.axhline(40, linestyle=":", color="#d62728", linewidth=0.8)
            if rsi is not None:
                rsi = rsi.dropna().sort_index()
                common_rsi = close.index.intersection(rsi.index)
                if not common_rsi.empty:
                    ax_rsi.plot(rsi.loc[common_rsi].index, rsi.loc[common_rsi], color="#9467bd")
                    ax_rsi.fill_between(rsi.loc[common_rsi].index, rsi.loc[common_rsi], 40, where=(rsi.loc[common_rsi] < 40), color="#d62728", alpha=0.12)
                    # Highlight today's RSI if opt_b is True
                    if opt_b and (common_rsi.size > 0):
                        today = common_rsi[-1]
                        v = rsi.loc[today]
                        # extract scalar
                        val = v.item() if hasattr(v, "item") else float(v)
                        ax_rsi.scatter([today], [val], s=70, color="#d62728", edgecolor="k")
                else:
                    # No overlapping RSI data — annotate
                    ax_rsi.text(0.5, 0.5, "No RSI data", ha="center", va="center", transform=ax_rsi.transAxes, fontsize=9, color="#666666")
            else:
                ax_rsi.text(0.5, 0.5, "No RSI data", ha="center", va="center", transform=ax_rsi.transAxes, fontsize=9, color="#666666")
        except Exception:
            # If plotting RSI fails, ensure axis remains but continue
            pass

        # Legend & layout
        ax.legend(loc="upper left")
        fig.autofmt_xdate()
        # Use gridspec spacing (already set via hspace) and avoid plt.tight_layout() which
        # can emit warnings for complex shared axes; rely on subplots_adjust if needed.
        fig.subplots_adjust(hspace=0.25)
        fig.savefig(out)
        plt.close(fig)
        return out

    except Exception as e:  # noqa: BLE001
        logger.error(f"[{now_str()}] Trend plot error: {e}")
        return None
