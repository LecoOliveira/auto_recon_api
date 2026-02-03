from http import HTTPStatus


def test_token_wrong_password(client, user):
    response = client.post(
        '/api/v1/auth/token/',
        data={'username': user.email, 'password': 'wrongpassword'},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()['message'] == 'Incorrect username or password'


def test_token_wrong_user(client):
    response = client.post(
        '/api/v1/auth/token/',
        data={'username': 'úser', 'password': 'wrongpassword'},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()['message'] == 'Incorrect username or password'


def test_refresh_token(client, token):
    response = client.post(
        '/api/v1/auth/refresh_token',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['token_type'] == 'bearer'
