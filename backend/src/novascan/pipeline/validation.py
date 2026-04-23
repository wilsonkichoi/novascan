"""Shared validation utilities for pipeline Lambda functions.

Provides event validation, S3 key validation, and image size guard
functions used by all pipeline Lambdas.

SECURITY-REVIEW references: H5 (S3 key validation), H6 (event validation),
L5 (image size guard).
"""

from __future__ import annotations

import re
from typing import Any

# S3 key format: receipts/{ULID}.{jpg|jpeg|png}
# ULID is 26 chars of Crockford's Base32 (uppercase alphanumeric)
_S3_KEY_PATTERN = re.compile(r"^receipts/[A-Za-z0-9]{26}\.(jpg|jpeg|png)$")

# Maximum image size in bytes (10 MB)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

# Allowed model IDs for Nova/Bedrock Lambdas (M8)
ALLOWED_MODEL_IDS = frozenset({
    "amazon.nova-lite-v1:0",
    "amazon.nova-pro-v1:0",
    "us.amazon.nova-2-lite-v1:0",
})


def validate_event_fields(event: dict[str, Any], required_fields: list[str]) -> list[str]:
    """Validate that all required fields are present and non-empty in the event.

    Returns a list of missing/empty field names. Empty list means validation passed.
    """
    missing = []
    for field in required_fields:
        value = event.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing


def validate_s3_key(key: str, bucket: str, expected_bucket: str) -> bool:
    """Validate S3 key matches expected receipt format and bucket matches expected bucket.

    H5 — S3 key must match: receipts/{ULID}.{jpg|jpeg|png}
    Bucket must match the RECEIPTS_BUCKET env var (if set).
    """
    if not _S3_KEY_PATTERN.match(key):
        return False
    # If expected bucket is configured, enforce match
    return not (expected_bucket and bucket != expected_bucket)


def validate_model_id(model_id: str) -> bool:
    """Validate that the model ID is in the allowlist.

    M8 — Only allowlisted Nova model IDs are accepted.
    """
    return model_id in ALLOWED_MODEL_IDS


def check_image_size(content_length: int) -> None:
    """Check that image size does not exceed the maximum allowed size.

    L5 — Max 10MB. Raises ValueError if exceeded.
    """
    if content_length > MAX_IMAGE_SIZE_BYTES:
        raise ValueError(
            f"Image size {content_length} bytes exceeds maximum "
            f"allowed size of {MAX_IMAGE_SIZE_BYTES} bytes"
        )
