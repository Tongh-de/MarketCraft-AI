from fastapi import FastAPI

from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.posters import router as posters_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Agentic e-commerce marketing content production API",
)
app.include_router(campaigns_router, prefix="/api/v1")
app.include_router(posters_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
