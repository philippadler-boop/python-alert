# spx_alert/logging_utils.py
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Optional

from .config import LOG_CSV, LOCAL_TZ, RETENTION_DAYS, now_str
from .buckets import Bucket


def append_csv_log(
    ts: str,
    bucket: Bucket,
    dd: float,
    close: float,
    peak: float,
    peak_date: str,
    plot_path: Optional[Path],
    ticker: str,
    is_test: bool,
) -> None:
    """Append a log row to the CSV log file.

    The log is shared for all runs (test + real),
    with an is_test flag distinguishing the two.
    """
    LOG_CSV.parent.mkdir(parents=True, exist_ok=True)

    if not LOG_CSV.exists():
        with LOG_CSV.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [
                    "ts_iso",
                    "bucket_id",
                    "dd_pct",
                    "close",
                    "peak",
                    "peak_date",
                    "note",
                    "ticker",
                    "is_test",
                    "plot_path",
                ]
            )

    with LOG_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [
                ts,
                bucket.id,
                f"{dd:.2f}",
                f"{close:.2f}",
                f"{peak:.2f}",
                peak_date,
                bucket.note,
                ticker,
                int(is_test),
                str(plot_path or ""),
            ]
        )


def _cutoff_dt() -> dt.datetime:
    return dt.datetime.now(tz=LOCAL_TZ) - dt.timedelta(days=RETENTION_DAYS)


def clean_old_plots(plots_dir: Path) -> int:
    """Delete old PNG plots older than RETENTION_DAYS."""
    if not plots_dir.exists():
        return 0
    cutoff = _cutoff_dt()
    deleted = 0
    for p in plots_dir.glob("*.png"):
        try:
            mtime = dt.datetime.fromtimestamp(p.stat().st_mtime, tz=LOCAL_TZ)
            if mtime < cutoff:
                p.unlink(missing_ok=True)
                deleted += 1
        except Exception as e:  # noqa: BLE001
            print(f"[{now_str()}] Plot cleanup skipped for {p.name}: {e}")
    if deleted:
        print(f"[{now_str()}] Plot cleanup: removed {deleted} old file(s).")
    return deleted


def clean_old_log_rows() -> int:
    """Remove old rows from the CSV log file (older than RETENTION_DAYS)."""
    if not LOG_CSV.exists():
        return 0

    cutoff = _cutoff_dt()
    kept, removed = [], 0

    try:
        with LOG_CSV.open("r", newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if not rows:
            return 0

        header, data = rows[0], rows[1:]
        ts_idx = header.index("ts_iso") if "ts_iso" in header else 0

        for r in data:
            try:
                ts = dt.datetime.fromisoformat(r[ts_idx])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=LOCAL_TZ)
                if ts >= cutoff:
                    kept.append(r)
                else:
                    removed += 1
            except Exception:
                kept.append(r)

        if removed:
            tmp = LOG_CSV.with_suffix(".tmp.csv")
            with tmp.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(header)
                w.writerows(kept)
            tmp.replace(LOG_CSV)
            print(f"[{now_str()}] Log cleanup: removed {removed} old row(s).")

        return removed
    except Exception as e:  # noqa: BLE001
        print(f"[{now_str()}] Log cleanup error: {e}")
        return 0
