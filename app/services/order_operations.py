from functools import lru_cache
from uuid import UUID

from app.domain.models import AuditEvent
from app.domain.operations import (
    CommerceOrder,
    InventoryRecord,
    OperationAction,
    OperationDecisionRequest,
    OperationExecutionResult,
    OperationStatus,
    OrderOperationRun,
    OrderProcessRequest,
    SalesChannel,
)
from app.services.commerce_adapters import (
    CommerceAdapterError,
    CommercePlatformGateway,
    InventoryGateway,
    MockCommercePlatformGateway,
    MockERPGateway,
    MockFeishuNotifier,
    OperationsNotifier,
)
from app.services.persistence import JsonStateStore, get_state_store
from app.telemetry import traced
from app.workflows.order_fulfillment import build_order_fulfillment_graph


class OperationsNotFoundError(Exception):
    pass


class OperationsConflictError(Exception):
    pass


class OrderOperationsService:
    def __init__(
        self,
        state_store: JsonStateStore | None = None,
        inventory_gateway: InventoryGateway | None = None,
        platform_gateway: CommercePlatformGateway | None = None,
        notifier: OperationsNotifier | None = None,
    ) -> None:
        self.state_store = state_store or get_state_store()
        self.inventory_gateway = inventory_gateway or MockERPGateway(self.state_store)
        self.platform_gateway = platform_gateway or MockCommercePlatformGateway(
            self.state_store
        )
        self.notifier = notifier or MockFeishuNotifier()
        self.graph = build_order_fulfillment_graph(self.inventory_gateway)

    def _save(self, run: OrderOperationRun) -> None:
        self.state_store.put(
            "order_operation_run", str(run.run_id), run.model_dump(mode="json")
        )

    def upsert_inventory(self, record: InventoryRecord) -> InventoryRecord:
        return self.inventory_gateway.upsert_inventory(record)

    def get_inventory(self, sku: str) -> InventoryRecord:
        return self.inventory_gateway.get_inventory(sku)

    def upsert_platform_order(self, order: CommerceOrder) -> CommerceOrder:
        return self.platform_gateway.upsert_order(order)

    @traced("operations.platform_order.process")
    def process_platform_order(
        self,
        channel: SalesChannel,
        order_id: str,
        actor: str,
        idempotency_key: str,
    ) -> OrderOperationRun:
        try:
            order = self.platform_gateway.pull_order(channel, order_id)
        except CommerceAdapterError as exc:
            raise OperationsNotFoundError(str(exc)) from exc
        return self.process(
            OrderProcessRequest(
                order=order,
                actor=actor,
                idempotency_key=idempotency_key,
            )
        )

    @traced("operations.order.process")
    def process(self, request: OrderProcessRequest) -> OrderOperationRun:
        cached = self.state_store.get(
            "order_operation_idempotency", request.idempotency_key
        )
        if cached:
            if cached["order_id"] != request.order.order_id:
                raise OperationsConflictError(
                    "idempotency key is already used by another order"
                )
            return self.get(UUID(cached["run_id"]))

        existing_order = self.state_store.get(
            "order_operation_order", request.order.order_id
        )
        if existing_order:
            raise OperationsConflictError(
                "order has already been processed with another idempotency key"
            )

        output = self.graph.invoke({"order": request.order})
        run = OrderOperationRun(
            order=request.order,
            inventory_checks=output["inventory_checks"],
            recommended_action=output["recommended_action"],
            recommendation_reason=output["recommendation_reason"],
            risk_flags=output["risk_flags"],
            requested_by=request.actor,
            idempotency_key=request.idempotency_key,
            trace=output["trace"],
        )
        run.notification_id = self.notifier.request_review(
            run.order, run.recommended_action.value, run.run_id
        )
        run.audit_log.append(
            AuditEvent(
                actor=request.actor,
                action="order_evaluated",
                details={
                    "order_id": run.order.order_id,
                    "recommended_action": run.recommended_action.value,
                    "review_notification": "mock_feishu",
                },
            )
        )
        self._save(run)
        self.state_store.put(
            "order_operation_idempotency",
            request.idempotency_key,
            {"order_id": request.order.order_id, "run_id": str(run.run_id)},
        )
        self.state_store.put(
            "order_operation_order",
            request.order.order_id,
            {"run_id": str(run.run_id)},
        )
        return run

    def get(self, run_id: UUID) -> OrderOperationRun:
        payload = self.state_store.get("order_operation_run", str(run_id))
        if not payload:
            raise OperationsNotFoundError("order operation run not found")
        return OrderOperationRun.model_validate(payload)

    def list_runs(
        self, status: OperationStatus | None = None, limit: int = 50
    ) -> list[OrderOperationRun]:
        runs = [
            OrderOperationRun.model_validate(payload)
            for payload in self.state_store.list("order_operation_run")
        ]
        if status:
            runs = [run for run in runs if run.status == status]
        return sorted(
            runs,
            key=lambda run: run.order.created_at,
            reverse=True,
        )[:limit]

    @traced("operations.order.decide")
    def decide(
        self, run_id: UUID, request: OperationDecisionRequest
    ) -> OrderOperationRun:
        run = self.get(run_id)
        if run.status != OperationStatus.PENDING_REVIEW:
            raise OperationsConflictError("operation is not pending review")
        if run.requested_by == request.reviewer:
            raise OperationsConflictError("reviewer must differ from the submitter")
        run.reviewed_by = request.reviewer
        run.review_reason = request.reason
        run.status = (
            OperationStatus.APPROVED
            if request.action == "approve"
            else OperationStatus.REJECTED
        )
        run.audit_log.append(
            AuditEvent(
                actor=request.reviewer,
                action=(
                    "operation_approved"
                    if request.action == "approve"
                    else "operation_rejected"
                ),
                details={"reason": request.reason or ""},
            )
        )
        self._save(run)
        return run

    @traced("operations.order.execute")
    def execute(self, run_id: UUID, actor: str) -> OrderOperationRun:
        run = self.get(run_id)
        if run.status in {OperationStatus.COMPLETED, OperationStatus.PARTIAL_FAILED}:
            return run
        if run.status != OperationStatus.APPROVED:
            raise OperationsConflictError("only approved operations can be executed")

        if run.recommended_action == OperationAction.FULFILL_ORDER:
            self._execute_fulfillment(run)
        else:
            self._execute_restock(run)

        run.status = (
            OperationStatus.COMPLETED
            if all(item.status == "completed" for item in run.execution_results)
            else OperationStatus.PARTIAL_FAILED
        )
        run.trace.append("execute_approved_operation")
        run.audit_log.append(
            AuditEvent(
                actor=actor,
                action="operation_executed",
                details={"status": run.status.value},
            )
        )
        self._save(run)
        return run

    def _execute_fulfillment(self, run: OrderOperationRun) -> None:
        for line in run.order.lines:
            try:
                external_id = self.inventory_gateway.reserve(
                    line.sku, line.quantity, run.idempotency_key
                )
                run.execution_results.append(
                    OperationExecutionResult(
                        system="erp",
                        action=f"reserve_inventory:{line.sku}",
                        status="completed",
                        external_id=external_id,
                        mock=True,
                    )
                )
            except CommerceAdapterError as exc:
                run.execution_results.append(
                    OperationExecutionResult(
                        system="erp",
                        action=f"reserve_inventory:{line.sku}",
                        status="failed",
                        error=str(exc),
                        mock=True,
                    )
                )
        reservations_succeeded = all(
            item.status == "completed" for item in run.execution_results
        )
        if reservations_succeeded:
            try:
                run.execution_results.append(
                    self.platform_gateway.create_fulfillment(
                        run.order, run.run_id, run.idempotency_key
                    )
                )
            except CommerceAdapterError as exc:
                run.execution_results.append(
                    OperationExecutionResult(
                        system="commerce_platform",
                        action="create_fulfillment",
                        status="failed",
                        error=str(exc),
                        mock=True,
                    )
                )

    def _execute_restock(self, run: OrderOperationRun) -> None:
        for check in run.inventory_checks:
            if not check.shortage:
                continue
            try:
                external_id = self.inventory_gateway.create_restock_task(
                    check.sku, check.shortage, run.idempotency_key
                )
                run.execution_results.append(
                    OperationExecutionResult(
                        system="erp",
                        action=f"create_restock_task:{check.sku}",
                        status="completed",
                        external_id=external_id,
                        mock=True,
                    )
                )
            except CommerceAdapterError as exc:
                run.execution_results.append(
                    OperationExecutionResult(
                        system="erp",
                        action=f"create_restock_task:{check.sku}",
                        status="failed",
                        error=str(exc),
                        mock=True,
                    )
                )


@lru_cache
def get_order_operations_service() -> OrderOperationsService:
    return OrderOperationsService()
