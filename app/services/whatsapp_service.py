"""
WhatsApp Service — Meta WhatsApp Cloud API + agent_service integration.

Receives incoming text messages, routes them through the existing LangGraph
agent (agent_service.run_agent), persists chat history per phone number in
MongoDB, and sends the agent's reply back via Meta's Graph API.
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.core.config import settings
from app.services.agent_service import run_agent

logger = logging.getLogger(__name__)


def _meta_api_url() -> str:
    """Build the Meta API URL at call time so config reloads are picked up."""
    return f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"


def _meta_headers() -> dict:
    """Build the Meta API headers at call time so token updates are picked up."""
    return {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


# ────────────────────────────────────────────────────────────
#  Message serialization for MongoDB
# ────────────────────────────────────────────────────────────
_TYPE_MAP = {
    "human": HumanMessage,
    "ai": AIMessage,
    "system": SystemMessage,
    "tool": ToolMessage,
}


def _serialize_messages(messages: list[BaseMessage]) -> list[dict]:
    """Convert LangChain messages to JSON-safe dicts for MongoDB storage."""
    serialized = []
    for msg in messages:
        entry = {
            "type": msg.type,
            "content": msg.content,
        }
        # Preserve tool_calls on AI messages (needed for tool replay)
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            entry["tool_calls"] = msg.tool_calls
        # Preserve tool_call_id on ToolMessages
        if hasattr(msg, "tool_call_id") and msg.tool_call_id:
            entry["tool_call_id"] = msg.tool_call_id
        serialized.append(entry)
    return serialized


def _deserialize_messages(data: list[dict]) -> list[BaseMessage]:
    """Restore LangChain messages from MongoDB dicts."""
    messages: list[BaseMessage] = []
    for entry in data:
        msg_cls = _TYPE_MAP.get(entry["type"])
        if msg_cls is None:
            continue  # skip unknown types gracefully

        kwargs: dict = {"content": entry["content"]}

        # Rebuild tool_calls for AIMessage
        if msg_cls is AIMessage and entry.get("tool_calls"):
            kwargs["tool_calls"] = entry["tool_calls"]
        # Rebuild tool_call_id for ToolMessage
        if msg_cls is ToolMessage and entry.get("tool_call_id"):
            kwargs["tool_call_id"] = entry["tool_call_id"]

        messages.append(msg_cls(**kwargs))
    return messages


# ────────────────────────────────────────────────────────────
#  In-memory fallback (used when database is unreachable)
# ────────────────────────────────────────────────────────────
_memory_sessions: dict[str, list[BaseMessage]] = {}


# ────────────────────────────────────────────────────────────
#  Session helpers  (PostgreSQL with in-memory fallback)
# ────────────────────────────────────────────────────────────
async def _get_chat_history(phone: str) -> list[BaseMessage]:
    """Load persisted chat history for a phone number."""
    from app.db.database import get_db_ctx
    from app.db.models import WhatsAppSessionDB
    from sqlalchemy import select

    try:
        async with get_db_ctx() as session:
            stmt = select(WhatsAppSessionDB).where(WhatsAppSessionDB.phone == phone)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
            if doc and doc.messages:
                return _deserialize_messages(doc.messages)
            return []
    except Exception as e:
        logger.warning(f"Database unavailable for chat history: {e}, using in-memory fallback")
    return _memory_sessions.get(phone, [])


async def _save_chat_history(phone: str, messages: list[BaseMessage]):
    """Persist the updated chat history (falls back to memory)."""
    from app.db.database import get_db_ctx
    from app.db.models import WhatsAppSessionDB
    from sqlalchemy import select

    _memory_sessions[phone] = messages  # Always keep in memory
    try:
        async with get_db_ctx() as session:
            stmt = select(WhatsAppSessionDB).where(WhatsAppSessionDB.phone == phone)
            result = await session.execute(stmt)
            doc = result.scalar_one_or_none()
            
            if doc:
                doc.messages = _serialize_messages(messages)
                doc.updated_at = datetime.now(timezone.utc)
            else:
                doc = WhatsAppSessionDB(
                    phone=phone,
                    messages=_serialize_messages(messages),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
            session.add(doc)
            await session.commit()
    except Exception as e:
        logger.warning(f"Database unavailable — chat history saved in memory only: {e}")


async def _clear_session(phone: str):
    """Delete session (used on 'reset' command)."""
    from app.db.database import get_db_ctx
    from app.db.models import WhatsAppSessionDB
    from sqlalchemy import delete

    _memory_sessions.pop(phone, None)
    try:
        async with get_db_ctx() as session:
            stmt = delete(WhatsAppSessionDB).where(WhatsAppSessionDB.phone == phone)
            await session.execute(stmt)
            await session.commit()
    except Exception:
        pass


# ────────────────────────────────────────────────────────────
#  WhatsApp user provisioning + internal token
# ────────────────────────────────────────────────────────────
async def _get_or_create_wa_user(phone: str) -> str:
    """
    Ensure a user record exists for this WhatsApp phone number
    and return a minimal internal JWT token the agent can use
    to call complaint API endpoints.
    """
    from app.db.database import get_db_ctx
    from app.db.models import UserDB
    from sqlalchemy import select

    user_id = f"whatsapp:{phone}"

    try:
        async with get_db_ctx() as session:
            stmt = select(UserDB).where(UserDB.firebase_uid == user_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if not existing:
                db_user = UserDB(
                    firebase_uid=user_id,
                    email=f"{phone.replace('+', '')}@whatsapp.pscrm",
                    name=f"WhatsApp User ({phone})",
                    phone=phone,
                    role="citizen",
                    created_at=datetime.now(timezone.utc),
                )
                session.add(db_user)
                await session.commit()
    except Exception as e:
        logger.warning(f"Database unavailable — skipping user provisioning: {e}")

    # Generate a lightweight internal JWT (works without DB)
    from app.core.security import create_internal_token
    return create_internal_token(sub=user_id)


# ────────────────────────────────────────────────────────────
#  Core message processor
# ────────────────────────────────────────────────────────────
async def process_message(phone: str, text: str) -> None:
    """
    Process an incoming WhatsApp text message:
    1. Load chat history
    2. Run through agent_service
    3. Save updated history
    4. Send reply via Meta API
    """
    text_lower = text.strip().lower()

    # ── Special commands ──────────────────────────────────
    if text_lower in ("reset", "restart", "start over"):
        await _clear_session(phone)
        await send_whatsapp_message(
            phone,
            "🔄 Session cleared! Send me a message describing your problem "
            "and I'll help you file a complaint.",
        )
        return

    try:
        # Load history & get token
        chat_history = await _get_chat_history(phone)
        token = await _get_or_create_wa_user(phone)

        # Run agent in thread pool (run_agent is synchronous)
        reply_text, updated_history = await asyncio.to_thread(
            run_agent,
            user_message=text,
            token=token,
            chat_history=chat_history,
        )

        # Persist updated history
        await _save_chat_history(phone, updated_history)

        # Send reply back on WhatsApp
        await send_whatsapp_message(phone, reply_text)

    except Exception as e:
        logger.error("WhatsApp processing error for %s: %s", phone, e, exc_info=True)
        await send_whatsapp_message(
            phone,
            "⚠️ Sorry, we're temporarily unavailable. Please try again in a moment.",
        )


# ────────────────────────────────────────────────────────────
#  Send message via Meta WhatsApp Cloud API
# ────────────────────────────────────────────────────────────
async def send_whatsapp_message(to: str, body: str) -> None:
    """
    Send a text message to a WhatsApp user via Meta Cloud API.

    Args:
        to:   Phone number in international format (e.g. "919876543210")
        body: The text message to send
    """
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _meta_api_url(),
                json=payload,
                headers=_meta_headers(),
            )
        if resp.status_code != 200:
            logger.error(
                "Meta API send failed (HTTP %s): %s",
                resp.status_code,
                resp.text,
            )
        else:
            logger.info("WhatsApp reply sent to %s", to)
    except Exception as e:
        logger.error("Meta API request failed to %s: %s", to, e)