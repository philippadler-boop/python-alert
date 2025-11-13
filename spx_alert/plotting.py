# spx_alert/plotting.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from .config import PLOTS_DIR, PLOT_LOOKBACK_DAYS, INDEX_TICKER, now_str


def make_alert_plot(series: pd.Series, title: str = "SPX vs Recent High") -> Optional[Path]:
    """Save plot PNG of price + rolling high, return path (or None on failure)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import pyplot as plt

        s = series.dropna()
        if s.empty:
            print(f"[{now_str()}] Plot skipped: empty data.")
            return None

        s = s.iloc[-PLOT_LOOKBACK_DAYS:]
        roll = s.cummax()

        ts = now_str().replace(":", "-")
        fname = f"{INDEX_TICKER.replace('^','')}_{ts}.png"
        out_path = (PLOTS_DIR / fname).resolve()

        fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
        ax.plot(s.index, s.values, label="Close", lw=1.5)
        ax.plot(roll.index, roll.values, label="Recent High", lw=1.2, ls="--")
        ax.scatter(s.index[-1], s.iloc[-1], s=40, zorder=5)
        ax.set_title(title)
        ax.set_xlabel("Date")
        ax.set_ylabel("Price")
        ax.legend(loc="best")
        fig.autofmt_xdate()
        plt.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)

        print(f"[{now_str()}] Plot saved → {out_path}")
        return out_path
    except Exception as e:
        print(f"[{now_str()}] Plot error: {e}")
        return None
