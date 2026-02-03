from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from typing import Optional

from fastapi import APIRouter, HTTPException
from redis import Redis
from rq.exceptions import NoSuchJobError
from rq.job import Job
from sqlalchemy import select

from auto_recon_api.api.deps import CurrentUser, DbSession
from auto_recon_api.models import Domain
from auto_recon_api.schemas import (
    JobDomainItem,
    JobMeta,
    JobResponse,
    UrlJobMeta,
)

router = APIRouter(prefix='/jobs', tags=['jobs'])

redis_conn = Redis(host='redis', port=6379)


def _datetime(date_time: Optional[datetime]) -> Optional[str]:
    return date_time.isoformat() if date_time else None


@router.get('/{job_id}', response_model=JobResponse)
async def get_job(
    job_id: str, session: DbSession, user: CurrentUser
) -> JobResponse:
    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except NoSuchJobError:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Job not found'
        )
    except Exception as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f'Failed to load job: {exc!r}'
        )

    status = job.get_status()
    error = job.exc_info if status == 'failed' else None

    meta_raw = job.meta or {}
    job_type = 'urls' if job.origin == 'urls' else 'subdomains'

    progress = None

    if job_type == 'subdomains':
        meta = JobMeta.model_validate(meta_raw)

        total = int(meta.total or 0)
        done = int(meta.done or 0)
        failed = int(meta.failed or 0)

        if total:
            progress = (done + failed) / total

        if status == 'finished':
            progress = 1.0
        elif status in {'failed', 'stopped', 'canceled'}:
            progress = None

        domain_ids = meta.domain_ids or []
        errors_by_domain = meta.errors_by_domain or {}

        domains_payload: list[JobDomainItem] = []
        if domain_ids:
            result = await session.execute(
                select(Domain).where(
                    Domain.user_id == user.id,
                    Domain.id.in_(domain_ids),
                )
            )
            domains = result.scalars().all()
            by_id = {d.id: d for d in domains}

            for did in domain_ids:
                domain = by_id.get(did)
                if not domain:
                    continue
                domains_payload.append(
                    JobDomainItem(
                        id=domain.id,
                        name=domain.name,
                        status=domain.status,
                        updated_at=_datetime(domain.updated_at),
                        error=errors_by_domain.get(str(domain.id)),
                    )
                )

        meta_out = meta
        domains_out = domains_payload

    else:
        seen = int(meta_raw.get('seen') or 0)
        inserted = int(meta_raw.get('inserted') or 0)
        phase = meta_raw.get('phase')

        result_obj = job.result if isinstance(job.result, dict) else {}
        if not seen:
            s = result_obj.get('seen')
            if isinstance(s, int):
                seen = s
        if not inserted:
            ins = result_obj.get('inserted')
            if isinstance(ins, int):
                inserted = ins

        errors = 0
        e = result_obj.get('errors')
        if isinstance(e, int):
            errors = e

        meta_out = UrlJobMeta(
            phase=phase or status,
            seen=seen,
            inserted=inserted,
            errors=errors,
            last_error=meta_raw.get('last_error'),
        )

        if status == 'finished':
            progress = 1.0
        elif seen > 0:
            progress = min(inserted / seen, 1.0)
        else:
            progress = None

        domains_out = []

    return JobResponse(
        id=job.id,
        type=job_type,
        queue=job.origin,
        status=status,
        enqueued_at=_datetime(job.enqueued_at),
        started_at=_datetime(job.started_at),
        ended_at=_datetime(job.ended_at),
        progress=progress,
        meta=meta_out,
        domains=domains_out,
        result=job.result if isinstance(job.result, dict) else None,
        error=error,
    )
