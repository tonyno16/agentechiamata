from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from app.config import get_settings, get_supabase_client, get_langfuse_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"[STARTUP] {settings.app_name} v{settings.app_version}")
    print(f"[STARTUP] Supabase: {settings.supabase_url}")
    print(f"[STARTUP] Langfuse: {settings.langfuse_host}")
    yield
    # Flush Langfuse traces on shutdown
    try:
        langfuse = get_langfuse_client()
        langfuse.flush()
        print("[SHUTDOWN] Langfuse flushed.")
    except Exception:
        pass
    print("[SHUTDOWN] Done.")


app = FastAPI(
    title="Affiliate Sales AI Agent",
    description="AI Agent for affiliate sales automation via WhatsApp",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    settings = get_settings()
    health = {
        "status": "healthy",
        "service": "fastapi-agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.app_version,
        "dependencies": {},
    }

    # Check Supabase
    try:
        supabase = get_supabase_client()
        supabase.table("products").select("id").limit(1).execute()
        health["dependencies"]["supabase"] = "connected"
    except Exception as e:
        health["dependencies"]["supabase"] = f"error: {str(e)}"
        health["status"] = "degraded"

    # Check Langfuse
    try:
        get_langfuse_client()
        health["dependencies"]["langfuse"] = "configured"
    except Exception as e:
        health["dependencies"]["langfuse"] = f"error: {str(e)}"
        health["status"] = "degraded"

    return health


@app.get("/")
async def root():
    return {"message": "Affiliate Sales AI Agent API", "docs": "/docs"}
