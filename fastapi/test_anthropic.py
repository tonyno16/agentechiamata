"""
Test script: FastAPI -> Anthropic connectivity
Run inside FastAPI container:

    docker compose exec fastapi python test_anthropic.py

Uses the Models API to pick the first available model (Claude 4.x, 3.x, etc.).
"""

import os

import anthropic

# Fallback model IDs if listing fails (Claude 4.x → 3.x)
FALLBACK_MODELS = [
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
]


def get_models_to_try(client: anthropic.Anthropic) -> list[str]:
    """Return list of model IDs to try: from API list first, else fallbacks."""
    try:
        resp = client.models.list(limit=50)
        if resp.data:
            ids = [m.id for m in resp.data]
            print(f"  Available models (first): {ids[0]}")
            return ids
    except Exception as e:
        print(f"  (models.list failed: {e}, using fallback list)")
    return FALLBACK_MODELS


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY non impostata nell'ambiente")

    client = anthropic.Anthropic(api_key=api_key)

    print("Test: Listing available Claude models...")
    models_to_try = get_models_to_try(client)

    print("Test: Sending prompt to Claude...")
    message = None
    for model_id in models_to_try:
        try:
            message = client.messages.create(
                model=model_id,
                max_tokens=100,
                messages=[
                    {
                        "role": "user",
                        "content": "Rispondi con esattamente una parola: 'connesso'",
                    }
                ],
            )
            print(f"  Using model: {model_id}")
            break
        except anthropic.NotFoundError:
            continue
    if message is None:
        raise SystemExit("Nessun modello Claude disponibile per questa API key.")

    response_text = message.content[0].text
    print(f"  Response: {response_text}")
    print(
        f"  Tokens used: {message.usage.input_tokens} input, {message.usage.output_tokens} output"
    )
    print("\n=== ANTHROPIC TEST PASSED ===")


if __name__ == "__main__":
    main()
