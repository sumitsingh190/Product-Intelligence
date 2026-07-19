from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file= ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    #Application
    app_env : Literal["development", "staging", "production"] = "development"
    app_name : str = "ProductOS AI"
    app_version : str = "0.1.0"
    secret_key: str = "sumit_singh@prakash_1313"
    debug: bool = True
    log_level: str = "INFO"

    # Backend API
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_workers: int = 4
    api_v1_prefix: str = "/api/v1"
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "productos_ai"
    postgres_user: str = "postgres"
    postgres_password: str = "Sumit@1313"
    # database_url: str = "postgresql+asyncpg://postgres:Sumit%401313@localhost:5432/productos_ai"
    # database_url_sync: str = "postgresql://postgres:Sumit%401313@localhost:5432/productos_ai"
    db_pool_size: int = 20
    db_max_overflow: int = 40
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    @computed_field
    @property
    def database_url(self) -> str:
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    @computed_field
    @property
    def database_url_sync(self) -> str:
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


    #Redis
    redis_url : str = "redis://localhost:6379/0"
    cache_ttl_short: int = 300
    cache_ttl_medium: int = 3600
    cache_ttl_long: int = 86400


    #Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    #Groq LLM
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_max_tokens: int = 8192
    groq_temperature: float = 0.1
    groq_timeout_seconds: int = 60


    #Google AI Studio (embeddings)
    google_api_key: str= ""
    embedding_model: str = "models/text-embedding-004"
    embedding_dimension: int = 768
    embedding_task_type: str = "RETRIEVAL_DOCUMENT"
    embedding_batch_size: int = 100


    #Langsmith
    langchain_tracing_v2: bool = False
    langchain_api_key : str = ""
    langchain_project: str = "productos-ai"


    #Agent memory
    agent_memory_enabled: bool = True
    agent_checkpoint_redis_url : str = "redis://localhost:6379/1"

    # DuckDB
    duckdb_path : str = "./data/analytics.duckdb"
    duckdb_threads : int = 4
    duckdb_memory_limit: str = "4GB"
    etl_sync_interval: int = 3600


    # JWT
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int =7
    jwt_secret_key : str = "sumit_singh_prakash_1313"

    #Observability
    otel_enabled: bool = False
    otel_service_name : str = "productos-ai-backend"
    otel_exporter_otlp_endpoint : str = "http://localhost:4317"
    prometheus_enabled : bool = True

    @computed_field
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    #Feature Flags
    feature_competitor_intelligence : bool = True
    feature_auto_prd_generation : bool = True
    feature_sprint_planning : bool = True
    feature_executive_reports : bool = True
    feature_semantic_search : bool = True
    feature_rag_reranker : bool = True
    feature_strategy_validator : bool = True
    feature_reconsider_rejected : bool = True
    feature_email_digests : bool = True
    feature_slack_notifications : bool = True

    #Notifications (stub when keys are empty)
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "noreply@productos.ai"
    slack_webhook_url: str= ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings= get_settings()