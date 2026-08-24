from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_wechat_mock_draft_review_and_publish_flow() -> None:
    configuration = client.get("/api/v1/wechat/configuration")
    assert configuration.status_code == 200
    assert configuration.json()["mode"] == "mock"
    assert configuration.json()["configured"] is True

    material = client.post(
        "/api/v1/wechat/materials/images",
        files={"file": ("cover.png", b"fake-png", "image/png")},
    )
    assert material.status_code == 201
    media_id = material.json()["media_id"]
    assert media_id.startswith("mock-thumb-")

    created = client.post(
        "/api/v1/wechat/drafts",
        json={
            "articles": [
                {
                    "title": "MarketCraft AI 新品内容测试",
                    "author": "运营团队",
                    "digest": "从商品素材到公众号发布的完整演示。",
                    "content": "<h2>新品上线</h2><p>这是一篇演示内容。</p>",
                    "thumb_media_id": media_id,
                }
            ],
            "actor": "editor-a",
        },
    )
    assert created.status_code == 201
    draft = created.json()
    assert draft["status"] == "draft"

    self_review = client.post(
        f"/api/v1/wechat/drafts/{draft['draft_id']}/review",
        json={"reviewer": "editor-a", "action": "approve"},
    )
    assert self_review.status_code == 409

    approved = client.post(
        f"/api/v1/wechat/drafts/{draft['draft_id']}/review",
        json={"reviewer": "reviewer-b", "action": "approve"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    published = client.post(
        f"/api/v1/wechat/drafts/{draft['draft_id']}/publish",
        json={"actor": "publisher-c"},
    )
    assert published.status_code == 200
    assert published.json()["status"] == "submitted"
    publish_id = published.json()["publish_id"]

    checked = client.get(f"/api/v1/wechat/publications/{publish_id}/status")
    assert checked.status_code == 200
    assert checked.json()["status"] == "published"


def test_wechat_reject_requires_reason() -> None:
    response = client.post(
        "/api/v1/wechat/drafts/unknown/review",
        json={"reviewer": "reviewer-b", "action": "reject"},
    )
    assert response.status_code == 422

