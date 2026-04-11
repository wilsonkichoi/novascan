"""Tests for Bedrock Extract Lambda handler (shadow pipeline).

Validates the spec contract from SPEC.md Section 3 (Processing Flow):
- Receives S3 image reference + optional custom categories
- Sends image directly to Bedrock Nova (multimodal) for extraction
- Returns ExtractionResult, modelId, and processingTimeMs on success
- Returns error payload on Bedrock/S3 error
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Lambda context stub
# ---------------------------------------------------------------------------


@dataclass
class FakeLambdaContext:
    """Minimal Lambda context for Lambda Powertools."""

    function_name: str = "bedrock-extract"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:bedrock-extract"
    aws_request_id: str = "test-request-id"


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------


_VALID_EXTRACTION_JSON = json.dumps({
    "merchant": {"name": "Target", "address": "456 Oak Ave"},
    "receiptDate": "2026-03-20",
    "currency": "USD",
    "lineItems": [
        {"name": "T-Shirt", "quantity": 2, "unitPrice": 12.99, "totalPrice": 25.98},
        {"name": "Socks", "quantity": 1, "unitPrice": 4.99, "totalPrice": 4.99},
    ],
    "subtotal": 30.97,
    "tax": 2.55,
    "total": 33.52,
    "category": "retail-shopping",
    "subcategory": "department-store",
    "paymentMethod": "VISA *5678",
    "confidence": 0.89,
})


def _make_event(
    bucket: str = "test-bucket",
    key: str = "receipts/01XYZ789ABCDEF012345JKLM90.jpg",
    custom_categories: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build an event matching the Step Functions input shape for Bedrock Extract."""
    return {
        "bucket": bucket,
        "key": key,
        "customCategories": custom_categories or [],
    }


def _make_bedrock_response(text: str) -> dict[str, Any]:
    """Build a mock Bedrock invoke_model response."""
    body = json.dumps({
        "output": {
            "message": {
                "content": [{"text": text}],
            }
        }
    })
    mock_body = MagicMock()
    mock_body.read.return_value = body.encode("utf-8")
    return {"body": mock_body}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _pipeline_env(monkeypatch):
    """Set env vars for pipeline Lambdas and disable tracing/metrics."""
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "novascan-test")
    monkeypatch.setenv("POWERTOOLS_TRACE_DISABLED", "1")
    monkeypatch.setenv("POWERTOOLS_METRICS_NAMESPACE", "NovaScanTest")
    monkeypatch.setenv("NOVA_MODEL_ID", "amazon.nova-lite-v1:0")
    monkeypatch.setenv("RECEIPTS_BUCKET", "test-bucket")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoke_handler(event: dict[str, Any]) -> dict[str, Any]:
    """Import and invoke the bedrock_extract handler."""
    from pipeline.bedrock_extract import handler

    return handler(event, FakeLambdaContext())


# ---------------------------------------------------------------------------
# Successful extraction
# ---------------------------------------------------------------------------


class TestBedrockExtractSuccess:
    """Valid image -> valid ExtractionResult via Bedrock Nova multimodal."""

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_returns_extraction_result(self, mock_s3, mock_bedrock):
        """Successful extraction returns extractionResult dict."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image"), "ContentLength": 10}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert "extractionResult" in result, "Success response must contain extractionResult"
        assert isinstance(result["extractionResult"], dict)

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_extraction_matches_spec_schema(self, mock_s3, mock_bedrock):
        """ExtractionResult must match SPEC Section 7 schema."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image"), "ContentLength": 10}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())
        extraction = result["extractionResult"]

        # Top-level required fields per SPEC Section 7
        assert "merchant" in extraction
        assert "name" in extraction["merchant"]
        assert "lineItems" in extraction
        assert isinstance(extraction["lineItems"], list)
        assert "total" in extraction
        assert "category" in extraction
        assert "subcategory" in extraction
        assert "confidence" in extraction

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_returns_model_id(self, mock_s3, mock_bedrock):
        """Response must include the Bedrock model ID used."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image"), "ContentLength": 10}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert "modelId" in result
        assert isinstance(result["modelId"], str)
        assert len(result["modelId"]) > 0

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_returns_processing_time_ms(self, mock_s3, mock_bedrock):
        """Response must include processingTimeMs as a non-negative integer."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image"), "ContentLength": 10}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert "processingTimeMs" in result
        assert isinstance(result["processingTimeMs"], int)
        assert result["processingTimeMs"] >= 0

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_no_error_key_on_success(self, mock_s3, mock_bedrock):
        """Success response must NOT contain error/errorType."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image"), "ContentLength": 10}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert "error" not in result
        assert "errorType" not in result

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_handles_markdown_wrapped_json(self, mock_s3, mock_bedrock):
        """Bedrock may wrap JSON in markdown code fences; handler must strip them."""
        wrapped = f"```json\n{_VALID_EXTRACTION_JSON}\n```"
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image"), "ContentLength": 10}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(wrapped)

        result = _invoke_handler(_make_event())

        assert "extractionResult" in result
        assert result["extractionResult"]["merchant"]["name"] == "Target"

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_png_image_handled(self, mock_s3, mock_bedrock):
        """PNG images should be processed correctly (media type inferred)."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-png"), "ContentLength": 8}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event(key="receipts/01XYZ789ABCDEF012345JKLM90.png"))

        assert "extractionResult" in result

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_custom_categories_accepted(self, mock_s3, mock_bedrock):
        """Handler accepts custom categories without error."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image"), "ContentLength": 10}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        custom_cats = [
            {"slug": "pet-supplies", "displayName": "Pet Supplies", "parentCategory": "other"}
        ]
        result = _invoke_handler(_make_event(custom_categories=custom_cats))

        assert "extractionResult" in result

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_extraction_confidence_in_valid_range(self, mock_s3, mock_bedrock):
        """Confidence from extraction should be within [0.0, 1.0]."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image"), "ContentLength": 10}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        confidence = result["extractionResult"]["confidence"]
        assert 0.0 <= confidence <= 1.0, f"Confidence {confidence} out of [0, 1] range"


