# spx_alert/state.py
from __future__ import annotations

import json
from typing import Dict, Any

from .config import SPX_INDEX, IndexConfig


def load_state(ix: IndexConfig = SPX_INDEX) -> Dict[str, Any]:
    """Load JSON state from disk for a given index."""
    path = ix.state_file
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            # if file is corrupted, start fresh
            pass
    return {"fired_buckets": {}}


def save_state(state: Dict[str, Any], ix: IndexConfig = SPX_INDEX) -> None:
    """Persist JSON state for a given index to disk."""
    path = ix.state_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))
