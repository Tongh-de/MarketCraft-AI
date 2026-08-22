from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, status

from app.domain.models import (
    ApprovalDecisionRequest,
    CampaignLifecycle,
    CampaignPackage,
    CampaignRequest,
    CampaignRevisionRequest,
    PublishBatchResult,
    PublishRequest,
    ReviewSubmitRequest,
)
from app.services.lifecycle import (
    LifecycleConflictError,
    LifecycleNotFoundError,
    get_lifecycle_service,
)
from app.workflows.campaign import run_campaign

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("/generate", response_model=CampaignPackage)
def generate_campaign(
    request: CampaignRequest,
    x_thread_id: str | None = Header(default=None),
    x_actor: str = Header(default="content-agent"),
) -> CampaignPackage:
    thread_id = x_thread_id or str(uuid4())
    package = run_campaign(request, thread_id)
    get_lifecycle_service().create_draft(package, x_actor)
    return package


def _raise_http_error(error: Exception) -> None:
    if isinstance(error, LifecycleNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/{campaign_id}", response_model=CampaignLifecycle)
def get_campaign_lifecycle(campaign_id: UUID) -> CampaignLifecycle:
    try:
        return get_lifecycle_service().get(campaign_id)
    except LifecycleNotFoundError as error:
        _raise_http_error(error)


@router.post("/{campaign_id}/versions", response_model=CampaignLifecycle)
def revise_campaign(
    campaign_id: UUID, request: CampaignRevisionRequest
) -> CampaignLifecycle:
    try:
        return get_lifecycle_service().revise(campaign_id, request)
    except (LifecycleNotFoundError, LifecycleConflictError) as error:
        _raise_http_error(error)


@router.post("/{campaign_id}/submit-review", response_model=CampaignLifecycle)
def submit_campaign_review(
    campaign_id: UUID, request: ReviewSubmitRequest
) -> CampaignLifecycle:
    try:
        return get_lifecycle_service().submit_review(campaign_id, request.actor)
    except (LifecycleNotFoundError, LifecycleConflictError) as error:
        _raise_http_error(error)


@router.post("/{campaign_id}/decision", response_model=CampaignLifecycle)
def decide_campaign(
    campaign_id: UUID, request: ApprovalDecisionRequest
) -> CampaignLifecycle:
    try:
        return get_lifecycle_service().decide(campaign_id, request)
    except (LifecycleNotFoundError, LifecycleConflictError) as error:
        _raise_http_error(error)


@router.post("/{campaign_id}/publish", response_model=PublishBatchResult)
def publish_campaign(campaign_id: UUID, request: PublishRequest) -> PublishBatchResult:
    try:
        return get_lifecycle_service().publish(campaign_id, request)
    except (LifecycleNotFoundError, LifecycleConflictError) as error:
        _raise_http_error(error)
