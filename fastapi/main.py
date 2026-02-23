from fastapi import FastAPI
from datetime import datetime, timezone

app = FastAPI(
    title="Affiliate Sales AI Agent",
    description="AI Agent for affiliate sales automation",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "fastapi-agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
    }


@app.get("/")
async def root():
    return {"message": "Affiliate Sales AI Agent API", "docs": "/docs"}
