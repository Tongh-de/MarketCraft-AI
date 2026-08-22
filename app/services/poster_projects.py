from datetime import UTC, datetime
from functools import lru_cache
from html import escape
from pathlib import Path
from uuid import UUID

from app.core.config import get_settings
from app.domain.creation import (
    PosterCanvasPreset,
    PosterProject,
    PosterProjectRequest,
    PosterProjectUpdate,
)
from app.plugins.registry import CreativePluginRegistry, get_creative_plugin_registry
from app.services.persistence import JsonStateStore, get_state_store
from app.skills.registry import SkillRegistry, get_skill_registry

POSTER_CANVAS_SIZES = {
    PosterCanvasPreset.AMAZON_SQUARE: (2000, 2000),
    PosterCanvasPreset.TIKTOK_VERTICAL: (1080, 1440),
    PosterCanvasPreset.XIAOHONGSHU_3_4: (1242, 1660),
    PosterCanvasPreset.INSTAGRAM_SQUARE: (1080, 1080),
}


class PosterProjectNotFoundError(Exception):
    pass


class PosterProductImageNotFoundError(Exception):
    pass


class PosterProjectService:
    def __init__(
        self,
        state_store: JsonStateStore | None = None,
        skill_registry: SkillRegistry | None = None,
        plugin_registry: CreativePluginRegistry | None = None,
        upload_dir: str | Path | None = None,
    ) -> None:
        self.state_store = state_store or get_state_store()
        self.skill_registry = skill_registry or get_skill_registry()
        self.plugin_registry = plugin_registry or get_creative_plugin_registry()
        self.upload_dir = Path(upload_dir or get_settings().upload_dir).resolve()

    def _save(self, project: PosterProject) -> None:
        self.state_store.put(
            "poster_project", str(project.project_id), project.model_dump(mode="json")
        )

    def _ensure_product_image_exists(self, image_url: str) -> None:
        filename = Path(image_url).name
        candidate = (self.upload_dir / filename).resolve()
        if candidate.parent != self.upload_dir or not candidate.is_file():
            raise PosterProductImageNotFoundError("uploaded product image was not found")

    def create(self, request: PosterProjectRequest) -> PosterProject:
        self._ensure_product_image_exists(request.product.source_image_url)
        skill = self.skill_registry.get("poster-design")
        result = skill.execute(request, self.plugin_registry)
        width, height = POSTER_CANVAS_SIZES[request.preset]
        project = PosterProject(
            plugin_id=result.plugin_id,
            product=request.product,
            title=request.title,
            subtitle=request.subtitle,
            price_text=request.price_text,
            call_to_action=request.call_to_action,
            preset=request.preset,
            canvas_width=width,
            canvas_height=height,
            style=request.style,
            brand_color=request.brand_color.upper(),
            background_color=request.background_color.upper(),
            text_color=request.text_color.upper(),
            layout=request.layout,
            generation_prompt=result.generation_prompt,
            preview_url="",
            mock=result.mock,
            trace=result.trace,
            requested_by=request.actor,
            updated_by=request.actor,
        )
        project.preview_url = f"/api/v1/poster-projects/{project.project_id}/preview.svg"
        self._save(project)
        return project

    def get(self, project_id: UUID) -> PosterProject:
        payload = self.state_store.get("poster_project", str(project_id))
        if not payload:
            raise PosterProjectNotFoundError("poster project not found")
        return PosterProject.model_validate(payload)

    def list_projects(self, limit: int = 50) -> list[PosterProject]:
        projects = [
            PosterProject.model_validate(payload)
            for payload in self.state_store.list("poster_project")
        ]
        return sorted(projects, key=lambda item: item.updated_at, reverse=True)[:limit]

    def update(self, project_id: UUID, request: PosterProjectUpdate) -> PosterProject:
        project = self.get(project_id)
        changed_fields = request.model_fields_set - {"actor"}
        for field in changed_fields:
            value = getattr(request, field)
            if value is not None:
                setattr(project, field, value)
        if request.preset:
            project.canvas_width, project.canvas_height = POSTER_CANVAS_SIZES[request.preset]
        project.brand_color = project.brand_color.upper()
        project.background_color = project.background_color.upper()
        project.text_color = project.text_color.upper()
        project.version += 1
        project.updated_by = request.actor
        project.updated_at = datetime.now(UTC)
        project.trace.append(f"design_updated:v{project.version}")
        self._save(project)
        return project

    def render_svg(self, project_id: UUID) -> str:
        project = self.get(project_id)
        width, height = project.canvas_width, project.canvas_height
        layout = project.layout
        product_width = width * layout.product_scale
        product_height = height * layout.product_scale * 0.78
        product_x = width * layout.product_x - product_width / 2
        product_y = height * layout.product_y - product_height / 2
        content_x = width * layout.content_x
        content_y = height * layout.content_y
        title_size = max(42, int(width * 0.065))
        subtitle_size = max(24, int(width * 0.025))
        price_size = max(38, int(width * 0.048))
        button_width = width * 0.24
        button_height = height * 0.045
        text_anchor = {"left": "start", "center": "middle", "right": "end"}[
            layout.text_align
        ]
        mock_badge = (
            f'<g><rect x="{width - 190}" y="36" width="150" height="52" rx="26" '
            'fill="#FFFFFF" fill-opacity=".78"/><text '
            f'x="{width - 115}" y="70" text-anchor="middle" font-size="22" '
            'font-family="sans-serif" fill="#8A5B12">MOCK</text></g>'
            if project.mock
            else ""
        )
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<defs>
  <linearGradient id="background" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{project.background_color}"/><stop offset="1" stop-color="#FFFFFF" stop-opacity=".72"/></linearGradient>
  <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="20" stdDeviation="24" flood-color="#173C2E" flood-opacity=".12"/></filter>
