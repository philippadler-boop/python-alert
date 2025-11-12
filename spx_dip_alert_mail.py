#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SPX Dip Alert — Gmail Email + CSV Log + Plot (saved, attached, inline)

- Computes drawdown from most-recent high on ^GSPC
- Alerts by buckets (one email per bucket per peak); resets on new peak
- Gmail SMTP (STARTTLS/587), CSV logging, PNG plot saved/attached/inline
- Test modes: --test, --test-bucket B10|B20|B70, --show-plot

.env keys (place next to this file):
FROM_EMAIL=you@gmail.com
TO_EMAIL=you@gmail.com
APP_PASSWORD=your_16_char_app_pw

# Optional settings
DRY_RUN=0
LOCAL_TZ=Europe/Berlin
LOOKBACK_DAYS=1095
SAVE_PLOTS=1
PLOTS_DIR=C:/Users/phili/OneDrive/Dokumente/python-alert/plots
LOG_CSV=C:/Users/phili/OneDrive/Dokumente/python-alert/spx_dip_alert_log.csv
PLOT_LOOKBACK_DAYS=180
"""

from __future__ import annotations

import os, json, math, time, csv, smtplib, ssl, platform, argparse, subprocess, sys, socket
import datetime as dt
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from email.utils import make_msgid

# ---------- setup & env ----------
SCRIPT_DIR = Path(__file__).parent.resolve()
load_dotenv()

INDEX_TICKER = os.getenv("INDEX_TICKER", "^GSPC")
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "1095"))
TZ = ZoneInfo(os.getenv("LOCAL_TZ", "Europe/Berlin"))
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"

SAVE_PLOTS = os.getenv("SAVE_PLOTS", "1") == "1"
PLOTS_DIR = Path(os.getenv("PLOTS_DIR", SCRIPT_DIR / "plots")).resolve()
LOG_CSV = Path(os.getenv("LOG_CSV", SCRIPT_DIR / "spx_dip_alert_log.csv")).resolve()
PLOT_LOOKBACK_DAYS = int(os.getenv("PLOT_LOOKBACK_DAYS", "180"))

STATE_FILE = (SCRIPT_DIR / ".spx_alert_state.json").resolve()
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))  # days to keep plots & log rows

# ---------- buckets ----------
DEFAULT_BUCKETS = [
    {"id": "B10", "lo": -8.0,   "hi": -5.0,   "note": "Deploy 10% of Cash Bucket"},
    {"id": "B20", "lo": -15.0,  "hi": -10.0,  "note": "Deploy 20% of Cash Bucket"},
    {"id": "B70", "lo": -999.0, "hi": -20.0,  "note": "Deploy remaining 70% in weekly tranches"},
]

# ---------- helpers ----------
def now_str() -> str:
    return dt.datetime.now(tz=TZ).isoformat(timespec="seconds")

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_peak_date": None, "fired_buckets": {}}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def fetch_series(ticker: str, days: int) -> pd.Series:
    """Fetch daily close series; squeezes to Series if DataFrame."""
    end = dt.date.today()
    start = end - dt.timedelta(days=days + 10)
    last_err: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            df = yf.download(ticker, start=start, end=end, interval="1d",
                             auto_adjust=True, progress=False, threads=False)
            if df is not None and not df.empty and "Close" in df:
                s = df["Close"].dropna()
                if isinstance(s, pd.DataFrame):
                    s = s.dropna(axis=1, how="all")
                    if s.shape[1] > 0:
                        s = s.iloc[:, 0]
                if isinstance(s, pd.Series) and not s.empty:
                    return s
            last_err = RuntimeError("No data fetched or missing Close column")
        except Exception as e:
            last_err = e
        if attempt < 3:
            time.sleep(attempt * 2)
    raise RuntimeError(f"Data fetch failed: {last_err}")

def compute_drawdown(close: pd.Series) -> Tuple[float, float, float, pd.Timestamp]:
    """Return (current, peak_value, dd_pct, peak_date)."""
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, -1]
    rolling_max = close.cummax()
    dd_pct = (close / rolling_max - 1.0) * 100.0
    current = float(close.iat[-1])
    peak_value = float(rolling_max.iat[-1])
    dd = float(dd_pct.iat[-1])
    # last time a new high was set (round to avoid float equality issues)
    eq = (close.round(6) == rolling_max.round(6))
    peak_idx = eq[eq].index[-1]
    return current, peak_value, dd, pd.Timestamp(peak_idx)

def pick_bucket(dd: float, buckets: list[dict]) -> Optional[dict]:
    for b in buckets:
        if b["lo"] <= dd <= b["hi"]:
            return b
    return None

# ---------- plotting ----------
def make_alert_plot(series: pd.Series, title: str = "SPX vs Recent High") -> Optional[Path]:
    """Save plot PNG and return its path (or None on failure)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import pyplot as plt

        s = series.dropna()
        if s.empty:
            print(f"[{now_str()}] Plot skipped: empty data.")
            return None
        s = s.iloc[-PLOT_LOOKBACK_DAYS:]
        roll = s.cummax()

        ts = now_str().replace(":", "-")
        fname = f"{INDEX_TICKER.replace('^','')}_{ts}.png"
        out_path = (PLOTS_DIR / fname).resolve()

        fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
        ax.plot(s.index, s.values, label="Close", lw=1.5)
        ax.plot(roll.index, roll.values, label="Recent High", lw=1.2, ls="--")
        ax.scatter(s.index[-1], s.iloc[-1], s=40, zorder=5)
        ax.set_title(title)
        ax.set_xlabel("Date"); ax.set_ylabel("Price"); ax.legend(loc="best")
        fig.autofmt_xdate(); plt.tight_layout()
        fig.savefig(out_path); plt.close(fig)
        print(f"[{now_str()}] Plot saved → {out_path}")
        return out_path
    except Exception as e:
        print(f"[{now_str()}] Plot error: {e}")
        return None

