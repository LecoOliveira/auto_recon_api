from __future__ import annotations

import asyncio

import httpx
import pytest

from auto_recon_api.workers import subdomains as sub_mod

BEGIN_THRESHOLD = 2


@pytest.mark.asyncio
async def test_process_one_domain_http_status_error_marks_failed(monkeypatch):
    # Domain and run objects that will be mutated by the session
    class DomainObj:
        def __init__(self):
            self.id = 10
            self.name = 'example.com'
            self.status = 'pending'

    class RunObj:
        def __init__(self):
            self.status = 'pending'
            self.started_at = None
            self.ended_at = None
            self.error_message = None

    domain = DomainObj()
    run = RunObj()

    # Session that returns domain then run
    # (and again domain/run on later calls)
    class Sess:
        def __init__(self):
            self._calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def scalar(self, *a, **k):  # noqa: PLR6301
            # first scalar -> domain, second -> run, subsequent pattern repeats
            resp = domain if self._calls % 2 == 0 else run
            self._calls += 1
            return resp

        def begin(self):  # noqa: PLR6301
            class Tx:
                async def __aenter__(self):
                    return None

                async def __aexit__(self, *a):
                    return False

            return Tx()

        @staticmethod
        def add(o):
            # ignore adds
            return None

    monkeypatch.setattr(sub_mod, 'get_sessionmaker', lambda: (lambda: Sess()))  # noqa: PLW0108

    # client that raises HTTPStatusError
    class DummyResp:
        status_code = 502
        text = 'bad gateway'

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):  # noqa: PLR6301
            raise httpx.HTTPStatusError(
                'err',
                request=None,
                response=DummyResp(),
            )

    with pytest.raises(RuntimeError) as exc:
        await sub_mod._process_one_domain(
            domain_id=domain.id,
            job_id=1,
            client=Client(),
            semaphore=asyncio.Semaphore(1),
        )

    # ensure domain/run were marked failed and the error message
    # contains the HTTP status
    assert domain.status == 'failed'
    assert run.status == 'failed'
    assert 'HTTP 502' in str(run.error_message)
    assert str(domain.id) in str(exc.value)


@pytest.mark.asyncio
async def test_process_one_domain_invalid_json_sets_failed(monkeypatch):
    # Domain and run objects
    class DomainObj:
        def __init__(self):
            self.id = 11
            self.name = 'bad-json.com'
            self.status = 'pending'

    class RunObj:
        def __init__(self):
            self.status = 'pending'
            self.error_message = None
            self.ended_at = None

    domain = DomainObj()
    run = RunObj()

    class Sess:
        def __init__(self):
            self._calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def scalar(self, *a, **k):  # noqa: PLR6301
            resp = domain if self._calls % 2 == 0 else run
            self._calls += 1
            return resp

        def begin(self):  # noqa: PLR6301
            class Tx:
                async def __aenter__(self):
                    return None

                async def __aexit__(self, *a):
                    return False

            return Tx()

        @staticmethod
        def add(o):
            return None

    monkeypatch.setattr(sub_mod, 'get_sessionmaker', lambda: (lambda: Sess()))  # noqa: PLW0108

    class BadResp:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():  # noqa: PLR6301
            raise ValueError('not json')

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):  # noqa: PLR6301
            return BadResp()

    with pytest.raises(RuntimeError):
        await sub_mod._process_one_domain(
            domain_id=domain.id,
            job_id=2,
            client=Client(),
            semaphore=asyncio.Semaphore(1),
        )

    assert domain.status == 'failed'


@pytest.mark.asyncio
async def test_process_one_domain_persist_failure_logs_and_reraises(
    monkeypatch
):
    # Simulate database begin() raising on second (persistence) attempt
    class DomainObj:
        def __init__(self):
            self.id = 12
            self.name = 'persist-fail.com'
            self.status = 'pending'

    domain = DomainObj()

    class Sess:
        def __init__(self):
            self._begins = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def scalar(self, *a, **k):  # noqa: PLR6301
            return domain

        def begin(self):  # noqa: PLR6301
            self._begins += 1

            class Tx:
                async def __aenter__(self_non):
                    # fail on second begin — the inner persistence after
                    # the exception
                    if self._begins >= BEGIN_THRESHOLD:
                        raise RuntimeError('db broken')

                async def __aexit__(self_non, *a):
                    return False

            return Tx()

        @staticmethod
        def add(o):
            return None

    monkeypatch.setattr(sub_mod, 'get_sessionmaker', lambda: (lambda: Sess()))  # noqa: PLW0108

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):  # noqa: PLR6301
            raise httpx.RequestError('boom')

    with pytest.raises(RuntimeError):
        await sub_mod._process_one_domain(
            domain_id=domain.id,
            job_id=None,
            client=Client(),
            semaphore=asyncio.Semaphore(1),
        )

    # because persisting the failure failed, domain should still be in a
    # previous state or remain running
    assert domain.status in {'running', 'pending'}


