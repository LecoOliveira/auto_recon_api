from http import HTTPStatus


def test_create_user(client):
    response = client.post(
        '/users/',
        json={
            'username': 'teste',
            'email': 'teste@teste.com',
            'password': 'teste',
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['username'] == 'teste'


def test_update_user(client, user, token):
    response = client.put(
        f'/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'username': 'new_username',
            'email': 'test@email.com',
            'password': 'new_password',
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        'id': user.id,
        'username': 'new_username',
        'email': 'test@email.com',
    }
