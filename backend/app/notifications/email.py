"""
Email delivery(SendGrid). Stubbed when the feature flag is off
"""

from __future__ import annotations
import httpx
import structlog

from app.config import settings

log=structlog.get_logger()

SENDGRID_URL="https://api.sendgrid.com/v3/mail/send"

def send_email(
    to: str | list[str],
    subject: str,
    html_body: str,
    *,
    text_body: str | None=None,
    from_email: str | None=None,
    )-> dict:
    """Send a transactional email via SendGrid
    Returns a small status dict so callers don't need to check status codes. 
    No-ops (returns ("sent": False, "reason": ...)) when feature-flagged off or when the SENDGRID_API KEY is empty.
    """
    recipients = [to] if isinstance(to, str) else list(to)

    if not settings.feature_email_digests:
        log.info("email_stub_disabled_by_flag", subject=subject, to=recipients) 
        return {"sent": False, "reason": "feature_email_digests=False"}

    if not settings.sendgrid_api_key:
        log.info("email_stub_no_key", subject=subject, to=recipients, preview=html_body[:160]) 
        return {"sent": False, "reason": "sendgrid_api_key empty (stubbed)"}

    payload = {
        "personalizations": [{"to": [{"email": r} for r in recipients]}], 
        "from": {"email": from_email or settings.sendgrid_from_email},
        "subject":subject,
        "content": [
            {"type": "text/plain", "value": text_body or _strip_html(html_body)},
            {"type": "text/html", "value": html_body},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.sendgrid_api_key}",
        "Content-Type": "application/json",
    } 
    try:
        with httpx.Client(timeout=15.0) as client:
            r=client.post(SENDGRID_URL, json=payload, headers=headers)

        if 200 <= r.status_code < 300:
            log.info("email_sent", subject=subject, to=recipients, status=r.status_code)
            return {"sent": True, "status": r.status_code}
        
        log.warning("email_failed", subject=subject, status=r.status_code, body=r.text[:200])
        return {"sent": False, "status": r.status_code, "reason": r.text[:200]}
    except Exception as e: # noqa: BLE001
        log.warning("email_exception", subject=subject, error=str(e))
        return {"sent": False, "reason": str(e)}

def _strip_html(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", html)