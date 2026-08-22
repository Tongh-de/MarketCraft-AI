from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.domain.listings import (
    ListingDecisionRequest,
    ListingPackageRequest,
    ListingPublishBatchResult,
    ListingPublishRequest,
    ListingReviewRequest,
    ProductListingPackage,
)
from app.observability import LISTING_PUBLICATIONS
from app.services.listing_packages import (
    ListingPackageConflictError,
    ListingPackageNotFoundError,
    get_listing_package_service,
)

router = APIRouter(prefix="/listing-packages", tags=["multi-platform listings"])


def _raise_http_error(error: Exception) -> None:
    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(error, ListingPackageNotFoundError)
        else status.HTTP_409_CONFLICT
    )
    raise HTTPException(status_code=code, detail=str(error)) from error


@router.post("", response_model=ProductListingPackage, status_code=status.HTTP_201_CREATED)
def create_listing_package(request: ListingPackageRequest) -> ProductListingPackage:
    try:
        return get_listing_package_service().create(request)
    except (ListingPackageNotFoundError, ListingPackageConflictError) as error:
        _raise_http_error(error)


@router.get("", response_model=list[ProductListingPackage])
def list_listing_packages(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ProductListingPackage]:
    return get_listing_package_service().list_packages(limit)


@router.get("/{package_id}", response_model=ProductListingPackage)
def get_listing_package(package_id: UUID) -> ProductListingPackage:
    try:
        return get_listing_package_service().get(package_id)
    except ListingPackageNotFoundError as error:
        _raise_http_error(error)


@router.post("/{package_id}/submit-review", response_model=ProductListingPackage)
def submit_listing_review(
    package_id: UUID, request: ListingReviewRequest
) -> ProductListingPackage:
    try:
        return get_listing_package_service().submit_review(package_id, request.actor)
    except (ListingPackageNotFoundError, ListingPackageConflictError) as error:
        _raise_http_error(error)


@router.post("/{package_id}/decision", response_model=ProductListingPackage)
def decide_listing_package(
    package_id: UUID, request: ListingDecisionRequest
) -> ProductListingPackage:
    try:
        return get_listing_package_service().decide(package_id, request)
    except (ListingPackageNotFoundError, ListingPackageConflictError) as error:
        _raise_http_error(error)


@router.post("/{package_id}/publish", response_model=ListingPublishBatchResult)
def publish_listing_package(
    package_id: UUID, request: ListingPublishRequest
) -> ListingPublishBatchResult:
    try:
        result = get_listing_package_service().publish(package_id, request)
        for item in result.results:
            LISTING_PUBLICATIONS.labels(item.platform.value, item.status).inc()
        return result
    except (ListingPackageNotFoundError, ListingPackageConflictError) as error:
        _raise_http_error(error)
