from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_generate_campaign_endpoint() -> None:
    response = client.post(
        "/api/v1/campaigns/generate",
        json={
            "product": {
                "sku": "CUP-001",
                "name": "轻盈随行保温杯",
                "category": "咖啡杯",
                "description": "适合通勤与办公室使用的可拆洗不锈钢保温杯。",
                "attributes": {"容量": "450ml", "重量": "约280g"},
                "target_audience": "通勤用户",
                "price": 129,
            },
            "brand_id": "demo-brand",
            "platforms": ["xiaohongshu", "douyin"],
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "approved"
    assert result["quality_score"] == 100
    assert len(result["copies"]) == 2
    assert result["trace"][-1] == "package_result"

