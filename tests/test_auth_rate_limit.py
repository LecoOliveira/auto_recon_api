from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from auto_recon_api.api.v1.endpoints.auth import maybe_rate_limit


@pytest.mark.asyncio
async def test_maybe_rate_limit_skips_when_TESTING_set(monkeypatch):
    monkeypatch.setenv('TESTING', '1')
    req = Request({'type': 'http', 'method': 'GET', 'path': '/'})
    resp = Response()

    # should return early and not raise
    assert await maybe_rate_limit(req, resp) is None


@pytest.mark.asyncio
async def test_maybe_rate_limit_calls_limiter_when_not_testing(monkeypatch):
    monkeypatch.delenv('TESTING', raising=False)
    req = Request({'type': 'http', 'method': 'GET', 'path': '/'})
    resp = Response()

    async_mock = AsyncMock()
    with patch('auto_recon_api.api.v1.endpoints.auth._limiter', new=async_mock):  # noqa: E501
        await maybe_rate_limit(req, resp)
        assert async_mock.await_count == 1
