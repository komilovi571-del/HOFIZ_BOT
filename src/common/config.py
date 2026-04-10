from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Optional, Union


class Settings(BaseSettings):
    # Telegram Bot
    bot_token: str
    bot_webhook_url: str = ""
    bot_webhook_secret: str = ""
    bot_mode: str = "polling"  # polling | webhook

    # Admin
    admin_ids: List[int] = Field(default_factory=list)

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return v

    # Database (Railway injects DATABASE_URL directly)
    database_url_override: Optional[str] = Field(default=None, alias="DATABASE_URL")
    db_host: str = "postgres"
    db_port: int = 5432
    db_name: str = "hofiz_bot"
    db_user: str = "hofiz"
    db_password: str = ""

    # Redis (Railway injects REDIS_URL directly)
    redis_url_override: Optional[str] = Field(default=None, alias="REDIS_URL")
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # Media Download API
    api_base_url: str = "http://api:8000"
    api_secret_key: str = ""

    # AudD
    audd_api_key: str = ""

    # Genius
    genius_api_key: str = ""

    # Yandex Object Storage
    yandex_storage_key: str = ""
    yandex_storage_secret: str = ""
    yandex_storage_bucket: str = "hofiz-media"
    yandex_storage_region: str = "ru-central1"

    # Backup
    backup_enabled: bool = True
    backup_cron: str = "0 2 * * *"
    backup_retention_days: int = 30

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            # Railway injects postgresql://... — asyncpg schemaga o'tkazamiz
            return self.database_url_override.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            ).replace(
                "postgres://", "postgresql+asyncpg://", 1
            )
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def database_url_sync(self) -> str:
        if self.database_url_override:
            return self.database_url_override.replace("postgres://", "postgresql://", 1)
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def redis_url(self) -> str:
        if self.redis_url_override:
            return self.redis_url_override
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
    }


settings = Settings()  # type: ignore[call-arg]
