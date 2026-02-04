from __future__ import annotations

import json

import pytest

import auto_recon_api.tasks.urls as urls_mod
from auto_recon_api.tasks.urls import (
    chunks,
    normalize_url,
    scan_urls_for_domain,
    url_hash,
)

# constants
URL_HASH_LEN = 64
FIVE = 5
TWO = 2


class DummyJob:
    def __init__(self):
        self.meta = {}
        self.saved = 0

    def save_meta(self):
        self.saved += 1


class DummyResultScalars:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class DummyResultFetchall:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class DummySession:
    def __init__(self, scalar_return=None, execute_return=None):
        self._scalar_return = scalar_return
        self._execute_return = execute_return
        self.added = []
        self.committed = False

    async def execute(self, *args, **kwargs):
        # If a specific execute_return was provided, return it.
        # Otherwise, if a scalar_return was provided assume this execute()
        # corresponds to a select(...).scalars().all()
        if self._execute_return is not None:
            return self._execute_return
        if self._scalar_return is not None:
            return DummyResultScalars(self._scalar_return)
        return DummyResultScalars([])

    async def scalar(self, *args, **kwargs):
        return self._scalar_return

    async def commit(self):
        self.committed = True

    async def refresh(self, *args, **kwargs):
        pass

    def add(self, obj):
        self.added.append(obj)


class DummyCtx:
    def __init__(self, sess):
        self.sess = sess

    async def __aenter__(self):
        return self.sess

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyStream:
    def __init__(self, lines):
        self._lines = lines

    @staticmethod
    def raise_for_status():
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class DummyClient:
    def __init__(self, timeout=None, lines=None):
        self._lines = lines or []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method, url, headers=None, json=None):
        return DummyCtx(DummyStream(self._lines))


def test_normalize_url_variants():
    assert normalize_url('HTTP://Example.COM') == 'http://example.com/'
    assert normalize_url('example.com/path/') == 'http://example.com/path'
    assert normalize_url('https://example.com/path?x=1') == 'https://example.com/path?x=1'
    assert normalize_url('  example.com  ') == 'http://example.com/'


def test_url_hash_is_stable():
    h1 = url_hash('http://example.com/')
    h2 = url_hash('http://example.com/')
    assert h1 == h2
    assert len(h1) == URL_HASH_LEN


def test_chunks():
    lst = list(range(7))
    parts = list(chunks(lst, 3))
    assert parts == [[0, 1, 2], [3, 4, 5], [6]]


def test_meta_init_and_update_no_job():
    # should be no-op
    urls_mod._meta_init(None)
    urls_mod._meta_update(None, foo=1)


def test_meta_init_and_update_with_job():
    j = DummyJob()
    urls_mod._meta_init(j)
    assert j.meta['phase'] == 'starting'
    assert j.meta['seen'] == 0
    urls_mod._meta_update(j, seen=FIVE)
    assert j.meta['seen'] == FIVE


def test_scan_urls_for_domain_no_hosts_sets_finished_meta(monkeypatch):
    # session returns no hosts
    # the first scalar call should return []
    sess = DummySession(scalar_return=[])
    monkeypatch.setattr(urls_mod, 'SessionLocal', lambda: DummyCtx(sess))

    job = DummyJob()
    monkeypatch.setattr(urls_mod, 'get_current_job', lambda: job)

    out = scan_urls_for_domain(1, 2)
    assert out == {'seen': 0, 'inserted': 0, 'errors': 0}
    assert job.meta['phase'] == 'finished'


def test_scan_urls_for_domain_with_hosts_and_stream(monkeypatch):
    # session returns list of hosts
    sess = DummySession(scalar_return=['a.example.com'])
    monkeypatch.setattr(urls_mod, 'SessionLocal', lambda: DummyCtx(sess))

    # prepare http lines coming from tool
    obj = {
        'url': 'https://a.example.com/p',
        'host': 'a.example.com',
        'hostname': 'a.example.com',
        'port': 443,
        'status_code': 200,
        'title': 't',
        'tech': None,
    }
    lines = [json.dumps(obj)]

    # replace AsyncClient with our DummyClient
    class FakeX:
        @staticmethod
        def AsyncClient(*_a, **_k):
            return DummyClient(lines=lines)

    monkeypatch.setattr(urls_mod, 'httpx', FakeX)

    # patch flush to return 1 inserted
    async def fake_flush(sessionmaker, rows):
        return 1

    monkeypatch.setattr(urls_mod, '_flush_urls', fake_flush)

    job = DummyJob()
    monkeypatch.setattr(urls_mod, 'get_current_job', lambda: job)

    out = scan_urls_for_domain(1, 2)
    assert out['seen'] == 1
    assert out['inserted'] == 1
    assert out['errors'] == 0
    assert job.meta['phase'] == 'finished'


def test_scan_urls_for_domain_exception_sets_failed(monkeypatch):
    # force asyncio.run to raise
    def fake_run(x, *a, **k):
        raise RuntimeError('boom')

    monkeypatch.setattr('asyncio.run', fake_run)

    job = DummyJob()
    monkeypatch.setattr(urls_mod, 'get_current_job', lambda: job)

    with pytest.raises(RuntimeError):
        scan_urls_for_domain(1, 2)

    assert job.meta['phase'] == 'failed'
    assert job.meta['errors'] >= 1
    assert 'boom' in job.meta.get('last_error', '')


@pytest.mark.asyncio
async def test__flush_urls_returns_count(monkeypatch):
    result = DummyResultFetchall([(1,), (2,)])
    sess = DummySession(execute_return=result)
    monkeypatch.setattr(urls_mod, 'SessionLocal', lambda: DummyCtx(sess))

    out = await urls_mod._flush_urls(urls_mod.SessionLocal, [])
    assert out == TWO
