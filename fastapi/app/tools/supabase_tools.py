"""Supabase CRUD operations used by agent nodes."""

import logging
from app.config import get_supabase_client

logger = logging.getLogger(__name__)


def get_lead(lead_id: str) -> dict | None:
    """Fetch a lead by ID."""
    sb = get_supabase_client()
    result = sb.table("leads").select("*").eq("id", lead_id).single().execute()
    return result.data


def get_product(product_id: str) -> dict | None:
    """Fetch a product by ID."""
    sb = get_supabase_client()
    result = sb.table("products").select("*").eq("id", product_id).single().execute()
    return result.data


def get_product_offers(product_id: str) -> list[dict]:
    """Fetch active offers for a product, ordered by discount descending."""
    sb = get_supabase_client()
    result = (
        sb.table("offers")
        .select("*")
        .eq("product_id", product_id)
        .eq("is_active", True)
        .order("discount_value", desc=True)
        .execute()
    )
    return result.data or []


def save_conversation_message(
    lead_id: str,
    sender: str,
    content: str,
    metadata: dict | None = None,
    llm_model: str | None = None,
    langfuse_trace_id: str | None = None,
) -> dict:
    """
    Save one message to the conversations table.
    sender: 'lead' | 'agent' | 'system'
    """
    sb = get_supabase_client()
    payload = {
        "lead_id": lead_id,
        "channel": "whatsapp",
        "direction": "inbound" if sender == "lead" else "outbound",
        "message_type": "text",
        "content": content,
        "sender": sender,
        "metadata": metadata or {},
    }
    if llm_model:
        payload["llm_model"] = llm_model
    if langfuse_trace_id:
        payload["langfuse_trace_id"] = langfuse_trace_id

    result = sb.table("conversations").insert(payload).execute()
    return result.data[0] if result.data else {}


def get_conversation_history(lead_id: str, limit: int = 20) -> list[dict]:
    """Return recent messages for a lead (oldest first)."""
    sb = get_supabase_client()
    result = (
        sb.table("conversations")
        .select("sender, content, created_at")
        .eq("lead_id", lead_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return result.data or []


def create_order(
    lead_id: str,
    product_id: str,
    offer_id: str | None,
    unit_price: float,
    quantity: int,
    shipping_address: str,
    shipping_city: str,
    shipping_zip: str,
    notes: str | None = None,
) -> dict:
    """Insert a new order. Payment method is always COD for this project."""
    sb = get_supabase_client()
    payload = {
        "lead_id": lead_id,
        "product_id": product_id,
        "offer_id": offer_id,
        "status": "pending",
        "quantity": quantity,
        "unit_price": unit_price,
        "total_price": round(unit_price * quantity, 2),
        "shipping_address": shipping_address,
        "shipping_city": shipping_city,
        "shipping_zip": shipping_zip,
        "payment_method": "COD",
        "notes": notes,
    }
    result = sb.table("orders").insert(payload).execute()
    return result.data[0] if result.data else {}


def update_lead_status(lead_id: str, status: str) -> None:
    """Update lead status (e.g. 'converted', 'lost')."""
    sb = get_supabase_client()
    sb.table("leads").update({"status": status}).eq("id", lead_id).execute()
