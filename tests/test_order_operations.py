from uuid import uuid4

import pytest

from app.domain.operations import (
    CommerceOrder,
    InventoryRecord,
    OperationDecisionRequest,
    OrderLine,
    OrderProcessRequest,
)
from app.services.commerce_adapters import CommerceAdapterError
from app.services.order_operations import (
    OperationsConflictError,
    OrderOperationsService,
)
from app.services.persistence import InMemoryJsonStateStore, SQLAlchemyJsonStateStore


def make_request(
    order_id: str, quantity: int = 2, idempotency_key: str | None = None
) -> OrderProcessRequest:
    return OrderProcessRequest(
        order=CommerceOrder(
            order_id=order_id,
            channel="amazon",
            buyer_region="US",
            lines=[OrderLine(sku="OPS-CUP-001", quantity=quantity)],
        ),
        actor="operations-agent",
        idempotency_key=idempotency_key or f"process-{order_id}",
    )


def approve(service: OrderOperationsService, run_id) -> None:
    service.decide(
        run_id,
        OperationDecisionRequest(reviewer="reviewer-b", action="approve"),
    )


def test_sufficient_inventory_requires_review_then_executes_idempotently() -> None:
    store = InMemoryJsonStateStore()
    service = OrderOperationsService(state_store=store)
    service.upsert_inventory(
        InventoryRecord(sku="OPS-CUP-001", available=20, reorder_point=5)
    )
    request = make_request(f"AMZ-{uuid4()}")

    first = service.process(request)
    replayed = service.process(request)
    assert first.run_id == replayed.run_id
    assert first.recommended_action == "fulfill_order"
    assert first.status == "pending_review"
    assert first.notification_id.startswith("mock-feishu-review-")
    assert first.trace == [
        "validate_order",
        "fetch_inventory",
        "plan_operation",
        "require_human_review",
    ]

    with pytest.raises(OperationsConflictError, match="reviewer must differ"):
        service.decide(
            first.run_id,
            OperationDecisionRequest(
                reviewer="operations-agent", action="approve"
            ),
        )

    approve(service, first.run_id)
    executed = service.execute(first.run_id, "executor-c")
    retried = service.execute(first.run_id, "executor-c")
    assert executed == retried
    assert executed.status == "completed"
    assert len(executed.execution_results) == 2
    assert all(result.mock for result in executed.execution_results)
    assert all(
        result.external_id and result.external_id.startswith("mock-")
        for result in executed.execution_results
    )
    assert service.get_inventory("OPS-CUP-001").available == 18


def test_inventory_shortage_creates_restock_plan_instead_of_fulfillment() -> None:
    service = OrderOperationsService(state_store=InMemoryJsonStateStore())
    service.upsert_inventory(
        InventoryRecord(sku="OPS-CUP-001", available=1, reorder_point=5)
    )
    run = service.process(make_request(f"TTS-{uuid4()}", quantity=4))
    assert run.recommended_action == "create_restock_task"
    assert run.inventory_checks[0].shortage == 3
    assert "inventory_shortage" in run.risk_flags

    approve(service, run.run_id)
    executed = service.execute(run.run_id, "executor-c")
    assert executed.status == "completed"
    assert len(executed.execution_results) == 1
    assert executed.execution_results[0].action.startswith("create_restock_task")
    assert service.get_inventory("OPS-CUP-001").available == 1


def test_platform_failure_is_recorded_without_fake_success() -> None:
    class FailingPlatformGateway:
        def create_fulfillment(self, order, run_id, idempotency_key):
            raise CommerceAdapterError("sandbox platform unavailable")

    service = OrderOperationsService(
        state_store=InMemoryJsonStateStore(),
        platform_gateway=FailingPlatformGateway(),
    )
    service.upsert_inventory(
        InventoryRecord(sku="OPS-CUP-001", available=10, reorder_point=2)
    )
    run = service.process(make_request(f"FAIL-{uuid4()}"))
    approve(service, run.run_id)
    executed = service.execute(run.run_id, "executor-c")
    assert executed.status == "partial_failed"
    assert executed.execution_results[-1].status == "failed"
    assert executed.execution_results[-1].external_id is None


def test_operation_survives_service_restart_with_sqlite(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'operations.db'}"
    first_service = OrderOperationsService(
        state_store=SQLAlchemyJsonStateStore(database_url)
    )
    first_service.upsert_inventory(
        InventoryRecord(sku="OPS-CUP-001", available=10, reorder_point=2)
    )
    run = first_service.process(make_request(f"PERSIST-{uuid4()}"))

    restarted_service = OrderOperationsService(
        state_store=SQLAlchemyJsonStateStore(database_url)
    )
    restored = restarted_service.get(run.run_id)
    assert restored.status == "pending_review"
    assert restored.order.order_id == run.order.order_id
    assert restored.notification_id.startswith("mock-feishu-review-")


def test_order_is_pulled_through_platform_gateway() -> None:
    service = OrderOperationsService(state_store=InMemoryJsonStateStore())
    service.upsert_inventory(
        InventoryRecord(sku="OPS-CUP-001", available=10, reorder_point=2)
    )
    order = CommerceOrder(
        order_id=f"PULL-{uuid4()}",
        channel="tiktok_shop",
        buyer_region="SG",
        lines=[OrderLine(sku="OPS-CUP-001", quantity=1)],
    )
    service.upsert_platform_order(order)
    run = service.process_platform_order(
        order.channel,
        order.order_id,
        actor="operations-agent",
        idempotency_key=f"pull-{order.order_id}",
    )
    assert run.order.channel == "tiktok_shop"
    assert run.recommended_action == "fulfill_order"
