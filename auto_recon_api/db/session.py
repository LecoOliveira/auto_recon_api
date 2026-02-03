from __future__ import annotations

import logging
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from auto_recon_api.core.config import get_settings

log = logging.getLogger(__name__)

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _init_engine_and_sessionmaker() -> tuple[
    object, async_sessionmaker[AsyncSession]
]:
    global _engine, _sessionmaker  # noqa: PLW0603
    if _engine is None or _sessionmaker is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL, pool_pre_ping=True
        )
        _sessionmaker = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _engine, _sessionmaker


async def get_db() -> AsyncIterator[AsyncSession]:
    _, session_maker = _init_engine_and_sessionmaker()
    async with session_maker() as session:
        yield session


async def close_engine() -> None:
    global _engine, _sessionmaker  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    _, session_maker = _init_engine_and_sessionmaker()
    return session_maker
