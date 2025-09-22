from http import HTTPStatus

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from auto_recon_api.database import SessionLocal
from auto_recon_api.models import Domain, Subdomain
from auto_recon_api.settings import Settings

settings = Settings()


async def find_subdomains(domain: str, domain_id: int):
    async with SessionLocal() as session:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    settings.SUBDOMAIN_URL, params={'domain': domain}
                )
                response.raise_for_status()
                try:
                    data = response.json()
                except ValueError:
                    raise HTTPException(
                        status_code=HTTPStatus.BAD_GATEWAY,
                        detail='Invalid JSON response from subdomain service',
                    )

            async with session.begin():
                for subdomain in data.get('subdomains', []):
                    session.add(
                        Subdomain(
                            host=subdomain['host'],
                            ip=subdomain.get('ip', '0.0.0.0'),
                            domain_id=domain_id,
                        )
                    )

                db_domain = await session.scalar(
                    select(Domain).where(Domain.id == domain_id)
                )
                if db_domain:
                    db_domain.status = 'done'
        except Exception as error:
            async with session.begin():
                db_domain = await session.scalar(
                    select(Domain).where(Domain.id == domain_id)
                )
                if db_domain:
                    db_domain.status = 'failed'
            print(f'Find_subdomains error for {domain}: {error}')
