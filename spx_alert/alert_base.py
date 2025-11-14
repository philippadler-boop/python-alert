
from __future__ import annotations
import os, subprocess, sys
from abc import ABC
from pathlib import Path
import pandas as pd
from .config import IndexConfig
from .data import fetch_series

class AlertBaseRunner(ABC):
    def __init__(self, ix: IndexConfig, peak_window=None):
        self.ix = ix
        self.peak_window = peak_window

    def fetch_series(self) -> pd.Series:
        return fetch_series(self.ix)

    @staticmethod
    def open_plot(path: Path | None):
        if not path: 
            return
        try:
            if os.name == 'nt':
                os.startfile(str(path))
            elif sys.platform.startswith('darwin'):
                subprocess.run(['open', str(path)], check=False)
            else:
                subprocess.run(['xdg-open', str(path)], check=False)
        except Exception as e:
            from .config import now_str
            print(f'[{now_str()}] Could not open plot: {e}')
