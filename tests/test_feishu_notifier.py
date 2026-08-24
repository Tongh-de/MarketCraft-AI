import json
from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import Settings
from app.domain.operations import CommerceOrder, OrderLine, SalesChannel
from app.services.commerce_adapters import (
    FeishuWebhookNotifier,
    MockFeishuNotifier,
    get_operations_notifier,
)


def test_operations_notifier_defaults_to_mock() -> None:
    notifier = get_operations_notifier(Settings(_env_file=None))
    assert isinstance(notifier, MockFeishuNotifier)


def test_feishu_webhook_notifier_builds_signed_interactive_card(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return b'{"StatusCode":0,"StatusMessage":"success"}'

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("time.time", lambda: 1700000000)
    settings = Settings(
        feishu_approval_mode="webhook",
        feishu_webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test",
        feishu_webhook_secret="secret",
        feishu_approval_base_url="https://marketcraft.example.com",
        feishu_request_timeout_seconds=3,
    )
    order = CommerceOrder(
        order_id="AMZ-FEISHU-001",
        channel=SalesChannel.AMAZON,
        buyer_region="US",
        lines=[OrderLine(sku="SKU-1", quantity=2)],
        created_at=datetime.now(UTC),
    )
    run_id = uuid4()

    notification_id = FeishuWebhookNotifier(settings).request_review(
        order, "fulfill_order", run_id
    )

    assert notification_id == f"feishu-review-{run_id}"
    assert captured["timeout"] == 3
    assert captured["body"]["msg_type"] == "interactive"
    assert captured["body"]["timestamp"] == "1700000000"
    assert captured["body"]["sign"]
    card = captured["body"]["card"]
    assert card["header"]["title"]["content"] == "MarketCraft \u8ba2\u5355\u5ba1\u6279"
    assert "AMZ-FEISHU-001" in card["elements"][0]["text"]["content"]
    assert "\u8ba2\u5355\u53f7" in card["elements"][0]["text"]["content"]
    assert card["elements"][-1]["actions"][0]["url"] == "https://marketcraft.example.com/app#operations"
