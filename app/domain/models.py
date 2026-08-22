from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator


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
    copies: list[PlatformCopy]
    poster_prompt: str
    quality_score: int = Field(ge=0, le=100)
    quality_issues: list[QualityIssue] = Field(default_factory=list)
    status: str
    trace: list[str]

