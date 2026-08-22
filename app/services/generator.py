from abc import ABC, abstractmethod

from app.domain.models import CampaignRequest, Platform, PlatformCopy


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


def get_generator() -> ContentGenerator:
    # Phase 2 introduces a production LLM provider behind the same interface.
    return MockContentGenerator()

