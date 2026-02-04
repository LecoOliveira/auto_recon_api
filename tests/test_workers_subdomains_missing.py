from __future__ import annotations

from auto_recon_api.workers import subdomains as sub_mod

TOTAL = 3
CURRENT = 5
FAILED_ID = 9


class SimpleJob:
    def __init__(self):
        self.meta = {}
        self.saved = 0

    def save_meta(self):
        self.saved += 1


def test_helpers_noop_with_various_falsey_values():
    # Should be no-ops and not raise for multiple falsey values
    falsy = [None, False, 0, ""]
    for val in falsy:
        sub_mod._init_job_meta(val, [1])
        assert sub_mod._job_touch(val) is None
        assert sub_mod._job_set_current(val, 1, "x") is None
        assert sub_mod._job_mark_done(val, 1) is None
        assert sub_mod._job_mark_failed(val, 1, "err") is None


def test_job_helpers_mutate_meta_and_save_called():
    job = SimpleJob()
    # init should populate meta and call save_meta once
    sub_mod._init_job_meta(job, [5, 6, 7])
    assert job.meta["total"] == TOTAL
    assert job.meta["domain_ids"] == [5, 6, 7]

    before = job.saved
    # touch should update updated_at and call save_meta
    sub_mod._job_touch(job)
    assert job.saved > before

    # set current
    sub_mod._job_set_current(job, CURRENT, "example.com")
    assert job.meta["current_domain_id"] == CURRENT
    assert job.meta["current_domain"] == "example.com"

    # mark done
    sub_mod._job_mark_done(job, CURRENT)
    assert CURRENT in job.meta["done_domain_ids"]

    # mark failed
    sub_mod._job_mark_failed(job, FAILED_ID, "something bad")
    assert FAILED_ID in job.meta["failed_domain_ids"]
    assert job.meta["errors_by_domain"][str(FAILED_ID)] == "something bad"
    assert f"domain_id={FAILED_ID}" in job.meta["last_error"]
