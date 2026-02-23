"""
LangGraph node functions — one per conversation state.

Each async function receives a ConversationState dict and returns a dict
with the fields to update (merged by the runner in graph.py).
"""

import json
import logging
import re
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents import prompts
from app.agents.state import ConversationState
from app.config import get_llm

logger = logging.getLogger(__name__)


# ── Internal helpers ────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_msg(role: str, content: str, state_name: str) -> dict:
    return {"role": role, "content": content, "timestamp": _now(), "state": state_name}


def _build_lc_messages(state: ConversationState, max_history: int = 12) -> list:
    """Convert the last N state messages to LangChain format."""
    result = []
    for msg in state["messages"][-max_history:]:
        if msg["role"] == "user":
            result.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            result.append(AIMessage(content=msg["content"]))
    return result


def _extract_json(text: str) -> dict:
    """Robustly extract a JSON object from an LLM response string."""
    text = text.strip()
    # Strip markdown code fences
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    # Find first {...}
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse LLM JSON: %.200s", text)
        return {}


async def _llm_json(system_prompt: str, lc_messages: list) -> dict:
    """Call the LLM and return the parsed JSON dict."""
    llm = get_llm()
    msgs = [SystemMessage(content=system_prompt)] + lc_messages
    response = await llm.ainvoke(msgs)
    return _extract_json(response.content)


def _append(state: ConversationState, content: str) -> list:
    """Append an agent message to the messages list."""
    return list(state["messages"]) + [_make_msg("assistant", content, state["current_state"])]


# ── Supabase helpers (fail-safe) ─────────────────────────────────────────────

def _get_product(product_id: str) -> dict:
    try:
        from app.tools.supabase_tools import get_product
        return get_product(product_id) or {}
    except Exception as exc:
        logger.warning("get_product failed: %s", exc)
        return {}


def _get_offers(product_id: str) -> list:
    try:
        from app.tools.supabase_tools import get_product_offers
        return get_product_offers(product_id)
    except Exception as exc:
        logger.warning("get_product_offers failed: %s", exc)
        return []


def _get_lead(lead_id: str) -> dict:
    try:
        from app.tools.supabase_tools import get_lead
        return get_lead(lead_id) or {}
    except Exception as exc:
        logger.warning("get_lead failed: %s", exc)
        return {}


def _save_msg(lead_id: str, sender: str, content: str, state_name: str) -> None:
    try:
        from app.tools.supabase_tools import save_conversation_message
        save_conversation_message(lead_id, sender, content, {"state": state_name})
    except Exception as exc:
        logger.warning("save_conversation_message failed: %s", exc)


def _missing_fields(collected: dict, phone: str) -> list[str]:
    """Return list of data still needed from the customer."""
    missing = []
    if not collected.get("name"):
        missing.append("nome e cognome")
    addr = collected.get("address", {})
    if not addr.get("street"):
        missing.append("via e numero civico")
    if not addr.get("cap"):
        missing.append("CAP")
    if not addr.get("city"):
        missing.append("città")
    if not addr.get("provincia"):
        missing.append("provincia")
    if not collected.get("phone_confirm"):
        missing.append(f"conferma numero di telefono ({phone})")
    return missing


# ── Node Functions ───────────────────────────────────────────────────────────

async def node_welcome(state: ConversationState) -> dict:
    """First contact: introduce Marco and ask an opening question."""
    product = _get_product(state["product_id"])
    product_name = product.get("name", "il nostro prodotto")

    result = await _llm_json(prompts.welcome_prompt(product_name), [])

    msg = result.get("message", f"Ciao! Sono Marco, consulente per {product_name}. 😊 Come posso aiutarla?")
    next_state = result.get("next_state", "discovery")

    _save_msg(state["lead_id"], "agent", msg, "welcome")
    return {
        "messages": _append(state, msg),
        "current_state": next_state,
        "language_verified": True,
    }


async def node_discovery(state: ConversationState) -> dict:
    """Understand the lead's needs and decide whether to show offers."""
    result = await _llm_json(prompts.discovery_prompt(), _build_lc_messages(state))

    msg = result.get("message", "Capisco. Può dirmi qualcosa in più sulla sua situazione?")
    next_state = result.get("next_state", "discovery")
    sentiment = result.get("sentiment", "neutral")

    _save_msg(state["lead_id"], "agent", msg, "discovery")
    return {
        "messages": _append(state, msg),
        "current_state": next_state,
        "sentiment": sentiment,
    }


async def node_offers(state: ConversationState) -> dict:
    """Present product offers and ask which the customer prefers."""
    product = _get_product(state["product_id"])
    offers = _get_offers(state["product_id"])
    product_name = product.get("name", "il prodotto")
    price = float(product.get("price", 0))

    result = await _llm_json(
        prompts.offers_prompt(product_name, price, offers),
        _build_lc_messages(state),
    )

    msg = result.get("message", "Ecco le nostre offerte disponibili! Quale preferisce?")
    next_state = result.get("next_state", "offers")
    selected_offer_id = result.get("selected_offer_id")

    collected = dict(state.get("collected_data", {}))
    if selected_offer_id:
        collected["selected_offer_id"] = selected_offer_id

    _save_msg(state["lead_id"], "agent", msg, "offers")
    return {
        "messages": _append(state, msg),
        "current_state": next_state,
        "collected_data": collected,
    }


