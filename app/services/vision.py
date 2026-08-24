from abc import ABC, abstractmethod
import json
import re

from openai import BadRequestError, OpenAI

from app.core.config import Settings, get_settings
from app.domain.models import CampaignRequest, VisualAnalysis


def _parse_visual_json(content: str) -> VisualAnalysis:
    text = content.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return VisualAnalysis.model_validate_json(text)


class VisionAnalyzer(ABC):
    @abstractmethod
    def analyze(self, request: CampaignRequest) -> VisualAnalysis: ...


class MockVisionAnalyzer(VisionAnalyzer):
    def analyze(self, request: CampaignRequest) -> VisualAnalysis:
        product = request.product
        if not product.image_urls:
            return VisualAnalysis(
                scene_summary="未提供商品图片，当前仅根据结构化商品资料生成内容。",
                detected_elements=[product.name, product.category],
                visual_strengths=[],
                visual_risks=["缺少图片，无法核验商品外观、包装和视觉细节"],
                recommended_layout="使用居中主体构图，并为标题、价格和行动按钮保留安全区。",
                confidence=0.35,
            )
        return VisualAnalysis(
            scene_summary=f"已接收 {len(product.image_urls)} 张商品参考图，Mock 模式不解析像素。",
            detected_elements=[product.name, product.category],
            visual_strengths=["已提供视觉参考，可用于真实模型核验商品外观"],
            visual_risks=["Mock 模式未执行实际视觉识别"],
            recommended_layout="保持商品主体比例，使用简洁背景并避免遮挡包装文字。",
            confidence=0.5,
        )


class OpenAIVisionAnalyzer(VisionAnalyzer):
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when GENERATION_MODE=openai")
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
        )

    def analyze(self, request: CampaignRequest) -> VisualAnalysis:
        product = request.product
        if not product.image_urls:
            return MockVisionAnalyzer().analyze(request)

        content: list[dict[str, str]] = [
            {
                "type": "input_text",
                "text": (
                    "分析这些电商商品图片。识别商品主体、包装、颜色、使用场景、"
                    "可用于海报的视觉优势和潜在风险。不得推断图片中无法确认的功效。"
                ),
            }
        ]
        content.extend(
            {"type": "input_image", "image_url": str(url), "detail": "high"}
            for url in product.image_urls[:4]
        )
        response = self.client.responses.parse(
            model=self.settings.openai_model,
            input=[{"role": "user", "content": content}],
            text_format=VisualAnalysis,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("model returned no structured visual analysis")
        return parsed


class OpenAICompatibleVisionAnalyzer(VisionAnalyzer):
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when GENERATION_MODE=openai_compatible")
        if not settings.openai_base_url:
            raise ValueError("OPENAI_BASE_URL is required when GENERATION_MODE=openai_compatible")
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
        )

    def analyze(self, request: CampaignRequest) -> VisualAnalysis:
        product = request.product
        if not product.image_urls:
            return MockVisionAnalyzer().analyze(request)

        schema = VisualAnalysis.model_json_schema()
        content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": (
                    "分析这些电商商品图片。识别商品主体、包装、颜色、使用场景、"
                    "可用于海报的视觉优势和潜在风险。不得推断图片中无法确认的功效。"
                    "只返回合法 JSON，不要 Markdown。"
                    f"JSON Schema: {json.dumps(schema, ensure_ascii=False)}"
                ),
            }
        ]
        content.extend(
            {"type": "image_url", "image_url": {"url": str(url)}} for url in product.image_urls[:4]
        )
        try:
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[{"role": "user", "content": content}],
                temperature=0.2,
            )
        except BadRequestError as exc:
            if "support image" in str(exc).lower():
                return MockVisionAnalyzer().analyze(request)
            raise
        result = response.choices[0].message.content
        if not result:
            raise RuntimeError("compatible model returned no visual analysis")
        return _parse_visual_json(result)


def get_vision_analyzer() -> VisionAnalyzer:
    settings = get_settings()
    if settings.generation_mode == "openai":
        return OpenAIVisionAnalyzer(settings)
    if settings.generation_mode == "openai_compatible":
        return OpenAICompatibleVisionAnalyzer(settings)
    return MockVisionAnalyzer()
