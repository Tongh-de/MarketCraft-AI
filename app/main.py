from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.creation import router as creation_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.listings import router as listings_router
from app.api.v1.operations import router as operations_router
from app.api.v1.performance import router as performance_router
from app.api.v1.platform_extensions import router as platform_extensions_router
from app.api.v1.poster_projects import router as poster_projects_router
from app.api.v1.posters import router as posters_router
from app.api.v1.products import router as products_router
from app.api.v1.wechat import router as wechat_router
from app.core.config import get_settings
from app.observability import prometheus_middleware
from app.telemetry import configure_langsmith

configure_langsmith()
settings = get_settings()
static_dir = Path(__file__).parent / "static"
upload_dir = Path(settings.upload_dir).resolve()
upload_dir.mkdir(parents=True, exist_ok=True)
app = FastAPI(
    title=settings.app_name,
    version="0.11.0",
    description="Cross-border e-commerce content and operations Agent API",
)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")
app.include_router(campaigns_router, prefix="/api/v1")
app.include_router(creation_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(listings_router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1")
app.include_router(performance_router, prefix="/api/v1")
app.include_router(platform_extensions_router, prefix="/api/v1")
app.include_router(posters_router, prefix="/api/v1")
app.include_router(poster_projects_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(wechat_router, prefix="/api/v1")
app.middleware("http")(prometheus_middleware)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/app")


@app.get("/app", include_in_schema=False)
def unified_app() -> FileResponse:
    return FileResponse(static_dir / "app_shell.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(static_dir / "dashboard.html")


@app.get("/studio", include_in_schema=False)
def studio() -> FileResponse:
    return FileResponse(static_dir / "studio.html")


@app.get("/campaign-studio", include_in_schema=False)
def campaign_studio() -> FileResponse:
    return FileResponse(static_dir / "campaign_studio.html")


@app.get("/competitors", include_in_schema=False)
def competitors() -> FileResponse:
    return FileResponse(static_dir / "competitors.html")


@app.get("/poster-editor", include_in_schema=False)
def poster_editor() -> FileResponse:
    return FileResponse(static_dir / "poster_editor.html")


@app.get("/image-studio", include_in_schema=False)
def image_studio() -> FileResponse:
    return FileResponse(static_dir / "image_studio.html")


@app.get("/listing-workbench", include_in_schema=False)
def listing_workbench() -> FileResponse:
    return FileResponse(static_dir / "listing_workbench.html")


@app.get("/performance-insights", include_in_schema=False)
def performance_insights() -> FileResponse:
    return FileResponse(static_dir / "performance_insights.html")


@app.get("/wechat-publisher", include_in_schema=False)
def wechat_publisher() -> FileResponse:
    return FileResponse(static_dir / "wechat_publisher.html")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
