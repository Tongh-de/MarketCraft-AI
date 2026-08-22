from html import escape
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.domain.creation import (
    CreateCreationTaskRequest,
    CreationTask,
    PluginDescriptor,
    SkillDescriptor,
)
from app.plugins.registry import get_creative_plugin_registry
from app.services.creation_tasks import (
    CreationTaskNotFoundError,
    get_creation_task_service,
)
from app.skills.registry import get_skill_registry

router = APIRouter(prefix="/creation", tags=["AI product creation"])


@router.get("/plugins", response_model=list[PluginDescriptor])
def list_creative_plugins() -> list[PluginDescriptor]:
    return get_creative_plugin_registry().list_descriptors()


@router.get("/skills", response_model=list[SkillDescriptor])
def list_creative_skills() -> list[SkillDescriptor]:
    return get_skill_registry().list_descriptors()


@router.post("/tasks", response_model=CreationTask, status_code=status.HTTP_201_CREATED)
def create_creation_task(request: CreateCreationTaskRequest) -> CreationTask:
    return get_creation_task_service().create(request)


@router.get("/tasks", response_model=list[CreationTask])
def list_creation_tasks(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[CreationTask]:
    return get_creation_task_service().list_tasks(limit)


@router.get("/tasks/{task_id}", response_model=CreationTask)
def get_creation_task(task_id: UUID) -> CreationTask:
    try:
        return get_creation_task_service().get(task_id)
    except CreationTaskNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error


@router.get("/mock-assets/{asset_name}.svg", include_in_schema=False)
def render_mock_asset(asset_name: str) -> Response:
    kind = asset_name.rsplit("-", maxsplit=1)[-1]
    labels = {
        "front_view": "商品正面图",
        "side_view": "商品侧面图",
        "back_view": "商品背面图",
        "detail_view": "商品细节图",
        "model_try_on": "模特试穿图",
        "poster": "商品营销海报",
        "short_video": "15秒商品视频",
    }
    label = escape(labels.get(kind, "AI 商品素材"))
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800">
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
<stop stop-color="#ecfdf5"/><stop offset="1" stop-color="#f5f3ff"/>
</linearGradient></defs>
<rect width="800" height="800" rx="36" fill="url(#bg)"/>
<rect x="170" y="130" width="460" height="480" rx="32" fill="#ffffff" stroke="#a7f3d0"/>
<path d="M310 275h180l76 92-74 58-22-34v160H330V391l-22 34-74-58z" fill="#d6c2a8"/>
<text x="400" y="680" text-anchor="middle" font-family="sans-serif" font-size="34" fill="#064e3b">{label}</text>
<text x="400" y="725" text-anchor="middle" font-family="sans-serif" font-size="22" fill="#64748b">MOCK · 等待真实生成插件</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")
