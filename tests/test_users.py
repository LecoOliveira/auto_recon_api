from http import HTTPStatus


def test_create_user(client):
    response = client.post(
        '/api/v1/users/',
        json={
            'username': 'teste',
            'email': 'teste@teste.com',
            'password': 'teste',
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['username'] == 'teste'


def test_create_user_username_exists(client, user):
    response = client.post(
        '/api/v1/users/',
        json={
            'username': user.username,
            'email': 'test@mail.com',
            'password': '123456',
        },
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['message'] == 'Username or email already used'


def test_create_user_email_exists(client, user):
    response = client.post(
        '/api/v1/users/',
        json={
            'username': 'test',
            'email': user.email,
            'password': '123456',
        },
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()['message'] == 'Username or email already used'


def test_read_user(client, user, token):
    response = client.get(
        f'/api/v1/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        'id': user.id,
        'username': user.username,
        'email': user.email,
    }


def test_get_user_not_found(client, token, user_2):
    response = client.get(
        f'/api/v1/users/{user_2.id}',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['message'] == 'Not enough permissions'


def test_update_user(client, user, token):
    response = client.put(
        f'/api/v1/users/{user.id}',
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


def test_update_other_user(client, user_2, token):
    response = client.put(
        f'/api/v1/users/{user_2.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'username': 'new_username',
            'email': 'test@email.com',
            'password': 'new_password',
        },
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_update_user_already_exists(client, user_2, user, token):
    response = client.put(
        f'/api/v1/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'username': user_2.username,
            'email': 'test@email.com',
            'password': 'new_password',
        },
    )

    assert response.status_code == HTTPStatus.CONFLICT


def test_delete_user(client, user, token):
    response = client.delete(
        f'/api/v1/users/{user.id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['message'] == 'User deleted successfully'


def test_delete_user_without_permissions(client, user_2, token):
    response = client.delete(
        f'/api/v1/users/{user_2.id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()['message'] == 'Not enough permissions'
