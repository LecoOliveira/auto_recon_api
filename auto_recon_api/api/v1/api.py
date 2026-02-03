from __future__ import annotations

from fastapi import APIRouter

from auto_recon_api.api.v1.endpoints import (
    auth,
    domains,
    jobs,
    subdomains,
    users,
)

api_router = APIRouter()

api_router.include_router(users.router, tags=['users'])
api_router.include_router(auth.router, tags=['auth'])
api_router.include_router(domains.router, tags=['domains'])
api_router.include_router(jobs.router, tags=['jobs'])
api_router.include_router(subdomains.router, tags=['subdomains'])
