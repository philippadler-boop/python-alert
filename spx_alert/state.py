from __future__ import annotations

import json
from typing import Dict, Any

from .config import STATE_FILE


def load_state() -> Dict[str, Any]:
    """Load JSON state from disk (which buckets fired for which peak)."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            # if file is corrupted, start fresh
            pass
    return {"fired_buckets": {}}


def save_state(state: Dict[str, Any]) -> None:
    """Persist JSON state to disk."""
    STATE_FILE.write_text(json.dumps(state, indent=2))
