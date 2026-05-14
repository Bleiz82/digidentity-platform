import structlog
from fastapi import FastAPI

from digidentity_api.api.conversations import router as conversations_router

log = structlog.get_logger()

app = FastAPI(
    title="DigIdentity API",
    version="0.1.0",
    description="DigIdentity Living Site — Core API",
)

app.include_router(conversations_router, prefix="/api/v1")


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
