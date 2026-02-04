from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any

import pytest
import pytest_asyncio

from auto_recon_api.core.pagination import decode_cursor, encode_cursor
from auto_recon_api.models import DiscoveredURL, Domain


def auth_headers(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def extract_ids(items: list[dict[str, Any]]) -> list[int]:
    return [int(i['id']) for i in items]


async def seed_urls(   # noqa: PLR0913
    session,
    *,
    domain_id: int,
    base_time: datetime,
    n: int,
    host: str,
    status_code: int,
    prefix: str,
) -> list[int]:
    rows: list[DiscoveredURL] = []
    for i in range(n):
        url = f'{prefix}/p{i}'
        # url_hash fake só para não colidir unique / facilitar seed.
        r = DiscoveredURL(
            domain_id=domain_id,
            url=url,
            url_hash=f'hash_{host}_{status_code}_{i}',
            host=host,
            hostname=host,
            port=443,
            status_code=status_code,
            title='t',
            tech=None,
        )
        # set created_at after construction (column has init=False)
        r.created_at = base_time - timedelta(seconds=i)
        rows.append(r)

    session.add_all(rows)
    await session.commit()

    for r in rows:
        await session.refresh(r)

    return [r.id for r in rows]


@pytest_asyncio.fixture
async def urls_seeded(session, domain):
    '''
    Dataset variado para testar host/status/q/ext/cursor.
    '''
    base = datetime.utcnow()

    ids_rh_200 = await seed_urls(
        session,
        domain_id=domain.id,
        base_time=base,
        n=80,
        host='rh.businesscorp.com.br',
        status_code=HTTPStatus.OK,
        prefix='https://rh.businesscorp.com.br',
    )

    ids_rh_404 = await seed_urls(
        session,
        domain_id=domain.id,
        base_time=base - timedelta(minutes=10),
        n=30,
        host='rh.businesscorp.com.br',
        status_code=HTTPStatus.NOT_FOUND,
        prefix='https://rh.businesscorp.com.br',
    )

    ids_dev_301 = await seed_urls(
        session,
        domain_id=domain.id,
        base_time=base - timedelta(minutes=20),
        n=25,
        host='dev.businesscorp.com.br',
        status_code=HTTPStatus.MOVED_PERMANENTLY,
        prefix='https://dev.businesscorp.com.br',
    )

    # adiciona alguns com extensão 'pdf' e querystring pra testar ext
    extra = []
    a = DiscoveredURL(
        domain_id=domain.id,
        url='https://rh.businesscorp.com.br/uploads/a.pdf',
        url_hash='hash_pdf_1',
        host='rh.businesscorp.com.br',
        hostname='rh.businesscorp.com.br',
        port=443,
        status_code=HTTPStatus.OK,
        title='pdf',
        tech=None,
    )
    a.created_at = base - timedelta(hours=1)
    b = DiscoveredURL(
        domain_id=domain.id,
        url='https://rh.businesscorp.com.br/uploads/b.PDF?x=1',
        url_hash='hash_pdf_2',
        host='rh.businesscorp.com.br',
        hostname='rh.businesscorp.com.br',
        port=443,
        status_code=HTTPStatus.OK,
        title='pdf',
        tech=None,
    )
    b.created_at = base - timedelta(hours=1, seconds=1)
    extra.extend([a, b])
    session.add_all(extra)
    await session.commit()
    for r in extra:
        await session.refresh(r)

    total = len(ids_rh_200) + len(ids_rh_404) + len(ids_dev_301) + len(extra)

    return {'total': total}


def test_domain_urls_requires_auth(client, domain):
    r = client.get(f'/api/v1/domains/{domain.id}/urls')
    assert r.status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}


@pytest.mark.asyncio
async def test_urls_404_domain_not_owned(client, token, session, user_2):
    d2 = Domain(name='other.com', user_id=user_2.id)
    session.add(d2)
    await session.commit()
    await session.refresh(d2)

    r = client.get(
        f'/api/v1/domains/{d2.id}/urls',
        headers=auth_headers(token),
    )
    assert r.status_code == HTTPStatus.NOT_FOUND
    assert r.json().get('message') == 'Domain not found'


@pytest.mark.asyncio
async def test_domain_urls_cursor_pagination_no_dup_no_missing(
    client, token, domain, urls_seeded
):
    # page 1
    limit = 50
    r1 = client.get(
        f'/api/v1/domains/{domain.id}/urls',
        headers=auth_headers(token),
        params={'limit': limit},
    )
    assert r1.status_code == HTTPStatus.OK
    b1 = r1.json()

    assert 'items' in b1
    assert 'next_cursor' in b1
    ids1 = set(extract_ids(b1['items']))
    assert len(ids1) <= limit
    assert b1['next_cursor'] is not None

    # page 2
    r2 = client.get(
        f'/api/v1/domains/{domain.id}/urls',
        headers=auth_headers(token),
        params={'limit': limit, 'cursor': b1['next_cursor']},
    )
    assert r2.status_code == HTTPStatus.OK
    b2 = r2.json()
    ids2 = set(extract_ids(b2['items']))

    assert ids1.isdisjoint(ids2)

    # continua até acabar
    all_ids = ids1 | ids2
    cursor = b2['next_cursor']

    while cursor:
        r = client.get(
            f'/api/v1/domains/{domain.id}/urls',
            headers=auth_headers(token),
            params={'limit': limit, 'cursor': cursor},
        )
        assert r.status_code == HTTPStatus.OK
        b = r.json()

        new_ids = set(extract_ids(b['items']))
        assert all_ids.isdisjoint(new_ids)  # sem duplicatas
        all_ids |= new_ids
        cursor = b['next_cursor']

    assert len(all_ids) == urls_seeded['total']


