from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from app.domain.listings import ListingPlatform


class PerformanceSource(StrEnum):
    MOCK_PLATFORM_API = "mock_platform_api"
    MANUAL_DEMO = "manual_demo"


class OptimizationPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OptimizationCategory(StrEnum):
    CREATIVE = "creative"
    CONVERSION = "conversion"
    ADVERTISING = "advertising"
    INVENTORY = "inventory"
    CUSTOMER_EXPERIENCE = "customer_experience"
    GROWTH = "growth"


class PerformanceSnapshotRequest(BaseModel):
    package_id: UUID
    platform: ListingPlatform
    period_start: date
    period_end: date
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    add_to_carts: int = Field(ge=0)
    orders: int = Field(ge=0)
    units_sold: int = Field(ge=0)
    revenue: float = Field(ge=0)
    ad_spend: float = Field(ge=0)
    returns: int = Field(default=0, ge=0)
    inventory: int = Field(ge=0)
    source: PerformanceSource = PerformanceSource.MANUAL_DEMO
    actor: str = Field(default="data-operator", min_length=2, max_length=100)

    @model_validator(mode="after")
    def validate_period_and_funnel(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must not be earlier than period_start")
        if self.clicks > self.impressions:
            raise ValueError("clicks cannot exceed impressions")
        if self.add_to_carts > self.clicks:
            raise ValueError("add_to_carts cannot exceed clicks")
        if self.orders > self.add_to_carts:
            raise ValueError("orders cannot exceed add_to_carts")
        if self.units_sold < self.orders:
            raise ValueError("units_sold cannot be lower than orders")
        if self.returns > self.units_sold:
            raise ValueError("returns cannot exceed units_sold")
        return self


class PerformanceSnapshot(BaseModel):
    snapshot_id: UUID = Field(default_factory=uuid4)
    package_id: UUID
    sku: str
    platform: ListingPlatform
    external_listing_id: str
    period_start: date
    period_end: date
    impressions: int
    clicks: int
    add_to_carts: int
    orders: int
    units_sold: int
    revenue: float
    ad_spend: float
    returns: int
    inventory: int
    ctr: float = Field(ge=0)
    add_to_cart_rate: float = Field(ge=0)
    conversion_rate: float = Field(ge=0)
    roas: float = Field(ge=0)
    return_rate: float = Field(ge=0)
    source: PerformanceSource
    mock: Literal[True] = True
    captured_by: str
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DemoSnapshotRequest(BaseModel):
    actor: str = Field(default="mock-data-connector", min_length=2, max_length=100)


class PerformanceAnalysisRequest(BaseModel):
    actor: str = Field(default="performance-analyst", min_length=2, max_length=100)


class PlatformPerformanceSummary(BaseModel):
    platform: ListingPlatform
    impressions: int
    clicks: int
    orders: int
    units_sold: int
    revenue: float
    inventory: int
    ctr: float
    conversion_rate: float
    roas: float
    return_rate: float


class OptimizationRecommendation(BaseModel):
    recommendation_id: UUID = Field(default_factory=uuid4)
    platform: ListingPlatform | None = None
    category: OptimizationCategory
    priority: OptimizationPriority
    title: str
    diagnosis: str
    evidence: list[str] = Field(min_length=1)
    suggested_actions: list[str] = Field(min_length=1)
    target_metric: str
    requires_human_approval: bool = True


class PerformanceAnalysisReport(BaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    package_id: UUID
    sku: str
    product_name: str
    skill_id: str = "commerce-performance-optimization"
    snapshot_ids: list[UUID]
    summaries: list[PlatformPerformanceSummary]
    headline: str
    cross_platform_findings: list[str]
    recommendations: list[OptimizationRecommendation]
    data_quality_notes: list[str]
    trace: list[str]
    requested_by: str
    mock: Literal[True] = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
