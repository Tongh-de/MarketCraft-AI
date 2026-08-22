from app.domain.models import CampaignRequest, ProductInput
from app.workflows.campaign import run_campaign


def test_campaign_workflow_returns_traceable_package() -> None:
    request = CampaignRequest(
        product=ProductInput(
            sku="CUP-001",
            name="轻盈随行保温杯",
            category="咖啡杯",
            description="适合通勤和办公室使用，可拆洗的不锈钢保温杯。",
            attributes={"容量": "450ml", "重量": "约280g"},
            target_audience="通勤用户",
        )
    )
    result = run_campaign(request, "test-thread")
    assert result.product_sku == "CUP-001"
    assert len(result.copies) == 2
    assert result.visual_analysis.confidence == 0.35
    assert result.trace == [
        "analyze_product_visuals",
        "extract_selling_points",
        "retrieve_brand_context",
        "generate_content",
        "quality_review",
        "package_result",
    ]
