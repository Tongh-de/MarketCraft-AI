from abc import ABC, abstractmethod

from openai import OpenAI

from app.core.config import Settings, get_settings
from app.domain.models import PosterRequest, PosterResponse


class PosterGenerator(ABC):
    @abstractmethod
    def generate(self, request: PosterRequest) -> PosterResponse: ...


class MockPosterGenerator(PosterGenerator):
    def generate(self, request: PosterRequest) -> PosterResponse:
        return PosterResponse(
            status="mock",
            model="mock-poster-generator",
            revised_prompt=request.prompt,
        )


class OpenAIPosterGenerator(PosterGenerator):
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when GENERATION_MODE=openai")
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
        )

    def generate(self, request: PosterRequest) -> PosterResponse:
        result = self.client.images.generate(
            model=self.settings.openai_image_model,
            prompt=request.prompt,
            n=1,
            size=request.size,
            quality=request.quality,
            output_format="png",
        )
        if not result.data or not result.data[0].b64_json:
            raise RuntimeError("image model returned no image data")
        return PosterResponse(
            status="generated",
            model=self.settings.openai_image_model,
            image_base64=result.data[0].b64_json,
            revised_prompt=getattr(result.data[0], "revised_prompt", None),
        )


def get_poster_generator() -> PosterGenerator:
    settings = get_settings()
    if settings.generation_mode == "openai":
        return OpenAIPosterGenerator(settings)
    return MockPosterGenerator()

