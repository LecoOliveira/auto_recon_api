from __future__ import annotations

import asyncio
import hashlib
import json
from urllib.parse import urlsplit, urlunsplit

import httpx
from rq import get_current_job
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from auto_recon_api.database import SessionLocal
from auto_recon_api.models import DiscoveredURL, Subdomain
from auto_recon_api.settings import get_settings

settings = get_settings()

HOSTS_PER_REQUEST = 200
BATCH_SIZE = 2000


def normalize_url(url: str) -> str:
    url = url.strip()
    parts = urlsplit(url)
    scheme = (parts.scheme or 'http').lower()
    netloc = parts.netloc.lower()
    path = parts.path or '/'
    query = parts.query
    normalized = urlunsplit((scheme, netloc, path, query, ''))
    if normalized.endswith('/') and len(path) > 1:
        normalized = normalized[:-1]
    return normalized


def url_hash(u: str) -> str:
    return hashlib.sha256(u.encode('utf-8')).hexdigest()


def chunks(lst: list[str], n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _meta_init(job):
    if not job:
        return
    job.meta.setdefault('phase', 'starting')
    job.meta.setdefault('seen', 0)
    job.meta.setdefault('inserted', 0)
    job.meta.setdefault('errors', 0)
    job.save_meta()


def _meta_update(job, **kwargs):
    if not job:
        return
    job.meta.update(kwargs)
    job.save_meta()


def scan_urls_for_domain(domain_id: int, user_id: int) -> dict:
    job = get_current_job()
    if job:
        job.meta['phase'] = 'starting'
        job.meta['seen'] = 0
        job.meta['inserted'] = 0
        job.meta['errors'] = 0
        job.save_meta()

    try:
        asyncio.run(_scan_urls_for_domain(domain_id, job))
        if job:
            job.meta['phase'] = 'finished'
            job.save_meta()
    except Exception as exc:
        if job:
            job.meta['phase'] = 'failed'
            job.meta['errors'] = int(job.meta.get('errors', 0)) + 1
            job.meta['last_error'] = str(exc)
            job.save_meta()
        raise

    if job:
        return {
            'seen': int(job.meta.get('seen', 0)),
            'inserted': int(job.meta.get('inserted', 0)),
            'errors': int(job.meta.get('errors', 0)),
        }
    return {'seen': 0, 'inserted': 0, 'errors': 0}


async def _scan_urls_for_domain(domain_id: int, job) -> None:
    seen_local = 0
    inserted_local = 0

    async with SessionLocal() as session:
        hosts = (
            await session.execute(
                select(Subdomain.host).where(Subdomain.domain_id == domain_id)
            )
        ).scalars().all()

    if not hosts:
        if job:
            job.meta['phase'] = 'finished'
            job.meta['seen'] = 0
            job.meta['inserted'] = 0
            job.save_meta()
        return

    if job:
        job.meta['phase'] = 'running'
        job.meta['total_hosts'] = len(hosts)
        job.save_meta()

    async with httpx.AsyncClient(timeout=None) as client:
        for host_chunk in chunks(list(hosts), HOSTS_PER_REQUEST):
            payload = [{'host': h, 'ip': ''} for h in host_chunk]
            buffer: list[dict] = []

            async with client.stream(
                'POST',
                f'{settings.API_TOOLS_URL}/hosts/stream',
                headers={'X-Internal-Token': settings.INTERNAL_TOKEN},
                json=payload,
            ) as r:
                r.raise_for_status()

                async for line in r.aiter_lines():
                    if not line:
                        continue

                    obj = json.loads(line)
                    raw_url = obj.get('url')
                    if not raw_url:
                        continue

                    norm = normalize_url(raw_url)

                    buffer.append(
                        {
                            'domain_id': domain_id,
                            'host': obj.get('host'),
                            'url': norm,
                            'url_hash': url_hash(norm),
                            'hostname': obj.get('hostname'),
                            'port': obj.get('port'),
                            'status_code': obj.get('status_code'),
                            'title': obj.get('title'),
                            'tech': obj.get('tech'),
                        }
                    )

                    seen_local += 1

                    if len(buffer) >= BATCH_SIZE:
                        if job:
                            job.meta['phase'] = 'flushing'
                            job.save_meta()

                        inserted_now = await _flush_urls(SessionLocal, buffer)
                        inserted_local += inserted_now
                        buffer.clear()

                        if job:
                            job.meta['phase'] = 'running'
                            job.meta['seen'] = seen_local
                            job.meta['inserted'] = inserted_local
                            job.save_meta()

                        print(
                            f'[urls] domain={domain_id} \
                            seen={seen_local} inserted={inserted_local}'
                        )

            if buffer:
                if job:
                    job.meta['phase'] = 'flushing'
                    job.save_meta()

                inserted_now = await _flush_urls(SessionLocal, buffer)
                inserted_local += inserted_now
                buffer.clear()

                if job:
                    job.meta['phase'] = 'running'
                    job.meta['seen'] = seen_local
                    job.meta['inserted'] = inserted_local
                    job.save_meta()

                print(
                    f'[urls] domain={domain_id} seen={seen_local} \
                    inserted={inserted_local}'
                )

    if job:
        job.meta['phase'] = 'finished'
        job.meta['seen'] = seen_local
        job.meta['inserted'] = inserted_local
        job.save_meta()


async def _flush_urls(sessionmaker, rows: list[dict]) -> None:
    async with sessionmaker() as session:
        stmt = insert(DiscoveredURL.__table__).values(rows)
        stmt = stmt.on_conflict_do_nothing(constraint='uq_domain_urlhash')
        stmt = stmt.returning(DiscoveredURL.id)
        res = await session.execute(stmt)
        await session.commit()
        inserted = len(res.fetchall())
        return inserted
