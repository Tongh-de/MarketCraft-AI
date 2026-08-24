import os
from collections.abc import Callable
from typing import TypeVar

from langsmith import traceable

from app.core.config import get_settings


F = TypeVar("F", bound=Callable)


def configure_langsmith() -> None:
    settings = get_settings()
    if not settings.langsmith_tracing:
        return
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)
    os.environ.setdefault("LANGSMITH_ENDPOINT", settings.langsmith_endpoint)
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)


def traced(name: str, run_type: str = "chain") -> Callable[[F], F]:
    return traceable(name=name, run_type=run_type)  # type: ignore[return-value]
