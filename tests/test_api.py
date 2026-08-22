from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_and_static_assets_are_served() -> None:
    root = client.get("/", follow_redirects=False)
    dashboard = client.get("/dashboard")
    stylesheet = client.get("/static/dashboard.css")
    script = client.get("/static/dashboard.js")
    assert root.status_code == 307
    assert root.headers["location"] == "/dashboard"
    assert dashboard.status_code == 200
    assert "跨境电商运营中心" in dashboard.text
    assert stylesheet.status_code == 200
    assert script.status_code == 200


def test_creation_studio_and_assets_are_served() -> None:
    studio = client.get("/studio")
    stylesheet = client.get("/static/studio.css")
    script = client.get("/static/studio.js")

    assert studio.status_code == 200
    assert "AI 商品上架工作台" in studio.text
    assert "商品素材生成 Skill" in studio.text
    assert stylesheet.status_code == 200
    assert script.status_code == 200


def test_competitor_analysis_studio_is_served() -> None:
    page = client.get("/competitors")
    stylesheet = client.get("/static/competitors.css")
    script = client.get("/static/competitors.js")

    assert page.status_code == 200
    assert "竞品视觉分析工作台" in page.text
    assert "不直接复制竞品素材" in page.text
    assert stylesheet.status_code == 200
    assert script.status_code == 200


def test_editable_poster_studio_is_served() -> None:
    page = client.get("/poster-editor")
    stylesheet = client.get("/static/poster_editor.css")
    script = client.get("/static/poster_editor.js")

    assert page.status_code == 200
    assert "AI 商品海报工作台" in page.text
    assert "可编辑图层" in page.text
    assert stylesheet.status_code == 200
    assert script.status_code == 200


def test_prometheus_metrics_endpoint() -> None:
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "marketcraft_http_requests_total" in response.text
    assert "marketcraft_http_request_duration_seconds" in response.text


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
    assert result["brand_citations"]
    assert result["visual_analysis"]["confidence"] == 0.35
    assert result["trace"][-1] == "package_result"
    lifecycle = client.get(f"/api/v1/campaigns/{result['campaign_id']}")
    assert lifecycle.status_code == 200
    assert lifecycle.json()["status"] == "draft"
    assert lifecycle.json()["current_version"] == 1


def test_mock_poster_endpoint_is_keyless() -> None:
    response = client.post(
        "/api/v1/posters/generate",
        json={
            "prompt": "干净的电商保温杯商品海报，居中构图并保留标题安全区。",
            "size": "1024x1024",
            "quality": "medium",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "mock"
    assert response.json()["image_base64"] is None


def test_knowledge_search_endpoint_returns_traceable_sources() -> None:
    response = client.post(
        "/api/v1/knowledge/search",
        json={
            "query": "咖啡杯容量和材质怎么宣传",
            "brand_id": "demo-brand",
            "category": "咖啡杯",
            "limit": 3,
        },
    )
    assert response.status_code == 200
    assert response.json()["results"]
    assert response.json()["results"][0]["source"]


def test_product_catalog_api_versions_updates() -> None:
    payload = {
        "sku": "API-CUP-001",
        "name": "接口测试保温杯",
        "category": "咖啡杯",
        "description": "用于验证商品目录接口新增、更新和搜索行为。",
        "attributes": {"容量": "400ml"},
        "target_audience": "办公室用户",
        "brand_id": "demo-brand",
    }
    created = client.put("/api/v1/products/API-CUP-001", json=payload)
    updated = client.put(
        "/api/v1/products/API-CUP-001", json={**payload, "price": 99}
    )
    searched = client.post(
        "/api/v1/products/search/query", json={"query": "办公室 保温杯"}
    )
    assert created.status_code == 200
    assert created.json()["version"] == 1
    assert updated.json()["version"] == 2
    assert searched.json()["items"][0]["sku"] == "API-CUP-001"


def test_order_inventory_review_and_fulfillment_api() -> None:
    inventory = client.put(
        "/api/v1/operations/inventory/API-OPS-001",
        json={
            "sku": "API-OPS-001",
            "warehouse": "US-WEST",
            "available": 8,
            "reserved": 0,
            "reorder_point": 2,
        },
    )
    assert inventory.status_code == 200

    processed = client.post(
        "/api/v1/operations/orders/process",
        json={
            "order": {
                "order_id": "AMZ-API-ORDER-001",
                "channel": "amazon",
                "buyer_region": "US",
                "lines": [{"sku": "API-OPS-001", "quantity": 2}],
            },
            "actor": "operations-agent",
            "idempotency_key": "process-amz-api-order-001",
        },
    )
    assert processed.status_code == 200
    run = processed.json()
    assert run["status"] == "pending_review"
    assert run["recommended_action"] == "fulfill_order"
    assert run["notification_id"].startswith("mock-feishu-review-")

    self_review = client.post(
        f"/api/v1/operations/runs/{run['run_id']}/decision",
        json={"reviewer": "operations-agent", "action": "approve"},
    )
    assert self_review.status_code == 409

    approved = client.post(
        f"/api/v1/operations/runs/{run['run_id']}/decision",
        json={"reviewer": "reviewer-b", "action": "approve"},
    )
    executed = client.post(
        f"/api/v1/operations/runs/{run['run_id']}/execute",
        json={"actor": "executor-c"},
    )
    assert approved.status_code == 200
    assert executed.status_code == 200
    assert executed.json()["status"] == "completed"
    assert all(item["mock"] for item in executed.json()["execution_results"])

    stock = client.get("/api/v1/operations/inventory/API-OPS-001")
    assert stock.json()["available"] == 6
