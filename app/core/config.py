from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MarketCraft AI"
    app_env: str = "development"
    log_level: str = "INFO"
    generation_mode: Literal["mock", "openai"] = "mock"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_image_model: str = "gpt-image-2"
    openai_timeout_seconds: float = 60
    retrieval_mode: Literal["memory", "milvus"] = "memory"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_dim: int = 512
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = ""
    milvus_collection: str = "marketcraft_brand_knowledge"
    persistence_mode: Literal["memory", "database"] = "memory"
    database_url: str = "sqlite+pysqlite:///./marketcraft.db"
    idempotency_mode: Literal["memory", "redis"] = "memory"
    redis_url: str = "redis://localhost:6379/0"
    idempotency_ttl_seconds: int = 604800
    upload_dir: str = "./data/uploads"
    max_upload_bytes: int = 10485760

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
