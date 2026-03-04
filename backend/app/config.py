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

    @field_validator('database_url')
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith('postgresql://'):
            return value.replace('postgresql://', 'postgresql+asyncpg://', 1)
        if value.startswith('postgres://'):
            return value.replace('postgres://', 'postgresql+asyncpg://', 1)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
