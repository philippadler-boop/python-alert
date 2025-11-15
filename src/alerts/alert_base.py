
from __future__ import annotations
import os, subprocess, sys
from abc import ABC
from pathlib import Path
import pandas as pd
from ..config.config import IndexConfig
from ..data import fetch_series
from ..logging import logger

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
            from ..config.config import now_str
            logger.warning(f'Could not open plot: {e}')
