from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.domain.models import AuditEvent


class WechatMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"


class WechatDraftStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUBMITTED = "submitted"
    PUBLISHED = "published"
    FAILED = "failed"


class WechatArticle(BaseModel):
    title: str = Field(min_length=1, max_length=64)
    author: str = Field(default="MarketCraft AI", max_length=64)
    digest: str = Field(default="", max_length=120)
    content: str = Field(min_length=1, max_length=100_000)
    content_source_url: HttpUrl | None = None
    thumb_media_id: str = Field(min_length=3, max_length=256)
    show_cover_pic: Literal[0, 1] = 1
    need_open_comment: Literal[0, 1] = 0
    only_fans_can_comment: Literal[0, 1] = 0


class WechatDraftCreateRequest(BaseModel):
    articles: list[WechatArticle] = Field(min_length=1, max_length=8)
    actor: str = Field(default="content-editor", min_length=2, max_length=100)


class WechatReviewRequest(BaseModel):
    reviewer: str = Field(min_length=2, max_length=100)
    action: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if self.action == "reject" and not self.reason:
            raise ValueError("reason is required when rejecting a draft")
        return self


class WechatPublishRequest(BaseModel):
    actor: str = Field(default="publisher", min_length=2, max_length=100)


class WechatMaterialUploadResult(BaseModel):
    media_id: str
    url: str | None = None
    mode: WechatMode
    mock: bool


class WechatDraftRecord(BaseModel):
    draft_id: UUID = Field(default_factory=uuid4)
    external_media_id: str
    articles: list[WechatArticle]
    mode: WechatMode
    status: WechatDraftStatus = WechatDraftStatus.DRAFT
    created_by: str
    reviewed_by: str | None = None
    review_reason: str | None = None
    publish_id: str | None = None
    last_error: str | None = None
    audit_log: list[AuditEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WechatPublicationStatus(BaseModel):
    publish_id: str
    publish_status: int | None = None
    status: str
    article_id: str | None = None
    article_detail: dict | None = None
    fail_idx: list[int] = Field(default_factory=list)
    mode: WechatMode
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WechatConfigurationStatus(BaseModel):
    mode: WechatMode
    configured: bool
    app_id_loaded: bool
    app_secret_loaded: bool
    api_base: str
    message: str

