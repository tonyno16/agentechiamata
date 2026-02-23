"""
Conversation API — endpoints consumed by n8n WF-2 (WhatsApp agent).

POST /conversation/start   — start a new session, returns welcome message
POST /conversation/message — send user reply, returns agent response(s)
GET  /conversation/{id}/state — debug: inspect session state
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.graph import create_session, get_session, process_turn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversation", tags=["conversation"])


# ── Request / response models ────────────────────────────────────────────────

class StartRequest(BaseModel):
    lead_id: str = Field(..., description="UUID of the lead (from Supabase)")
    product_id: str = Field(..., description="UUID of the product to sell")


class MessageRequest(BaseModel):
    conversation_id: str = Field(..., description="Session ID returned by /start")
    message: str = Field(..., description="User's WhatsApp message text")


class ConversationResponse(BaseModel):
    conversation_id: str
    messages: list[str] = Field(
        ..., description="Agent messages (may be >1 due to auto-chaining)"
    )
    state: str = Field(..., description="Current conversation state after this turn")
    finished: bool = False

    @property
    def message(self) -> str | None:
        """Convenience: first message (for single-message consumers)."""
        return self.messages[0] if self.messages else None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/start", response_model=ConversationResponse, summary="Start a new conversation")
async def start_conversation(req: StartRequest):
    """
    Called by n8n WF-1 after inserting a lead.
    Creates a session and returns the agent's opening message.
    """
    conversation_id = create_session(req.lead_id, req.product_id)
    try:
        result = await process_turn(conversation_id, user_message=None)
    except Exception as exc:
        logger.error("Error starting conversation %s: %s", conversation_id[:8], exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
    return ConversationResponse(**result)


@router.post("/message", response_model=ConversationResponse, summary="Process a user message")
async def send_message(req: MessageRequest):
    """
    Called by n8n WF-2 when a WhatsApp message arrives.
    Returns one or more agent messages to be sent back.
    """
    if get_session(req.conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    try:
        result = await process_turn(req.conversation_id, user_message=req.message)
    except Exception as exc:
        logger.error("Error in conversation %s: %s", req.conversation_id[:8], exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
    return ConversationResponse(**result)


@router.get("/{conversation_id}/state", summary="Inspect conversation state (debug)")
async def get_conversation_state(conversation_id: str):
    """Returns the full in-memory state for debugging."""
    state = get_session(conversation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "conversation_id": conversation_id,
        "current_state": state["current_state"],
        "message_count": len(state["messages"]),
        "collected_data": state["collected_data"],
        "sentiment": state["sentiment"],
        "upsell_attempted": state["upsell_attempted"],
        "upsell_accepted": state["upsell_accepted"],
        "objections_count": len(state["objections"]),
        "finished": state["current_state"] in {"completed", "abandoned"},
    }
