from app.domain.models import CampaignRequest, PlatformCopy, ProductInput
from app.services.quality import QualityService


def make_request() -> CampaignRequest:
    return CampaignRequest(
        product=ProductInput(
            sku="SKU-1",
            name="测试水杯",
            category="咖啡杯",
            description="适合办公室日常使用的测试商品描述。",
            target_audience="通勤用户",
        ),
        forbidden_claims=["包治百病"],
    )


def test_forbidden_claim_reduces_quality_score() -> None:
    copies = [
        PlatformCopy(
            platform="xiaohongshu",
            title="测试商品",
            body="这是一款百分百适合所有人的产品。",
            hashtags=["#测试"],
            call_to_action="查看详情",
        )
    ]
    score, issues = QualityService().review(make_request(), copies)
    assert score == 75
    assert issues[0].rule == "prohibited_claim"

