"""
Notifications stub : feature-flagged email + slack delivery

When the corresponding feature flag is off or credentials are missing,
notifications are logged (so we can verify the path locally) but not sent.

Public API:

    from app.notifications import send_email, send_slack
    send(to="alice@example.com", subject="...", html_body="...")
    send_slack(text="...")
"""

from __future__ import annotations

from app.notifications.email import send_email
from app.notifications.slack import send_slack

__all__ = ["send_email", "send_slack"]