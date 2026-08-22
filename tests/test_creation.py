from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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
    }
    assert all(item["mode"] == "mock" for item in plugins.json())
    assert skills.status_code == 200
    assert skills.json()[0]["skill_id"] == "product-asset-generation"


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