# ---------- CSV logging ----------
def append_csv_log(ts: str, bucket: dict, dd: float, close: float, peak: float,
                   peak_date: str, plot_path: Optional[Path], ticker: str, is_test: bool):
    if not LOG_CSV.exists():
        with LOG_CSV.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "ts_iso","bucket_id","dd_pct","close","peak","peak_date",
                "note","ticker","is_test","plot_path"
            ])
    with LOG_CSV.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            ts, bucket["id"], f"{dd:.2f}", f"{close:.2f}", f"{peak:.2f}",
            peak_date, bucket["note"], ticker, int(is_test), str(plot_path or "")
        ])

# ---------- email (Gmail-safe HTML) ----------
def build_html_email(ticker, close, peak, dd, peak_date, bucket, cid:str, extra_note:str=""):
    lo, hi, note = bucket["lo"], bucket["hi"], bucket["note"]
    lo_s = f"{lo:.0f}%" if math.isfinite(lo) else "-∞"
    hi_s = f"{hi:.0f}%"
    extra = f"<p>{extra_note}</p>" if extra_note else ""
    return f"""
<html>
  <body style="background:#ffffff;margin:0;padding:16px;">
    <div style="color:#111111;font:14px/1.45 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial;">
      <h3 style="margin:0 0 12px 0;">SPX Dip Alert</h3>
      <table cellpadding="6" cellspacing="0" border="0" style="border-collapse:collapse;">
        <tr><td><b>Ticker</b></td><td>{ticker}</td></tr>
        <tr><td><b>Close</b></td><td>{close:.2f}</td></tr>
        <tr><td><b>Recent High</b></td><td>{peak:.2f} (set {peak_date.date().isoformat()})</td></tr>
        <tr><td><b>Drawdown</b></td><td>{dd:.2f}%</td></tr>
        <tr><td><b>Bucket</b></td><td>{hi_s} to {lo_s}</td></tr>
        <tr><td><b>Plan</b></td><td>{note}</td></tr>
        <tr><td><b>Time</b></td><td>{now_str()}</td></tr>
      </table>
      <p style="color:#555;margin:12px 0 0 0;">This message is an alert only (no trades executed).</p>
      {extra}
      <div style="margin-top:14px;"><img src="cid:{cid}" style="max-width:100%;height:auto;border:1px solid #ddd"/></div>
    </div>
  </body>
</html>
"""

