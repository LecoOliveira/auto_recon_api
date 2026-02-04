from __future__ import annotations

import pytest

from auto_recon_api.core.pagination import decode_cursor


def test_decode_cursor_invalid_raises():
    with pytest.raises(ValueError):  # noqa: PT011
        # missing separator and invalid ISO timestamp
        decode_cursor("invalid-cursor")
