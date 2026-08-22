from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from app.domain.operations import (
    CommerceOrder,
    InventoryCheck,
    OperationAction,
)
from app.services.commerce_adapters import InventoryGateway


class OrderFulfillmentState(TypedDict):
    order: CommerceOrder
    inventory_checks: NotRequired[list[InventoryCheck]]
    recommended_action: NotRequired[OperationAction]
    recommendation_reason: NotRequired[str]
    risk_flags: NotRequired[list[str]]
    trace: NotRequired[list[str]]


def build_order_fulfillment_graph(inventory_gateway: InventoryGateway):
    def validate_order(state: OrderFulfillmentState) -> dict:
        return {"trace": ["validate_order"]}

    def fetch_inventory(state: OrderFulfillmentState) -> dict:
        checks = []
        for line in state["order"].lines:
            inventory = inventory_gateway.get_inventory(line.sku)
            checks.append(
                InventoryCheck(
                    sku=line.sku,
                    required=line.quantity,
                    available=inventory.available,
                    shortage=max(line.quantity - inventory.available, 0),
                    warehouse=inventory.warehouse,
                )
            )
        return {
            "inventory_checks": checks,
            "trace": [*state.get("trace", []), "fetch_inventory"],
        }

    def plan_operation(state: OrderFulfillmentState) -> dict:
        checks = state["inventory_checks"]
        shortages = [check for check in checks if check.shortage > 0]
        if shortages:
            total_shortage = sum(check.shortage for check in shortages)
            action = OperationAction.CREATE_RESTOCK_TASK
            reason = (
                f"{len(shortages)} 个 SKU 库存不足，合计缺口 {total_shortage}，"
                "建议创建补货任务并暂停履约。"
            )
            risk_flags = ["inventory_shortage", "fulfillment_blocked"]
        else:
            action = OperationAction.FULFILL_ORDER
            reason = "所有 SKU 可用库存充足，建议预占库存并创建平台履约任务。"
            risk_flags = []
            for check in checks:
                inventory = inventory_gateway.get_inventory(check.sku)
                if inventory.available - check.required <= inventory.reorder_point:
                    risk_flags.append(f"low_stock_after_reservation:{check.sku}")
        return {
            "recommended_action": action,
            "recommendation_reason": reason,
            "risk_flags": risk_flags,
            "trace": [*state.get("trace", []), "plan_operation"],
        }

    def require_human_review(state: OrderFulfillmentState) -> dict:
        return {"trace": [*state.get("trace", []), "require_human_review"]}

    builder = StateGraph(OrderFulfillmentState)
    builder.add_node("validate_order", validate_order)
    builder.add_node("fetch_inventory", fetch_inventory)
    builder.add_node("plan_operation", plan_operation)
    builder.add_node("require_human_review", require_human_review)
    builder.add_edge(START, "validate_order")
    builder.add_edge("validate_order", "fetch_inventory")
    builder.add_edge("fetch_inventory", "plan_operation")
    builder.add_edge("plan_operation", "require_human_review")
    builder.add_edge("require_human_review", END)
    return builder.compile()
