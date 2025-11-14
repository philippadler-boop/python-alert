
from __future__ import annotations
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from .config import now_str, DIP_PLOT_LOOKBACK_DAYS, TREND_PLOT_LOOKBACK_DAYS

def _make_path(ix, prefix):
    ts=now_str().replace(':','').replace('-','').replace('T','_')
    p=ix.plots_dir/f"{ix.id}_{prefix}_{ts}.png"
    p.parent.mkdir(parents=True,exist_ok=True)
    return p

def make_alert_plot(ix, series, title=None):
    try:
        if isinstance(series,pd.DataFrame): series=series.iloc[:,-1]
        series=series.dropna().sort_index()
        rm=series.cummax()
        cutoff=series.index.max()-pd.Timedelta(days=DIP_PLOT_LOOKBACK_DAYS)
        series=series.loc[series.index>=cutoff]
        rm=rm.loc[rm.index>=cutoff]
        out=_make_path(ix,"alert")
        fig,ax=plt.subplots(figsize=(10,5))
        ax.plot(series.index,series,label="Close")
        ax.plot(rm.index,rm,label="Recent High")
        ax.set_title(title or f"{ix.name} — Close vs Recent High")
        ax.legend(); fig.autofmt_xdate(); plt.tight_layout(); fig.savefig(out); plt.close(fig)
        return out
    except Exception as e:
        print(f"[{now_str()}] Dip plot error: {e}"); return None

def make_trend_plot(ix, close, ma, *, hold_indices=None, cross_idx=None, title=None):
    try:
        if isinstance(close,pd.DataFrame): close=close.iloc[:,-1]
        close=close.dropna().sort_index(); ma=ma.dropna().sort_index()
        common=close.index.intersection(ma.index)
        close=close.loc[common]; ma=ma.loc[common]
        cutoff=close.index.max()-pd.Timedelta(days=TREND_PLOT_LOOKBACK_DAYS)
        close=close.loc[close.index>=cutoff]
        ma=ma.loc[ma.index>=cutoff]
        out=_make_path(ix,"alert")
        fig,ax=plt.subplots(figsize=(10,5))
        ax.plot(close.index,close,label="Close")
        ax.plot(ma.index,ma,'--',label="MA")
        above=close>ma
        ax.fill_between(close.index,close,ma,where=above,alpha=0.15)
        if hold_indices is not None:
            hold_set=set(pd.to_datetime(list(hold_indices)))
            mask=close.index.isin(hold_set)
            ax.fill_between(close.index,close,ma,where=mask,alpha=0.3)
        if cross_idx is not None and cross_idx in close.index:
            ax.scatter(
                [cross_idx],
                [close.loc[cross_idx]],
                color="green",
                s=70,
                label="Cross From Below",
                zorder=5,
            )
        ax.set_title(title or f"{ix.name} — Trend MA")
        ax.legend(); fig.autofmt_xdate(); plt.tight_layout(); fig.savefig(out); plt.close(fig)
        return out
    except Exception as e:
        print(f"[{now_str()}] Trend plot error: {e}"); return None
