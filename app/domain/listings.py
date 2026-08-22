from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.models import AuditEvent


class ListingPlatform(StrEnum):
    AMAZON = "amazon"
    TIKTOK_SHOP = "tiktok_shop"
    SHOPIFY = "shopify"


class ListingStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    PARTIAL_FAILED = "partial_failed"


class ListingProductDetails(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=10, max_length=3000)
    attributes: dict[str, str] = Field(default_factory=dict)
    price: float = Field(gt=0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    inventory: int = Field(ge=0, le=10_000_000)

    @field_validator("attributes")
    @classmethod
    def limit_attributes(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 30:
            raise ValueError("attributes cannot contain more than 30 items")
        return value


class ListingPackageRequest(BaseModel):
    creation_task_id: UUID
    poster_project_id: UUID | None = None
    product: ListingProductDetails
    platforms: list[ListingPlatform] = Field(min_length=1, max_length=3)
    actor: str = Field(default="listing-operator", min_length=2, max_length=100)

    @field_validator("platforms")
    @classmethod
    def require_unique_platforms(
        cls, value: list[ListingPlatform]
    ) -> list[ListingPlatform]:
        if len(value) != len(set(value)):
            raise ValueError("listing platforms must be unique")
        return value


class ListingAsset(BaseModel):
    asset_type: str
    label: str
    url: str
    source: Literal["creation_task", "poster_project"]
    mock: bool


class PlatformListingDraft(BaseModel):
    platform: ListingPlatform
    title: str
    description: str
    bullet_points: list[str]
    tags: list[str]
    category: str
    price: float
    currency: str
    inventory: int
    asset_urls: list[str]


class ListingSkillResult(BaseModel):
    drafts: list[PlatformListingDraft]
    trace: list[str]


class ListingPublicationResult(BaseModel):
    platform: ListingPlatform
    status: Literal["published", "failed"]
    external_id: str | None = None
    error: str | None = None
    mock: bool = True


class ProductListingPackage(BaseModel):
    package_id: UUID = Field(default_factory=uuid4)
    status: ListingStatus = ListingStatus.DRAFT
    version: int = Field(default=1, ge=1)
    skill_id: str = "product-listing-package"
    creation_task_id: UUID
    poster_project_id: UUID | None = None
    product: ListingProductDetails
    platforms: list[ListingPlatform]
    assets: list[ListingAsset]
    drafts: list[PlatformListingDraft]
    requested_by: str
    reviewed_by: str | None = None
    review_reason: str | None = None
    publication_results: list[ListingPublicationResult] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)
    audit_log: list[AuditEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ListingReviewRequest(BaseModel):
    actor: str = Field(min_length=2, max_length=100)


class ListingDecisionRequest(BaseModel):
    reviewer: str = Field(min_length=2, max_length=100)
    action: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if self.action == "reject" and not self.reason:
            raise ValueError("reason is required when rejecting a listing package")
        return self


class ListingPublishRequest(BaseModel):
    actor: str = Field(min_length=2, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ListingPublishBatchResult(BaseModel):
    package_id: UUID
    version: int
    idempotency_key: str
    status: ListingStatus
    results: list[ListingPublicationResult]
