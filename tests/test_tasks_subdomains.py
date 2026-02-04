from __future__ import annotations

import pytest

import auto_recon_api.tasks.subdomains as tsub


class DummyResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class DummySession:
    def __init__(self, scalar_return=None):
        self._scalar_return = scalar_return
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def scalar(self, *a, **k):
        return self._scalar_return

    def begin(self):
        return self

    def add(self, o):
        self.added.append(o)


class DummyCtx:
    def __init__(self, sess):
        self.sess = sess

    async def __aenter__(self):
        return self.sess

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_find_subdomains_success(monkeypatch):
    domain_obj = type(
        'D',
        (),
        {
            'id': 1,
            'name': 'example.com',
            'status': 'pending',
        },
    )()
    sess = DummySession(scalar_return=domain_obj)
    monkeypatch.setattr(tsub, 'SessionLocal', lambda: DummyCtx(sess))

    class FakeResp:
        @staticmethod
        def raise_for_status():
            pass

        @staticmethod
        def json():
            return {'subdomains': [{'host': 'a.example.com', 'ip': '1.2.3.4'}]}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        @staticmethod
        async def post(url, params=None):
            return FakeResp()

    FakeX = type('X', (), {'AsyncClient': lambda *a, **k: FakeClient()})
    monkeypatch.setattr(tsub, 'httpx', FakeX)

    await tsub.find_subdomains('example.com', 1)
    # domain_obj should have been set to done
    assert domain_obj.status == 'done'


@pytest.mark.asyncio
async def test_find_subdomains_invalid_json_sets_failed(monkeypatch):
    domain_obj = type(
        'D',
        (),
        {
            'id': 2,
            'name': 'bad.com',
            'status': 'pending',
        },
    )()
    sess = DummySession(scalar_return=domain_obj)
    monkeypatch.setattr(tsub, 'SessionLocal', lambda: DummyCtx(sess))

    class BadResp:
        @staticmethod
        def raise_for_status():
            pass

        @staticmethod
        def json():
            raise ValueError('no json')

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        @staticmethod
        async def post(url, params=None):
            return BadResp()

    FakeX = type('X', (), {'AsyncClient': lambda *a, **k: FakeClient()})
    monkeypatch.setattr(tsub, 'httpx', FakeX)

    # run and ensure it doesn't raise unhandled exception
    await tsub.find_subdomains('bad.com', 2)
    # domain_obj should be marked failed
    assert domain_obj.status == 'failed'
