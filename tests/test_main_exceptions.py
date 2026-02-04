from __future__ import annotations

import json

import pytest
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from auto_recon_api.main import create_app


def make_request():
    return Request({'type': 'http', 'method': 'GET', 'path': '/'})


@pytest.mark.asyncio
async def test_http_exception_handler_with_string_detail():
    app = create_app()
    exc = StarletteHTTPException(status_code=400, detail='oops')

    r = await app.exception_handlers[type(exc)](make_request(), exc)
    body = json.loads(r.body)
    assert body['code'] == 'http_error'
    assert body['message'] == 'oops'
    assert body['details'] is None


@pytest.mark.asyncio
async def test_http_exception_handler_with_non_string_detail():
    app = create_app()
    detail = {'x': 1}
    exc = StarletteHTTPException(status_code=400, detail=detail)

    r = await app.exception_handlers[type(exc)](make_request(), exc)
    body = json.loads(r.body)
    assert body['code'] == 'http_error'
    assert body['message'] == 'Request error'
    assert body['details'] == detail


@pytest.mark.asyncio
async def test_request_validation_handler():
    app = create_app()
    errors = [{'loc': ['body'], 'msg': 'bad', 'type': 'value_error'}]
    exc = RequestValidationError(errors)

    r = await app.exception_handlers[type(exc)](make_request(), exc)
    body = json.loads(r.body)
    assert body['code'] == 'validation_error'
    assert body['message'] == 'Invalid input'
    assert body['details'] == errors


@pytest.mark.asyncio
async def test_unhandled_exception_handler():
    app = create_app()
    exc = Exception('boom')

    r = await app.exception_handlers[type(exc)](make_request(), exc)
    body = json.loads(r.body)
    assert body['code'] == 'internal_error'
    assert body['message'] == 'Internal server error'
