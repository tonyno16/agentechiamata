"""
Conversation runner and in-memory session store.

Architecture:
  - Sessions are kept in a process-level dict (_sessions).
  - TASK-017 will replace this with Supabase-backed persistence.
  - The runner dispatches to node functions and auto-chains terminal
    transitions (order_creation → handoff → completed) so a single
    API call can produce multiple agent messages.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import StateGraph, END

from app.agents.state import ConversationState
from app.agents.nodes import (
    node_welcome,
    node_discovery,
    node_offers,
    node_objections,
    node_data_collection,
    node_upsell,
    node_order_creation,
    node_handoff,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_NODE_MAP: dict[str, Any] = {
    "welcome": node_welcome,
    "discovery": node_discovery,
    "offers": node_offers,
    "objections": node_objections,
    "data_collection": node_data_collection,
    "upsell": node_upsell,
    "order_creation": node_order_creation,
    "handoff": node_handoff,
}

# States that auto-chain (don't require a new user message to run)
_AUTO_CHAIN: frozenset[str] = frozenset({"order_creation", "handoff"})
_TERMINAL: frozenset[str] = frozenset({"completed", "abandoned"})

# ── In-memory session store (replaced in TASK-017) ───────────────────────────
_sessions: dict[str, ConversationState] = {}


# ── LangGraph definition (for schema documentation & future use) ─────────────

def build_graph() -> StateGraph:
    """Return a compiled LangGraph StateGraph for the conversation flow."""

    def _router(state: ConversationState) -> str:
        s = state["current_state"]
        return END if s in _TERMINAL else s

    g = StateGraph(ConversationState)
    for name, fn in _NODE_MAP.items():
        g.add_node(name, fn)
    g.set_entry_point("welcome")
    for name in _NODE_MAP:
        g.add_conditional_edges(name, _router)
    return g


# ── Session helpers ──────────────────────────────────────────────────────────

def create_session(lead_id: str, product_id: str) -> str:
    """Create a new ConversationState and return the conversation_id."""
    conversation_id = str(uuid.uuid4())
    _sessions[conversation_id] = ConversationState(
        conversation_id=conversation_id,
        lead_id=lead_id,
        product_id=product_id,
        current_state="welcome",
        messages=[],
        collected_data={},
        objections=[],
        upsell_attempted=False,
        upsell_accepted=False,
        language_verified=False,
        sentiment="neutral",
    )
    logger.info("Session created: %s (lead=%s, product=%s)", conversation_id[:8], lead_id[:8], product_id[:8])
    return conversation_id


def get_session(conversation_id: str) -> ConversationState | None:
    return _sessions.get(conversation_id)


def _save_session(conversation_id: str, state: ConversationState) -> None:
    _sessions[conversation_id] = state


def list_sessions() -> list[str]:
    return list(_sessions.keys())


# ── Turn processor ───────────────────────────────────────────────────────────

async def process_turn(
    conversation_id: str,
    user_message: str | None = None,
) -> dict:
    """
    Process one conversation turn.

    - user_message=None  → first turn, agent speaks first (welcome).
    - user_message=<str> → subsequent turns, user replied.

    Returns:
        {
            "conversation_id": str,
            "messages": list[str],   # one or more agent messages
            "state": str,            # current_state after processing
            "finished": bool,
        }
    """
    state = get_session(conversation_id)
    if state is None:
        raise ValueError(f"Conversation '{conversation_id}' not found")

    current = state["current_state"]

    # Already finished
    if current in _TERMINAL:
        return {
            "conversation_id": conversation_id,
            "messages": [],
            "state": current,
            "finished": True,
        }

    # Add user message to state (and persist to Supabase)
    if user_message:
        state = {
            **state,
            "messages": list(state["messages"]) + [
                {
                    "role": "user",
                    "content": user_message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "state": current,
                }
            ],
        }
        try:
            from app.tools.supabase_tools import save_conversation_message
            save_conversation_message(
                state["lead_id"], "lead", user_message, {"state": current}
            )
        except Exception as exc:
            logger.warning("Could not save user message to Supabase: %s", exc)

    # Dispatch nodes, auto-chaining through non-interactive states
    collected_messages: list[str] = []
    prev_count = len(state["messages"])

    for _ in range(6):  # Safety cap on auto-chaining
        node_state = state["current_state"]
        if node_state in _TERMINAL:
            break

        node_fn = _NODE_MAP.get(node_state)
        if node_fn is None:
            logger.error("No node function for state '%s'", node_state)
            break

        updates = await node_fn(state)
        state = {**state, **updates}

        # Collect new agent messages produced by this node
        new_msgs = state["messages"][prev_count:]
        prev_count = len(state["messages"])
        collected_messages.extend(
            m["content"] for m in new_msgs if m["role"] == "assistant"
        )

        # Continue auto-chaining only for states that don't need user input
        if state["current_state"] not in _AUTO_CHAIN:
            break

    _save_session(conversation_id, state)

    return {
        "conversation_id": conversation_id,
        "messages": collected_messages,
        "state": state["current_state"],
        "finished": state["current_state"] in _TERMINAL,
    }
