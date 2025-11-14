# Root package for the alert system
from .alerts import DEFAULT_BUCKETS
from .config import INDEXES, DEFAULT_INDEX_ID
from .runner import run_from_args