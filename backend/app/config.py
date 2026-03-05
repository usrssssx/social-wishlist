from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Social Wishlist API'
    database_url: str = 'postgresql+asyncpg://wishlist:wishlist@db:5432/wishlist'
    jwt_secret: str = 'change-me-in-production'
    jwt_algorithm: str = 'HS256'
    access_token_expire_minutes: int = 60 * 24 * 30
    cors_origins: str = Field(default='http://localhost:3000')
    min_contribution_amount: float = 100.0
    app_base_url: str = 'http://localhost:3001'
    environment: str = 'development'
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    smtp_from_email: str = 'no-reply@wishlist.local'
    verify_email_token_ttl_minutes: int = 60 * 24
    reset_password_token_ttl_minutes: int = 60
    captcha_provider: str = 'turnstile'
    captcha_secret_key: str | None = None
    captcha_verify_url: str = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'

    @field_validator('database_url')
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith('postgresql://'):
            return value.replace('postgresql://', 'postgresql+asyncpg://', 1)
        if value.startswith('postgres://'):
            return value.replace('postgres://', 'postgresql+asyncpg://', 1)
        return value

    def sync_database_url(self) -> str:
        return self.database_url.replace('postgresql+asyncpg://', 'postgresql+psycopg://', 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
