"""Tests for Nova Structure Lambda handler.

Validates the spec contract from SPEC.md Section 3 (Processing Flow):
- Receives Textract output + S3 image reference + custom categories
- Sends to Bedrock Nova for structured extraction
- Returns ExtractionResult, modelId, and processingTimeMs on success
- Returns error payload on Bedrock API error
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from moto import mock_aws
import boto3


# ---------------------------------------------------------------------------
# Lambda context stub
# ---------------------------------------------------------------------------


@dataclass
class FakeLambdaContext:
    """Minimal Lambda context for Lambda Powertools."""

    function_name: str = "nova-structure"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:nova-structure"
    aws_request_id: str = "test-request-id"


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------


_VALID_EXTRACTION_JSON = json.dumps({
    "merchant": {"name": "Whole Foods Market", "address": "123 Main St"},
    "receiptDate": "2026-03-25",
    "currency": "USD",
    "lineItems": [
        {"name": "Organic Milk", "quantity": 1, "unitPrice": 5.99, "totalPrice": 5.99}
    ],
    "subtotal": 5.99,
    "tax": 0.49,
    "total": 6.48,
    "category": "groceries-food",
    "subcategory": "supermarket-grocery",
    "confidence": 0.92,
})

_TEXTRACT_RESULT = {
    "expenseDocuments": [
        {
            "SummaryFields": [
                {"Type": {"Text": "VENDOR_NAME"}, "ValueDetection": {"Text": "Whole Foods", "Confidence": 99.0}},
                {"Type": {"Text": "TOTAL"}, "ValueDetection": {"Text": "6.48", "Confidence": 97.0}},
            ],
            "LineItemGroups": [],
        }
    ],
    "bucket": "test-bucket",
    "key": "receipts/abc123.jpg",
}


def _make_event(
    bucket: str = "test-bucket",
    key: str = "receipts/abc123.jpg",
    textract_result: dict[str, Any] | None = None,
    custom_categories: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build an event matching the Step Functions input shape for Nova Structure."""
    if textract_result is None:
        textract_result = _TEXTRACT_RESULT
    return {
        "textractResult": textract_result,
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


@pytest.fixture
def s3_with_image():
    """Create a mocked S3 bucket with a test receipt image."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-bucket")
        s3.put_object(Bucket="test-bucket", Key="receipts/abc123.jpg", Body=b"fake-image-bytes")
        yield s3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoke_handler(event: dict[str, Any]) -> dict[str, Any]:
    """Import and invoke the nova_structure handler."""
    from pipeline.nova_structure import handler

    return handler(event, FakeLambdaContext())


# ---------------------------------------------------------------------------
# Successful structuring
# ---------------------------------------------------------------------------


class TestNovaStructureSuccess:
    """Valid Textract output -> valid ExtractionResult via Bedrock Nova."""

    @patch("pipeline.nova_structure.bedrock_client")
    @patch("pipeline.nova_structure.s3_client")
    def test_returns_extraction_result(self, mock_s3, mock_bedrock):
        """Successful structuring returns extractionResult dict."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image")}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert "extractionResult" in result, "Success response must contain extractionResult"
        assert isinstance(result["extractionResult"], dict)

    @patch("pipeline.nova_structure.bedrock_client")
    @patch("pipeline.nova_structure.s3_client")
    def test_extraction_result_has_required_fields(self, mock_s3, mock_bedrock):
        """ExtractionResult must match SPEC Section 7 schema fields."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image")}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())
        extraction = result["extractionResult"]

        assert "merchant" in extraction
        assert "name" in extraction["merchant"]
        assert "lineItems" in extraction
        assert "total" in extraction
        assert "category" in extraction
        assert "confidence" in extraction

    @patch("pipeline.nova_structure.bedrock_client")
    @patch("pipeline.nova_structure.s3_client")
    def test_returns_model_id(self, mock_s3, mock_bedrock):
        """Response must include the Bedrock model ID used."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image")}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert "modelId" in result, "Response must include modelId"
        assert isinstance(result["modelId"], str)
        assert len(result["modelId"]) > 0

    @patch("pipeline.nova_structure.bedrock_client")
    @patch("pipeline.nova_structure.s3_client")
    def test_returns_processing_time_ms(self, mock_s3, mock_bedrock):
        """Response must include processingTimeMs as a non-negative integer."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image")}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert "processingTimeMs" in result, "Response must include processingTimeMs"
        assert isinstance(result["processingTimeMs"], int)
        assert result["processingTimeMs"] >= 0

    @patch("pipeline.nova_structure.bedrock_client")
    @patch("pipeline.nova_structure.s3_client")
    def test_no_error_key_on_success(self, mock_s3, mock_bedrock):
        """Success response must NOT contain error/errorType."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image")}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert "error" not in result
        assert "errorType" not in result

    @patch("pipeline.nova_structure.bedrock_client")
    @patch("pipeline.nova_structure.s3_client")
    def test_handles_markdown_wrapped_json(self, mock_s3, mock_bedrock):
        """Bedrock may wrap JSON in markdown code fences; handler must strip them."""
        wrapped = f"```json\n{_VALID_EXTRACTION_JSON}\n```"
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image")}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(wrapped)

        result = _invoke_handler(_make_event())

        assert "extractionResult" in result
        assert result["extractionResult"]["merchant"]["name"] == "Whole Foods Market"

    @patch("pipeline.nova_structure.bedrock_client")
    @patch("pipeline.nova_structure.s3_client")
    def test_custom_categories_passed_through(self, mock_s3, mock_bedrock):
        """Custom categories from user should be included in the pipeline event."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image")}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        custom_cats = [{"slug": "costco", "displayName": "Costco", "parentCategory": "groceries-food"}]
        event = _make_event(custom_categories=custom_cats)

        # Should not error when custom categories are present
        result = _invoke_handler(event)
        assert "extractionResult" in result


# ---------------------------------------------------------------------------
# Bedrock API errors
# ---------------------------------------------------------------------------


class TestNovaStructureErrors:
    """Bedrock API failures return error payloads, not exceptions."""

    @patch("pipeline.nova_structure.bedrock_client")
    @patch("pipeline.nova_structure.s3_client")
    def test_bedrock_error_returns_error_payload(self, mock_s3, mock_bedrock):
        """Bedrock API exception should produce an error payload."""
        from botocore.exceptions import ClientError

        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image")}
        mock_bedrock.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel",
        )

        result = _invoke_handler(_make_event())

        assert "error" in result, "Error response must contain 'error' key"
        assert "errorType" in result, "Error response must contain 'errorType' key"
        assert isinstance(result["error"], str)

    @patch("pipeline.nova_structure.bedrock_client")
    @patch("pipeline.nova_structure.s3_client")
    def test_s3_read_error_returns_error_payload(self, mock_s3, mock_bedrock):
        """S3 read failure (for image) should return error payload."""
        from botocore.exceptions import ClientError

        mock_s3.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}},
            "GetObject",
        )

        result = _invoke_handler(_make_event())

        assert "error" in result
        assert "errorType" in result

    @patch("pipeline.nova_structure.bedrock_client")
    @patch("pipeline.nova_structure.s3_client")
    def test_malformed_bedrock_response_returns_error_payload(self, mock_s3, mock_bedrock):
        """Invalid JSON from Bedrock should return error payload."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image")}
        mock_bedrock.invoke_model.return_value = _make_bedrock_response("not valid json at all {{{")

        result = _invoke_handler(_make_event())

        assert "error" in result
        assert "errorType" in result

    @patch("pipeline.nova_structure.bedrock_client")
    @patch("pipeline.nova_structure.s3_client")
    def test_error_payload_has_no_extraction_result(self, mock_s3, mock_bedrock):
        """Error payloads must NOT contain extractionResult."""
        mock_bedrock.invoke_model.side_effect = RuntimeError("boom")
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image")}

        result = _invoke_handler(_make_event())

        assert "extractionResult" not in result

    @patch("pipeline.nova_structure.bedrock_client")
    @patch("pipeline.nova_structure.s3_client")
    def test_error_does_not_raise(self, mock_s3, mock_bedrock):
        """Handler must catch all exceptions and return payload."""
        mock_s3.get_object.return_value = {"Body": io.BytesIO(b"fake-image")}
        mock_bedrock.invoke_model.side_effect = Exception("Totally unexpected")

        result = _invoke_handler(_make_event())
        assert isinstance(result, dict)
        assert "error" in result
