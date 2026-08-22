from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.domain.performance import (
    DemoSnapshotRequest,
    PerformanceAnalysisReport,
    PerformanceAnalysisRequest,
    PerformanceSnapshot,
    PerformanceSnapshotRequest,
)
from app.observability import PERFORMANCE_ANALYSES, PERFORMANCE_SNAPSHOTS
from app.services.performance import (
    PerformanceConflictError,
    PerformanceNotFoundError,
    get_commerce_performance_service,
)

router = APIRouter(prefix="/performance", tags=["commerce performance feedback"])


def _raise_http_error(error: Exception) -> None:
    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(error, PerformanceNotFoundError)
        else status.HTTP_409_CONFLICT
    )
    raise HTTPException(status_code=code, detail=str(error)) from error


@router.post(
    "/snapshots",
    response_model=PerformanceSnapshot,
    status_code=status.HTTP_201_CREATED,
)
def create_performance_snapshot(
    request: PerformanceSnapshotRequest,
) -> PerformanceSnapshot:
    try:
        snapshot = get_commerce_performance_service().create_snapshot(request)
        PERFORMANCE_SNAPSHOTS.labels(snapshot.platform.value, snapshot.source.value).inc()
        return snapshot
    except (PerformanceNotFoundError, PerformanceConflictError) as error:
        _raise_http_error(error)


@router.get("/snapshots", response_model=list[PerformanceSnapshot])
def list_performance_snapshots(
    package_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[PerformanceSnapshot]:
    return get_commerce_performance_service().list_snapshots(package_id, limit)


@router.post(
    "/packages/{package_id}/demo-snapshots",
    response_model=list[PerformanceSnapshot],
    status_code=status.HTTP_201_CREATED,
)
def create_demo_snapshots(
    package_id: UUID, request: DemoSnapshotRequest
) -> list[PerformanceSnapshot]:
    try:
        snapshots = get_commerce_performance_service().create_demo_snapshots(
            package_id, request.actor
        )
        for snapshot in snapshots:
            PERFORMANCE_SNAPSHOTS.labels(
                snapshot.platform.value, snapshot.source.value
            ).inc()
        return snapshots
    except (PerformanceNotFoundError, PerformanceConflictError) as error:
        _raise_http_error(error)


@router.post(
    "/packages/{package_id}/analyze",
    response_model=PerformanceAnalysisReport,
    status_code=status.HTTP_201_CREATED,
)
def analyze_performance(
    package_id: UUID, request: PerformanceAnalysisRequest
) -> PerformanceAnalysisReport:
    try:
        report = get_commerce_performance_service().analyze(package_id, request.actor)
        PERFORMANCE_ANALYSES.labels("completed", str(report.mock).lower()).inc()
        return report
    except (PerformanceNotFoundError, PerformanceConflictError) as error:
        PERFORMANCE_ANALYSES.labels("failed", "true").inc()
        _raise_http_error(error)


@router.get("/reports", response_model=list[PerformanceAnalysisReport])
def list_performance_reports(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[PerformanceAnalysisReport]:
    return get_commerce_performance_service().list_reports(limit)


@router.get("/reports/{report_id}", response_model=PerformanceAnalysisReport)
def get_performance_report(report_id: UUID) -> PerformanceAnalysisReport:
    try:
        return get_commerce_performance_service().get_report(report_id)
    except PerformanceNotFoundError as error:
        _raise_http_error(error)