</defs>
<rect width="{width}" height="{height}" fill="url(#background)"/>
<circle cx="{width * 0.9}" cy="{height * 0.08}" r="{width * 0.22}" fill="{project.brand_color}" fill-opacity=".10"/>
<rect x="{width * 0.035}" y="{height * 0.03}" width="{width * 0.93}" height="{height * 0.94}" rx="{width * 0.035}" fill="#FFFFFF" fill-opacity=".16" stroke="#FFFFFF" stroke-opacity=".55"/>
<image href="{escape(project.product.source_image_url)}" x="{product_x}" y="{product_y}" width="{product_width}" height="{product_height}" preserveAspectRatio="xMidYMid meet" filter="url(#shadow)"/>
<g font-family="Inter, PingFang SC, Microsoft YaHei, sans-serif" fill="{project.text_color}" text-anchor="{text_anchor}">
  <text x="{content_x}" y="{content_y}" font-size="{title_size}" font-weight="760">{escape(project.title)}</text>
  <text x="{content_x}" y="{content_y + subtitle_size * 2}" font-size="{subtitle_size}" fill-opacity=".68">{escape(project.subtitle)}</text>
  <text x="{content_x}" y="{content_y + subtitle_size * 4.5}" font-size="{price_size}" font-weight="760" fill="{project.brand_color}">{escape(project.price_text)}</text>
</g>
<rect x="{content_x}" y="{content_y + subtitle_size * 5.5}" width="{button_width}" height="{button_height}" rx="{button_height / 2}" fill="{project.brand_color}"/>
<text x="{content_x + button_width / 2}" y="{content_y + subtitle_size * 5.5 + button_height * 0.66}" text-anchor="middle" font-family="sans-serif" font-size="{subtitle_size * 0.82}" font-weight="700" fill="#FFFFFF">{escape(project.call_to_action)}</text>
{mock_badge}
</svg>"""


@lru_cache
def get_poster_project_service() -> PosterProjectService:
    return PosterProjectService()
