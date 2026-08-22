from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.posters import router as posters_router
from app.api.v1.products import router as products_router
from app.core.config import get_settings
from app.observability import prometheus_middleware

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Agentic e-commerce marketing content production API",
)
app.include_router(campaigns_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(posters_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.middleware("http")(prometheus_middleware)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
