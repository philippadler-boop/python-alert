# spx_alert/plotting.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from .config import SPX_INDEX, IndexConfig, now_str


def make_alert_plot(
    ix: IndexConfig,
    series: pd.Series,
    title: str | None = None,
) -> Optional[Path]:
    """Save a PNG plot of price + rolling high and return the path."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt  # type: ignore

        s = series.dropna()
        if s.empty:
            print(f"[{now_str()}] Plot skipped: empty data.")
            return None

        s = s.iloc[-ix.plot_lookback_days:]
        roll = s.cummax()

        ts = now_str().replace(":", "-")
        ticker_clean = ix.ticker.replace("^", "")
        fname = f"{ticker_clean}_{ts}.png"
        out_path = (ix.plots_dir / fname).resolve()

        fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
        ax.plot(s.index, s.values, label="Close", lw=1.5)
        ax.plot(roll.index, roll.values, label="Recent High", lw=1.2, ls="--")
        ax.scatter(s.index[-1], s.iloc[-1], s=40, zorder=5)
        ax.set_title(title or f"{ix.name} — Close vs Recent High")
        ax.set_xlabel("Date")
        ax.set_ylabel("Price")
        ax.legend(loc="best")
        fig.autofmt_xdate()
        plt.tight_layout()
        fig.savefig(out_path)
        plt.close(fig)

        print(f"[{now_str()}] Plot saved → {out_path}")
        return out_path
    except Exception as e:  # noqa: BLE001
        print(f"[{now_str()}] Plot error: {e}")
        return None
