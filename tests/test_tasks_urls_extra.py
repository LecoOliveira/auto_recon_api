from __future__ import annotations

import asyncio
import json

import pytest

import auto_recon_api.tasks.urls as urls_mod
from tests.test_tasks_urls import (
    DummyClient,
    DummyCtx,
    DummyJob,
    DummyResultFetchall,
    DummySession,
)

TWO = 2


def make_obj(i):
    return {
        'url': f'https://a.example.com/p{i}',
        'host': 'a.example.com',
        'hostname': 'a.example.com',
        'port': 443,
        'status_code': 200,
        'title': 't',
        'tech': None,
    }


def test_scan_urls_for_domain_multiple_flushes(monkeypatch):
    sess = DummySession(scalar_return=['a.example.com'])
    monkeypatch.setattr(urls_mod, 'SessionLocal', lambda: DummyCtx(sess))

    lines = [json.dumps(make_obj(1)), json.dumps(make_obj(2))]

    class FakeX:
        @staticmethod
        def AsyncClient(*_a, **_k):
            return DummyClient(lines=lines)

    monkeypatch.setattr(urls_mod, 'httpx', FakeX)

    # force flush after each item
    monkeypatch.setattr(urls_mod, 'BATCH_SIZE', 1)

    async def fake_flush(sessionmaker, rows):
        return len(rows)

    monkeypatch.setattr(urls_mod, '_flush_urls', fake_flush)

    job = DummyJob()
    monkeypatch.setattr(urls_mod, 'get_current_job', lambda: job)

    out = urls_mod.scan_urls_for_domain(1, 2)

    assert out['seen'] == TWO
    assert out['inserted'] == TWO
    assert out['errors'] == 0
    assert job.meta['phase'] == 'finished'


def test__flush_urls_returns_zero_when_nothing(monkeypatch):
    result = DummyResultFetchall([])
    sess = DummySession(execute_return=result)
    monkeypatch.setattr(urls_mod, 'SessionLocal', lambda: DummyCtx(sess))

    out = asyncio.run(urls_mod._flush_urls(urls_mod.SessionLocal, []))
    assert out == 0


def test_scan_urls_for_domain_flush_raises_sets_failed(monkeypatch):
    sess = DummySession(scalar_return=['a.example.com'])
    monkeypatch.setattr(urls_mod, 'SessionLocal', lambda: DummyCtx(sess))

    lines = [json.dumps(make_obj(1))]

    class FakeX2:
        @staticmethod
        def AsyncClient(*_a, **_k):
            return DummyClient(lines=lines)

    monkeypatch.setattr(urls_mod, 'httpx', FakeX2)

    async def fake_flush(sessionmaker, rows):
        raise RuntimeError('boom')

    monkeypatch.setattr(urls_mod, '_flush_urls', fake_flush)

    job = DummyJob()
    monkeypatch.setattr(urls_mod, 'get_current_job', lambda: job)

    with pytest.raises(RuntimeError):
        urls_mod.scan_urls_for_domain(1, 2)

    assert job.meta['phase'] == 'failed'
    assert job.meta['errors'] >= 1
