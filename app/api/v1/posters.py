from fastapi import APIRouter

from app.domain.models import PosterRequest, PosterResponse
from app.services.poster import get_poster_generator

router = APIRouter(prefix="/posters", tags=["posters"])


@router.post("/generate", response_model=PosterResponse)
def generate_poster(request: PosterRequest) -> PosterResponse:
    return get_poster_generator().generate(request)

