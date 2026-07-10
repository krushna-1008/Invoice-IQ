import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str | None = os.getenv("ANTHROPIC_MODEL")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    api_keys: str = os.getenv("INVOICEIQ_API_KEYS", "tenant-1:dev-secret,demo-tenant:demo-secret")
    approval_token_secret: str = os.getenv("APPROVAL_TOKEN_SECRET", "dev-approval-token-secret")
    approval_token_ttl_hours: int = int(os.getenv("APPROVAL_TOKEN_TTL_HOURS", "72"))
    extraction_confidence_threshold: float = float(os.getenv("EXTRACTION_CONFIDENCE_THRESHOLD", "0.75"))
    max_pdf_pages: int = int(os.getenv("EXTRACTION_MAX_PDF_PAGES", "5"))
    celery_task_always_eager: bool = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
    celery_queue_enabled: bool = os.getenv("CELERY_QUEUE_ENABLED", "false").lower() == "true"


settings = Settings()
