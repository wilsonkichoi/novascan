"""Shared API response helpers.

Extracted from receipts.py, transactions.py, and categories.py to eliminate
duplication of the standard error response builder (see wave-m5-1 review [S2]).
"""

from __future__ import annotations

import json
from typing import Any

from aws_lambda_powertools.event_handler import Response, content_types


def error_response(status_code: int, code: str, message: str) -> Response[Any]:
    """Build a standard error response."""
    return Response(
        status_code=status_code,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps({"error": {"code": code, "message": message}}),
    )