@pytest.mark.asyncio
async def test_urls_host_status_q_ext(client, token, domain, urls_seeded):
    # status_code=404
    r = client.get(
        f'/api/v1/domains/{domain.id}/urls',
        headers=auth_headers(token),
        params={'limit': 200, 'status_code': 404},
    )
    assert r.status_code == HTTPStatus.OK
    items = r.json()['items']
    assert items
    assert all(i['status_code'] == HTTPStatus.NOT_FOUND for i in items)

    # host=dev.businesscorp.com.br
    r = client.get(
        f'/api/v1/domains/{domain.id}/urls',
        headers=auth_headers(token),
        params={'limit': 200, 'host': 'dev.businesscorp.com.br'},
    )
    assert r.status_code == HTTPStatus.OK
    items = r.json()['items']
    assert items
    assert all(i['host'] == 'dev.businesscorp.com.br' for i in items)

    # q (ilike na url)
    r = client.get(
        f'/api/v1/domains/{domain.id}/urls',
        headers=auth_headers(token),
        params={'limit': 200, 'q': '/p1'},
    )
    assert r.status_code == HTTPStatus.OK
    items = r.json()['items']
    assert items
    assert all('/p1' in i['url'] for i in items)

    # ext (regex \.ext(\?|$)) - deve pegar .pdf e .PDF?x=1
    r = client.get(
        f'/api/v1/domains/{domain.id}/urls',
        headers=auth_headers(token),
        params={'limit': 200, 'ext': 'pdf'},
    )
    assert r.status_code == HTTPStatus.OK
    items = r.json()['items']
    assert items
    assert all(
        i['url'].lower().endswith('.pdf') or '.pdf?' in i['url'].lower()
        for i in items
    )


def test_domain_urls_invalid_cursor_400(client, token, domain):
    r = client.get(
        f'/api/v1/domains/{domain.id}/urls',
        headers=auth_headers(token),
        params={'cursor': 'isso_nao_e_cursor', 'limit': 10},
    )
    assert r.status_code == HTTPStatus.BAD_REQUEST
    assert r.json().get('message') == 'Invalid cursor'


def test_cursor_roundtrip_naive_datetime():
    _id = 2112
    ts = datetime(2026, 2, 2, 21, 39, 45, 670535)  # naive
    cur = encode_cursor(ts, 2112)
    out_ts, out_id = decode_cursor(cur)
    assert out_ts == ts
    assert out_id == _id


def test_cursor_roundtrip_aware_datetime_converts_to_naive_utc():
    # aware -> encode deve converter pra UTC naive
    _id = 7
    ts_aware = datetime(2026, 2, 2, 21, 39, 45, 670535, tzinfo=timezone.utc)
    cur = encode_cursor(ts_aware, 7)
    out_ts, out_id = decode_cursor(cur)
    assert out_ts.tzinfo is None
    assert out_ts == datetime(2026, 2, 2, 21, 39, 45, 670535)
    assert out_id == _id


@pytest.mark.asyncio
async def test_domain_urls_cursor_matches_last_item_and_next_page_is_older(
    client, token, domain, urls_seeded
):
    limit = 10
    r1 = client.get(
        f'/api/v1/domains/{domain.id}/urls',
        headers=auth_headers(token),
        params={'limit': limit},
    )
    assert r1.status_code == HTTPStatus.OK
    b1 = r1.json()
    items1 = b1['items']
    assert len(items1) == limit
    assert b1['next_cursor']

    last = items1[-1]
    last_ts = datetime.fromisoformat(last['created_at'])
    last_id = int(last['id'])

    c_ts, c_id = decode_cursor(b1['next_cursor'])
    assert c_ts.replace(microsecond=0) == last_ts.replace(microsecond=0)
    assert c_id == last_id

    r2 = client.get(
        f'/api/v1/domains/{domain.id}/urls',
        headers=auth_headers(token),
        params={'limit': limit, 'cursor': b1['next_cursor']},
    )
    assert r2.status_code == HTTPStatus.OK
    b2 = r2.json()
    items2 = b2['items']
    assert items2  # deve existir

    first2 = items2[0]
    first2_ts = datetime.fromisoformat(first2['created_at'])
    first2_id = int(first2['id'])

    assert (
        first2_ts < last_ts
        or (first2_ts == last_ts and first2_id < last_id)
    )
