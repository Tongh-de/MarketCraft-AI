from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_published_listing() -> dict:
    task_response = client.post(
        "/api/v1/creation/tasks",
        json={
            "product": {
                "sku": "PERF-JACKET-001",
                "name": "轻盈城市机能夹克",
                "category": "女装外套",
                "source_image_url": "https://example.com/performance-jacket.png",
                "description": "轻量防泼水面料与简约廓形，适合通勤和旅行。",
                "target_audience": "城市通勤女性",
            },
            "instruction": "生成多角度图片与模特试穿图。",
            "requested_outputs": ["front_view", "side_view", "model_try_on"],
            "preferred_plugin_id": "comfyui.mock",
            "actor": "performance-test",
        },
    )
    assert task_response.status_code == 201
    task = task_response.json()

    package_response = client.post(
        "/api/v1/listing-packages",
        json={
            "creation_task_id": task["task_id"],
            "product": {
                "sku": "PERF-JACKET-001",
                "name": "轻盈城市机能夹克",
                "category": "女装外套",
                "description": "轻量防泼水面料与简约廓形，适合通勤和旅行场景。",
                "attributes": {"材质": "轻量防泼水", "颜色": "燕麦米"},
                "price": 69,
                "currency": "USD",
                "inventory": 200,
            },
            "platforms": ["amazon", "tiktok_shop", "shopify"],
            "actor": "listing-operator",
        },
    )
    assert package_response.status_code == 201
    package = package_response.json()

    submitted = client.post(
        f"/api/v1/listing-packages/{package['package_id']}/submit-review",
        json={"actor": "listing-operator"},
    )
    approved = client.post(
        f"/api/v1/listing-packages/{package['package_id']}/decision",
        json={"reviewer": "reviewer-b", "action": "approve"},
    )
    published = client.post(
        f"/api/v1/listing-packages/{package['package_id']}/publish",
        json={
            "actor": "publisher-c",
            "idempotency_key": f"performance-{package['package_id']}-v1",
        },
    )
    assert submitted.status_code == 200
    assert approved.status_code == 200
    assert published.status_code == 200
    return client.get(f"/api/v1/listing-packages/{package['package_id']}").json()


def test_mock_data_feedback_and_evidence_backed_optimization_report() -> None:
    package = _create_published_listing()

    missing = client.post(
        f"/api/v1/performance/packages/{package['package_id']}/analyze",
        json={"actor": "performance-analyst"},
    )
    assert missing.status_code == 409
    assert "snapshots are missing" in missing.json()["detail"]

    synced = client.post(
        f"/api/v1/performance/packages/{package['package_id']}/demo-snapshots",
        json={"actor": "mock-data-connector"},
    )
    assert synced.status_code == 201
    snapshots = synced.json()
    assert len(snapshots) == 3
    assert all(item["mock"] for item in snapshots)
    assert all(item["source"] == "mock_platform_api" for item in snapshots)
    shopify = next(item for item in snapshots if item["platform"] == "shopify")
    assert shopify["ctr"] == 1.19
    assert shopify["conversion_rate"] == 5.19
    assert shopify["roas"] == 1.88

    analyzed = client.post(
        f"/api/v1/performance/packages/{package['package_id']}/analyze",
        json={"actor": "performance-analyst"},
    )
    assert analyzed.status_code == 201
    report = analyzed.json()
    assert report["mock"] is True
    assert len(report["summaries"]) == 3
    assert len(report["snapshot_ids"]) == 3
    assert report["cross_platform_findings"]
    assert report["recommendations"]
    assert all(
        item["requires_human_approval"] for item in report["recommendations"]
    )
    categories = {item["category"] for item in report["recommendations"]}
    assert {"creative", "advertising", "inventory", "growth"} <= categories
    assert "mark_actions_for_human_review" in report["trace"]
    assert "Mock 平台连接器" in report["data_quality_notes"][0]

    fetched = client.get(f"/api/v1/performance/reports/{report['report_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["report_id"] == report["report_id"]


def test_performance_snapshot_validates_funnel_counts() -> None:
    package = _create_published_listing()
    response = client.post(
        "/api/v1/performance/snapshots",
        json={
            "package_id": package["package_id"],
            "platform": "amazon",
            "period_start": "2026-08-01",
            "period_end": "2026-08-07",
            "impressions": 100,
            "clicks": 120,
            "add_to_carts": 20,
            "orders": 8,
            "units_sold": 8,
            "revenue": 552,
            "ad_spend": 100,
            "returns": 0,
            "inventory": 50,
        },
    )

    assert response.status_code == 422
    assert "clicks cannot exceed impressions" in response.text
