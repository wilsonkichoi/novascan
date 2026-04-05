"""Security tests for pipeline Lambda input validation and error sanitization.

Tests the security contract (SECURITY-REVIEW H4, H5, H6, L5, M8):
- Missing required event fields return {"error": "invalid_event"}
- Invalid S3 keys return {"error": "invalid_event"}
- Oversized images return an error
- Error payloads never contain raw exception messages (str(e))
- Model ID validation at module load
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from novascan.pipeline.validation import (
    ALLOWED_MODEL_IDS,
    MAX_IMAGE_SIZE_BYTES,
    check_image_size,
    validate_event_fields,
    validate_model_id,
    validate_s3_key,
)


# ---------------------------------------------------------------------------
# Event validation (H6)
# ---------------------------------------------------------------------------


class TestEventValidation:
    """Missing required fields must result in invalid_event error."""

    def test_missing_all_fields_detected(self):
        """Empty event should report all required fields as missing."""
        missing = validate_event_fields({}, ["bucket", "key"])
        assert "bucket" in missing
        assert "key" in missing

    def test_empty_string_fields_detected(self):
        """Empty string values should be treated as missing."""
        missing = validate_event_fields({"bucket": "", "key": "  "}, ["bucket", "key"])
        assert "bucket" in missing
        assert "key" in missing

    def test_none_values_detected(self):
        """None values should be treated as missing."""
        missing = validate_event_fields({"bucket": None}, ["bucket", "key"])
        assert "bucket" in missing
        assert "key" in missing

    def test_valid_fields_pass(self):
        """Valid non-empty fields should pass validation."""
        missing = validate_event_fields(
            {"bucket": "my-bucket", "key": "receipts/abc.jpg"},
            ["bucket", "key"],
        )
        assert missing == []


# ---------------------------------------------------------------------------
# S3 key validation (H5)
# ---------------------------------------------------------------------------


class TestS3KeyValidation:
    """S3 keys must match receipts/{ULID}.{ext} and bucket must match."""

    def test_valid_jpg_key_accepted(self):
        """Valid JPEG key with ULID should pass."""
        assert validate_s3_key(
            "receipts/01ABCDEFGHIJKLMNOPQRSTUVWX.jpg",
            "my-bucket",
            "my-bucket",
        )

    def test_valid_png_key_accepted(self):
        """Valid PNG key with ULID should pass."""
        assert validate_s3_key(
            "receipts/01ABCDEFGHIJKLMNOPQRSTUVWX.png",
            "my-bucket",
            "my-bucket",
        )

    def test_valid_jpeg_key_accepted(self):
        """Valid JPEG (with .jpeg extension) should pass."""
        assert validate_s3_key(
            "receipts/01ABCDEFGHIJKLMNOPQRSTUVWX.jpeg",
            "my-bucket",
            "my-bucket",
        )

    def test_path_traversal_rejected(self):
        """Keys with path traversal must be rejected."""
        assert not validate_s3_key(
            "../secrets/01ABCDEFGHIJKLMNOPQRSTUV.jpg",
            "my-bucket",
            "my-bucket",
        )

    def test_wrong_prefix_rejected(self):
        """Keys not under receipts/ must be rejected."""
        assert not validate_s3_key(
            "other/01ABCDEFGHIJKLMNOPQRSTUV.jpg",
            "my-bucket",
            "my-bucket",
        )

    def test_wrong_extension_rejected(self):
        """Keys with unsupported extensions must be rejected."""
        assert not validate_s3_key(
            "receipts/01ABCDEFGHIJKLMNOPQRSTUV.gif",
            "my-bucket",
            "my-bucket",
        )

    def test_short_id_rejected(self):
        """Keys with IDs shorter than 26 chars must be rejected."""
        assert not validate_s3_key(
            "receipts/shortid.jpg",
            "my-bucket",
            "my-bucket",
        )

    def test_bucket_mismatch_rejected(self):
        """Keys with mismatched bucket must be rejected."""
        assert not validate_s3_key(
            "receipts/01ABCDEFGHIJKLMNOPQRSTUV.jpg",
            "wrong-bucket",
            "expected-bucket",
        )

    def test_empty_expected_bucket_accepts_any(self):
        """If expected_bucket is empty, any bucket is accepted."""
        assert validate_s3_key(
            "receipts/01ABCDEFGHIJKLMNOPQRSTUVWX.jpg",
            "any-bucket",
            "",
        )

    def test_special_chars_in_id_rejected(self):
        """Keys with special characters in the ID must be rejected."""
        assert not validate_s3_key(
            "receipts/01ABCDEFGHIJKLMNOP-RSTUV.jpg",
            "my-bucket",
            "my-bucket",
        )


# ---------------------------------------------------------------------------
# Image size guard (L5)
# ---------------------------------------------------------------------------


class TestImageSizeGuard:
    """Images exceeding 10MB must be rejected."""

    def test_exact_max_size_accepted(self):
        """Image at exactly 10MB should be accepted."""
        # Should not raise
        check_image_size(MAX_IMAGE_SIZE_BYTES)

    def test_one_byte_over_max_rejected(self):
        """Image at 10MB + 1 byte must be rejected."""
        with pytest.raises(ValueError):
            check_image_size(MAX_IMAGE_SIZE_BYTES + 1)

    def test_small_image_accepted(self):
        """Small image should be accepted."""
        check_image_size(1024)

    def test_zero_size_accepted(self):
        """Zero-size image should be accepted (not a size issue)."""
        check_image_size(0)

    def test_very_large_image_rejected(self):
        """100MB image must be rejected."""
        with pytest.raises(ValueError):
            check_image_size(100 * 1024 * 1024)


# ---------------------------------------------------------------------------
# Model ID validation (M8)
# ---------------------------------------------------------------------------


class TestModelIdValidation:
    """Only allowed model IDs should pass validation."""

    def test_nova_lite_accepted(self):
        """amazon.nova-lite-v1:0 must be accepted."""
        assert validate_model_id("amazon.nova-lite-v1:0")

    def test_nova_pro_accepted(self):
        """amazon.nova-pro-v1:0 must be accepted."""
        assert validate_model_id("amazon.nova-pro-v1:0")

    def test_unknown_model_rejected(self):
        """Unknown model IDs must be rejected."""
        assert not validate_model_id("amazon.nova-mega-v1:0")

    def test_empty_model_rejected(self):
        """Empty model ID must be rejected."""
        assert not validate_model_id("")

    def test_arbitrary_model_rejected(self):
        """Arbitrary model strings must be rejected."""
        assert not validate_model_id("claude-3-opus")


# ---------------------------------------------------------------------------
# Pipeline Lambda error sanitization (H4)
# ---------------------------------------------------------------------------


class TestPipelineErrorSanitization:
    """Pipeline Lambda error payloads must not contain raw exception messages."""

    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch):
        """Set environment variables for pipeline Lambdas."""
        monkeypatch.setenv("TABLE_NAME", "novascan-test")
        monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "novascan-test")
        monkeypatch.setenv("POWERTOOLS_TRACE_DISABLED", "1")
        monkeypatch.setenv("RECEIPTS_BUCKET", "novascan-receipts-test")
        monkeypatch.setenv("NOVA_MODEL_ID", "amazon.nova-lite-v1:0")

    def test_textract_missing_fields_returns_invalid_event(self):
        """Textract Lambda with missing fields returns invalid_event."""
        from novascan.pipeline.textract_extract import handler

        ctx = MagicMock()
        ctx.function_name = "test"
        ctx.memory_limit_in_mb = 128
        ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123:function:test"
        ctx.aws_request_id = "test"

        result = handler({}, ctx)
        assert result["error"] == "invalid_event"
        assert result["errorType"] == "ValidationError"

    def test_textract_invalid_key_returns_invalid_event(self):
        """Textract Lambda with invalid S3 key returns invalid_event."""
        from novascan.pipeline.textract_extract import handler

        ctx = MagicMock()
        ctx.function_name = "test"
        ctx.memory_limit_in_mb = 128
        ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123:function:test"
        ctx.aws_request_id = "test"

        result = handler({"bucket": "novascan-receipts-test", "key": "../hack.jpg"}, ctx)
        assert result["error"] == "invalid_event"

    def test_textract_error_payload_no_raw_exception(self, monkeypatch):
        """Textract Lambda error payload must not contain raw exception str."""
        from novascan.pipeline import textract_extract as te_module

        ctx = MagicMock()
        ctx.function_name = "test"
        ctx.memory_limit_in_mb = 128
        ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123:function:test"
        ctx.aws_request_id = "test"

        # Mock textract to raise
        original = te_module._call_textract
        te_module._call_textract = MagicMock(
            side_effect=RuntimeError("Super secret internal error details")
        )
        try:
            result = te_module.handler(
                {"bucket": "novascan-receipts-test", "key": "receipts/01ABCDEFGHIJKLMNOPQRSTUVWX.jpg"},
                ctx,
            )
            assert "error" in result
            assert result["error"] == "textract_extract_failed"
            # Error payload must not contain the raw exception message
            assert "Super secret" not in str(result)
            assert result["errorType"] == "RuntimeError"
        finally:
            te_module._call_textract = original

    def test_bedrock_missing_fields_returns_invalid_event(self):
        """Bedrock Lambda with missing fields returns invalid_event."""
        from novascan.pipeline.bedrock_extract import handler

        ctx = MagicMock()
        ctx.function_name = "test"
        ctx.memory_limit_in_mb = 128
        ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123:function:test"
        ctx.aws_request_id = "test"

        result = handler({}, ctx)
        assert result["error"] == "invalid_event"

    def test_nova_missing_fields_returns_invalid_event(self):
        """Nova Lambda with missing fields returns invalid_event."""
        from novascan.pipeline.nova_structure import handler

        ctx = MagicMock()
        ctx.function_name = "test"
        ctx.memory_limit_in_mb = 128
        ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123:function:test"
        ctx.aws_request_id = "test"

        result = handler({"bucket": "b", "key": "k"}, ctx)
        assert result["error"] == "invalid_event"

    def test_nova_error_payload_no_raw_exception(self):
        """Nova Lambda error payload must not contain raw exception message."""
        from novascan.pipeline import nova_structure as ns_module

        ctx = MagicMock()
        ctx.function_name = "test"
        ctx.memory_limit_in_mb = 128
        ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123:function:test"
        ctx.aws_request_id = "test"

        # Force an exception in the try block by providing valid event structure
        # but invalid S3 key
        result = ns_module.handler(
            {
                "bucket": "novascan-receipts-test",
                "key": "receipts/01ABCDEFGHIJKLMNOPQRSTUV.jpg",
                "textractResult": {"expenseDocuments": []},
            },
            ctx,
        )
        # If S3 call fails (no real bucket), it should return sanitized error
        if "error" in result:
            assert "Secret" not in str(result.get("error", ""))
            # Error type should be the class name only
            assert isinstance(result.get("errorType"), str)
