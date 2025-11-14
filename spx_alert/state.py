# spx_alert/state.py
from __future__ import annotations

import json
from typing import Dict, Any

from .config import STATE_FILE


def load_state() -> Dict[str, Any]:
    """Load JSON state from disk.

    Structure is:
        {
            "fired_buckets": {
                "<peak_key>": ["B10", "B20"]
            }
        }

    The state is only written when a real bucket alert fires,
    so the file may not exist until the first alert.
    """
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:  # noqa: BLE001
            # If file is corrupted, start fresh
            pass
    return {"fired_buckets": {}}


def save_state(state: Dict[str, Any]) -> None:
    """Persist JSON state to disk."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))
