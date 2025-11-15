from __future__ import annotations

from .config import INDEXES, DEFAULT_INDEX_ID, PEAK_WINDOW_DEFAULT, now_str
from .alerts.dip_runner import DipAlertRunner
from .alerts.trend_runner import TrendEntryRunner
from .alerts.combined_runner import CombinedRunner
from .logging import clean_old_plots, clean_old_log_rows


def _run_single_index(ix, args, peak_window: str, *, mode: str) -> None:
    """Run the selected alert mode for a single index (with housekeeping)."""
    # Housekeeping
    clean_old_plots(ix.plots_dir)
    clean_old_log_rows(ix)

    if mode == "dip":
        runner = DipAlertRunner(ix, peak_window=peak_window)
        if getattr(args, "test", False):
            # Simple SMTP / dip wiring test
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

    # ----------------- Peak window precedence -----------------
    # CLI --peak-window  >  PEAK_WINDOW_DEFAULT  >  "1y"
    cli_peak = getattr(args, "peak_window", None)
    if cli_peak:
        peak_window = cli_peak
    elif PEAK_WINDOW_DEFAULT:
        peak_window = PEAK_WINDOW_DEFAULT
    else:
        peak_window = "1y"

    # ----------------- Mode resolution -----------------
    dip_flag = getattr(args, "dip_entry", False)
    trend_flag = getattr(args, "trend_entry", False)
    both_flag = getattr(args, "both_modes", False)

    # Default is combined mode ("both") if user doesn't choose explicitly
    if dip_flag:
        mode = "dip"
    elif trend_flag:
        mode = "trend"
    elif both_flag:
        mode = "both"
    else:
        mode = "both"

    test_bucket = getattr(args, "test_bucket", None)
    is_test = getattr(args, "test", False)

    # ----------------- Validate incompatible combinations -----------------

    # test-bucket only makes sense in dip mode; forbid for trend / both
    if test_bucket is not None and mode in ("trend", "both"):
        print(
            f"[{now_str()}] --test-bucket is only valid in dip mode "
            "(no --trend-entry / --both-modes)."
        )
        return

    # Combined mode + --test is ambiguous by design, keep semantics strict
    if mode == "both" and is_test:
        print(
            f"[{now_str()}] --test is not supported in combined mode (--both-modes). "
            "Use dip-only or trend-only for testing."
        )
        return

    # For safety, don't allow '--index all' with test/test-bucket
    if ix_id == "all" and (is_test or test_bucket is not None):
        print(
            f"[{now_str()}] '--index all' cannot be combined with --test or "
            "--test-bucket. Choose a specific index."
        )
        return

    # ----------------- Dispatch -----------------

    if ix_id == "all":
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
