from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.creation import router as creation_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.operations import router as operations_router
from app.api.v1.posters import router as posters_router
from app.api.v1.products import router as products_router
from app.core.config import get_settings
from app.observability import prometheus_middleware

settings = get_settings()
static_dir = Path(__file__).parent / "static"
app = FastAPI(
    title=settings.app_name,
    version="0.4.0",
    description="Cross-border e-commerce content and operations Agent API",
)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.include_router(campaigns_router, prefix="/api/v1")
app.include_router(creation_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1")
app.include_router(posters_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.middleware("http")(prometheus_middleware)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(static_dir / "dashboard.html")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
