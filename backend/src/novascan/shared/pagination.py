"""Shared pagination cursor helpers for DynamoDB GSI1 queries.

Extracted from receipts.py and transactions.py to eliminate duplication
of security-critical cursor validation logic (see wave-m5-1 review [S2]).
"""

from __future__ import annotations

import base64
import json
from typing import Any

# Expected keys in a valid GSI1 pagination cursor
VALID_CURSOR_KEYS = {"GSI1PK", "GSI1SK", "PK", "SK"}


def encode_cursor(last_key: dict[str, Any]) -> str:
    """Base64-encode DynamoDB LastEvaluatedKey as opaque pagination cursor."""
    return base64.urlsafe_b64encode(json.dumps(last_key).encode()).decode()


def decode_cursor(cursor: str, *, user_id: str) -> dict[str, Any]:
    """Decode and validate opaque pagination cursor.

    Validates that:
    - Decoded JSON has exactly {GSI1PK, GSI1SK, PK, SK} keys (H1 mitigation)
    - GSI1PK and PK match USER#{authenticated_userId} (ownership check)

    Raises:
        ValueError: If cursor is invalid or targets another user.
    """
    try:
        decoded = json.loads(base64.urlsafe_b64decode(cursor))
    except Exception as e:
        raise ValueError(f"Cursor decode failed: {type(e).__name__}") from e

    if not isinstance(decoded, dict):
        raise ValueError("Cursor must decode to a JSON object")

    if set(decoded.keys()) != VALID_CURSOR_KEYS:
        raise ValueError(f"Cursor has invalid keys: {set(decoded.keys())}")

    expected_user = f"USER#{user_id}"
    if decoded.get("GSI1PK") != expected_user:
        raise ValueError("Cursor GSI1PK does not match authenticated user")
    if decoded.get("PK") != expected_user:
        raise ValueError("Cursor PK does not match authenticated user")

    return decoded
