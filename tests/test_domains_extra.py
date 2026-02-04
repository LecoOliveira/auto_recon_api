from __future__ import annotations

from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from auto_recon_api.api.v1.endpoints.domains import (
    add_domains,
    enqueue_subdomain_recon,
)
from auto_recon_api.schemas import EnterDomainSchema


@pytest.mark.asyncio
async def test_scan_domain_urls_enqueues_job(client, token, domain):
    with patch(
        'auto_recon_api.api.v1.endpoints.domains.urls_queue.enqueue',
        autospec=True,
    ) as mock_enqueue:
        mock_enqueue.return_value.id = 'urls-job-1'

        response = client.post(
            f'/api/v1/domains/{domain.id}/urls/scan',
            headers={'Authorization': f'Bearer {token}'},
        )

        assert response.status_code == HTTPStatus.ACCEPTED
        data = response.json()['data']
        assert data['job_id'] == 'urls-job-1'
        assert data['domain_id'] == domain.id


def test_enqueue_subdomain_recon_returns_job_id():
    with patch(
        'auto_recon_api.api.v1.endpoints.domains.subdomains_queue.enqueue',
        autospec=True,
    ) as mock_enqueue:
        mock_enqueue.return_value.id = 'sub-job-7'
        out = enqueue_subdomain_recon(7)
        assert out == 'sub-job-7'


@pytest.mark.asyncio
async def test_add_domains_empty_input(session, user):
    domains = EnterDomainSchema(domains=[])

    with pytest.raises(HTTPException) as exc:
        await add_domains(domains, session, user)

    assert exc.value.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.asyncio
async def test_add_domains_integrity_error(session, user):
    domains_input = EnterDomainSchema(domains=["duplicate.com"])

    # avoid touching Redis while still forcing commit to fail
    with patch(
        'auto_recon_api.api.v1.endpoints.domains.subdomains_queue.enqueue',
        autospec=True,
    ) as mock_enqueue:
        mock_enqueue.return_value.id = 'job-x'

        # make commit raise IntegrityError
        with patch.object(
            session,
            "commit",
            new=AsyncMock(
                side_effect=IntegrityError(
                    "msg",
                    "params",
                    Exception("orig"),
                )
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await add_domains(domains_input, session, user)

    assert exc_info.value.status_code == HTTPStatus.CONFLICT
    assert "One or more domains already exist" in exc_info.value.detail


def test_scan_domain_urls_not_found(client, token):
    # use non-existent domain id
    response = client.post(
        "/api/v1/domains/999/urls/scan",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    # app exception handler returns a payload with 'message'
    assert response.json()["message"] == "Domain not found"


def test_get_domains_filters(client, token):
    # create a domain with known status so filters match
    name = 'filterme.com'

    # mock enqueue to avoid touching Redis while creating domain
    with patch(
        'auto_recon_api.api.v1.endpoints.domains.subdomains_queue.enqueue',
        autospec=True,
    ) as mock_enqueue:
        mock_enqueue.return_value.id = 'job-filter'

        r = client.post(
            '/api/v1/domains/',
            json={'domains': [name]},
            headers={'Authorization': f'Bearer {token}'},
        )
        assert r.status_code == HTTPStatus.CREATED

    response = client.get(
        "/api/v1/domains/?q=%s&status=%s" % (name[:3], 'queued'),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["total"] >= 1
    assert any(item["name"] == name for item in data["items"])
