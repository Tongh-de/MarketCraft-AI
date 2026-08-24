import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.core.config import Settings, get_settings
from app.domain.operations import (
    CommerceOrder,
    InventoryRecord,
    OperationExecutionResult,
    SalesChannel,
)
from app.services.persistence import JsonStateStore, get_state_store


class CommerceAdapterError(Exception):
    pass


class InventoryGateway(Protocol):
    def get_inventory(self, sku: str) -> InventoryRecord: ...

    def upsert_inventory(self, record: InventoryRecord) -> InventoryRecord: ...

    def reserve(self, sku: str, quantity: int, idempotency_key: str) -> str: ...

    def create_restock_task(
        self, sku: str, quantity: int, idempotency_key: str
    ) -> str: ...


class CommercePlatformGateway(Protocol):
    def upsert_order(self, order: CommerceOrder) -> CommerceOrder: ...

    def pull_order(self, channel: SalesChannel, order_id: str) -> CommerceOrder: ...

    def create_fulfillment(
        self, order: CommerceOrder, run_id: UUID, idempotency_key: str
    ) -> OperationExecutionResult: ...


class OperationsNotifier(Protocol):
    def request_review(self, order: CommerceOrder, action: str, run_id: UUID) -> str: ...


def _deterministic_id(prefix: str, raw: str) -> str:
    return f"mock-{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:18]}"


class MockERPGateway:
    """Deterministic ERP adapter; every external identifier is explicitly marked Mock."""

    def __init__(self, state_store: JsonStateStore | None = None) -> None:
        self.state_store = state_store or get_state_store()

    def get_inventory(self, sku: str) -> InventoryRecord:
        payload = self.state_store.get("inventory", sku)
        if not payload:
            return InventoryRecord(sku=sku, available=0, reorder_point=10)
        return InventoryRecord.model_validate(payload)

    def upsert_inventory(self, record: InventoryRecord) -> InventoryRecord:
        updated = record.model_copy(update={"updated_at": datetime.now(UTC)})
        self.state_store.put("inventory", updated.sku, updated.model_dump(mode="json"))
        return updated

    def reserve(self, sku: str, quantity: int, idempotency_key: str) -> str:
        reservation_key = f"{idempotency_key}:{sku}"
        cached = self.state_store.get("inventory_reservation", reservation_key)
        if cached:
            return cached["external_id"]
        record = self.get_inventory(sku)
        if record.available < quantity:
            raise CommerceAdapterError(f"insufficient inventory for SKU {sku}")
        updated = record.model_copy(
            update={
                "available": record.available - quantity,
                "reserved": record.reserved + quantity,
                "updated_at": datetime.now(UTC),
            }
        )
        external_id = _deterministic_id("erp-reservation", reservation_key)
        self.upsert_inventory(updated)
        self.state_store.put(
            "inventory_reservation",
            reservation_key,
            {"external_id": external_id},
        )
        return external_id

    def create_restock_task(
        self, sku: str, quantity: int, idempotency_key: str
    ) -> str:
        raw = f"{idempotency_key}:{sku}:{quantity}"
        return _deterministic_id("erp-restock", raw)


class MockCommercePlatformGateway:
    def __init__(self, state_store: JsonStateStore | None = None) -> None:
        self.state_store = state_store or get_state_store()

    def upsert_order(self, order: CommerceOrder) -> CommerceOrder:
        self.state_store.put(
            "commerce_platform_order",
            f"{order.channel.value}:{order.order_id}",
            order.model_dump(mode="json"),
        )
        return order

    def pull_order(self, channel: SalesChannel, order_id: str) -> CommerceOrder:
        payload = self.state_store.get(
            "commerce_platform_order", f"{channel.value}:{order_id}"
        )
        if not payload:
            raise CommerceAdapterError("platform order not found in Mock adapter")
        return CommerceOrder.model_validate(payload)

    def create_fulfillment(
        self, order: CommerceOrder, run_id: UUID, idempotency_key: str
    ) -> OperationExecutionResult:
        raw = f"{order.channel}:{order.order_id}:{run_id}:{idempotency_key}"
        return OperationExecutionResult(
            system="commerce_platform",
            action="create_fulfillment",
            status="completed",
            external_id=_deterministic_id(order.channel.value, raw),
            mock=True,
        )


