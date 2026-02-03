from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Iterable

import httpx
from fastapi import HTTPException
from rq import get_current_job
from sqlalchemy import select

from auto_recon_api.core.config import get_settings
from auto_recon_api.db.session import get_sessionmaker
from auto_recon_api.models import Domain, DomainRun, Subdomain

log = logging.getLogger(__name__)


def _short_err(exc: Exception, limit: int = 300) -> str:
    return f'{type(exc).__name__}: {exc}'[:limit]


def _normalize_domain_error(exc: Exception) -> str:
    if isinstance(exc, httpx.ReadTimeout):
        return 'ReadTimeout: recon_tool took a long time to respond ' \
        '(increase timeout or optimize tool)'
    if isinstance(exc, httpx.ConnectError):
        return 'ConnectError: failed to connect to recon_tool'
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response else '?'
        body = (exc.response.text or '')[:200] if exc.response else ''
        return f'HTTP {status} from recon_tool: {body}'
    if isinstance(exc, httpx.RequestError):
        return f'RequestError: {exc}'
    return _short_err(exc)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _init_job_meta(job, domain_ids: list[int]) -> None:
    if not job:
        return
    meta = job.meta or {}
    if 'domain_ids' not in meta:
        meta.update(
            {
                'domain_ids': domain_ids,
                'total': len(domain_ids),
                'done': 0,
                'failed': 0,
                'done_domain_ids': [],
                'failed_domain_ids': [],
                'current_domain_id': None,
                'current_domain': None,
                'last_error': None,
                'started_at': _utcnow().isoformat(),
                'updated_at': _utcnow().isoformat(),
                'errors_by_domain': {},
            }
        )
        job.meta = meta
        job.save_meta()


def _job_touch(job) -> None:
    if not job:
        return
    job.meta['updated_at'] = _utcnow().isoformat()
    job.save_meta()


def _job_set_current(job, domain_id: int, domain: str) -> None:
    if not job:
        return
    job.meta['current_domain_id'] = domain_id
    job.meta['current_domain'] = domain
    _job_touch(job)


def _job_mark_done(job, domain_id: int) -> None:
    if not job:
        return
    job.meta['done'] = int(job.meta.get('done') or 0) + 1
    job.meta.setdefault('done_domain_ids', []).append(domain_id)
    job.meta['current_domain_id'] = None
    job.meta['current_domain'] = None
    _job_touch(job)


def _job_mark_failed(job, domain_id: int, message: str) -> None:
    if not job:
        return
    job.meta['failed'] = int(job.meta.get('failed') or 0) + 1
    job.meta.setdefault('failed_domain_ids', []).append(domain_id)
    job.meta.setdefault('errors_by_domain', {})[str(domain_id)] = message
    job.meta['last_error'] = f'domain_id={domain_id}'
    job.meta['current_domain_id'] = None
    job.meta['current_domain'] = None
    _job_touch(job)


async def _process_one_domain(
    *,
    domain_id: int,
    job_id: int | None,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> None:
    settings = get_settings()
    Session = get_sessionmaker()

    async with semaphore:
        async with Session() as session:
            domain_name = None
            try:
                async with session.begin():
                    domain_obj = await session.scalar(
                        select(Domain).where(Domain.id == domain_id)
                    )
                    if not domain_obj:
                        return

                    domain_name = domain_obj.name
                    domain_obj.status = 'running'

                    if job_id:
                        run = await session.scalar(
                            select(DomainRun)
                            .where(
                                DomainRun.domain_id == domain_id,
                                DomainRun.job_id == job_id,
                            )
                            .order_by(DomainRun.id.desc())
                            .limit(1)
                        )
                        if run:
                            run.status = 'running'
                            run.started_at = run.started_at or _utcnow()
                            run.error_message = None

                response = await client.post(
                    settings.SUBDOMAIN_URL,
                    params={'domain': domain_name},
                )
                response.raise_for_status()

                try:
                    data = response.json()
                except ValueError as exc:
                    raise HTTPException(
                        status_code=HTTPStatus.BAD_GATEWAY,
                        detail='Invalid JSON response from subdomain service'
                    ) from exc

                subdomains = data.get('subdomains', [])

                async with session.begin():
                    for sub in subdomains:
                        session.add(
                            Subdomain(
                                host=sub['host'],
                                ip=sub.get('ip', '0.0.0.0'),
                                domain_id=domain_id,
                            )
                        )

                    domain_obj = await session.scalar(
                        select(Domain).where(Domain.id == domain_id)
                    )
                    if domain_obj:
                        domain_obj.status = 'done'

                    if job_id:
                        run = await session.scalar(
                            select(DomainRun)
                            .where(
                                DomainRun.domain_id == domain_id,
                                DomainRun.job_id == job_id,
                            )
                            .order_by(DomainRun.id.desc())
                            .limit(1)
                        )
                        if run:
                            run.status = 'done'
                            run.ended_at = _utcnow()
                            run.error_message = None

            except Exception as exc:
                msg = _normalize_domain_error(exc)
                log.exception(
                    f'Recon failed: {msg}',
                    extra={'domain_id': domain_id, 'domain': domain_name},
                )
                try:
                    async with session.begin():
                        domain_obj = await session.scalar(
                            select(Domain).where(Domain.id == domain_id)
                        )
                        if domain_obj:
                            domain_obj.status = 'failed'

                        if job_id:
                            run = await session.scalar(
                                select(DomainRun)
                                .where(
                                    DomainRun.domain_id == domain_id,
                                    DomainRun.job_id == job_id,
                                )
                                .order_by(DomainRun.id.desc())
                                .limit(1)
                            )
                            if run:
                                run.status = 'failed'
                                run.ended_at = _utcnow()
                                run.error_message = msg

                except Exception:
                    log.exception(
                        'Failed to persist failure',
                        extra={'domain_id': domain_id},
                    )
                raise RuntimeError(f'{domain_id}: {msg}') from exc


async def find_subdomains(domain_ids: list[int], concurrency: int = 3) -> None:
    job = get_current_job()
    job_id = job.id if job else None
    _init_job_meta(job, domain_ids)

    timeout = httpx.Timeout(connect=10.0, read=240.0, write=30.0, pool=10.0)
    semaphore = asyncio.Semaphore(concurrency)

    async def runner(domain_id: int) -> tuple[int, str | None]:
        try:
            await _process_one_domain(
                domain_id=domain_id,
                job_id=job_id,
                client=client,
                semaphore=semaphore,
            )
            return domain_id, None
        except Exception as exc:
            return domain_id, str(exc)

    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [asyncio.create_task(runner(did)) for did in domain_ids]

        for finished in asyncio.as_completed(tasks):
            domain_id, err = await finished
            if err is None:
                _job_mark_done(job, domain_id)
            else:
                _job_mark_failed(job, domain_id, err)

    if job:
        job.meta['finished_at'] = _utcnow().isoformat()
        job.meta['updated_at'] = _utcnow().isoformat()
        job.save_meta()


def run_find_subdomains(domain_ids: Iterable[int]) -> None:
    asyncio.run(find_subdomains(list(domain_ids)))
