from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    ENV: str = 'dev'
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SUBDOMAIN_URL: str
    INTERNAL_TOKEN: str
    API_TOOLS_URL: str

    CORS_ORIGINS: str = 'http://localhost:3000,http://localhost:5173'

    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(',') if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
