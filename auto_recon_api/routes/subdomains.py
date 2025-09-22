from http import HTTPStatus

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from auto_recon_api.models import Subdomain
from auto_recon_api.routes.domains.base import CurrentUser, Session
from auto_recon_api.schemas import SubdomainResponse

router = APIRouter(
    prefix='/domains/{domain_id}/subdomains', tags=['subdomains']
)


@router.get('/', response_model=SubdomainResponse, status_code=HTTPStatus.OK)
async def get_subdomains(
    domain_id: int,
    session: Session,
    user: CurrentUser,
    skip: int = 0,
    limit: int = 20,
):
    if not user:
        raise HTTPException(
            detail='Not enough permissions',
            status_code=HTTPStatus.FORBIDDEN
        )

    result = await session.execute(
        select(Subdomain)
        .where(Subdomain.domain_id == domain_id)
        .offset(skip)
        .limit(limit)
    )
    subdomains = result.scalars().all()

    if not subdomains:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='No subdomains found'
        )

    return {'subdomains': subdomains}
