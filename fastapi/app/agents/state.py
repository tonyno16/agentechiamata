from typing import TypedDict, Literal


class ConversationState(TypedDict):
    conversation_id: str
    lead_id: str
    product_id: str
    current_state: Literal[
        "welcome",
        "discovery",
        "offers",
        "objections",
        "data_collection",
        "upsell",
        "order_creation",
        "handoff",
        "completed",
        "abandoned",
    ]
    # [{role, content, timestamp, state}]
    messages: list
    # {name, phone_confirm, address: {street, city, cap, provincia}, selected_offer_id, upsell_product_id}
    collected_data: dict
    # [{type, message, attempt, resolved}]
    objections: list
    upsell_attempted: bool
    upsell_accepted: bool
    language_verified: bool
    sentiment: Literal["positive", "neutral", "negative"]
