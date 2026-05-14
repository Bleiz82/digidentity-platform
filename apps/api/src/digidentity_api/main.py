import structlog
from fastapi import FastAPI

log = structlog.get_logger()

app = FastAPI(
    title="DigIdentity API",
    version="0.1.0",
    description="DigIdentity Living Site — Core API",
)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
