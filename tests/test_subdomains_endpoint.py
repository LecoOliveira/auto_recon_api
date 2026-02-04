from __future__ import annotations

import asyncio
from http import HTTPStatus

import pytest

from auto_recon_api.models import Domain, Subdomain


def test_subdomains_404_if_domain_not_owned(client, token, session, user_2):
    d2 = Domain(name='other.com', user_id=user_2.id)
    session.add(d2)

    # commit sync via async fixture session

    async def _commit():
        await session.commit()
        await session.refresh(d2)

    asyncio.get_event_loop().run_until_complete(_commit())

    r = client.get(
        f'/api/v1/domains/{d2.id}/subdomains',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert r.status_code == HTTPStatus.NOT_FOUND
    assert r.json()['message'] == 'Domain not found'


@pytest.mark.asyncio
async def test_get_subdomains_returns_list(client, token, session, domain):
    s1 = Subdomain(host='a.example.com', ip='1.2.3.4', domain_id=domain.id)
    s2 = Subdomain(host='b.example.com', ip='5.6.7.8', domain_id=domain.id)
    session.add_all([s1, s2])
    await session.commit()
    await session.refresh(s1)
    await session.refresh(s2)

    _data = 2
    r = client.get(
        f'/api/v1/domains/{domain.id}/subdomains',
        headers={'Authorization': f'Bearer {token}'}
    )
    assert r.status_code == HTTPStatus.OK
    data = r.json()
    assert data['total'] == _data
    assert any(d['host'] == 'a.example.com' for d in data['subdomains'])
    assert any(d['host'] == 'b.example.com' for d in data['subdomains'])
