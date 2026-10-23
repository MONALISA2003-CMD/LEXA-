"""Small server-side email adapter for security-sensitive account email.

The initial provider is Resend's transactional-email API. It uses the Python
standard library so the API does not need a new runtime dependency. Provider
secrets must never be exposed to the Next.js browser bundle.
"""
from __future__ import annotations

import json
from html import escape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import settings


class EmailDeliveryError(RuntimeError):
    """Email provider request failed; callers should log only its exception type."""


def send_password_reset_email(recipient: str, reset_url: str) -> None:
    api_key = settings.resend_api_key.strip()
    sender = settings.email_from.strip()
    if not api_key or not sender:
        raise EmailDeliveryError("Transactional email is not configured")

    payload = {
        "from": sender,
        "to": [recipient],
        "subject": "Reset your LEXA password",
        "text": (
            "We received a request to reset your LEXA password. "
            f"Open this link within {settings.password_reset_minutes} minutes to choose a new password: "
            f"{reset_url}\n\nIf you did not request this, you can ignore this email."
        ),
        "html": (
            "<p>We received a request to reset your LEXA password.</p>"
            f"<p><a href=\"{escape(reset_url, quote=True)}\">Choose a new password</a> (link expires in "
            f"{settings.password_reset_minutes} minutes).</p>"
            "<p>If you did not request this, you can ignore this email.</p>"
        ),
    }
    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.email_timeout_seconds) as response:
            if response.status < 200 or response.status >= 300:
                raise EmailDeliveryError(f"Email provider returned HTTP {response.status}")
    except HTTPError as exc:
        # Do not include provider response bodies; they may contain addresses or data.
        raise EmailDeliveryError(f"Email provider returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise EmailDeliveryError("Email provider unavailable") from exc
