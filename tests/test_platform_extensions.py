from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_custom_skill_can_be_auto_edited_enabled_and_planned() -> None:
    catalog = client.get("/api/v1/platform/skill-plugins")
    assert catalog.status_code == 200
    assert "commerce-performance-optimization" in {
        item["plugin_id"] for item in catalog.json()
    }
    assert all(item["status"] == "enabled" for item in catalog.json() if item["built_in"])

    created = client.post(
        "/api/v1/platform/skill-plugins",
        json={
            "plugin_id": "test-growth-copilot",
            "name": "增长分析助手",
            "description": "读取经营指标并生成带数字证据的增长实验建议。",
            "instructions": "只读取数据并输出分析，不直接修改广告、价格或库存。",
            "triggers": ["分析增长数据", "生成实验建议"],
            "capabilities": ["performance_read", "insight_generation"],
            "tool_bindings": ["performance.load", "performance.analyze"],
            "risk_level": "review_required",
            "actor": "test-designer",
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "draft"
    assert created.json()["version"] == "1.0.0"

    blocked = client.post(
        "/api/v1/platform/skill-plugins/test-growth-copilot/invoke",
        json={"prompt": "分析增长数据", "actor": "tester"},
    )
    assert blocked.status_code == 409

    edited = client.post(
        "/api/v1/platform/skill-plugins/test-growth-copilot/auto-edit",
        json={
            "change_request": "增加低库存判断，并要求建议附带原始指标",
            "actor": "skill-ai-editor",
        },
    )
    assert edited.status_code == 200
    assert edited.json()["version"] == "1.0.1"
    assert edited.json()["status"] == "draft"
    assert "低库存判断" in edited.json()["instructions"]
    assert edited.json()["auto_edit_history"]

    enabled = client.post(
        "/api/v1/platform/skill-plugins/test-growth-copilot/status",
        json={"status": "enabled", "actor": "skill-admin"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "enabled"

    invoked = client.post(
        "/api/v1/platform/skill-plugins/test-growth-copilot/invoke",
        json={"prompt": "请分析增长数据并生成实验建议", "actor": "tester"},
    )
    assert invoked.status_code == 200
    plan = invoked.json()
    assert plan["status"] == "planned"
    assert plan["mock"] is True
    assert plan["approval_required"] is True
    assert plan["planned_tools"] == ["performance.load", "performance.analyze"]
    assert "分析增长数据" in plan["matched_triggers"]
    assert plan["trace"][-1] == "stop_before_external_write"


def test_built_in_skill_cannot_be_auto_edited() -> None:
    response = client.post(
        "/api/v1/platform/skill-plugins/product-asset-generation/auto-edit",
        json={"change_request": "修改内置执行逻辑", "actor": "tester"},
    )

    assert response.status_code == 409
    assert "built-in skills cannot be auto-edited" in response.json()["detail"]


def test_external_service_registry_keeps_mock_and_live_boundaries_explicit() -> None:
    catalog = client.get("/api/v1/platform/external-services")
    assert catalog.status_code == 200
    assert {"comfyui.mock", "jimeng.mock", "amazon.mock", "erp.mock"} <= {
        item["service_id"] for item in catalog.json()
    }
    assert all(item["mode"] == "mock" for item in catalog.json() if item["built_in"])

    mock_service = client.post(
        "/api/v1/platform/external-services",
        json={
            "service_id": "test-creative.mock",
            "name": "测试图片服务",
            "kind": "creative_generation",
            "description": "用于验证自定义图片服务适配器注册流程。",
            "auth_type": "none",
            "capabilities": ["image_generation"],
            "mode": "mock",
            "actor": "test-admin",
        },
    )
    assert mock_service.status_code == 201
    assert mock_service.json()["status"] == "connected"
    mock_health = client.post(
        "/api/v1/platform/external-services/test-creative.mock/health"
    )
    assert mock_health.status_code == 200
    assert mock_health.json()["checked"] is True
    assert "未访问真实外部服务" in mock_health.json()["message"]

    live_service = client.post(
        "/api/v1/platform/external-services",
        json={
            "service_id": "test-creative.live",
            "name": "待联调图片服务",
            "kind": "creative_generation",
            "description": "保存生产接口边界，但不虚构已经完成真实网络联调。",
            "base_url": "https://api.example.com",
            "auth_type": "api_key",
            "secret_reference": "env:TEST_CREATIVE_API_KEY",
            "capabilities": ["image_generation"],
            "mode": "live",
            "actor": "test-admin",
        },
    )
    assert live_service.status_code == 201
    assert live_service.json()["status"] == "pending_configuration"
    live_health = client.post(
        "/api/v1/platform/external-services/test-creative.live/health"
    )
    assert live_health.status_code == 200
    assert live_health.json()["checked"] is False
    assert "尚未执行真实网络联调" in live_health.json()["message"]


def test_live_external_service_requires_endpoint_and_secret_reference() -> None:
    response = client.post(
        "/api/v1/platform/external-services",
        json={
            "service_id": "invalid-live-service",
            "name": "无效服务",
            "kind": "custom",
            "description": "缺少生产接口地址和密钥引用的服务。",
            "auth_type": "api_key",
            "capabilities": ["custom_action"],
            "mode": "live",
        },
    )

    assert response.status_code == 422
