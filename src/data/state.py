# spx_alert/state.py
from __future__ import annotations

import json
import logging
from typing import Dict, Any

from ..config.config import SPX_INDEX, IndexConfig

logger = logging.getLogger(__name__)


def _validate_state(state: Dict[str, Any]) -> bool:
    """Validate state structure. Returns True if valid, False otherwise."""
    if not isinstance(state, dict):
        logger.warning("State is not a dictionary")
        return False
    if "fired_buckets" not in state:
        logger.warning("State missing 'fired_buckets' key")
        return False
    if not isinstance(state["fired_buckets"], dict):
        logger.warning("State 'fired_buckets' is not a dictionary")
        return False
    return True


def load_state(ix: IndexConfig = SPX_INDEX) -> Dict[str, Any]:
    """Load JSON state from disk for a given index. Returns clean state if corrupted."""
    path = ix.state_file
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            state = json.loads(path.read_text())
            if _validate_state(state):
                return state
            else:
                logger.warning(f"State file {path.name} failed validation, starting fresh")
        except json.JSONDecodeError as e:
            logger.warning(f"State file {path.name} corrupted (JSON error: {e}), starting fresh")
        except Exception as e:
            logger.warning(f"Error loading state file {path.name}: {e}, starting fresh")
    return {"fired_buckets": {}}


def save_state(state: Dict[str, Any], ix: IndexConfig = SPX_INDEX) -> None:
    """Persist JSON state for a given index to disk."""
    path = ix.state_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))
