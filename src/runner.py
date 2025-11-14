# spx_alert/runner.py
from __future__ import annotations

from .config.config import INDEXES, DEFAULT_INDEX_ID, now_str
from .alerts.dip_runner import DipAlertRunner
from .alerts.trend_runner import TrendEntryRunner
from .alerts.combined_runner import CombinedRunner
from .logging.logging_utils import clean_old_plots, clean_old_log_rows


def _run_single_index(ix, args, peak_window: str, *, mode: str) -> None:
    """Run the selected alert mode for a single index (with housekeeping)."""
    # Housekeeping
    clean_old_plots(ix.plots_dir)
    clean_old_log_rows(ix)

    if mode == "dip":
        runner = DipAlertRunner(ix, peak_window=peak_window)
        if getattr(args, "test", False):
            runner.run_test_email()
        elif getattr(args, "test_bucket", None):
            runner.run_test_bucket(args.test_bucket, args.show_plot)
        else:
            runner.run(show_plot=args.show_plot)
        return

    if mode == "trend":
        runner = TrendEntryRunner(ix)
        runner.run(
            series=None,
            is_test=getattr(args, "test", False),
            show_plot=args.show_plot,
        )
        return

    if mode == "both":
        runner = CombinedRunner(ix, peak_window=peak_window)
        runner.run(show_plot=args.show_plot)
        return


def run_from_args(args) -> None:
    """Entry point used by main.py to dispatch based on CLI args."""
    ix_id = getattr(args, "index", None) or DEFAULT_INDEX_ID

    peak_window = getattr(args, "peak_window", None) or ""
    trend_flag = getattr(args, "trend_entry", False)
    both_flag = getattr(args, "both_modes", False)

    if both_flag and trend_flag:
        print(
            f"[{now_str()}] Cannot use --trend-entry and --both-modes together. "
            "Choose one mode."
        )
        return

    if both_flag:
        mode = "both"
    elif trend_flag:
        mode = "trend"
    else:
        mode = "dip"

    # Validate incompatible combinations
    if mode in ("trend", "both") and getattr(args, "test_bucket", None):
        print(
            f"[{now_str()}] --test-bucket is only valid in dip mode "
            "(no --trend-entry / --both-modes)."
        )
        return

    if mode == "both" and getattr(args, "test", False):
        print(
            f"[{now_str()}] --test is not supported in combined mode (--both-modes). "
            "Use dip-only or trend-only for testing."
        )
        return

    if ix_id == "all":
        if getattr(args, "test", False) or getattr(args, "test_bucket", None):
            print(
                f"[{now_str()}] '--index all' cannot be combined with --test or "
                "--test-bucket. Choose a specific index."
            )
            return

        for ix_key, ix in INDEXES.items():
            print(f"[{now_str()}] Running {mode} mode for index '{ix_key}'...")
            _run_single_index(ix, args, peak_window=peak_window, mode=mode)
        return

    ix = INDEXES.get(ix_id)
    if not ix:
        available = ", ".join(INDEXES.keys())
        print(f"[{now_str()}] Unknown index '{ix_id}'. Available: {available}")
        return

    _run_single_index(ix, args, peak_window=peak_window, mode=mode)
