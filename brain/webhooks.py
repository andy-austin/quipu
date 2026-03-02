"""Webhook trigger endpoints for the Brain service."""

import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from brain import graph as graph_module
from brain.dependencies import verify_user
from brain.logging import log
from brain.rate_limit import check_rate_limit

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookCreateRequest(BaseModel):
    name: str = Field(..., description="Human-readable name for this webhook")
    agent: str = Field(default="chat", description="Agent type to run when triggered")
    system_prompt: str | None = Field(default=None, description="Optional system prompt")


class WebhookTriggerRequest(BaseModel):
    message: str = Field(..., description="Message to send to the agent")


def _get_mcp_tool(name: str):
    """Look up an MCP tool by name, or return None."""
    for t in graph_module.remote_mcp_tools:
        if t.name == name:
            return t
    return None


def _verify_signature(secret: str, body: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 signature of the request body."""
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


@router.post("")
async def register_webhook(req: WebhookCreateRequest, user_id: str = Depends(verify_user)):
    """Register a new webhook trigger for the authenticated user."""
    check_rate_limit(user_id)

    tool = _get_mcp_tool("create_webhook")
    if tool is None:
        raise HTTPException(status_code=503, detail="Webhook service not available")

    result = await tool.ainvoke(
        {
            "user_id": user_id,
            "name": req.name,
            "agent": req.agent,
            "system_prompt": req.system_prompt,
        }
    )
    if isinstance(result, str):
        result = json.loads(result)
    return result


@router.get("")
async def webhooks_list(user_id: str = Depends(verify_user)):
    """List all webhooks for the authenticated user."""

    tool = _get_mcp_tool("list_webhooks")
    if tool is None:
        return {"webhooks": []}

    result = await tool.ainvoke({"user_id": user_id})
    if isinstance(result, str):
        result = json.loads(result)
    return result


@router.delete("/{webhook_id}")
async def webhook_delete(webhook_id: str, user_id: str = Depends(verify_user)):
    """Delete a webhook."""

    tool = _get_mcp_tool("delete_webhook")
    if tool is None:
        raise HTTPException(status_code=503, detail="Webhook service not available")

    result = await tool.ainvoke({"user_id": user_id, "webhook_id": webhook_id})
    if isinstance(result, str):
        result = json.loads(result)
    return result


@router.post("/{webhook_id}/trigger")
async def webhook_trigger(webhook_id: str, request: Request):
    """Incoming webhook — validates HMAC signature and starts an agent run.

    The request must include an X-Webhook-Signature header with the
    HMAC-SHA256 signature of the body using the webhook's secret.
    """
    # Get webhook details
    tool = _get_mcp_tool("get_webhook")
    if tool is None:
        raise HTTPException(status_code=503, detail="Webhook service not available")

    webhook = await tool.ainvoke({"webhook_id": webhook_id})
    if isinstance(webhook, str):
        webhook = json.loads(webhook)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if not webhook.get("active", False):
        raise HTTPException(status_code=410, detail="Webhook is inactive")

    # Verify HMAC signature
    body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")
    if not _verify_signature(webhook["secret"], body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Rate limit the webhook owner
    check_rate_limit(webhook["user_id"])

    # Parse the trigger payload
    try:
        payload = await request.json()
        message = payload.get("message", "")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    # Save the run via MCP
    save_tool = _get_mcp_tool("save_run")
    run_data = {
        "url": f"webhook:{webhook_id}",
        "user_id": webhook["user_id"],
        "metadata_json": json.dumps(
            {
                "source": "webhook",
                "webhook_id": webhook_id,
                "webhook_name": webhook["name"],
                "agent": webhook["agent"],
                "message": message[:500],
            }
        ),
    }
    run_result = None
    if save_tool:
        result = await save_tool.ainvoke(run_data)
        if isinstance(result, str):
            result = json.loads(result)
        run_result = result

    log.info(
        "webhook_triggered",
        webhook_id=webhook_id,
        user_id=webhook["user_id"],
        agent=webhook["agent"],
    )

    return {
        "status": "triggered",
        "webhook_id": webhook_id,
        "agent": webhook["agent"],
        "run": run_result,
    }