def send_email(subject: str,
               body_text: str,
               *,
               html_kwargs: dict | None = None,
               attachments: list[Path] | None = None,
               inline_path: Path | None = None):
    FROM_EMAIL, TO_EMAIL, APP_PASS = map(os.getenv, ["FROM_EMAIL", "TO_EMAIL", "APP_PASSWORD"])
    if not (FROM_EMAIL and TO_EMAIL and APP_PASS):
        raise RuntimeError("Missing FROM_EMAIL / TO_EMAIL / APP_PASSWORD in .env")

    INLINE_IMAGE = os.getenv("INLINE_IMAGE", "0") == "1"

    import certifi
    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cafile=certifi.where())

    # Root is multipart/mixed (best for Gmail)
    msg_root = MIMEMultipart("mixed")
    msg_root["Subject"] = subject
    msg_root["From"] = FROM_EMAIL
    msg_root["To"] = TO_EMAIL

    # Bodies: multipart/alternative (plain + HTML)
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body_text, _subtype="plain", _charset="utf-8"))

    html = None
    if html_kwargs:
        # build the robust HTML we added earlier
        cid = None
        if INLINE_IMAGE and inline_path and inline_path.exists():
            cid = make_msgid()[1:-1]
        html = build_html_email(**html_kwargs, cid=(cid or "chart"))
    else:
        html = f"<div style='color:#111;font:14px/1.45 -apple-system,Segoe UI,Roboto,Helvetica,Arial;white-space:pre-wrap'>{body_text}</div>"

    alt.attach(MIMEText(html, _subtype="html", _charset="utf-8"))

    # If inlining is requested, wrap alt in 'related' and attach image as inline
    if INLINE_IMAGE and inline_path and inline_path.exists():
        rel = MIMEMultipart("related")
        rel.attach(alt)
        with open(inline_path, "rb") as f:
            img = MIMEImage(f.read(), name=inline_path.name)
        # Use the same cid as in HTML above
        cid = make_msgid()[1:-1]
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline", filename=inline_path.name)
        rel.attach(img)
        msg_root.attach(rel)
    else:
        # No inline: just attach the alternative bodies
        msg_root.attach(alt)

    # Regular attachments (PNG plot etc.)
    for p in attachments or []:
        if not p:
            continue
        with open(p, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="png")
        part.add_header("Content-Disposition", "attachment", filename=p.name)
        msg_root.attach(part)

    if DRY_RUN:
        print(f"[DRY_RUN] Would send '{subject}' (inline={INLINE_IMAGE and bool(inline_path)}, attachments={[p.name for p in (attachments or [])]})")
        return

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as s:
        s.ehlo(); s.starttls(context=ctx); s.ehlo()
        s.login(FROM_EMAIL, APP_PASS.replace(" ", ""))
        s.sendmail(FROM_EMAIL, [TO_EMAIL], msg_root.as_string())

# ---------- email text/subject helpers ----------
def make_email_subject(bucket: dict, dd: float) -> str:
    lo, hi = bucket["lo"], bucket["hi"]
    rng = f"{int(hi)}% to {int(lo)}%" if math.isfinite(lo) else f"≤ {int(hi)}%"
    return f"SPX DIP ALERT — {rng} (DD {dd:.2f}%)"

def make_email_body(ticker: str, close: float, peak: float, dd: float,
                    peak_date: dt.date, bucket: dict, note: str = "") -> str:
    lo, hi = bucket["lo"], bucket["hi"]
    lines = [
        "[SPX Dip Alert]",
        f"Ticker: {ticker}",
        f"Close: {close:.2f}",
        f"Recent High: {peak:.2f} (on {peak_date.date()})",
        f"Drawdown: {dd:.2f}%",
        f"Bucket: {hi:.1f}% to {lo:.1f}%",
        f"Plan: {bucket['note']}",
        f"Time: {now_str()}",
    ]
    if note:
        lines.append(note)
    return "\n".join(lines)

# ---------- cleanup helpers ----------

def _cutoff_dt() -> dt.datetime:
    return dt.datetime.now(tz=TZ) - dt.timedelta(days=RETENTION_DAYS)

def clean_old_plots() -> int:
    """Delete plot PNGs older than RETENTION_DAYS in PLOTS_DIR."""
    if not PLOTS_DIR.exists():
        return 0
    cutoff = _cutoff_dt()
    deleted = 0
    for p in PLOTS_DIR.glob("*.png"):
        try:
            mtime = dt.datetime.fromtimestamp(p.stat().st_mtime, tz=TZ)
            if mtime < cutoff:
                p.unlink(missing_ok=True)
                deleted += 1
        except Exception as e:
            print(f"[{now_str()}] Plot cleanup skipped for {p.name}: {e}")
    if deleted:
        print(f"[{now_str()}] Plot cleanup: removed {deleted} old file(s).")
    return deleted

def clean_old_log_rows() -> int:
    """Rewrite LOG_CSV keeping only rows with ts_iso >= cutoff."""
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
                # if ts is naive, assume local TZ
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=TZ)
                if ts >= cutoff:
                    kept.append(r)
                else:
                    removed += 1
            except Exception:
                # if we can't parse, keep the row to avoid accidental data loss
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
    except Exception as e:
        print(f"[{now_str()}] Log cleanup error: {e}")
        return 0