def test_init_job_meta_idempotent():
    job = type(
        'J',
        (),
        {
            'meta': {'domain_ids': [1, 2]},
            'saved': 0,
            'save_meta': lambda s: None,
        },
    )()
    # calling again should not alter or save
    sub_mod._init_job_meta(job, [1, 2])
    assert job.meta.get('domain_ids') == [1, 2]


def test_helpers_noop_when_job_none():
    # these should be no-ops and not raise
    sub_mod._init_job_meta(None, [1])
    sub_mod._job_touch(None)
    sub_mod._job_set_current(None, 1, 'x')
    sub_mod._job_mark_done(None, 1)
    sub_mod._job_mark_failed(None, 1, 'msg')


@pytest.mark.asyncio
async def test_process_one_domain_success_with_job_updates_run(monkeypatch):
    class DomainObj:
        def __init__(self):
            self.id = 20
            self.name = 'job-success.com'
            self.status = 'pending'

    class RunObj:
        def __init__(self):
            self.status = 'pending'
            self.started_at = None
            self.ended_at = None
            self.error_message = None

    domain = DomainObj()
    run = RunObj()

    class Sess:
        def __init__(self):
            self._calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def scalar(self, *a, **k):  # noqa: PLR6301
            # domain, run, domain, run sequence
            resp = domain if self._calls % 2 == 0 else run
            self._calls += 1
            return resp

        def begin(self):  # noqa: PLR6301
            class Tx:
                async def __aenter__(self):
                    return None

                async def __aexit__(self, *a):
                    return False

            return Tx()

        @staticmethod
        def add(o):
            return None

    monkeypatch.setattr(sub_mod, 'get_sessionmaker', lambda: (lambda: Sess()))  # noqa: PLW0108

    class FakeResp:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():  # noqa: PLR6301
            return {'subdomains': [{'host': 'a.example.com', 'ip': '1.2.3.4'}]}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):  # noqa: PLR6301
            return FakeResp()

    await sub_mod._process_one_domain(
        domain_id=domain.id,
        job_id=1,
        client=Client(),
        semaphore=asyncio.Semaphore(1),
    )

    assert domain.status == 'done'
    assert run.status == 'done'
    assert run.ended_at is not None
    assert run.error_message is None


@pytest.mark.asyncio
async def test_invalid_json_triggers_http_exception(monkeypatch):
    # ensure ValueError -> HTTPException path executes
    # and is passed into the normalization step
    class DomainObj:
        def __init__(self):
            self.id = 30
            self.name = 'capture-json.com'
            self.status = 'pending'

    domain = DomainObj()

    class Sess:
        def __init__(self):
            self._calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def scalar(self, *a, **k):  # noqa: PLR6301
            # return domain for both select calls
            return domain

        def begin(self):  # noqa: PLR6301
            class Tx:
                async def __aenter__(self):
                    return None

                async def __aexit__(self, *a):
                    return False

            return Tx()

        @staticmethod
        def add(o):
            return None

    monkeypatch.setattr(sub_mod, 'get_sessionmaker', lambda: (lambda: Sess()))  # noqa: PLW0108

    class BadResp:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():  # noqa: PLR6301
            raise ValueError('no json')

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):  # noqa: PLR6301
            return BadResp()

    captured = {}

    def fake_normalize(exc):
        captured['type'] = type(exc)
        return 'captured'

    monkeypatch.setattr(sub_mod, '_normalize_domain_error', fake_normalize)

    with pytest.raises(RuntimeError):
        await sub_mod._process_one_domain(
            domain_id=domain.id,
            job_id=None,
            client=Client(),
            semaphore=asyncio.Semaphore(1),
        )

    assert captured.get('type') is not None
    # the exception forwarded to the normalizer should be an HTTPException
    assert captured.get('type').__name__ == 'HTTPException'
