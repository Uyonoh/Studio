"""Opaque cursor pagination utilities.

Cursors are base64-encoded ``created_at|id`` pairs so they remain stable
across concurrent inserts (unlike plain offset pagination).
"""

import base64
from datetime import datetime
from uuid import UUID


def encode_cursor(created_at: datetime, item_id: UUID) -> str:
    """Encode a (created_at, id) pair into an opaque base64 cursor string."""
    raw = f"{created_at.isoformat()}|{item_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """Decode a cursor string back to (created_at, id).

    Raises ``ValueError`` if the cursor is malformed or cannot be decoded.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_str, id_str = raw.split("|", 1)
        return datetime.fromisoformat(ts_str), UUID(id_str)
    except Exception as exc:
        raise ValueError(f"Invalid pagination cursor: {cursor!r}") from exc
