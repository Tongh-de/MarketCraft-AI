from abc import ABC, abstractmethod
import base64
import json
import time
from urllib import request as urlrequest
from urllib.error import HTTPError

from openai import OpenAI

from app.core.config import Settings, get_settings
from app.domain.models import PosterRequest, PosterResponse
from app.telemetry import traced


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
        return self._generate(request)

    @traced("image.openai.generate", run_type="llm")
    def _generate(self, request: PosterRequest) -> PosterResponse:
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


class WanxPosterGenerator(PosterGenerator):
    """DashScope/Tongyi Wanx text-to-image adapter."""

    def __init__(self, settings: Settings) -> None:
        if not settings.dashscope_api_key:
            raise ValueError("DASHSCOPE_API_KEY is required when IMAGE_GENERATION_MODE=wanx")
        self.settings = settings

    def generate(self, request: PosterRequest) -> PosterResponse:
        return self._generate(request)

    @traced("image.wanx.generate", run_type="llm")
    def _generate(self, request: PosterRequest) -> PosterResponse:
        task_id = self._submit_task(request)
        result_url = self._wait_for_result(task_id)
        image_base64 = self._download_base64(result_url)
        return PosterResponse(
            status="generated",
            model=self.settings.wanx_model,
            image_base64=image_base64,
            revised_prompt=request.prompt,
        )

    def _submit_task(self, request: PosterRequest) -> str:
        image_prompt: dict | list[dict[str, str]]
        if self.settings.wanx_model.startswith("wan2."):
            image_prompt = [{"role": "user", "content": [{"text": request.prompt}]}]
            input_payload = {"messages": image_prompt}
        else:
            input_payload = {"prompt": request.prompt}
        payload = {
            "model": self.settings.wanx_model,
            "input": input_payload,
            "parameters": {
                "size": self._size(request.size),
                "n": 1,
                "prompt_extend": True,
                "watermark": False,
                "negative_prompt": "",
            },
        }
        body = self._request_json(
            "POST",
            f"{self.settings.wanx_base_url.rstrip('/')}/services/aigc/image-generation/generation",
            payload,
            extra_headers={"X-DashScope-Async": "enable"},
        )
        task_id = body.get("output", {}).get("task_id") or body.get("task_id")
        if not task_id:
            raise RuntimeError(f"Wanx did not return task_id: {body}")
        return str(task_id)

    def _wait_for_result(self, task_id: str) -> str:
        deadline = time.monotonic() + self.settings.wanx_timeout_seconds
        status_url = f"{self.settings.wanx_base_url.rstrip('/')}/tasks/{task_id}"
        last_body: dict | None = None
        while time.monotonic() < deadline:
            body = self._request_json("GET", status_url)
            last_body = body
            output = body.get("output", body)
            status = str(output.get("task_status", output.get("status", ""))).upper()
            if status in {"SUCCEEDED", "SUCCESS", "COMPLETED"}:
                result_url = self._extract_result_url(output)
                if result_url:
                    return result_url
                raise RuntimeError(f"Wanx task succeeded without image URL: {body}")
            if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                message = output.get("message") or output.get("task_metrics") or body
                raise RuntimeError(f"Wanx task {status.lower()}: {message}")
            time.sleep(self.settings.wanx_poll_interval_seconds)
        raise TimeoutError(f"Wanx task timed out: {last_body}")

    def _extract_result_url(self, output: dict) -> str | None:
        for item in output.get("results", []):
            if isinstance(item, dict) and item.get("url"):
                return str(item["url"])
        for choice in output.get("choices", []):
            message = choice.get("message", {}) if isinstance(choice, dict) else {}
            for item in message.get("content", []):
                if isinstance(item, dict) and item.get("image"):
                    return str(item["image"])
        for key in ("url", "image_url"):
            if output.get(key):
                return str(output[key])
        return None

    def _download_base64(self, image_url: str) -> str:
        with urlrequest.urlopen(image_url, timeout=self.settings.openai_timeout_seconds) as response:
            return base64.b64encode(response.read()).decode("ascii")

    def _request_json(
        self,
        method: str,
        url: str,
        payload: dict | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
            **(extra_headers or {}),
        }
        req = urlrequest.Request(url, data=data, headers=headers, method=method)
        try:
            with urlrequest.urlopen(req, timeout=self.settings.openai_timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Wanx API HTTP {exc.code}: {detail}") from exc

    def _size(self, request_size: str) -> str:
        width, height = (int(value) for value in request_size.split("x", maxsplit=1))
        if width >= 1280 and height >= 1280:
            return f"{width}*{height}"
        return self.settings.wanx_size


def get_poster_generator() -> PosterGenerator:
    settings = get_settings()
    if settings.image_generation_mode == "openai":
        return OpenAIPosterGenerator(settings)
    if settings.image_generation_mode == "wanx":
        return WanxPosterGenerator(settings)
    return MockPosterGenerator()
