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


def test_create_update_and_export_editable_poster_project() -> None:
    upload_response = client.post(
        "/api/v1/creation/uploads",
        files={"file": ("poster-product.png", VALID_PNG, "image/png")},
    )
    assert upload_response.status_code == 201
    upload = upload_response.json()

    created = client.post(
        "/api/v1/poster-projects",
        json={
            "product": {
                "sku": "POSTER-JACKET-001",
                "name": "轻盈通勤夹克",
                "category": "女装外套",
                "source_image_url": upload["url"],
                "target_audience": "城市通勤女性",
            },
            "title": "轻盈通勤，自在有型",
            "subtitle": "柔软面料 · 简约版型",
            "price_text": "新品价 ¥399",
            "call_to_action": "立即查看",
            "preset": "xiaohongshu_3_4",
            "style": "clean",
            "preferred_plugin_id": "comfyui.mock",
            "actor": "test-designer",
        },
    )

    assert created.status_code == 201
    project = created.json()
    assert project["version"] == 1
    assert project["plugin_id"] == "comfyui.mock"
    assert project["mock"] is True
    assert (project["canvas_width"], project["canvas_height"]) == (1242, 1660)
    assert project["preview_url"].endswith("/preview.svg")

    preview = client.get(project["preview_url"])
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("image/svg+xml")
    assert "轻盈通勤，自在有型" in preview.text
    assert upload["url"] in preview.text
    assert "MOCK" in preview.text

    updated = client.put(
        f"/api/v1/poster-projects/{project['project_id']}",
        json={
            "title": "通勤新主张",
            "preset": "amazon_square",
            "brand_color": "#245C45",
            "layout": {
                "product_x": 0.62,
                "product_y": 0.58,
                "product_scale": 0.64,
                "content_x": 0.08,
                "content_y": 0.16,
                "text_align": "left",
            },
            "actor": "test-designer",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["canvas_width"] == 2000
    assert updated.json()["canvas_height"] == 2000
    assert updated.json()["layout"]["product_x"] == 0.62

    downloaded = client.get(f"{project['preview_url']}?download=true")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-disposition"].startswith("attachment")
    assert "通勤新主张" in downloaded.text

    stored_file = Path(get_settings().upload_dir) / Path(upload["url"]).name
    stored_file.unlink(missing_ok=True)


def test_poster_project_requires_an_uploaded_product_image() -> None:
    response = client.post(
        "/api/v1/poster-projects",
        json={
            "product": {
                "sku": "POSTER-MISSING-001",
                "name": "缺少图片的商品",
                "category": "测试商品",
                "source_image_url": "/uploads/not-found.png",
            },
            "title": "无法创建的海报",
        },
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
