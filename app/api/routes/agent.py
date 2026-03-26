# api/routes/agent.py

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from app.services.agent_service import run_agent
from app.api.deps import get_current_user

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentRequest(BaseModel):
    message: str


@router.post("/chat")
async def agent_chat(payload: AgentRequest, request: Request, current_user=Depends(get_current_user)):
    # Extract the raw Bearer token from the Authorization header
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    response_text, _ = run_agent(
        user_message=payload.message,
        token=token,
    )
    return {"response": response_text}  # plain text → pass directly to Tavus