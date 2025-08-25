import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from auto_recon_api.database import get_session


@pytest.mark.asyncio
async def test_get_session_returns_session():
    async for session in get_session():
        assert isinstance(session, AsyncSession)
