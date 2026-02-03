from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ToolSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    INTERNAL_TOKEN: str
    API_TOOLS_URL: str


@lru_cache(maxsize=1)
def get_settings() -> ToolSettings:
    return ToolSettings()
