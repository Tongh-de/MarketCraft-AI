from fastapi import APIRouter, HTTPException, status

from app.domain.platform_extensions import (
    ExternalServiceConnector,
    ExternalServiceCreateRequest,
    ExternalServiceHealthResult,
    ExternalServiceUpdateRequest,
    SkillAutoEditRequest,
    SkillInvocationPlan,
    SkillInvocationRequest,
    SkillPluginCreateRequest,
    SkillPluginManifest,
    SkillPluginStatusRequest,
    SkillPluginUpdateRequest,
)
from app.services.platform_extensions import (
    PlatformExtensionConflictError,
    PlatformExtensionNotFoundError,
    get_external_service_connector_service,
    get_skill_plugin_service,
)

router = APIRouter(prefix="/platform", tags=["skills and external services"])


def _raise_http_error(error: Exception) -> None:
    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(error, PlatformExtensionNotFoundError)
        else status.HTTP_409_CONFLICT
    )
    raise HTTPException(status_code=code, detail=str(error)) from error


@router.get("/skill-plugins", response_model=list[SkillPluginManifest])
def list_skill_plugins() -> list[SkillPluginManifest]:
    return get_skill_plugin_service().list_plugins()


@router.post(
    "/skill-plugins",
    response_model=SkillPluginManifest,
    status_code=status.HTTP_201_CREATED,
)
def create_skill_plugin(request: SkillPluginCreateRequest) -> SkillPluginManifest:
    try:
        return get_skill_plugin_service().create(request)
    except PlatformExtensionConflictError as error:
        _raise_http_error(error)


@router.get("/skill-plugins/{plugin_id}", response_model=SkillPluginManifest)
def get_skill_plugin(plugin_id: str) -> SkillPluginManifest:
    try:
        return get_skill_plugin_service().get(plugin_id)
    except PlatformExtensionNotFoundError as error:
        _raise_http_error(error)


@router.put("/skill-plugins/{plugin_id}", response_model=SkillPluginManifest)
def update_skill_plugin(
    plugin_id: str, request: SkillPluginUpdateRequest
) -> SkillPluginManifest:
    try:
        return get_skill_plugin_service().update(plugin_id, request)
    except (PlatformExtensionNotFoundError, PlatformExtensionConflictError) as error:
        _raise_http_error(error)


@router.post(
    "/skill-plugins/{plugin_id}/auto-edit", response_model=SkillPluginManifest
)
def auto_edit_skill_plugin(
    plugin_id: str, request: SkillAutoEditRequest
) -> SkillPluginManifest:
    try:
        return get_skill_plugin_service().auto_edit(plugin_id, request)
    except (PlatformExtensionNotFoundError, PlatformExtensionConflictError) as error:
        _raise_http_error(error)


@router.post(
    "/skill-plugins/{plugin_id}/status", response_model=SkillPluginManifest
)
def set_skill_plugin_status(
    plugin_id: str, request: SkillPluginStatusRequest
) -> SkillPluginManifest:
    try:
        return get_skill_plugin_service().set_status(plugin_id, request)
    except (PlatformExtensionNotFoundError, PlatformExtensionConflictError) as error:
        _raise_http_error(error)


@router.post(
    "/skill-plugins/{plugin_id}/invoke", response_model=SkillInvocationPlan
)
def invoke_skill_plugin(
    plugin_id: str, request: SkillInvocationRequest
) -> SkillInvocationPlan:
    try:
        return get_skill_plugin_service().invoke(plugin_id, request)
    except (PlatformExtensionNotFoundError, PlatformExtensionConflictError) as error:
        _raise_http_error(error)


@router.get("/external-services", response_model=list[ExternalServiceConnector])
def list_external_services() -> list[ExternalServiceConnector]:
    return get_external_service_connector_service().list_connectors()


@router.post(
    "/external-services",
    response_model=ExternalServiceConnector,
    status_code=status.HTTP_201_CREATED,
)
def create_external_service(
    request: ExternalServiceCreateRequest,
) -> ExternalServiceConnector:
    try:
        return get_external_service_connector_service().create(request)
    except PlatformExtensionConflictError as error:
        _raise_http_error(error)


@router.put(
    "/external-services/{service_id}", response_model=ExternalServiceConnector
)
def update_external_service(
    service_id: str, request: ExternalServiceUpdateRequest
) -> ExternalServiceConnector:
    try:
        return get_external_service_connector_service().update(service_id, request)
    except (PlatformExtensionNotFoundError, PlatformExtensionConflictError) as error:
        _raise_http_error(error)


@router.post(
    "/external-services/{service_id}/health",
    response_model=ExternalServiceHealthResult,
)
def check_external_service_health(service_id: str) -> ExternalServiceHealthResult:
    try:
        return get_external_service_connector_service().check_health(service_id)
    except PlatformExtensionNotFoundError as error:
        _raise_http_error(error)
