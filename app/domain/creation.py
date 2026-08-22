from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class CreativeAssetKind(StrEnum):
    FRONT_VIEW = "front_view"
    SIDE_VIEW = "side_view"
    BACK_VIEW = "back_view"
    DETAIL_VIEW = "detail_view"
    MODEL_TRY_ON = "model_try_on"
    POSTER = "poster"
    SHORT_VIDEO = "short_video"


class CreativeCapability(StrEnum):
    MULTI_VIEW_GENERATION = "multi_view_generation"
    VIRTUAL_TRY_ON = "virtual_try_on"
    POSTER_GENERATION = "poster_generation"
    VIDEO_GENERATION = "video_generation"
    COMPETITOR_ANALYSIS = "competitor_analysis"


class CreationTaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PluginMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"


class PluginStatus(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class CreativeProductInput(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=80)
    source_image_url: str = Field(min_length=4, max_length=2000)
    description: str = Field(default="", max_length=3000)
    target_audience: str = Field(default="通用消费者", min_length=2, max_length=300)
    brand_id: str = Field(default="demo-brand", min_length=2, max_length=64)
    reference_image_urls: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("reference_image_urls")
    @classmethod
    def validate_reference_urls(cls, value: list[str]) -> list[str]:
        if any(len(item) < 4 or len(item) > 2000 for item in value):
            raise ValueError("reference image URLs must contain 4 to 2000 characters")
        return value


class CreateCreationTaskRequest(BaseModel):
    product: CreativeProductInput
    instruction: str = Field(min_length=2, max_length=2000)
    requested_outputs: list[CreativeAssetKind] = Field(
        default_factory=lambda: [
            CreativeAssetKind.FRONT_VIEW,
            CreativeAssetKind.SIDE_VIEW,
            CreativeAssetKind.BACK_VIEW,
            CreativeAssetKind.MODEL_TRY_ON,
        ],
        min_length=1,
        max_length=12,
    )
    skill_id: str = Field(default="product-asset-generation", min_length=2, max_length=80)
    preferred_plugin_id: str | None = Field(default=None, min_length=2, max_length=80)
    actor: str = Field(default="creative-operator", min_length=2, max_length=100)

    @field_validator("requested_outputs")
    @classmethod
    def require_unique_outputs(
        cls, value: list[CreativeAssetKind]
    ) -> list[CreativeAssetKind]:
        if len(value) != len(set(value)):
            raise ValueError("requested outputs must be unique")
        return value


class GeneratedCreativeAsset(BaseModel):
    asset_id: UUID = Field(default_factory=uuid4)
    kind: CreativeAssetKind
    label: str
    url: str
    provider: str
    mock: bool
    metadata: dict[str, str] = Field(default_factory=dict)


class UploadedProductImage(BaseModel):
    upload_id: UUID = Field(default_factory=uuid4)
    original_filename: str
    content_type: str
    size_bytes: int = Field(gt=0)
    checksum_sha256: str
    url: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PluginDescriptor(BaseModel):
    plugin_id: str
    name: str
    description: str
    mode: PluginMode
    status: PluginStatus
    capabilities: list[CreativeCapability]


class SkillDescriptor(BaseModel):
    skill_id: str
    name: str
    description: str
    version: str
    required_capabilities: list[CreativeCapability]


class SkillExecutionResult(BaseModel):
    plugin_id: str
    assets: list[GeneratedCreativeAsset]
    trace: list[str]


class CreationTask(BaseModel):
    task_id: UUID = Field(default_factory=uuid4)
    status: CreationTaskStatus = CreationTaskStatus.QUEUED
    progress: int = Field(default=0, ge=0, le=100)
    skill_id: str
    plugin_id: str | None = None
    product: CreativeProductInput
    instruction: str
    requested_outputs: list[CreativeAssetKind]
    assets: list[GeneratedCreativeAsset] = Field(default_factory=list)
    requested_by: str
    error: str | None = None
    trace: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class CompetitorImageInput(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    image_url: str = Field(min_length=4, max_length=2000)


class CompetitorAnalysisRequest(BaseModel):
    product: CreativeProductInput
    competitor_images: list[CompetitorImageInput] = Field(min_length=1, max_length=8)
    instruction: str = Field(
        default="分析竞品视觉规律并生成差异化创作建议",
        min_length=2,
        max_length=2000,
    )
    preferred_plugin_id: str | None = Field(default=None, min_length=2, max_length=80)
    actor: str = Field(default="creative-strategist", min_length=2, max_length=100)


class CompetitorAnalysisDimension(BaseModel):
    dimension: str
    competitor_pattern: str
    own_product_gap: str
    recommendation: str
    confidence: float = Field(ge=0, le=1)


class DifferentiatedCreativeBrief(BaseModel):
    name: str
    visual_direction: str
    composition: str
    copy_angle: str
    differentiation: str


class CompetitorPluginResult(BaseModel):
    plugin_id: str
    summary: str
    dimensions: list[CompetitorAnalysisDimension]
    opportunities: list[str]
    creative_briefs: list[DifferentiatedCreativeBrief]
    trace: list[str]
    mock: bool


class CompetitorAnalysisReport(BaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    status: CreationTaskStatus = CreationTaskStatus.QUEUED
    skill_id: str = "competitor-visual-analysis"
    plugin_id: str | None = None
    product: CreativeProductInput
    competitor_images: list[CompetitorImageInput]
    instruction: str
    requested_by: str
    summary: str = ""
    dimensions: list[CompetitorAnalysisDimension] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    creative_briefs: list[DifferentiatedCreativeBrief] = Field(default_factory=list)
    compliance_notes: list[str] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)
    mock: bool = True
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class PosterCanvasPreset(StrEnum):
    AMAZON_SQUARE = "amazon_square"
    TIKTOK_VERTICAL = "tiktok_vertical"
    XIAOHONGSHU_3_4 = "xiaohongshu_3_4"
    INSTAGRAM_SQUARE = "instagram_square"


class PosterVisualStyle(StrEnum):
    CLEAN = "clean"
    PREMIUM = "premium"
    ENERGETIC = "energetic"
    LIFESTYLE = "lifestyle"


class PosterLayout(BaseModel):
    product_x: float = Field(default=0.7, ge=0.15, le=0.85)
    product_y: float = Field(default=0.58, ge=0.2, le=0.85)
    product_scale: float = Field(default=0.58, ge=0.25, le=0.9)
    content_x: float = Field(default=0.08, ge=0.03, le=0.7)
    content_y: float = Field(default=0.16, ge=0.05, le=0.75)
    text_align: str = Field(default="left", pattern=r"^(left|center|right)$")


class PosterProjectRequest(BaseModel):
    product: CreativeProductInput
    title: str = Field(min_length=2, max_length=80)
    subtitle: str = Field(default="", max_length=160)
    price_text: str = Field(default="", max_length=40)
    call_to_action: str = Field(default="立即查看", min_length=2, max_length=30)
    preset: PosterCanvasPreset = PosterCanvasPreset.XIAOHONGSHU_3_4
    style: PosterVisualStyle = PosterVisualStyle.CLEAN
    brand_color: str = Field(default="#176044", pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str = Field(default="#F3F0E8", pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str = Field(default="#17211B", pattern=r"^#[0-9A-Fa-f]{6}$")
    layout: PosterLayout = Field(default_factory=PosterLayout)
    preferred_plugin_id: str | None = Field(default=None, min_length=2, max_length=80)
    actor: str = Field(default="poster-designer", min_length=2, max_length=100)

    @model_validator(mode="after")
    def require_uploaded_product_image(self):
        if not self.product.source_image_url.startswith("/uploads/"):
            raise ValueError("poster projects require a product image from the upload API")
        return self


class PosterProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=80)
    subtitle: str | None = Field(default=None, max_length=160)
    price_text: str | None = Field(default=None, max_length=40)
    call_to_action: str | None = Field(default=None, min_length=2, max_length=30)
    preset: PosterCanvasPreset | None = None
    style: PosterVisualStyle | None = None
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    layout: PosterLayout | None = None
    actor: str = Field(default="poster-designer", min_length=2, max_length=100)

    @model_validator(mode="after")
    def require_design_change(self):
        changed = self.model_dump(exclude={"actor"}, exclude_none=True)
        if not changed:
            raise ValueError("at least one poster design field must be provided")
        return self


class PosterSkillResult(BaseModel):
    plugin_id: str
    generation_prompt: str
    trace: list[str]
    mock: bool


class PosterProject(BaseModel):
    project_id: UUID = Field(default_factory=uuid4)
    status: str = Field(default="draft", pattern=r"^(draft|approved)$")
    version: int = Field(default=1, ge=1)
    skill_id: str = "poster-design"
    plugin_id: str
    product: CreativeProductInput
    title: str
    subtitle: str
    price_text: str
    call_to_action: str
    preset: PosterCanvasPreset
    canvas_width: int = Field(gt=0)
    canvas_height: int = Field(gt=0)
    style: PosterVisualStyle
    brand_color: str
    background_color: str
    text_color: str
    layout: PosterLayout
    generation_prompt: str
    preview_url: str
    mock: bool
    trace: list[str] = Field(default_factory=list)
    requested_by: str
    updated_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