class MockFeishuNotifier:
    """No network call is made; the ID proves the notification path was exercised."""

    def request_review(self, order: CommerceOrder, action: str, run_id: UUID) -> str:
        raw = f"{order.order_id}:{action}:{run_id}"
        return _deterministic_id("feishu-review", raw)


class FeishuWebhookNotifier:
    """Send operation review requests to a Feishu custom bot webhook."""

    def __init__(self, settings: Settings) -> None:
        if not settings.feishu_webhook_url:
            raise ValueError("FEISHU_WEBHOOK_URL is required when FEISHU_APPROVAL_MODE=webhook")
        self.webhook_url = settings.feishu_webhook_url
        self.secret = settings.feishu_webhook_secret
        self.base_url = (settings.feishu_approval_base_url or "").rstrip("/")
        self.timeout = settings.feishu_request_timeout_seconds

    def request_review(self, order: CommerceOrder, action: str, run_id: UUID) -> str:
        payload = self._payload(order, action, run_id)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise CommerceAdapterError(f"Feishu review notification failed: {exc}") from exc
        try:
            result = json.loads(body)
        except json.JSONDecodeError as exc:
            raise CommerceAdapterError("Feishu returned a non-JSON response") from exc
        code = result.get("StatusCode", result.get("code", 0))
        if code not in (0, "0", None):
            message = result.get("msg") or result.get("StatusMessage") or body
            raise CommerceAdapterError(f"Feishu review notification failed: {message}")
        return f"feishu-review-{run_id}"

    def _payload(self, order: CommerceOrder, action: str, run_id: UUID) -> dict:
        skus = ", ".join(f"{line.sku} x{line.quantity}" for line in order.lines)
        review_url = f"{self.base_url}/app#operations" if self.base_url else ""
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "orange",
                "title": {"tag": "plain_text", "content": "MarketCraft \u8ba2\u5355\u5ba1\u6279"},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**\u8ba2\u5355\u53f7**\uff1a{order.order_id}\n"
                            f"**\u5e73\u53f0**\uff1a{order.channel.value}\n"
                            f"**\u5efa\u8bae\u52a8\u4f5c**\uff1a{action}\n"
                            f"**\u5546\u54c1**\uff1a{skus}\n"
                            f"**Run ID**\uff1a{run_id}"
                        ),
                    },
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "\u8bf7\u5728 MarketCraft \u540e\u53f0\u5b8c\u6210\u5ba1\u6279\uff1b\u5ba1\u6279\u4eba\u4e0e\u63d0\u4ea4\u4eba\u5fc5\u987b\u4e0d\u540c\u3002",
                        }
                    ],
                },
            ],
        }
        if review_url:
            card["elements"].append(
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "\u6253\u5f00\u5ba1\u6279\u53f0"},
                            "url": review_url,
                            "type": "primary",
                        }
                    ],
                }
            )
        payload = {"msg_type": "interactive", "card": card}
        if self.secret:
            timestamp = str(int(time.time()))
            payload["timestamp"] = timestamp
            payload["sign"] = self._sign(timestamp)
        return payload

    def _sign(self, timestamp: str) -> str:
        string_to_sign = f"{timestamp}\n{self.secret}"
        digest = hmac.new(string_to_sign.encode("utf-8"), b"", digestmod=hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")


def get_operations_notifier(settings: Settings | None = None) -> OperationsNotifier:
    settings = settings or get_settings()
    if settings.feishu_approval_mode == "webhook" and settings.feishu_webhook_url:
        return FeishuWebhookNotifier(settings)
    return MockFeishuNotifier()
