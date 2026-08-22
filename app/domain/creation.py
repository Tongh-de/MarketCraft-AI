from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


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
