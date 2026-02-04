from __future__ import annotations

from http import HTTPStatus

import pytest
from fastapi import HTTPException
from rq.exceptions import NoSuchJobError

from auto_recon_api.api.v1.endpoints.jobs import JobResponse, get_job


class FakeJob:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 'j1')
        self.origin = kwargs.get('origin', 'subdomains')
        self.meta = kwargs.get('meta', {})
        self.result = kwargs.get('result', {})
        self.enqueued_at = kwargs.get('enqueued_at')
        self.started_at = kwargs.get('started_at')
        self.ended_at = kwargs.get('ended_at')
        self.exc_info = kwargs.get('exc_info')
        self._status = kwargs.get('status', 'running')

    def get_status(self):
        return self._status


@pytest.mark.asyncio
async def test_get_job_not_found(monkeypatch, session, user):
    def raising_fetch(jid, connection=None):
        raise NoSuchJobError()

    monkeypatch.setattr(
        'auto_recon_api.api.v1.endpoints.jobs.Job.fetch',
        raising_fetch,
    )

    with pytest.raises(HTTPException) as exc:
        await get_job('not-exist', session, user)

    assert exc.value.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_get_job_fetch_error(monkeypatch, session, user):
    def fake_fetch(jid, connection=None):
        raise RuntimeError('boom')

    monkeypatch.setattr(
        'auto_recon_api.api.v1.endpoints.jobs.Job.fetch',
        fake_fetch,
    )

    with pytest.raises(HTTPException) as exc:
        await get_job('any', session, user)

    assert exc.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.asyncio
async def test_get_job_subdomains_returns_domains(
    monkeypatch, session, user, domain
):
    # fake job meta with one domain id
    meta = {
        'domain_ids': [domain.id],
        'total': 1,
        'done': 1,
        'failed': 0,
    }
    job = FakeJob(
        id='j2',
        origin='subdomains',
        meta=meta,
        status='finished',
    )

    def return_job(jid, connection=None):
        return job

    monkeypatch.setattr(
        'auto_recon_api.api.v1.endpoints.jobs.Job.fetch',
        return_job,
    )

    out = await get_job('j2', session, user)
    assert isinstance(out, JobResponse)
    assert out.type == 'subdomains'
    # domain info should be present
    assert len(out.domains) == 1
    assert out.domains[0].id == domain.id


@pytest.mark.asyncio
async def test_get_job_urls_progress(monkeypatch, session, user):
    meta = {}
    result = {'seen': 5, 'inserted': 3, 'errors': 0}
    job = FakeJob(
        id='j3',
        origin='urls',
        meta=meta,
        result=result,
        status='running',
    )

    def return_job(jid, connection=None):
        return job

    monkeypatch.setattr(
        'auto_recon_api.api.v1.endpoints.jobs.Job.fetch',
        return_job,
    )

    out = await get_job('j3', session, user)
    assert isinstance(out, JobResponse)
    assert out.type == 'urls'
    assert out.progress == pytest.approx(3 / 5)


@pytest.mark.asyncio
async def test_get_job_subdomains_failed_progress_none(
    monkeypatch, session, user
):
    meta = {'total': 10, 'done': 0, 'failed': 1, 'domain_ids': []}
    job = FakeJob(id='j4', origin='subdomains', meta=meta, status='failed')

    def return_job(jid, connection=None):
        return job

    monkeypatch.setattr(
        'auto_recon_api.api.v1.endpoints.jobs.Job.fetch',
        return_job,
    )

    out = await get_job('j4', session, user)
    assert isinstance(out, JobResponse)
    assert out.type == 'subdomains'
    assert out.progress is None


@pytest.mark.asyncio
async def test_get_job_subdomains_missing_domain(monkeypatch, session, user):
    # domain id that does not exist in DB
    meta = {'domain_ids': [999], 'total': 1, 'done': 0, 'failed': 0}
    job = FakeJob(id='j5', origin='subdomains', meta=meta, status='running')

    def return_job(jid, connection=None):
        return job

    monkeypatch.setattr(
        'auto_recon_api.api.v1.endpoints.jobs.Job.fetch',
        return_job,
    )

    out = await get_job('j5', session, user)
    assert isinstance(out, JobResponse)
    # domains list should be empty because the domain id is not present
    assert out.domains == []


@pytest.mark.asyncio
async def test_get_job_urls_finished_and_no_seen(monkeypatch, session, user):
    # finished -> progress 1.0
    result = {'seen': 5, 'inserted': 5}
    job = FakeJob(id='j6', origin='urls', result=result, status='finished')

    def return_job(jid, connection=None):
        return job

    monkeypatch.setattr(
        'auto_recon_api.api.v1.endpoints.jobs.Job.fetch',
        return_job,
    )

    out = await get_job('j6', session, user)
    assert isinstance(out, JobResponse)
    assert out.progress == pytest.approx(1.0)

    # no seen -> progress is None
    job2 = FakeJob(id='j7', origin='urls', result={}, status='running')

    def return_job2(jid, connection=None):
        return job2

    monkeypatch.setattr(
        'auto_recon_api.api.v1.endpoints.jobs.Job.fetch',
        return_job2,
    )

    out2 = await get_job('j7', session, user)
    assert out2.progress is None
