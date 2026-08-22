import json
from abc import ABC, abstractmethod

from openai import OpenAI
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.domain.models import CampaignRequest, Platform, PlatformCopy


class _SellingPointOutput(BaseModel):
    selling_points: list[str] = Field(min_length=1, max_length=5)


class _PlatformCopyOutput(BaseModel):
    copies: list[PlatformCopy]


class ContentGenerator(ABC):
    @abstractmethod
    def extract_selling_points(self, request: CampaignRequest) -> list[str]: ...

    @abstractmethod
    def generate_platform_copies(
        self,
        request: CampaignRequest,
        selling_points: list[str],
        brand_context: list[str],
    ) -> list[PlatformCopy]: ...

    @abstractmethod
    def generate_poster_prompt(
        self, request: CampaignRequest, selling_points: list[str]
    ) -> str: ...


class MockContentGenerator(ContentGenerator):
    """Deterministic provider used for local demos and automated tests."""

    def extract_selling_points(self, request: CampaignRequest) -> list[str]:
        product = request.product
        points = [f"面向{product.target_audience}的{product.category}解决方案"]
        points.extend(f"{key}：{value}" for key, value in list(product.attributes.items())[:4])
        if product.price:
            points.append(f"参考售价 {product.price:.2f} 元")
        return points[:5]

    def generate_platform_copies(
        self,
        request: CampaignRequest,
        selling_points: list[str],
        brand_context: list[str],
    ) -> list[PlatformCopy]:
        product = request.product
        first_point = selling_points[0]
        copies: list[PlatformCopy] = []
        for platform in request.platforms:
            if platform == Platform.XIAOHONGSHU:
                title = f"发现一个提升体验的好物｜{product.name}"
                body = f"最近在{request.objective}场景试了{product.name}。{first_point}。" \
                    f"更重要的是：{'；'.join(selling_points[1:4])}。"
                hashtags = [f"#{product.category}", "#好物分享", "#新品体验"]
                cta = "先收藏，再根据自己的使用场景选择。"
            elif platform == Platform.DOUYIN:
                title = f"30秒看懂{product.name}"
                body = f"如果你正在找{product.category}，先看这三点：{'；'.join(selling_points[:3])}。"
                hashtags = [f"#{product.category}", "#产品测评", "#实用好物"]
                cta = "点击了解详细参数。"
            else:
                title = f"{product.name}｜{selling_points[0]}"
                body = "；".join(selling_points)
                hashtags = [f"#{product.category}", "#官方正品"]
                cta = "查看商品详情并按需选购。"
            copies.append(
                PlatformCopy(
                    platform=platform,
                    title=title,
                    body=body,
                    hashtags=hashtags,
                    call_to_action=cta,
                )
            )
        return copies

    def generate_poster_prompt(
        self, request: CampaignRequest, selling_points: list[str]
    ) -> str:
        product = request.product
        return (
            f"电商营销海报，主体为{product.name}，{product.category}品类，"
            f"面向{product.target_audience}，视觉语气为{request.tone.value}，"
            f"突出卖点：{'、'.join(selling_points[:3])}；干净背景，主体清晰，"
            "保留标题与价格信息的安全排版区域，无水印，无虚构商品细节。"
        )


class OpenAIContentGenerator(ContentGenerator):
    """Production provider using schema-constrained Responses API outputs."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when GENERATION_MODE=openai")
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
        )

    def extract_selling_points(self, request: CampaignRequest) -> list[str]:
        response = self.client.responses.parse(
            model=self.settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "你是电商商品策略师。只根据输入事实提取1到5条可验证卖点，"
                        "禁止补充商品输入中不存在的功效、参数或承诺。"
                    ),
                },
                {
                    "role": "user",
                    "content": request.product.model_dump_json(exclude={"image_urls"}),
                },
            ],
            text_format=_SellingPointOutput,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("model returned no structured selling-point output")
        return parsed.selling_points

    def generate_platform_copies(
        self,
        request: CampaignRequest,
        selling_points: list[str],
        brand_context: list[str],
    ) -> list[PlatformCopy]:
        payload = {
            "request": request.model_dump(mode="json"),
            "selling_points": selling_points,
            "brand_context": brand_context,
        }
        response = self.client.responses.parse(
            model=self.settings.openai_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "你是电商内容运营。为每个指定平台各生成一条文案。"
                        "必须遵守品牌规则，卖点只能来自输入，避免绝对化和虚假宣传。"
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            text_format=_PlatformCopyOutput,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("model returned no structured platform-copy output")
        expected = set(request.platforms)
        actual = {copy.platform for copy in parsed.copies}
        if actual != expected:
            raise RuntimeError("model output does not cover exactly the requested platforms")
        return parsed.copies

    def generate_poster_prompt(
        self, request: CampaignRequest, selling_points: list[str]
    ) -> str:
        product = request.product
        return (
            f"Create a polished e-commerce product poster for {product.name}. "
            f"Category: {product.category}. Audience: {product.target_audience}. "
            f"Tone: {request.tone.value}. Verified selling points: "
            f"{' | '.join(selling_points[:3])}. Keep the product visually accurate, "
            "use a clean commercial composition, reserve safe areas for editable title and price, "
            "and do not invent logos, certificates, parameters, or product features."
        )


def get_generator() -> ContentGenerator:
    settings = get_settings()
    if settings.generation_mode == "openai":
        return OpenAIContentGenerator(settings)
    return MockContentGenerator()
