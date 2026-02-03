from __future__ import annotations

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from redis import Redis
from rq import Queue
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError

from auto_recon_api.api.deps import CurrentUser, DbSession
from auto_recon_api.core.pagination import decode_cursor, encode_cursor
from auto_recon_api.models import DiscoveredURL, Domain, DomainRun
from auto_recon_api.schemas import (
    DomainListItem,
    DomainListResponse,
    DomainResponseCreated,
    EnterDomainSchema,
    FilterDomain,
    Message,
    UrlItem,
    UrlListFilters,
    UrlListResponse,
)
from auto_recon_api.tasks.urls import scan_urls_for_domain
from auto_recon_api.workers.subdomains import run_find_subdomains

redis_conn = Redis(host='redis', port=6379)
subdomains_queue = Queue('subdomains', connection=redis_conn)
urls_queue = Queue('urls', connection=redis_conn)
router = APIRouter(prefix='/domains', tags=['domains'])
Filter = Annotated[FilterDomain, Depends()]
FilterUrl = Annotated[UrlListFilters, Depends()]


@router.post(
    '/', response_model=DomainResponseCreated, status_code=HTTPStatus.CREATED
)
async def add_domains(
    domains: EnterDomainSchema, session: DbSession, user: CurrentUser
):
    domain_names = set(domains.domains)
    if not domain_names:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail='No domains provided'
        )

    exists_names = (
        (
            await session.execute(
                select(Domain.name).where(
                    Domain.user_id == user.id,
                    Domain.name.in_(domain_names),
                )
            )
        )
        .scalars()
        .all()
    )
    exists_set = set(exists_names)

    new_names = [name for name in domain_names if name not in exists_set]
    new_domains = [
        Domain(
            name=name, user_id=user.id, status='queued'
        ) for name in new_names
    ]

    job_id = None

    try:
        if new_domains:
            session.add_all(new_domains)

            await session.flush()

            for domain in new_domains:
                await session.refresh(domain)

            domain_ids = [domain.id for domain in new_domains]

            job = subdomains_queue.enqueue(
                run_find_subdomains,
                domain_ids,
                retry=0,
                job_timeout=1200,
                result_ttl=86400,
                ttl=86400,
            )
            job_id = job.id

            session.add_all(
                [
                    DomainRun(
                        domain_id=did, job_id=job_id, status='queued'
                    ) for did in domain_ids
                ]
            )

        await session.commit()

    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=(
                'One or more domains already exist or violate unique'
                f'constraints.({str(error.orig)})'
            ),
        )

    added_items = [
        DomainListItem(
            id=domain.id,
            name=domain.name,
            status=domain.status,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
            job_id=job_id,
        )
        for domain in new_domains
    ]

    return DomainResponseCreated(
        job_id=job_id,
        added=added_items,
        already_exists=exists_names,
    )


@router.post('/{domain_id}/urls/scan', status_code=HTTPStatus.ACCEPTED)
async def scan_domain_urls(
    domain_id: int, session: DbSession, user: CurrentUser
):
    domain = await session.scalar(
        select(Domain).where(Domain.id == domain_id, Domain.user_id == user.id)
    )
    if not domain:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Domain not found'
        )

    job = urls_queue.enqueue(
        scan_urls_for_domain, domain_id, user.id, job_timeout=60 * 60
    )

    return {'data': {'job_id': job.id, 'domain_id': domain.id}}


@router.get('/', response_model=DomainListResponse, status_code=HTTPStatus.OK)
async def get_domains(
    session: DbSession, user: CurrentUser, filters: Filter
):
    where_clauses = [Domain.user_id == user.id]

    if filters.q:
        where_clauses.append(Domain.name.ilike(f'%{filters.q}%'))

    if filters.status:
        where_clauses.append(Domain.status == filters.status)

    base_ids = select(Domain.id).where(*where_clauses).subquery()
    total = await session.scalar(select(func.count()).select_from(base_ids))
    total = int(total or 0)

    latest_job_id = (
        select(DomainRun.job_id)
        .where(DomainRun.domain_id == Domain.id)
        .order_by(DomainRun.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )

    query = (
        select(
            Domain, latest_job_id.label('job_id')
        )
        .where(*where_clauses)
        .order_by(Domain.updated_at.desc())
        .offset(filters.offset)
        .limit(filters.limit)
    )

    result = await session.execute(query)
    rows = result.all()

    items = [
        DomainListItem(
            id=domain.id,
            name=domain.name,
            status=domain.status,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
            job_id=job_id,
        )
        for domain, job_id in rows
    ]

    return DomainListResponse(
        total=total,
        offset=filters.offset,
        limit=filters.limit,
        items=items,
    )


@router.get(
    '/{domain_id}/urls',
    response_model=UrlListResponse,
    status_code=HTTPStatus.OK,
)
async def list_domain_urls(
    domain_id: int,
    session: DbSession,
    user: CurrentUser,
    filters: FilterUrl,
) -> UrlListResponse:
    exists = await session.scalar(
        select(func.count())
        .select_from(Domain)
        .where(Domain.id == domain_id, Domain.user_id == user.id)
    )
    if not exists:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Domain not found'
        )

    where = [DiscoveredURL.domain_id == domain_id]

    if filters.host:
        where.append(DiscoveredURL.host == filters.host)

    if filters.status_code is not None:
        where.append(DiscoveredURL.status_code == filters.status_code)

    if filters.q:
        where.append(DiscoveredURL.url.ilike(f'%{filters.q}%'))

    if filters.ext:
        pattern = rf'\.{filters.ext}(\?|$)'
        where.append(DiscoveredURL.url.op('~*')(pattern))

    if filters.cursor:
        try:
            c_ts, c_id = decode_cursor(filters.cursor)
        except Exception:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail='Invalid cursor'
            )

        where.append(
            or_(
                DiscoveredURL.created_at < c_ts,
                and_(
                    DiscoveredURL.created_at == c_ts, DiscoveredURL.id < c_id
                ),
            )
        )

    query = (
        select(DiscoveredURL)
        .where(*where)
        .order_by(DiscoveredURL.created_at.desc(), DiscoveredURL.id.desc())
        .limit(filters.limit + 1)
    )

    res = await session.execute(query)
    rows = res.scalars().all()

    has_more = len(rows) > filters.limit
    rows = rows[: filters.limit]

    items = [
        UrlItem(
            id=r.id,
            url=r.url,
            host=r.host,
            hostname=r.hostname,
            port=r.port,
            status_code=r.status_code,
            title=r.title,
            tech=r.tech,
            created_at=r.created_at,
        )
        for r in rows
    ]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = encode_cursor(last.created_at, last.id)

    return UrlListResponse(next_cursor=next_cursor, items=items)


@router.delete(
    '/{domain_id}', response_model=Message, status_code=HTTPStatus.OK
)
async def delete_domain(domain_id: int, user: CurrentUser, session: DbSession):
    db_domain = await session.scalar(
        select(Domain).where(Domain.id == domain_id, Domain.user_id == user.id)
    )
    if not db_domain:
        raise HTTPException(
            detail='Domain not found', status_code=HTTPStatus.NOT_FOUND
        )

    await session.delete(db_domain)
    await session.commit()
    return {'message': 'Domain deleted'}


def enqueue_subdomain_recon(domain_id: int) -> str:
    job = subdomains_queue.enqueue(
        run_find_subdomains,
        [domain_id],
        retry=0,
        job_timeout=1200,
    )
    return job.id
