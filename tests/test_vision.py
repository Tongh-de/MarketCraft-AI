from app.domain.models import CampaignRequest, ProductInput
from app.services.vision import MockVisionAnalyzer


def test_missing_image_produces_explicit_visual_risk() -> None:
    request = CampaignRequest(
        product=ProductInput(
            sku="SKU-1",
            name="测试商品",
            category="咖啡杯",
            description="用于测试无图片情况下视觉分析的商品说明。",
            target_audience="通勤用户",
        )
    )
    result = MockVisionAnalyzer().analyze(request)
    assert result.confidence == 0.35
    assert "缺少图片" in result.visual_risks[0]
