from time import perf_counter

from fastapi import Request, Response
from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "marketcraft_http_requests_total",
    "HTTP requests handled by MarketCraft AI",
    ["method", "route", "status"],
)
HTTP_LATENCY = Histogram(
    "marketcraft_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
)
CAMPAIGN_GENERATIONS = Counter(
    "marketcraft_campaign_generations_total",
    "Campaign generation outcomes",
    ["status"],
)
PUBLICATIONS = Counter(
    "marketcraft_publications_total",
    "Per-platform publication outcomes",
    ["platform", "status"],
)
ORDER_OPERATIONS = Counter(
    "marketcraft_order_operations_total",
    "Order operation recommendations",
    ["channel", "action"],
)
OPERATION_EXECUTIONS = Counter(
    "marketcraft_operation_executions_total",
    "Order operation execution outcomes",
    ["system", "status"],
)
LISTING_PUBLICATIONS = Counter(
    "marketcraft_listing_publications_total",
    "Per-platform product listing publication outcomes",
    ["platform", "status"],
)
PERFORMANCE_SNAPSHOTS = Counter(
    "marketcraft_performance_snapshots_total",
    "Commerce performance snapshots received",
    ["platform", "source"],
)
PERFORMANCE_ANALYSES = Counter(
    "marketcraft_performance_analyses_total",
    "Commerce performance analysis outcomes",
    ["status", "mock"],
)


async def prometheus_middleware(request: Request, call_next) -> Response:
    started = perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    route_path = getattr(route, "path", "unmatched")
    HTTP_REQUESTS.labels(request.method, route_path, str(response.status_code)).inc()
    HTTP_LATENCY.labels(request.method, route_path).observe(perf_counter() - started)
    return response
