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


def _request_payload() -> dict:
    return {
        "product": {
            "sku": "JACKET-CREATION-001",
            "name": "轻盈通勤夹克",
            "category": "女装外套",
            "source_image_url": "https://example.com/jacket-source.png",
            "description": "米色轻薄通勤夹克，简约版型。",
            "target_audience": "城市通勤女性",
        },
        "instruction": "保持商品版型和颜色一致，生成多角度图片与模特试穿图。",
        "requested_outputs": [
            "front_view",
            "side_view",
            "back_view",
            "model_try_on",
        ],
        "preferred_plugin_id": "comfyui.mock",
        "actor": "tester",
    }


def test_skill_and_plugin_catalogs_are_visible() -> None:
    plugins = client.get("/api/v1/creation/plugins")
    skills = client.get("/api/v1/creation/skills")

    assert plugins.status_code == 200
    assert {item["plugin_id"] for item in plugins.json()} == {
        "comfyui.mock",
        "jimeng.mock",
        "multimodal-vision.mock",
    }
    assert all(item["mode"] == "mock" for item in plugins.json())
    assert skills.status_code == 200
    assert {item["skill_id"] for item in skills.json()} == {
        "product-asset-generation",
        "competitor-visual-analysis",
        "poster-design",
    }


def test_create_and_get_mock_product_asset_task() -> None:
    created = client.post("/api/v1/creation/tasks", json=_request_payload())

    assert created.status_code == 201
    task = created.json()
    assert task["status"] == "completed"
    assert task["progress"] == 100
    assert task["plugin_id"] == "comfyui.mock"
    assert len(task["assets"]) == 4
    assert {item["kind"] for item in task["assets"]} == {
        "front_view",
        "side_view",
        "back_view",
        "model_try_on",
    }
    assert all(item["mock"] for item in task["assets"])
    assert task["trace"][-1] == "task_completed"

    fetched = client.get(f"/api/v1/creation/tasks/{task['task_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["task_id"] == task["task_id"]

    preview = client.get(task["assets"][0]["url"])
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/svg+xml")


def test_plugin_capability_validation_is_explicit() -> None:
    payload = _request_payload()
    payload["requested_outputs"] = ["short_video"]
    payload["preferred_plugin_id"] = "comfyui.mock"

    response = client.post("/api/v1/creation/tasks", json=payload)

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert "does not support" in response.json()["error"]


def test_upload_product_image_and_serve_it() -> None:
    response = client.post(
        "/api/v1/creation/uploads",
        files={"file": ("../unsafe-name.png", VALID_PNG, "image/png")},
    )

    assert response.status_code == 201
    uploaded = response.json()
    assert uploaded["original_filename"] == "unsafe-name.png"
    assert uploaded["content_type"] == "image/png"
    assert uploaded["size_bytes"] == len(VALID_PNG)
    assert len(uploaded["checksum_sha256"]) == 64
    assert uploaded["url"].startswith("/uploads/")

    served = client.get(uploaded["url"])
    assert served.status_code == 200
    assert served.content == VALID_PNG

    stored_file = Path(get_settings().upload_dir) / Path(uploaded["url"]).name
    stored_file.unlink(missing_ok=True)


def test_upload_rejects_spoofed_image_content() -> None:
    response = client.post(
        "/api/v1/creation/uploads",
        files={"file": ("fake.png", b"this is not a png", "image/png")},
    )

    assert response.status_code == 415
    assert "does not match" in response.json()["detail"]


def test_create_and_get_mock_competitor_analysis() -> None:
    response = client.post(
        "/api/v1/creation/competitor-analyses",
        json={
            "product": {
                "sku": "JACKET-COMP-001",
                "name": "轻盈通勤夹克",
                "category": "女装外套",
                "source_image_url": "/uploads/own-product.png",
                "target_audience": "城市通勤女性",
            },
            "competitor_images": [
                {"label": "竞品 1", "image_url": "/uploads/competitor-1.png"},
                {"label": "竞品 2", "image_url": "/uploads/competitor-2.png"},
            ],
            "instruction": "分析视觉规律并生成原创差异化方案。",
            "preferred_plugin_id": "multimodal-vision.mock",
            "actor": "test-strategist",
        },
    )

    assert response.status_code == 201
    report = response.json()
    assert report["status"] == "completed"
    assert report["plugin_id"] == "multimodal-vision.mock"
    assert report["mock"] is True
    assert len(report["dimensions"]) == 5
    assert len(report["creative_briefs"]) == 3
    assert "未真实读取图片像素" in report["summary"]
    assert report["trace"][-1] == "report_completed"

    fetched = client.get(
        f"/api/v1/creation/competitor-analyses/{report['report_id']}"
    )
    assert fetched.status_code == 200
    assert fetched.json()["report_id"] == report["report_id"]
