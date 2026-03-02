"""Tools for sending notifications — email, Slack, and HTTP webhooks."""

import os
import time
from collections import defaultdict

import httpx

from hands.logging import log

# Rate limiting: max notifications per user per minute
_RATE_LIMIT = int(os.getenv("NOTIFICATION_RATE_LIMIT", "10"))
_RATE_WINDOW = 60  # seconds
_user_timestamps: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(user_id: str) -> None:
    """Enforce per-user notification rate limit."""
    now = time.monotonic()
    timestamps = _user_timestamps[user_id]
    # Prune old entries
    _user_timestamps[user_id] = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(_user_timestamps[user_id]) >= _RATE_LIMIT:
        raise ValueError(
            f"Rate limit exceeded: max {_RATE_LIMIT} notifications per {_RATE_WINDOW}s"
        )
    _user_timestamps[user_id].append(now)


async def send_email(
    user_id: str,
    to: str,
    subject: str,
    body: str,
) -> dict:
    """Send an email via SendGrid.

    Args:
        user_id: The requesting user (for rate limiting).
        to: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body.

    Returns:
        Dict with status and message_id.
    """
    _check_rate_limit(user_id)

    api_key = os.environ.get("SENDGRID_API_KEY", "")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@quipu.dev")

    if not api_key:
        log.warning("send_email_no_api_key")
        return {"status": "error", "error": "SENDGRID_API_KEY not configured"}

    log.info("send_email", user_id=user_id, to=to, subject=subject)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": from_email},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}],
            },
            timeout=10,
        )

    if resp.status_code in (200, 202):
        message_id = resp.headers.get("X-Message-Id", "")
        log.info("email_sent", to=to, message_id=message_id)
        return {"status": "sent", "message_id": message_id}
    log.error("email_failed", status=resp.status_code, body=resp.text[:200])
    return {"status": "error", "error": f"SendGrid returned {resp.status_code}"}


async def send_slack_message(
    user_id: str,
    webhook_url: str,
    text: str,
) -> dict:
    """Send a message to a Slack channel via incoming webhook.

    Args:
        user_id: The requesting user (for rate limiting).
        webhook_url: Slack incoming webhook URL.
        text: Message text (supports Slack mrkdwn).

    Returns:
        Dict with status.
    """
    _check_rate_limit(user_id)
    log.info("send_slack_message", user_id=user_id)

    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json={"text": text}, timeout=10)

    if resp.status_code == 200:
        log.info("slack_message_sent")
        return {"status": "sent"}
    log.error("slack_message_failed", status=resp.status_code, body=resp.text[:200])
    return {"status": "error", "error": f"Slack returned {resp.status_code}"}


async def send_webhook(
    user_id: str,
    url: str,
    payload: dict,
    headers: dict | None = None,
) -> dict:
    """Send an arbitrary HTTP POST to a webhook URL.

    Args:
        user_id: The requesting user (for rate limiting).
        url: Target webhook URL.
        payload: JSON payload to send.
        headers: Optional additional headers.

    Returns:
        Dict with status and response status code.
    """
    _check_rate_limit(user_id)
    log.info("send_webhook", user_id=user_id, url=url)

    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=request_headers, timeout=10)

    log.info("webhook_sent", url=url, status=resp.status_code)
    return {
        "status": "sent" if resp.status_code < 400 else "error",
        "response_status": resp.status_code,
    }
