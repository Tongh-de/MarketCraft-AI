import hashlib
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

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
