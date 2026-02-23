"""Telegram notification service for operator alerts."""

import logging
import httpx
from app.config import get_settings
from app.agents.state import ConversationState

logger = logging.getLogger(__name__)


async def notify_new_order(state: ConversationState) -> None:
    """Send a new order alert to the Telegram operator chat."""
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.info("Telegram not configured, skipping notification")
        return

    collected = state.get("collected_data", {})
    addr = collected.get("address", {})
    name = collected.get("name", "N/A")
    city = addr.get("city", "")
    cap = addr.get("cap", "")
    provincia = addr.get("provincia", "")
    offer_id_short = (collected.get("selected_offer_id") or "N/A")[:8]

    text = (
        "🛒 *NUOVO ORDINE*\n"
        f"Lead: `{state['lead_id'][:8]}...`\n"
        f"Nome: {name}\n"
        f"Indirizzo: {addr.get('street', 'N/A')}, {cap} {city} ({provincia})\n"
        f"Offerta: `{offer_id_short}...`\n"
        f"Upsell: {'✅' if state.get('upsell_accepted') else '❌'}\n"
        f"Prodotto: `{state.get('product_id', '')[:8]}...`"
    )

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )
            resp.raise_for_status()
    except Exception as e:
        logger.error(f"Telegram notification failed: {e}")
