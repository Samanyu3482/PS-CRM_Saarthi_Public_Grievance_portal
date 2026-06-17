"""
WhatsApp Webhook — receives Meta WhatsApp Cloud API messages and
routes them through the AI agent.

Meta sends JSON POST requests for incoming messages and a GET request
for webhook verification.
"""

import logging
from fastapi import APIRouter, Request, BackgroundTasks, Query
from fastapi.responses import PlainTextResponse, Response

from app.core.config import settings
from app.services import whatsapp_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


# ────────────────────────────────────────────────────────────
#  GET /whatsapp/webhook  — Webhook Verification
# ────────────────────────────────────────────────────────────
@router.get("/webhook")
async def verify_webhook(
    request: Request,
):
    """
    Meta sends a GET request with hub.mode, hub.verify_token, and
    hub.challenge when you register the webhook URL.  Return the
    challenge value if the verify token matches.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully")
        return PlainTextResponse(content=challenge, status_code=200)

    logger.warning("❌ Webhook verification failed (token mismatch)")
    return PlainTextResponse(content="Forbidden", status_code=403)


# ────────────────────────────────────────────────────────────
#  POST /whatsapp/webhook  — Incoming Messages
# ────────────────────────────────────────────────────────────
@router.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Meta WhatsApp Cloud API incoming message webhook.

    Immediately returns 200 (Meta requires fast ack), then
    processes the message in a background task.
    """
    body = await request.json()

    # Parse the Meta webhook payload
    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            # Not a message event (could be a status update) — ack and ignore
            return Response(status_code=200)

        message = messages[0]

        # Only process text messages
        if message.get("type") != "text":
            logger.info("Skipping non-text message type: %s", message.get("type"))
            return Response(status_code=200)

        phone = message["from"]        # e.g. "919876543210"
        text = message["text"]["body"]  # the actual message text

        logger.info("📩 WhatsApp message from %s: %s", phone, text[:100])

        # Process in background so webhook returns 200 immediately
        background_tasks.add_task(whatsapp_service.process_message, phone, text)

    except (KeyError, IndexError) as e:
        logger.warning("Could not parse Meta webhook payload: %s", e)

    return Response(status_code=200)