# ---------- main ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true",
                        help="Send a simple test email and exit (does not modify state).")
    parser.add_argument("--test-bucket", choices=["B10","B20","B70"],
                        help="Send a simulated bucket alert and exit (does not modify state).")
    parser.add_argument("--show-plot", action="store_true",
                        help="Open the saved plot locally after generation (manual runs).")
    args = parser.parse_args()
        
    # --- Auto-clean old files/rows ---
    clean_old_plots()
    clean_old_log_rows()

    buckets = DEFAULT_BUCKETS

    # --- test connection ---
    if args.test:
        send_email(
            "TEST — SPX Dip Alert wiring OK",
            f"[SPX Dip Alert — TEST]\nHost: {platform.node()}\nTime: {now_str()}\n✓ SMTP connection successful."
        )
        print(f"[{now_str()}] Test email sent.")
        return

    # --- simulated bucket ---
    if args.test_bucket:
        series = fetch_series(INDEX_TICKER, LOOKBACK_DAYS)
        close, peak, dd, peak_date = compute_drawdown(series)
        b = next((x for x in buckets if x["id"] == args.test_bucket), None)
        if not b:
            print(f"[{now_str()}] Unknown bucket {args.test_bucket}")
            return

        plot_path = make_alert_plot(series, title=f"{INDEX_TICKER} — Close vs Recent High (TEST)") if SAVE_PLOTS else None
        if args.show_plot and plot_path:
            if os.name == "nt":
                os.startfile(str(plot_path))
            elif sys.platform.startswith("darwin"):
                subprocess.run(["open", str(plot_path)], check=False)
            else:
                subprocess.run(["xdg-open", str(plot_path)], check=False)

        subject = make_email_subject(b, dd)
        body = make_email_body(INDEX_TICKER, close, peak, dd, peak_date, b, "(SIMULATED ALERT)")
        html_kwargs = dict(ticker=INDEX_TICKER, close=close, peak=peak, dd=dd, peak_date=peak_date, bucket=b)

        send_email(
            subject,
            body_text=body,
            html_kwargs=html_kwargs,
            attachments=[plot_path] if plot_path else None,
            inline_path=plot_path
        )

        append_csv_log(now_str(), b, dd, close, peak, str(peak_date.date()), plot_path, INDEX_TICKER, True)
        print(f"[{now_str()}] Test bucket email sent for {b['id']}.")
        return

    # --- normal run ---
    state = load_state()
    series = fetch_series(INDEX_TICKER, LOOKBACK_DAYS)
    close, peak, dd, peak_date = compute_drawdown(series)
    bucket = pick_bucket(dd, buckets)

    if not bucket:
        print(f"[{now_str()}] No alert. DD {dd:.2f}% (close {close:.2f}, peak {peak:.2f}).")
        return

    peak_key = str(peak_date.date())
    if bucket["id"] in state.get("fired_buckets", {}).get(peak_key, []):
        print(f"[{now_str()}] Bucket {bucket['id']} already fired for this peak.")
        return

    plot_path = make_alert_plot(series, title=f"{INDEX_TICKER} — Close vs Recent High") if SAVE_PLOTS else None
    if args.show_plot and plot_path:
        if os.name == "nt":
            os.startfile(str(plot_path))
        elif sys.platform.startswith("darwin"):
            subprocess.run(["open", str(plot_path)], check=False)
        else:
            subprocess.run(["xdg-open", str(plot_path)], check=False)

    subject = make_email_subject(bucket, dd)
    body = make_email_body(INDEX_TICKER, close, peak, dd, peak_date, bucket)
    html_kwargs = dict(ticker=INDEX_TICKER, close=close, peak=peak, dd=dd, peak_date=peak_date, bucket=bucket)

    try:
        send_email(
            subject,
            body_text=body,
            html_kwargs=html_kwargs,
            attachments=[plot_path] if plot_path else None,
            inline_path=plot_path
        )
        print(f"[{now_str()}] Alert sent.")
    except (smtplib.SMTPException, socket.timeout) as e:
        print(f"[{now_str()}] ERROR sending email: {e}")
        return

    append_csv_log(now_str(), bucket, dd, close, peak, str(peak_date.date()), plot_path, INDEX_TICKER, False)
    state.setdefault("fired_buckets", {}).setdefault(peak_key, []).append(bucket["id"])
    save_state(state)
    print(f"[{now_str()}] Logged and state updated.")

if __name__ == "__main__":
    main()
