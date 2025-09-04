from http import HTTPStatus
import httpx
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auto_recon_api.database import get_session
from auto_recon_api.models import Domain, Subdomain, User
from auto_recon_api.schemas import (
    DomainResponseCreated,
    DomainSchema,
    EnterDomainSchema,
    Message,
)
from auto_recon_api.security import get_current_user

router = APIRouter(prefix='/domains', tags=['domains'])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


async def find_subdomains(domain: str, session: Session, domain_id: int):
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        response = await client.post(
            f'http://recon_tool:8001/subdomains',
            params={'domain': domain}
        )

        data = response.json()

    for subdomain in data['subdomains']:
        session.add(
            Subdomain(
                host=subdomain['host'], ip=subdomain['ip'], domain_id=domain_id
            )
        )

    result = await session.execute(
        select(Domain).where(Domain.id == domain_id)
    )
    db_domain = result.scalar_one()
    db_domain.status = 'done'
    await session.commit()


@router.post(
    '/', response_model=DomainResponseCreated, status_code=HTTPStatus.CREATED
)
async def add_domains(
    domains: EnterDomainSchema,
    session: Session,
    user: CurrentUser,
    background_tasks: BackgroundTasks
):
    domain_names = set(domains.domains)
    exists_names = (
        (
            await session.execute(
                select(Domain.name).where(
                    Domain.user_id == user.id, Domain.name.in_(domain_names)
                )
            )
        )
        .scalars()
        .all()
    )
    new_names = [name for name in domain_names if name not in exists_names]
    new_domains = [Domain(name=name, user_id=user.id) for name in new_names]

    session.add_all(new_domains)

    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            detail='One or more domains already exist or violate unique'
            f' constraints. ({str(error.orig)})',
            status_code=HTTPStatus.CONFLICT
        )

    for db_domain in new_domains:
        await session.refresh(db_domain)
    
        background_tasks.add_task(
            find_subdomains, db_domain.name, session, db_domain.id
            )

    return {'added': new_domains, 'already_exists': exists_names}


@router.get('/', response_model=DomainSchema, status_code=HTTPStatus.OK)
async def get_domains(session: Session, user: CurrentUser):
    domains = (
        await session.scalars(select(Domain).where(Domain.user_id == user.id))
    ).all()

    return {'domains': domains}


@router.delete(
    '/{domain_id}', response_model=Message, status_code=HTTPStatus.OK
)
async def delete_domain(domain_id: int, user: CurrentUser, session: Session):
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
