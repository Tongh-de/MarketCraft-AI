from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MarketCraft AI"
    app_env: str = "development"
    log_level: str = "INFO"
    generation_mode: Literal["mock", "openai", "openai_compatible"] = "mock"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_image_model: str = "gpt-image-2"
    openai_timeout_seconds: float = 60
    image_generation_mode: Literal["mock", "openai", "wanx"] = "mock"
    dashscope_api_key: str | None = None
    wanx_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    wanx_model: str = "wan2.6-t2i"
    wanx_size: str = "1280*1280"
    wanx_poll_interval_seconds: float = 2
    wanx_timeout_seconds: float = 120
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "marketcraft-ai-local"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
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
    feishu_approval_mode: Literal["mock", "webhook"] = "mock"
    feishu_webhook_url: str | None = None
    feishu_webhook_secret: str | None = None
    feishu_approval_base_url: str | None = None
    feishu_request_timeout_seconds: float = 10
    wechat_mode: Literal["mock", "live"] = "mock"
    wechat_app_id: str | None = None
    wechat_app_secret: str | None = None
    wechat_api_base: str = "https://api.weixin.qq.com"
    wechat_timeout_seconds: float = 20
    wechat_max_material_bytes: int = 10_485_760

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
