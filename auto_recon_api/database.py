from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from auto_recon_api.db.session import get_db, get_sessionmaker

SessionLocal: async_sessionmaker[AsyncSession] = get_sessionmaker()


async def get_session():
    async for session in get_db():
        yield session
