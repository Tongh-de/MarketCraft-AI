from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)

VALID_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\rIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff"
    b"\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _create_sources() -> tuple[dict, dict, dict]:
    uploaded_response = client.post(
        "/api/v1/creation/uploads",
        files={"file": ("listing-jacket.png", VALID_PNG, "image/png")},
    )
    assert uploaded_response.status_code == 201
    uploaded = uploaded_response.json()

    task_response = client.post(
        "/api/v1/creation/tasks",
        json={
            "product": {
                "sku": "LISTING-JACKET-001",
                "name": "轻盈城市夹克",
                "category": "女装外套",
                "source_image_url": uploaded["url"],
                "description": "轻量防泼水面料，适合通勤和旅行场景。",
                "target_audience": "城市通勤女性",
            },
            "instruction": "生成多角度图、模特试穿图和商品展示图。",
            "requested_outputs": [
                "front_view",
                "side_view",
                "model_try_on",
            ],
            "preferred_plugin_id": "comfyui.mock",
            "actor": "listing-operator",
        },
    )
    assert task_response.status_code == 201
    task = task_response.json()
    assert task["status"] == "completed"

    poster_response = client.post(
        "/api/v1/poster-projects",
        json={
            "product": {
                "sku": "LISTING-JACKET-001",
                "name": "轻盈城市夹克",
                "category": "女装外套",
                "source_image_url": uploaded["url"],
                "target_audience": "城市通勤女性",
            },
            "title": "轻盈通勤，自在出发",
            "subtitle": "轻量 · 防泼水 · 日常百搭",
            "price_text": "$69",
            "call_to_action": "立即选购",
            "preset": "tiktok_vertical",
            "style": "lifestyle",
            "actor": "poster-designer",
        },
    )
    assert poster_response.status_code == 201
    return uploaded, task, poster_response.json()


def _listing_payload(task: dict, poster: dict) -> dict:
    return {
        "creation_task_id": task["task_id"],
        "poster_project_id": poster["project_id"],
        "product": {
            "sku": "LISTING-JACKET-001",
            "name": "轻盈城市夹克",
            "category": "女装外套",
            "description": "轻量防泼水面料，简约廓形适合通勤和旅行场景。",
            "attributes": {"材质": "轻量防泼水面料", "颜色": "燕麦米"},
            "price": 69,
            "currency": "USD",
            "inventory": 120,
        },
        "platforms": ["amazon", "tiktok_shop", "shopify"],
        "actor": "listing-operator",
    }


def test_listing_package_review_and_idempotent_mock_publish() -> None:
    uploaded, task, poster = _create_sources()
    created = client.post(
        "/api/v1/listing-packages", json=_listing_payload(task, poster)
    )

    assert created.status_code == 201
    package = created.json()
    assert package["status"] == "draft"
    assert len(package["drafts"]) == 3
    assert len(package["assets"]) == 4
    assert package["assets"][-1]["asset_type"] == "editable_poster"
    amazon = next(item for item in package["drafts"] if item["platform"] == "amazon")
    tiktok = next(
        item for item in package["drafts"] if item["platform"] == "tiktok_shop"
    )
    assert poster["preview_url"] not in amazon["asset_urls"]
    assert poster["preview_url"] in tiktok["asset_urls"]

    submitted = client.post(
        f"/api/v1/listing-packages/{package['package_id']}/submit-review",
        json={"actor": "listing-operator"},
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_review"

    self_review = client.post(
        f"/api/v1/listing-packages/{package['package_id']}/decision",
        json={"reviewer": "listing-operator", "action": "approve"},
    )
    assert self_review.status_code == 409
    assert "must differ" in self_review.json()["detail"]

    approved = client.post(
        f"/api/v1/listing-packages/{package['package_id']}/decision",
        json={"reviewer": "reviewer-b", "action": "approve"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    publish_payload = {
        "actor": "publisher-c",
        "idempotency_key": f"listing-{package['package_id']}-v1",
    }
    published = client.post(
        f"/api/v1/listing-packages/{package['package_id']}/publish",
        json=publish_payload,
    )
    replayed = client.post(
        f"/api/v1/listing-packages/{package['package_id']}/publish",
        json=publish_payload,
    )
    assert published.status_code == 200
    assert published.json() == replayed.json()
    assert published.json()["status"] == "published"
    assert len(published.json()["results"]) == 3
    assert all(item["mock"] for item in published.json()["results"])
    assert all(
        item["external_id"].startswith("mock-")
        for item in published.json()["results"]
    )

    fetched = client.get(f"/api/v1/listing-packages/{package['package_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "published"
    assert fetched.json()["audit_log"][-1]["action"] == "listing_publish_completed"

    stored_file = Path(get_settings().upload_dir) / Path(uploaded["url"]).name
    stored_file.unlink(missing_ok=True)


def test_listing_package_rejects_mismatched_creation_task_sku() -> None:
    uploaded, task, poster = _create_sources()
    payload = _listing_payload(task, poster)
    payload["product"]["sku"] = "DIFFERENT-SKU"

    response = client.post("/api/v1/listing-packages", json=payload)

    assert response.status_code == 409
    assert "SKU must match" in response.json()["detail"]
    stored_file = Path(get_settings().upload_dir) / Path(uploaded["url"]).name
    stored_file.unlink(missing_ok=True)
