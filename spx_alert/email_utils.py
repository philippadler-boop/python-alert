# spx_alert/email_utils.py
from __future__ import annotations

import math
import os
import ssl
from pathlib import Path
from typing import List, Optional, Dict, Any

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from email.utils import make_msgid

import certifi

from .config import DRY_RUN, INLINE_IMAGE, now_str
from .buckets import Bucket


def build_html_email(
    ticker: str,
    close: float,
    peak: float,
    dd: float,
    peak_date,
    bucket: Bucket,
    cid: Optional[str],
) -> str:
    """Return a simple HTML version of the alert email."""
    lo, hi, note = bucket.lo, bucket.hi, bucket.note
    lo_s = f"{lo:.0f}%" if math.isfinite(lo) else "-∞"
    hi_s = f"{hi:.0f}%"

    img_html = ""
    if cid:
        img_html = (
            "<div style='margin-top:14px;'>"
            f"<img src='cid:{cid}' "
            "style='max-width:100%;height:auto;border:1px solid #ddd'/>"
            "</div>"
        )

    return f"""
<html>
  <body style="background:#ffffff;margin:0;padding:16px;">
    <div style="color:#111;font:14px/1.45 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial;">
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
      {img_html}
    </div>
  </body>
</html>
"""


def make_email_subject(bucket: Bucket, dd: float) -> str:
    """Build a subject line including the bucket range and drawdown."""
    lo, hi = bucket.lo, bucket.hi
    if math.isfinite(lo):
        rng = f"{int(hi)}% to {int(lo)}%"
    else:
        rng = f"≤ {int(hi)}%"
    return f"SPX DIP ALERT — {rng} (DD {dd:.2f}%)"


def make_email_body(
    ticker: str,
    close: float,
    peak: float,
    dd: float,
    peak_date,
    bucket: Bucket,
    note: str = "",
) -> str:
    """Plain-text body for the alert."""
    lo, hi = bucket.lo, bucket.hi
    lines = [
        "[SPX Dip Alert]",
        f"Ticker: {ticker}",
        f"Close: {close:.2f}",
        f"Recent High: {peak:.2f} (on {peak_date.date()})",
        f"Drawdown: {dd:.2f}%",
        f"Bucket: {hi:.1f}% to {lo:.1f}%",
        f"Plan: {bucket.note}",
        f"Time: {now_str()}",
    ]
    if note:
        lines.append(note)
    return "\n".join(lines)


def send_email(
    subject: str,
    body_text: str,
    *,
    html_kwargs: Optional[Dict[str, Any]] = None,
    attachments: Optional[List[Path]] = None,
    inline_path: Optional[Path] = None,
) -> None:
    """Send an email using Gmail SMTP with an App Password."""
    from_email = os.getenv("FROM_EMAIL")
    to_email = os.getenv("TO_EMAIL")
    app_pass = os.getenv("APP_PASSWORD")

    if not (from_email and to_email and app_pass):
        raise RuntimeError("Missing FROM_EMAIL / TO_EMAIL / APP_PASSWORD in environment")

    ctx = ssl.create_default_context()
    ctx.load_verify_locations(cafile=certifi.where())

    msg_root = MIMEMultipart("mixed")
    msg_root["Subject"] = subject
    msg_root["From"] = from_email
    msg_root["To"] = to_email

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body_text, _subtype="plain", _charset="utf-8"))

    cid = None
    if INLINE_IMAGE and inline_path and inline_path.exists():
        cid = make_msgid()[1:-1]

    if html_kwargs:
        html = build_html_email(**html_kwargs, cid=cid)
    else:
        html = (
            "<div style='color:#111;font:14px/1.45 "
            "-apple-system,Segoe UI,Roboto,Helvetica,Arial;white-space:pre-wrap'>"
            f"{body_text}</div>"
        )

    alt.attach(MIMEText(html, _subtype="html", _charset="utf-8"))

    if INLINE_IMAGE and inline_path and inline_path.exists():
        rel = MIMEMultipart("related")
        rel.attach(alt)
        with inline_path.open("rb") as f:
            img = MIMEImage(f.read(), name=inline_path.name)
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline", filename=inline_path.name)
        rel.attach(img)
        msg_root.attach(rel)
    else:
        msg_root.attach(alt)

    for p in attachments or []:
        if not p:
            continue
        with p.open("rb") as f:
            part = MIMEApplication(f.read(), _subtype="png")
        part.add_header("Content-Disposition", "attachment", filename=p.name)
        msg_root.attach(part)

    if DRY_RUN:
        print(
            f"[DRY_RUN] Would send '{subject}' "
            f"(attachments={[p.name for p in (attachments or []) if p]})"
        )
        return

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as s:
        s.ehlo()
        s.starttls(context=ctx)
        s.ehlo()
        s.login(from_email, app_pass.replace(" ", ""))
        s.sendmail(from_email, [to_email], msg_root.as_string())
