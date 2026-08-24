from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.domain.wechat import (
    WechatConfigurationStatus,
    WechatConnectionHealth,
    WechatDraftCreateRequest,
    WechatDraftRecord,
    WechatMaterialUploadResult,
    WechatPublicationStatus,
    WechatPublishRequest,
    WechatReviewRequest,
)
from app.services.wechat import (
    WechatApiError,
    WechatConfigurationError,
    WechatConflictError,
    WechatNotFoundError,
    get_wechat_service,
)

router = APIRouter(prefix="/wechat", tags=["WeChat Official Account"])


def _raise_wechat_error(error: Exception) -> None:
    if isinstance(error, WechatNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, WechatApiError):
        code = status.HTTP_502_BAD_GATEWAY
    elif isinstance(error, WechatConfigurationError):
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        code = status.HTTP_409_CONFLICT
    raise HTTPException(status_code=code, detail=str(error)) from error


@router.get("/configuration", response_model=WechatConfigurationStatus)
def get_configuration() -> WechatConfigurationStatus:
    return get_wechat_service().configuration_status()


@router.post("/health", response_model=WechatConnectionHealth)
def check_connection_health() -> WechatConnectionHealth:
    try:
        return get_wechat_service().check_health()
    except (WechatConfigurationError, WechatApiError) as error:
        _raise_wechat_error(error)


@router.post(
    "/materials/images",
    response_model=WechatMaterialUploadResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_cover_image(file: UploadFile = File(...)) -> WechatMaterialUploadResult:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="only image uploads are supported")
    try:
        return get_wechat_service().upload_cover(
            file.filename or "cover.jpg", await file.read()
        )
    except (WechatConflictError, WechatConfigurationError, WechatApiError) as error:
        _raise_wechat_error(error)


@router.get("/drafts", response_model=list[WechatDraftRecord])
def list_drafts() -> list[WechatDraftRecord]:
    return get_wechat_service().list_drafts()


@router.post(
    "/drafts", response_model=WechatDraftRecord, status_code=status.HTTP_201_CREATED
)
def create_draft(request: WechatDraftCreateRequest) -> WechatDraftRecord:
    try:
        return get_wechat_service().create_draft(request)
    except (WechatConfigurationError, WechatApiError) as error:
        _raise_wechat_error(error)


@router.post("/drafts/{draft_id}/review", response_model=WechatDraftRecord)
def review_draft(
    draft_id: str, request: WechatReviewRequest
) -> WechatDraftRecord:
    try:
        return get_wechat_service().review(draft_id, request)
    except (WechatNotFoundError, WechatConflictError) as error:
        _raise_wechat_error(error)


@router.post("/drafts/{draft_id}/publish", response_model=WechatDraftRecord)
def publish_draft(
    draft_id: str, request: WechatPublishRequest
) -> WechatDraftRecord:
    try:
        return get_wechat_service().publish(draft_id, request)
    except (
        WechatNotFoundError,
        WechatConflictError,
        WechatConfigurationError,
        WechatApiError,
    ) as error:
        _raise_wechat_error(error)


@router.get(
    "/publications/{publish_id}/status", response_model=WechatPublicationStatus
)
def get_publication_status(publish_id: str) -> WechatPublicationStatus:
    try:
        return get_wechat_service().publication_status(publish_id)
    except (WechatConfigurationError, WechatApiError) as error:
        _raise_wechat_error(error)
