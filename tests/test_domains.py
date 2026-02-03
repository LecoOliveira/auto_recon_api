from http import HTTPStatus
from unittest.mock import patch

import pytest

# from fastapi import HTTPException
# from sqlalchemy import select
from auto_recon_api.models import Domain

# from auto_recon_api.routes.domains import add_domains
# from auto_recon_api.schemas import EnterDomainSchema


# def test_create_domain(client, token):
#     response = client.post(
#         '/domains/',
#         headers={'Authorization': f'Bearer {token}'},
#         json={'domains': ['teste.com']},
#     )

#     assert response.status_code == HTTPStatus.CREATED
#     assert response.json()['added'][0]['name'] == 'teste.com'


# @pytest.mark.asyncio
# async def test_add_domains_integrity_error(session, user):
#     domains_input = EnterDomainSchema(domains=['teste.com'])

#     with patch.object(
#         session,
#         'commit',
#         new=AsyncMock(side_effect=IntegrityError('msg', 'params', 'orig')),
#     ):
#         with pytest.raises(HTTPException) as exc_info:
#             await add_domains(domains_input, session, user)

#     assert 'One or more domains already exist' in exc_info.value.detail


@pytest.mark.asyncio
async def test_add_domains(client, token, session, user):
    tasks = 2
    with patch(
        'auto_recon_api.api.v1.endpoints.domains.subdomains_queue.enqueue',
        autospec=True
    ) as mock_enqueue:
        # ensure the mocked job has a serializable id
        mock_enqueue.return_value.id = 'job-1'

        response = client.post(
            '/api/v1/domains/',
            json={'domains': ['example.com', 'test.com']},
            headers={'Authorization': f'Bearer {token}'},
        )

        assert response.status_code == HTTPStatus.CREATED
        data = response.json()

        assert 'added' in data
        assert len(data['added']) == tasks
        assert data['already_exists'] == []
        assert data['job_id'] == 'job-1'
        assert mock_enqueue.call_count == 1
        args, kwargs = mock_enqueue.call_args
        assert isinstance(args[1], list)
        assert len(args[1]) == tasks

    results = (
        await session.execute(
            Domain.__table__.select().where(Domain.user_id == user.id)
        )
    ).all()
    assert len(results) == tasks


def test_get_domains(client, token, domain):
    response = client.get(
        '/api/v1/domains/', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.OK

    assert response.json()['items'][0]['name'] == domain.name


def test_delete_domain(client, token, domain):
    response = client.delete(
        f'/api/v1/domains/{domain.id}',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['message'] == 'Domain deleted'


def test_delete_domain_with_error(client, token):
    response = client.delete(
        '/api/v1/domains/100', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['message'] == 'Domain not found'
