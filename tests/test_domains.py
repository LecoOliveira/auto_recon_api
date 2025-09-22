from http import HTTPStatus
from unittest.mock import ANY, patch

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
        'auto_recon_api.routes.domains.find_subdomains', autospec=True
    ) as mock_find:
        response = client.post(
            '/domains/',
            json={'domains': ['example.com', 'test.com']},
            headers={'Authorization': f'Bearer {token}'},
        )

        assert response.status_code == HTTPStatus.CREATED
        data = response.json()

        assert 'added' in data
        assert len(data['added']) == tasks
        assert data['already_exists'] == []
        assert mock_find.call_count == tasks
        mock_find.assert_any_call('example.com', ANY)
        mock_find.assert_any_call('test.com', ANY)

    results = (
        await session.execute(
            Domain.__table__.select().where(Domain.user_id == user.id)
        )
    ).all()
    assert len(results) == tasks


def test_get_domains(client, token, domain):
    response = client.get(
        '/domains/', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.OK
    domain_name = {'name': domain.name}

    assert response.json()['domains'][0]['name'] == domain_name['name']


def test_delete_domain(client, token, domain):
    response = client.delete(
        f'/domains/{domain.id}', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['message'] == 'Domain deleted'


def test_delete_domain_with_error(client, token):
    response = client.delete(
        '/domains/100', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail'] == 'Domain not found'
