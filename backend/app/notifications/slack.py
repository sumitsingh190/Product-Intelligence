"""
Slack delivery via incoming webhook. Stubbed when feature-flagged off
"""

from __future__ import annotations
import httpx
import structlog

from app.config import settings

log=structlog.get_logger()

def send_slack(text: str, *, blocks: list | None = None) -> dict:
    if not settings.feature_slack_notifications:
        log.info("slack_stub_disabled_by_flag", preview=text[:160]) 
        return {"sent": False, "reason": "feature_slack_notifications=False"}

    if not settings.slack_webhook_url:
        log.info("slack_stub_no_webhook", preview=text[:160]) 
        return {"sent": False, "reason": "slack_webhook_url empty (stubbed)"}

    payload: dict={"text": text}
    if blocks:
        payload["blocks"] = blocks

    try:
        with httpx.Client(timeout=10.0) as client:
            r=client.post(settings.slack_webhook_url, json=payload)
        if r.status_code == 200:
            log.info("slack_sent", preview=text[:160])
            return {"sent": True}
        
        log.warning("slack_failed", status=r.status_code, body=r.text[:200]) 
        return {"sent": False, "status": r.status_code, "reason": r.text[:200]}
    except Exception as e: # noqa: BLE001
        log.warning("slack_exception", error=str(e))
        return {"sent": False, "reason": str(e)}