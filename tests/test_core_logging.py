from __future__ import annotations

import logging

from auto_recon_api.core.logging import configure_logging


def test_configure_logging_adds_handler_and_restores_state():
    root = logging.getLogger()
    # backup handlers
    handlers_backup = list(root.handlers)

    # ensure clean state
    root.handlers.clear()
    try:
        configure_logging()
        assert root.handlers, "configure_logging should add at least one handler"  # noqa: E501
    finally:
        # restore
        root.handlers[:] = handlers_backup


def test_configure_logging_no_duplicate_when_handlers_exist():
    root = logging.getLogger()
    handlers_backup = list(root.handlers)

    # ensure there is at least one handler
    root.handlers.clear()
    root.addHandler(logging.StreamHandler())
    try:
        before = list(root.handlers)
        configure_logging()
        after = list(root.handlers)
        assert len(
            after
        ) == len(before), "configure_logging should not add duplicate handlers"
    finally:
        root.handlers[:] = handlers_backup