# ---------------------------------------------------------------------------
# Bedrock API errors
# ---------------------------------------------------------------------------


class TestBedrockExtractErrors:
    """Bedrock/S3 failures return error payloads, not exceptions."""

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_bedrock_error_returns_error_payload(self, mock_s3, mock_bedrock):
        """Bedrock API exception should produce an error payload."""
        from botocore.exceptions import ClientError

        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image"), "ContentLength": 10}
        mock_bedrock.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ModelTimeoutException", "Message": "Model timed out"}},
            "InvokeModel",
        )

        result = _invoke_handler(_make_event())

        assert "error" in result, "Error response must contain 'error' key"
        assert "errorType" in result, "Error response must contain 'errorType' key"

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_s3_error_returns_error_payload(self, mock_s3, mock_bedrock):
        """S3 read failure returns error payload."""
        from botocore.exceptions import ClientError

        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

        result = _invoke_handler(_make_event())

        assert "error" in result
        assert "errorType" in result

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_malformed_json_returns_error_payload(self, mock_s3, mock_bedrock):
        """Invalid JSON from Bedrock should return error payload."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image"), "ContentLength": 10}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response("this is not json")

        result = _invoke_handler(_make_event())

        assert "error" in result
        assert "errorType" in result

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_error_payload_has_no_extraction_result(self, mock_s3, mock_bedrock):
        """Error payloads must NOT contain extractionResult."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image"), "ContentLength": 10}
        mock_bedrock.invoke_model.side_effect = RuntimeError("crash")

        result = _invoke_handler(_make_event())

        assert "extractionResult" not in result

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_error_does_not_raise(self, mock_s3, mock_bedrock):
        """Handler must catch all exceptions and return payload."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image"), "ContentLength": 10}
        mock_bedrock.invoke_model.side_effect = Exception("Unexpected")

        result = _invoke_handler(_make_event())
        assert isinstance(result, dict)
        assert "error" in result
        # H4 — Error sanitization: no raw exception text in error
        assert result["error"] == "bedrock_extract_failed"

    def test_missing_bucket_returns_invalid_event(self):
        """Missing bucket should return invalid_event immediately."""
        result = _invoke_handler({"key": "receipts/01XYZ789ABCDEF012345JKLM90.jpg"})
        assert result["error"] == "invalid_event"

    def test_missing_key_returns_invalid_event(self):
        """Missing key should return invalid_event immediately."""
        result = _invoke_handler({"bucket": "test-bucket"})
        assert result["error"] == "invalid_event"

    def test_invalid_s3_key_returns_invalid_event(self):
        """Invalid S3 key format should return invalid_event."""
        result = _invoke_handler({"bucket": "test-bucket", "key": "../../etc/passwd"})
        assert result["error"] == "invalid_event"

    @patch("pipeline.bedrock_extract.bedrock_client")
    @patch("pipeline.bedrock_extract.s3_client")
    def test_incomplete_extraction_still_valid(self, mock_s3, mock_bedrock):
        """Bedrock returning minimal valid JSON (just merchant name) should succeed."""
        minimal_json = json.dumps({
            "merchant": {"name": "Unknown Store"},
        })
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image"), "ContentLength": 10}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(minimal_json)

        result = _invoke_handler(_make_event())

        assert "extractionResult" in result
        assert result["extractionResult"]["merchant"]["name"] == "Unknown Store"
        # Defaults should be applied per SPEC Section 7
        assert result["extractionResult"]["category"] == "other"
        assert result["extractionResult"]["confidence"] == 0.0
