from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    PROJECT_NAME: str = "Contract Lifecycle & Approval Management"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"

    SECRET_KEY: str = "change-me-in-production-please-use-a-real-secret-key-32chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "contracts"
    POSTGRES_PASSWORD: str = "contracts"
    POSTGRES_DB: str = "contracts"

    DATABASE_URL: str = "postgresql://contracts:contracts@localhost:5432/contracts"

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_PATH: str = "./storage"
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "contracts"

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ]

    LLM_PROVIDER: str = "heuristic"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MODEL_ENDPOINT: str = ""

    AZURE_AI_ENABLED: bool = False
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str = ""
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str = ""
    AZURE_DOCUMENT_INTELLIGENCE_MODEL: str = "prebuilt-layout"
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT_NAME: str = "gpt-4o"
    AZURE_OPENAI_API_VERSION: str = "2024-02-01-preview"

    EMBEDDING_MODEL: str = "local-tfidf"
    EMBEDDING_DIM: int = 384

    AI_RISK_RULE_WEIGHT: float = 0.45
    AI_RISK_NLP_WEIGHT: float = 0.30
    AI_RISK_LLM_WEIGHT: float = 0.25

    DEFAULT_SLA_HOURS: int = 48

    RATE_LIMIT_PER_MIN: int = 120

    @property
    def sqlalchemy_database_uri(self) -> str:
        return self.DATABASE_URL


settings = Settings()
