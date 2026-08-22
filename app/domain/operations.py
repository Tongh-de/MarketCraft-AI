from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from app.domain.models import AuditEvent


class SalesChannel(StrEnum):
    AMAZON = "amazon"
    TIKTOK_SHOP = "tiktok_shop"


class OrderLine(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=10000)


class CommerceOrder(BaseModel):
    order_id: str = Field(min_length=3, max_length=128)
    channel: SalesChannel
    buyer_region: str = Field(min_length=2, max_length=64)
    lines: list[OrderLine] = Field(min_length=1, max_length=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def require_unique_skus(self):
        skus = [line.sku for line in self.lines]
        if len(skus) != len(set(skus)):
            raise ValueError("order lines must contain unique SKUs")
        return self


class InventoryRecord(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    warehouse: str = Field(default="default", min_length=2, max_length=64)
    available: int = Field(ge=0)
    reserved: int = Field(default=0, ge=0)
    reorder_point: int = Field(default=10, ge=0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InventoryCheck(BaseModel):
    sku: str
    required: int = Field(ge=1)
    available: int = Field(ge=0)
    shortage: int = Field(ge=0)
    warehouse: str


class OperationAction(StrEnum):
    FULFILL_ORDER = "fulfill_order"
    CREATE_RESTOCK_TASK = "create_restock_task"


class OperationStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    PARTIAL_FAILED = "partial_failed"


class OperationExecutionResult(BaseModel):
    system: Literal["erp", "commerce_platform"]
    action: str
    status: Literal["completed", "failed"]
    external_id: str | None = None
    error: str | None = None
    mock: bool = True


class OrderOperationRun(BaseModel):
    run_id: UUID = Field(default_factory=uuid4)
    order: CommerceOrder
    inventory_checks: list[InventoryCheck]
    recommended_action: OperationAction
    recommendation_reason: str
    risk_flags: list[str] = Field(default_factory=list)
    status: OperationStatus = OperationStatus.PENDING_REVIEW
    requested_by: str
    reviewed_by: str | None = None
    review_reason: str | None = None
    idempotency_key: str
    notification_id: str | None = None
    execution_results: list[OperationExecutionResult] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)
    audit_log: list[AuditEvent] = Field(default_factory=list)


class OrderProcessRequest(BaseModel):
    order: CommerceOrder
    actor: str = Field(min_length=2, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=128)


class PlatformOrderProcessRequest(BaseModel):
    actor: str = Field(min_length=2, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=128)


class OperationDecisionRequest(BaseModel):
    reviewer: str = Field(min_length=2, max_length=100)
    action: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if self.action == "reject" and not self.reason:
            raise ValueError("reason is required when rejecting an operation")
        return self


class OperationExecuteRequest(BaseModel):
    actor: str = Field(min_length=2, max_length=100)
