from __future__ import annotations

from datetime import datetime, timezone


def encode_cursor(created_at: datetime, _id: int) -> str:
    if created_at.tzinfo is not None:
        created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
    return f'{created_at.isoformat()}|{_id}'


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    ts_str, id_str = cursor.split('|', 1)
    ts = datetime.fromisoformat(ts_str)
    if ts.tzinfo is not None:
        ts = ts.replace(tzinfo=None)
    return ts, int(id_str)
