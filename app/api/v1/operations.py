from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.domain.operations import (
    CommerceOrder,
    InventoryRecord,
    OperationDecisionRequest,
    OperationExecuteRequest,
    OperationStatus,
    OrderOperationRun,
    OrderProcessRequest,
    PlatformOrderProcessRequest,
    SalesChannel,
)
from app.observability import OPERATION_EXECUTIONS, ORDER_OPERATIONS
from app.services.order_operations import (
    OperationsConflictError,
    OperationsNotFoundError,
    get_order_operations_service,
)

router = APIRouter(prefix="/operations", tags=["commerce operations"])


def _raise_http_error(error: Exception) -> None:
    if isinstance(error, OperationsNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.put("/inventory/{sku}", response_model=InventoryRecord)
def upsert_inventory(sku: str, record: InventoryRecord) -> InventoryRecord:
    if sku != record.sku:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="path SKU must match payload SKU",
        )
    return get_order_operations_service().upsert_inventory(record)


@router.get("/inventory/{sku}", response_model=InventoryRecord)
def get_inventory(sku: str) -> InventoryRecord:
    return get_order_operations_service().get_inventory(sku)


@router.post("/orders/process", response_model=OrderOperationRun)
def process_order(request: OrderProcessRequest) -> OrderOperationRun:
    try:
        run = get_order_operations_service().process(request)
        ORDER_OPERATIONS.labels(
            run.order.channel.value, run.recommended_action.value
        ).inc()
        return run
    except OperationsConflictError as error:
        _raise_http_error(error)


@router.put("/platform-orders/{channel}/{order_id}", response_model=CommerceOrder)
def seed_mock_platform_order(
    channel: SalesChannel, order_id: str, order: CommerceOrder
) -> CommerceOrder:
    if order.channel != channel or order.order_id != order_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="path channel/order ID must match payload order",
        )
    return get_order_operations_service().upsert_platform_order(order)


@router.post(
    "/platform-orders/{channel}/{order_id}/process",
    response_model=OrderOperationRun,
)
def process_platform_order(
    channel: SalesChannel, order_id: str, request: PlatformOrderProcessRequest
) -> OrderOperationRun:
    try:
        run = get_order_operations_service().process_platform_order(
            channel, order_id, request.actor, request.idempotency_key
        )
        ORDER_OPERATIONS.labels(
            run.order.channel.value, run.recommended_action.value
        ).inc()
        return run
    except (OperationsNotFoundError, OperationsConflictError) as error:
        _raise_http_error(error)


@router.get("/runs", response_model=list[OrderOperationRun])
def list_operation_runs(
    operation_status: Annotated[
        OperationStatus | None, Query(alias="status")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[OrderOperationRun]:
    return get_order_operations_service().list_runs(operation_status, limit)


@router.get("/runs/{run_id}", response_model=OrderOperationRun)
def get_operation_run(run_id: UUID) -> OrderOperationRun:
    try:
        return get_order_operations_service().get(run_id)
    except OperationsNotFoundError as error:
        _raise_http_error(error)


@router.post("/runs/{run_id}/decision", response_model=OrderOperationRun)
def decide_operation(
    run_id: UUID, request: OperationDecisionRequest
) -> OrderOperationRun:
    try:
        return get_order_operations_service().decide(run_id, request)
    except (OperationsNotFoundError, OperationsConflictError) as error:
        _raise_http_error(error)


@router.post("/runs/{run_id}/execute", response_model=OrderOperationRun)
def execute_operation(
    run_id: UUID, request: OperationExecuteRequest
) -> OrderOperationRun:
    try:
        run = get_order_operations_service().execute(run_id, request.actor)
        for result in run.execution_results:
            OPERATION_EXECUTIONS.labels(result.system, result.status).inc()
        return run
    except (OperationsNotFoundError, OperationsConflictError) as error:
        _raise_http_error(error)