async def node_objections(state: ConversationState) -> dict:
    """Handle customer objections empathetically."""
    objections = list(state.get("objections", []))
    attempt = len(objections) + 1

    result = await _llm_json(
        prompts.objections_prompt(attempt),
        _build_lc_messages(state),
    )

    msg = result.get("message", "Capisco la sua preoccupazione. Lasciami spiegare meglio…")
    next_state = result.get("next_state", "objections")

    objections.append({"attempt": attempt, "timestamp": _now()})

    _save_msg(state["lead_id"], "agent", msg, "objections")
    return {
        "messages": _append(state, msg),
        "current_state": next_state,
        "objections": objections,
    }


async def node_data_collection(state: ConversationState) -> dict:
    """Collect name, shipping address, and phone confirmation."""
    lead = _get_lead(state["lead_id"])
    phone = lead.get("phone") or lead.get("whatsapp_number") or "non disponibile"
    collected = dict(state.get("collected_data", {}))
    missing = _missing_fields(collected, phone)

    result = await _llm_json(
        prompts.data_collection_prompt(collected, phone, missing),
        _build_lc_messages(state),
    )

    msg = result.get("message", "Potrebbe indicarmi i dati per la spedizione?")
    next_state = result.get("next_state", "data_collection")

    # Merge newly collected data
    updates_from_llm = result.get("collected_data_update") or {}
    if isinstance(updates_from_llm, dict):
        for key, value in updates_from_llm.items():
            if key == "address" and isinstance(value, dict):
                addr = dict(collected.get("address") or {})
                addr.update(value)
                collected["address"] = addr
            else:
                collected[key] = value

    _save_msg(state["lead_id"], "agent", msg, "data_collection")
    return {
        "messages": _append(state, msg),
        "current_state": next_state,
        "collected_data": collected,
    }


async def node_upsell(state: ConversationState) -> dict:
    """
    Two-phase upsell node:
      Phase 1 (upsell_attempted=False): present the upsell offer, stay in 'upsell'.
      Phase 2 (upsell_attempted=True):  read yes/no, transition to 'order_creation'.
    """
    if not state.get("upsell_attempted"):
        # Phase 1: present offer
        result = await _llm_json(
            prompts.upsell_offer_prompt(),
            _build_lc_messages(state, max_history=4),
        )
        msg = result.get("message", "Prima di procedere, ho una proposta speciale per lei! 🎁")
        _save_msg(state["lead_id"], "agent", msg, "upsell")
        return {
            "messages": _append(state, msg),
            "current_state": "upsell",
            "upsell_attempted": True,
        }
    else:
        # Phase 2: read response
        result = await _llm_json(
            prompts.upsell_response_prompt(),
            _build_lc_messages(state, max_history=4),
        )
        msg = result.get("message", "Capito! Procedo con l'ordine.")
        upsell_accepted = bool(result.get("upsell_accepted", False))
        _save_msg(state["lead_id"], "agent", msg, "upsell")
        return {
            "messages": _append(state, msg),
            "current_state": "order_creation",
            "upsell_accepted": upsell_accepted,
        }


async def node_order_creation(state: ConversationState) -> dict:
    """Create the order in Supabase and generate a confirmation message."""
    collected = state.get("collected_data", {})
    addr = collected.get("address", {})
    order_summary = "Ordine in elaborazione"

    try:
        from app.tools.supabase_tools import create_order, update_lead_status, get_product

        product = _get_product(state["product_id"])
        unit_price = float(product.get("price", 0))
        offer_id = collected.get("selected_offer_id") or None

        order = create_order(
            lead_id=state["lead_id"],
            product_id=state["product_id"],
            offer_id=offer_id,
            unit_price=unit_price,
            quantity=1,
            shipping_address=addr.get("street", ""),
            shipping_city=addr.get("city", ""),
            shipping_zip=addr.get("cap", ""),
            notes=(
                f"Nome: {collected.get('name', '')} | "
                f"Provincia: {addr.get('provincia', '')} | "
                f"Upsell: {state.get('upsell_accepted', False)}"
            ),
        )
        order_id_short = str(order.get("id", ""))[:8]
        order_summary = (
            f"Ordine #{order_id_short}… — {product.get('name', 'Prodotto')} "
            f"€{unit_price:.2f} — Spedizione: {addr.get('city', '')} "
            f"({addr.get('cap', '')}) — Pagamento COD"
        )
        update_lead_status(state["lead_id"], "converted")

    except Exception as exc:
        logger.error("Error creating order: %s", exc, exc_info=True)
        order_summary = "Ordine registrato nel sistema"

    result = await _llm_json(
        prompts.order_confirmation_prompt(order_summary),
        [],
    )
    msg = result.get("message", "Perfetto! Il suo ordine è stato registrato. Grazie mille! 🎉")

    _save_msg(state["lead_id"], "agent", msg, "order_creation")
    return {
        "messages": _append(state, msg),
        "current_state": "handoff",
    }


async def node_handoff(state: ConversationState) -> dict:
    """Notify operator via Telegram and close the conversation."""
    result = await _llm_json(prompts.handoff_prompt(), [])
    msg = result.get(
        "message",
        "Un nostro consulente la ricontatterà entro oggi (lun-ven 9-18) per confermare. Grazie! 😊",
    )

    _save_msg(state["lead_id"], "agent", msg, "handoff")

    # Telegram notification (non-blocking failure)
    try:
        from app.services.telegram import notify_new_order
        await notify_new_order(state)
    except Exception as exc:
        logger.warning("Telegram notify failed: %s", exc)

    return {
        "messages": _append(state, msg),
        "current_state": "completed",
    }
