from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, List
from app.schemas.user import UserInDB, RoleEnum
from app.schemas.complaint import ComplaintCreate, ComplaintInDB, ComplaintUpdate
from app.api.deps import get_current_user, RoleChecker
from app.services import complaint_service

router = APIRouter(prefix="/complaints", tags=["complaints"])

@router.post("/", response_model=ComplaintInDB, status_code=status.HTTP_201_CREATED)
async def create_complaint(
    complaint_in: ComplaintCreate,
    current_user: UserInDB = Depends(RoleChecker([RoleEnum.citizen]))
):
    """
    Submit a new complaint. Only accessible by Citizens.
    """
    return await complaint_service.create_complaint(complaint_in, user_firebase_uid=current_user.firebase_uid)

@router.get("/my", response_model=List[ComplaintInDB])
async def get_my_complaints(
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get all complaints created by the logged-in user.
    """
    return await complaint_service.get_user_complaints(current_user.firebase_uid)

@router.get("/assigned", response_model=List[ComplaintInDB])
async def get_assigned_complaints(
    current_user: UserInDB = Depends(RoleChecker([RoleEnum.officer])),
    skip: int = 0,
    limit: int = 50
):
    """
    Get all complaints assigned to the logged-in officer.
    """
    return await complaint_service.get_assigned_complaints(current_user.firebase_uid, skip=skip, limit=limit)


@router.get("/spam", response_model=List[ComplaintInDB])
async def get_spam_complaints(
    current_user: UserInDB = Depends(RoleChecker([RoleEnum.officer, RoleEnum.ministry])),
    skip: int = 0,
    limit: int = 50
):
    """
    Get all spam-flagged complaints for officer/ministry review.
    """
    return await complaint_service.get_flagged_spam_complaints(skip=skip, limit=limit)


@router.get("/locations", response_model=List[dict])
async def get_complaint_locations(
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get coordinates, category, and status of all non-spam complaints for heatmap visualization.
    """
    return await complaint_service.get_all_complaint_locations()


@router.get("/{complaint_id}", response_model=ComplaintInDB)
async def get_complaint(
    complaint_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get specific complaint details.
    """
    complaint = await complaint_service.get_complaint_by_id(complaint_id)
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
        
    # Security: A citizen can only view their own complaints. 
    # Officers/Ministry/MP_MLA can view any complaint based on requirements.
    if current_user.role == RoleEnum.citizen and complaint.created_by != current_user.firebase_uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this complaint")
        
    return complaint

@router.delete("/{complaint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_complaint_endpoint(
    complaint_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Delete a complaint. Only the citizen who created it can delete it.
    """
    if current_user.role != RoleEnum.citizen:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only citizens can delete their complaints")
        
    success = await complaint_service.delete_complaint(complaint_id, current_user.firebase_uid)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found or not authorized to delete")
    return None

@router.patch("/{complaint_id}/status", response_model=ComplaintInDB)
async def update_complaint_status(
    complaint_id: str,
    update_data: ComplaintUpdate,
    current_user: UserInDB = Depends(RoleChecker([RoleEnum.officer, RoleEnum.ministry]))
):
    """
    Update complaint details (assign, resolve, duplicate_of, sentiment_score, etc.).
    Only Officers and Ministry officials can update complaints.
    """
    complaint = await complaint_service.get_complaint_by_id(complaint_id)
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
        
    updated = await complaint_service.update_complaint(complaint_id, update_data)
    return updated

from pydantic import BaseModel
class FeedbackCreate(BaseModel):
    rating: int
    comment: str | None = None

@router.post("/{complaint_id}/feedback", response_model=ComplaintInDB)
async def submit_feedback(
    complaint_id: str,
    feedback_in: FeedbackCreate,
    current_user: UserInDB = Depends(RoleChecker([RoleEnum.citizen]))
):
    """
    Submit feedback/rating for a resolved complaint. Only accessible by Citizens.
    """
    complaint = await complaint_service.get_complaint_by_id(complaint_id)
    if not complaint or complaint.created_by != current_user.firebase_uid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found or not authorized")
        
    updated = await complaint_service.add_feedback(complaint_id, feedback_in.rating, feedback_in.comment)
    if not updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to add feedback")
    return updated

class NoteCreate(BaseModel):
    text: str

@router.post("/{complaint_id}/notes", response_model=ComplaintInDB)
async def add_note(
    complaint_id: str,
    note_in: NoteCreate,
    current_user: UserInDB = Depends(RoleChecker([RoleEnum.officer, RoleEnum.ministry]))
):
    """
    Add an internal note to a complaint. Only accessible by Officers and Ministry.
    """
    complaint = await complaint_service.get_complaint_by_id(complaint_id)
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
        
    updated = await complaint_service.add_note(complaint_id, current_user.firebase_uid, note_in.text)
    if not updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to add note")
    return updated


# ─── AI Problem Summary ───────────────────────────────────
from app.core.config import settings

_openai_client: Any | None = None

def _get_openai_client() -> Any:
    global _openai_client
    if _openai_client is None:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        try:
            from openai import AsyncOpenAI
        except ModuleNotFoundError as exc:
            raise RuntimeError("OpenAI package is not installed in the backend environment") from exc
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


@router.get("/{complaint_id}/ai-summary")
async def get_ai_summary(
    complaint_id: str,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Generate a concise AI-powered problem description for a complaint.
    """
    complaint = await complaint_service.get_complaint_by_id(complaint_id)
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    # Build context string from complaint fields
    loc = complaint.location
    context = (
        f"Title: {complaint.title}\n"
        f"Description: {complaint.description}\n"
        f"Category: {complaint.category or 'Not categorised'}\n"
        f"Location: {loc.address}, {loc.city}, {loc.state} - {loc.pincode}\n"
        f"Priority: {complaint.priority.value}\n"
        f"Status: {complaint.status.value}\n"
        f"Filed on: {complaint.created_at.strftime('%d %b %Y, %H:%M')}\n"
    )

    try:
        client = _get_openai_client()
        chat = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.4,
            max_tokens=200,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a civic grievance analyst. Given a citizen's complaint, "
                        "produce a clear, professional 2-3 sentence summary that explains "
                        "the core problem, its location context, and the potential impact "
                        "on residents. Be concise and empathetic. Do NOT repeat the title."
                    ),
                },
                {"role": "user", "content": context},
            ],
        )
        summary = chat.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service unavailable: {str(e)}",
        )

    return {"summary": summary}


# ─── AI Complaint Assistant Chat ──────────────────────────
import json as _json

ASSISTANT_SYSTEM_PROMPT = """\
You are Saarthii AI — a friendly, empathetic assistant that helps Indian citizens \
file public service complaints (roads, water, electricity, sanitation, drainage, \
public infrastructure, etc.).

Your job is to have a natural conversation with the user to gather enough details \
to fill a complaint form. The form needs:
  - title: short summary (under 10 words)
  - description: detailed explanation of the issue
  - address: street address where the issue exists
  - city: city name
  - state: state name
  - pincode: 6-digit pincode

CONVERSATION RULES:
1. Start by asking the user to describe their problem.
2. Ask clarifying follow-up questions one at a time: What happened? Where exactly? \
   How long has it been? What is the impact?
3. Be warm, empathetic, and use simple language.
4. After gathering enough info (at minimum: what the problem is AND where it is), \
   generate the form data.

RESPONSE FORMAT — you MUST always respond with valid JSON:
{
  "reply": "Your conversational message to the user",
  "form_data": null
}

When you have gathered enough details, populate form_data:
{
  "reply": "Great! I have enough details. Here is what I will fill in for you...",
  "form_data": {
    "title": "...",
    "description": "...",
    "address": "...",
    "city": "...",
    "state": "...",
    "pincode": "..."
  }
}

If the user has not yet given enough info, keep form_data as null and ask more questions.
Always respond in the same language the user speaks (English or Hindi).
"""


class AssistantChatRequest(BaseModel):
    messages: list[dict]   # [{role: "user"|"assistant", content: str}, ...]


@router.post("/assistant/chat")
async def assistant_chat(
    body: AssistantChatRequest,
    current_user: UserInDB = Depends(get_current_user),
):
    """
    Multi-turn chat endpoint for the AI complaint filing assistant.
    Returns the AI reply + optional form_data when enough info is collected.
    """
    openai_messages: list[dict] = [
        {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT},
    ]
    # Append conversation history
    for msg in body.messages:
        openai_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })

    try:
        client = _get_openai_client()
        chat = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.5,
            max_tokens=500,
            response_format={"type": "json_object"},
            messages=openai_messages,
        )
        raw = chat.choices[0].message.content.strip()
        parsed = _json.loads(raw)
        return {
            "reply": parsed.get("reply", "I'm sorry, could you repeat that?"),
            "form_data": parsed.get("form_data"),
        }
    except _json.JSONDecodeError:
        import logging
        logging.warning(f"Assistant chat: JSON parse failed, raw response: {raw[:200]}")
        return {"reply": raw, "form_data": None}
    except Exception as e:
        import logging
        logging.error(f"Assistant chat error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service unavailable: {str(e)}",
        )
