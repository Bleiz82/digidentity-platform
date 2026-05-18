import os

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from digidentity_api.api.conversations import router as conversations_router
from digidentity_api.api.leads import router as leads_router
from digidentity_api.api.rendering import router as rendering_router

log = structlog.get_logger()

app = FastAPI(
    title="DigIdentity API",
    version="0.1.0",
    description="DigIdentity Living Site — Core API",
)

# CORS — Phase 2 dev configuration
# Phase 3: set allow_credentials=True + restrict to auth-carrying origins only
_cors_origins_raw = os.getenv(
    "DIGIDENTITY_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
allowed_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Tenant-Id", "Accept"],
    expose_headers=["X-Request-Id"],
    max_age=600,
)

app.include_router(conversations_router, prefix="/api/v1")
app.include_router(rendering_router, prefix="/api/v1")
app.include_router(leads_router, prefix="/api/v1")


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
