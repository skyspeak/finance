"""Send the weekly digest (and failure alerts) from Gmail. Stdlib only.

Two ways to authenticate, tried in this order:

1. Gmail SMTP + App Password (recommended). GMAIL_APP_PASSWORD is a 16-character
   password generated at https://myaccount.google.com/apppasswords for MAIL_FROM
   (needs 2-Step Verification). It does not expire; Google revokes it only if the
   account password changes or 2-Step Verification is turned off. No OAuth app, so
   no "Testing mode" 7-day refresh-token expiry.

2. Gmail API + OAuth refresh token: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
   GMAIL_REFRESH_TOKEN (scope gmail.send). Only long-lived if the OAuth consent
   screen is published to Production; in Testing, Google kills it after 7 days.

Env:
  MAIL_FROM   sender Gmail address   (default stuymusty@gmail.com)
  MAIL_TO     comma-separated list   (default: the payload's "to", else MAIL_FROM)

  python3 mailer.py --test           # send a one-line test message
"""
from __future__ import annotations

import base64
import json
import os
import smtplib
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

DEFAULT_FROM = "stuymusty@gmail.com"


class MailNotConfigured(RuntimeError):
    pass


def configured() -> str | None:
    if os.environ.get("GMAIL_APP_PASSWORD"):
        return "smtp"
    if all(os.environ.get(k) for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")):
        return "gmail-api"
    return None


def _message(sender: str, to: list[str], subject: str, html: str | None, text: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = f"Ten Themes <{sender}>"
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(text or " ")
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def _send_smtp(msg: EmailMessage, sender: str) -> str:
    password = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")  # Google displays it in groups of four
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=60) as s:
        s.login(sender, password)
        s.send_message(msg)
    return "smtp"


def _send_gmail_api(msg: EmailMessage) -> str:
    body = urllib.parse.urlencode({
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "refresh_token": os.environ["GMAIL_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body), timeout=30) as r:
            access = json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        if "invalid_grant" in detail:
            raise RuntimeError("Gmail refresh token expired or revoked (invalid_grant). If the OAuth consent "
                               "screen is in Testing, tokens die after 7 days — publish it to Production and "
                               "reconnect, or switch to GMAIL_APP_PASSWORD.") from e
        raise RuntimeError(f"Google token endpoint {e.code}: {detail[:300]}") from e
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=json.dumps({"raw": raw}).encode(),
        headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gmail send {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from e
    return "gmail-api"


def send(subject: str, text: str, html: str | None = None, to: list[str] | str | None = None) -> str:
    """Send one message. Returns the transport used; raises on failure."""
    how = configured()
    if not how:
        raise MailNotConfigured("set GMAIL_APP_PASSWORD (or GOOGLE_CLIENT_ID/SECRET + GMAIL_REFRESH_TOKEN)")
    sender = os.environ.get("MAIL_FROM", DEFAULT_FROM)
    env_to = os.environ.get("MAIL_TO")
    if env_to:
        to = env_to
    if isinstance(to, str):
        to = [a.strip() for a in to.split(",") if a.strip()]
    to = to or [sender]
    msg = _message(sender, to, subject, html, text)
    used = _send_smtp(msg, sender) if how == "smtp" else _send_gmail_api(msg)
    print(f"emailed '{subject[:70]}' to {', '.join(to)} via {used}", flush=True)
    return used


def send_params(path) -> str:
    """Send a build_email2.py payload (email2_params.json)."""
    p = json.load(open(path))
    return send(p["subject"], p.get("textBody") or "", p.get("htmlBody"), p.get("to"))


if __name__ == "__main__":
    if "--test" in sys.argv:
        send("Ten Themes mailer test", "If you can read this, the weekly digest can reach you.")
    else:
        print(__doc__)
