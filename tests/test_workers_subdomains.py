from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from auto_recon_api.workers import subdomains as sub_mod
from auto_recon_api.workers.subdomains import (
    _init_job_meta,  # noqa: PLC2701
    _job_mark_done,  # noqa: PLC2701
    _job_mark_failed,  # noqa: PLC2701
    _job_set_current,  # noqa: PLC2701
    _job_touch,  # noqa: PLC2701
    _normalize_domain_error,  # noqa: PLC2701
    _short_err,  # noqa: PLC2701
)


class DummyJob:
    def __init__(self):
        self.meta = {}
        self.saved = 0

    def save_meta(self):
        self.saved += 1


def test_short_err_truncates_and_pretty():
    limiter = 50
    e = Exception('x' * 400)
    out = _short_err(e, limit=limiter)
    assert isinstance(out, str)
    assert len(out) <= limiter


def test_normalize_domain_error_cases():
    # ReadTimeout
    e = httpx.ReadTimeout('timeout')
    assert 'recon_tool' in _normalize_domain_error(e)

    # ConnectError
    e = httpx.ConnectError('connect')
    assert 'ConnectError' in _normalize_domain_error(e)

    # HTTPStatusError with response
    class DummyResp:
        status_code = 502
        text = 'bad body'

    # HTTPStatusError expects (message, request, response)
    e = httpx.HTTPStatusError('err', request=None, response=DummyResp())
    s = _normalize_domain_error(e)
    assert 'HTTP 502' in s

    # RequestError
    e = httpx.RequestError('boom')
    assert 'RequestError' in _normalize_domain_error(e)

    # generic
    e = Exception('boom')
    assert isinstance(_normalize_domain_error(e), str)


def test_init_and_job_helpers():
    job = DummyJob()
    n = 2
    _init_job_meta(job, [1, 2])
    assert job.meta['total'] == n
    before = job.meta['updated_at']
    n_1 = 7
    n_2 = 9

    _job_touch(job)
    assert job.meta['updated_at'] != before

    _job_set_current(job, n_1, 'example.com')
    assert job.meta['current_domain_id'] == n_1

    _job_mark_done(job, n_1)
    assert n_1 in job.meta['done_domain_ids']

    _job_mark_failed(job, n_2, 'msg')
    assert n_2 in job.meta['failed_domain_ids']
    assert 'domain_id=9' in job.meta['last_error']


@pytest.mark.asyncio
async def test_process_one_domain_not_found(monkeypatch):
    # session.scalar returns None => early return
    class S:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def scalar(self, *a, **k):  # noqa: PLR6301
            return None

        def begin(self):  # noqa: PLR6301
            class Tx:
                async def __aenter__(self):
                    return None

                async def __aexit__(self, *a):
                    return False

            return Tx()

    monkeypatch.setattr(sub_mod, 'get_sessionmaker', lambda: (lambda: S()))  # noqa: PLW0108

    # Using a real httpx client is harmless here as it won't be called
    await sub_mod._process_one_domain(
        domain_id=123,
        job_id=None,
        client=AsyncMock(),
        semaphore=asyncio.Semaphore(1)
    )


@pytest.mark.asyncio
async def test_process_one_domain_success(monkeypatch):
    # Build a fake Domain object
    class DomainObj:
        def __init__(self):
            self.id = 10
            self.name = 'example.com'
            self.status = 'pending'

    domain = DomainObj()

    # Session that returns the domain, and records added Subdomains
    class Sess:
        def __init__(self):
            self.added = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def scalar(self, *a, **k):  # noqa: PLR6301
            # first call for domain
            return domain

        def begin(self):  # noqa: PLR6301
            class Tx:
                async def __aenter__(self):
                    return None

                async def __aexit__(self, *a):
                    return False

            return Tx()

        def add(self, o):
            self.added.append(o)

    monkeypatch.setattr(sub_mod, 'get_sessionmaker', lambda: (lambda: Sess()))  # noqa: PLW0108

    # Fake HTTP client that returns subdomains
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):  # noqa: PLR6301
            return {'subdomains': [{'host': 'a.example.com', 'ip': '1.2.3.4'}]}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, params=None):  # noqa: PLR6301
            return FakeResp()

    client = FakeClient()

    await sub_mod._process_one_domain(
        domain_id=10,
        job_id=None,
        client=client,
        semaphore=asyncio.Semaphore(1)
    )

    # domain object should be marked done and subdomain added
    assert domain.status == 'done'


@pytest.mark.asyncio
async def test_find_subdomains_marks_job_meta(monkeypatch):
    # patch _process_one_domain to succeed for id 1 and fail for id 2
    async def proc_success(*a, **k):
        return None

    async def proc_fail(*a, **k):
        raise RuntimeError('fail')

    async def proc_wrapper(domain_id, **kw):
        if domain_id == 1:
            return await proc_success()
        raise RuntimeError('fail')

    monkeypatch.setattr(sub_mod, '_process_one_domain', proc_wrapper)

    job = DummyJob()
    job.id = 'job-1'
    monkeypatch.setattr(sub_mod, 'get_current_job', lambda: job)

    # run
    await sub_mod.find_subdomains([1, 2], concurrency=2)

    assert job.meta['done'] >= 1
    assert job.meta['failed'] >= 1
    assert 'finished_at' in job.meta


def test_run_find_subdomains_uses_asyncio_run(monkeypatch):
    called = {}

    def fake_run(coro, *a, **k):
        called['ok'] = True

    monkeypatch.setattr('asyncio.run', fake_run)

    sub_mod.run_find_subdomains([1, 2])
    assert called.get('ok')
