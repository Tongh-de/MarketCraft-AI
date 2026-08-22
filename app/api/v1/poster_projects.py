from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.domain.creation import PosterProject, PosterProjectRequest, PosterProjectUpdate
from app.services.poster_projects import (
    PosterProductImageNotFoundError,
    PosterProjectNotFoundError,
    get_poster_project_service,
)

router = APIRouter(prefix="/poster-projects", tags=["editable poster projects"])


def _raise_not_found(error: Exception) -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("", response_model=PosterProject, status_code=status.HTTP_201_CREATED)
def create_poster_project(request: PosterProjectRequest) -> PosterProject:
    try:
        return get_poster_project_service().create(request)
    except (PosterProductImageNotFoundError, PosterProjectNotFoundError) as error:
        _raise_not_found(error)


@router.get("", response_model=list[PosterProject])
def list_poster_projects(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[PosterProject]:
    return get_poster_project_service().list_projects(limit)


@router.get("/{project_id}", response_model=PosterProject)
def get_poster_project(project_id: UUID) -> PosterProject:
    try:
        return get_poster_project_service().get(project_id)
    except PosterProjectNotFoundError as error:
        _raise_not_found(error)


@router.put("/{project_id}", response_model=PosterProject)
def update_poster_project(
    project_id: UUID, request: PosterProjectUpdate
) -> PosterProject:
    try:
        return get_poster_project_service().update(project_id, request)
    except PosterProjectNotFoundError as error:
        _raise_not_found(error)


@router.get("/{project_id}/preview.svg", include_in_schema=False)
def preview_poster_project(project_id: UUID, download: bool = False) -> Response:
    try:
        svg = get_poster_project_service().render_svg(project_id)
    except PosterProjectNotFoundError as error:
        _raise_not_found(error)
    headers = {"X-Content-Type-Options": "nosniff"}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="poster-{project_id}.svg"'
    return Response(content=svg, media_type="image/svg+xml", headers=headers)
