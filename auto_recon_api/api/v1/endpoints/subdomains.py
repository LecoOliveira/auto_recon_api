from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from auto_recon_api.api.deps import CurrentUser, DbSession
from auto_recon_api.models import Domain, Subdomain
from auto_recon_api.schemas import FilterPage, SubdomainResponse

router = APIRouter(
    prefix='/domains/{domain_id}/subdomains', tags=['subdomains']
)
Filter = Annotated[FilterPage, Depends()]


@router.get('/', response_model=SubdomainResponse, status_code=HTTPStatus.OK)
async def get_subdomains(
    domain_id: int,
    session: DbSession,
    user: CurrentUser,
    filters: Filter,
):
    domain_exists = await session.scalar(
        select(Domain.id).where(
            Domain.id == domain_id, Domain.user_id == user.id
        )
    )
    if not domain_exists:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Domain not found'
        )

    base_ids = (
        select(Subdomain.id)
        .where(Subdomain.domain_id == domain_id)
        .subquery()
    )
    total = await session.scalar(select(func.count()).select_from(base_ids))
    total = int(total or 0)

    result = await session.execute(
        select(Subdomain)
        .where(Subdomain.domain_id == domain_id)
        .order_by(Subdomain.id.desc())
        .offset(filters.offset)
        .limit(filters.limit)
    )
    subdomains = result.scalars().all()

    return SubdomainResponse(
        total=total,
        offset=filters.offset,
        limit=filters.limit,
        subdomains=subdomains,
    )
