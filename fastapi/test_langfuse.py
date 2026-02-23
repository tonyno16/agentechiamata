"""
Test script: FastAPI -> Langfuse connectivity
Run inside FastAPI container:

    docker compose exec fastapi python test_langfuse.py
"""
import os

from langfuse import get_client


def main() -> None:
    # Verifica che le chiavi ci siano (il client userebbe comunque le env)
    if not os.environ.get("LANGFUSE_PUBLIC_KEY") or not os.environ.get(
        "LANGFUSE_SECRET_KEY"
    ):
        raise SystemExit(
            "LANGFUSE_PUBLIC_KEY o LANGFUSE_SECRET_KEY non impostate nell'ambiente"
        )

    langfuse = get_client()

    print("Test: Creating Langfuse trace...")
    with langfuse.start_as_current_observation(
        as_type="span",
        name="connectivity-test",
        metadata={"test": True, "purpose": "TASK-004 connectivity verification"},
    ) as span:
        span.update(output="Connectivity test successful")

    langfuse.flush()
    print("\n=== LANGFUSE TEST PASSED ===")


if __name__ == "__main__":
    main()

