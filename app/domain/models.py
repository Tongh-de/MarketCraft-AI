from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class Platform(StrEnum):
    TAOBAO = "taobao"
    XIAOHONGSHU = "xiaohongshu"
    DOUYIN = "douyin"
    JD = "jd"


class Tone(StrEnum):
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    PREMIUM = "premium"
    ENERGETIC = "energetic"


class ProductInput(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=10, max_length=3000)
    attributes: dict[str, str] = Field(default_factory=dict)
    target_audience: str = Field(min_length=2, max_length=300)
    price: float | None = Field(default=None, gt=0)
    image_urls: list[HttpUrl] = Field(default_factory=list, max_length=8)

    @field_validator("attributes")
    @classmethod
    def limit_attributes(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 30:
            raise ValueError("attributes cannot contain more than 30 items")
        return value


class CampaignRequest(BaseModel):
    product: ProductInput
    brand_id: str = Field(default="demo-brand", min_length=2, max_length=64)
    platforms: list[Platform] = Field(
        default_factory=lambda: [Platform.XIAOHONGSHU, Platform.DOUYIN],
        min_length=1,
    )
    tone: Tone = Tone.FRIENDLY
    objective: str = Field(default="新品种草与转化", min_length=2, max_length=200)
    forbidden_claims: list[str] = Field(default_factory=list, max_length=30)


class QualityIssue(BaseModel):
    severity: str
    rule: str
    message: str


class VisualAnalysis(BaseModel):
    scene_summary: str
    detected_elements: list[str] = Field(default_factory=list)
    visual_strengths: list[str] = Field(default_factory=list)
    visual_risks: list[str] = Field(default_factory=list)
    recommended_layout: str
    confidence: float = Field(ge=0, le=1)


class KnowledgeDocument(BaseModel):
    doc_id: str = Field(min_length=2, max_length=128)
    brand_id: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=5, max_length=8000)
    category: str = Field(default="global", min_length=2, max_length=80)
    source: str = Field(default="manual", min_length=2, max_length=300)


class RetrievedContext(BaseModel):
    doc_id: str
    title: str
    content: str
    source: str
    score: float = Field(ge=0)
    retrieval_method: str = "hybrid_rrf"


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    brand_id: str = Field(default="demo-brand", min_length=2, max_length=64)
    category: str | None = Field(default=None, max_length=80)
    limit: int = Field(default=4, ge=1, le=20)


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: list[RetrievedContext]


class PlatformCopy(BaseModel):
    platform: Platform
    title: str
    body: str
    hashtags: list[str]
    call_to_action: str


class CampaignPackage(BaseModel):
    campaign_id: UUID = Field(default_factory=uuid4)
    product_sku: str
    selling_points: list[str]
    brand_context: list[str]
    brand_citations: list[RetrievedContext]
    visual_analysis: VisualAnalysis
    copies: list[PlatformCopy]
    poster_prompt: str
    quality_score: int = Field(ge=0, le=100)
    quality_issues: list[QualityIssue] = Field(default_factory=list)
    status: str
    trace: list[str]


class PosterRequest(BaseModel):
    prompt: str = Field(min_length=10, max_length=32000)
    size: str = Field(default="1024x1024", pattern=r"^\d{2,4}x\d{2,4}$")
    quality: str = Field(default="medium", pattern=r"^(low|medium|high|auto)$")


class PosterResponse(BaseModel):
    status: str
    model: str
    mime_type: str = "image/png"
    image_base64: str | None = None
    revised_prompt: str | None = None


class ProductRecord(ProductInput):
    brand_id: str = Field(default="demo-brand", min_length=2, max_length=64)
    version: int = Field(default=1, ge=1)
    status: str = Field(default="active", pattern=r"^(active|draft|archived)$")


class ProductSearchRequest(BaseModel):
    query: str = Field(default="", max_length=300)
    category: str | None = Field(default=None, max_length=80)
    brand_id: str | None = Field(default=None, max_length=64)
    limit: int = Field(default=10, ge=1, le=100)


class ProductSearchResponse(BaseModel):
    total: int
    items: list[ProductRecord]


class LifecycleStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    PARTIAL_FAILED = "partial_failed"


class AuditEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: str
    action: str
    details: dict[str, str] = Field(default_factory=dict)


class CampaignVersion(BaseModel):
    version: int = Field(ge=1)
    copies: list[PlatformCopy]
    poster_prompt: str
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    change_note: str


class CampaignLifecycle(BaseModel):
    campaign_id: UUID
    status: LifecycleStatus
    current_version: int
    versions: list[CampaignVersion]
    requested_by: str | None = None
    reviewed_by: str | None = None
    review_reason: str | None = None
    audit_log: list[AuditEvent] = Field(default_factory=list)


class CampaignRevisionRequest(BaseModel):
    actor: str = Field(min_length=2, max_length=100)
    change_note: str = Field(min_length=2, max_length=500)
    copies: list[PlatformCopy] | None = None
    poster_prompt: str | None = Field(default=None, min_length=10, max_length=32000)

    @model_validator(mode="after")
    def require_a_change(self):
        if self.copies is None and self.poster_prompt is None:
            raise ValueError("copies or poster_prompt must be provided")
        return self


class ReviewSubmitRequest(BaseModel):
    actor: str = Field(min_length=2, max_length=100)


class ApprovalDecisionRequest(BaseModel):
    reviewer: str = Field(min_length=2, max_length=100)
    action: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if self.action == "reject" and not self.reason:
            raise ValueError("reason is required when rejecting a campaign")
        return self


class PublishRequest(BaseModel):
    actor: str = Field(min_length=2, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=128)
    platforms: list[Platform] = Field(min_length=1)


class PlatformPublicationResult(BaseModel):
    platform: Platform
    status: Literal["published", "failed"]
    external_id: str | None = None
    error: str | None = None


class PublishBatchResult(BaseModel):
    campaign_id: UUID
    version: int
    idempotency_key: str
    status: LifecycleStatus
    results: list[PlatformPublicationResult]
