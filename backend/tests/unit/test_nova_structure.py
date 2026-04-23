"""Tests for Nova Structure Lambda handler.

Validates the spec contract from SPEC.md Section 3 (Processing Flow):
- Receives Textract output + custom categories (text only, no image)
- Sends to Bedrock Nova for categorization and normalization
- Returns ExtractionResult, modelId, and processingTimeMs on success
- Returns error payload on Bedrock API error
"""

from __future__ import annotations

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
    "key": "receipts/01ABC123DEF456GHI789JKLM90.jpg",
    "textractPages": 1,
}


def _make_event(
    bucket: str = "test-bucket",
    key: str = "receipts/01ABC123DEF456GHI789JKLM90.jpg",
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
        },
        "usage": {"inputTokens": 500, "outputTokens": 200},
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
    """Import and invoke the nova_structure handler."""
    from novascan.pipeline.nova_structure import handler

    return handler(event, FakeLambdaContext())


# ---------------------------------------------------------------------------
# Successful structuring
# ---------------------------------------------------------------------------


class TestNovaStructureSuccess:
    """Valid Textract output -> valid ExtractionResult via Bedrock Nova."""

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_returns_extraction_result(self, mock_bedrock):
        """Successful structuring returns extractionResult dict."""
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert "extractionResult" in result, "Success response must contain extractionResult"
        assert isinstance(result["extractionResult"], dict)

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_extraction_result_has_required_fields(self, mock_bedrock):
        """ExtractionResult must match SPEC Section 7 schema fields."""
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())
        extraction = result["extractionResult"]

        assert "merchant" in extraction
        assert "name" in extraction["merchant"]
        assert "lineItems" in extraction
        assert "total" in extraction
        assert "category" in extraction
        assert "confidence" in extraction

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_returns_model_id(self, mock_bedrock):
        """Response must include the Bedrock model ID used."""
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert "modelId" in result, "Response must include modelId"
        assert isinstance(result["modelId"], str)
        assert len(result["modelId"]) > 0

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_returns_processing_time_ms(self, mock_bedrock):
        """Response must include processingTimeMs as a non-negative integer."""
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert "processingTimeMs" in result, "Response must include processingTimeMs"
        assert isinstance(result["processingTimeMs"], int)
        assert result["processingTimeMs"] >= 0

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_returns_token_usage(self, mock_bedrock):
        """Response must include inputTokens and outputTokens."""
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert result["inputTokens"] == 500
        assert result["outputTokens"] == 200

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_returns_textract_pages(self, mock_bedrock):
        """Response must pass through textractPages from the Textract step."""
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert result["textractPages"] == 1

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_no_error_key_on_success(self, mock_bedrock):
        """Success response must NOT contain error/errorType."""
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        result = _invoke_handler(_make_event())

        assert "error" not in result
        assert "errorType" not in result

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_handles_markdown_wrapped_json(self, mock_bedrock):
        """Bedrock may wrap JSON in markdown code fences; handler must strip them."""
        wrapped = f"```json\n{_VALID_EXTRACTION_JSON}\n```"
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(wrapped)

        result = _invoke_handler(_make_event())

        assert "extractionResult" in result
        assert result["extractionResult"]["merchant"]["name"] == "Whole Foods Market"

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_custom_categories_passed_through(self, mock_bedrock):
        """Custom categories from user should be included in the pipeline event."""
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        custom_cats = [{"slug": "costco", "displayName": "Costco", "parentCategory": "groceries-food"}]
        event = _make_event(custom_categories=custom_cats)

        # Should not error when custom categories are present
        result = _invoke_handler(event)
        assert "extractionResult" in result

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_does_not_send_image_to_bedrock(self, mock_bedrock):
        """Nova Structure must send text-only to Bedrock (no image)."""
        mock_bedrock.invoke_model.return_value = _make_bedrock_response(_VALID_EXTRACTION_JSON)

        _invoke_handler(_make_event())

        call_args = mock_bedrock.invoke_model.call_args
        body = json.loads(call_args.kwargs.get("body", call_args[1].get("body", "{}")))
        content = body["messages"][0]["content"]
        for block in content:
            assert "image" not in block, "Nova Structure must not send image to Bedrock"


# ---------------------------------------------------------------------------
# Bedrock API errors
# ---------------------------------------------------------------------------


class TestNovaStructureErrors:
    """Bedrock API failures return error payloads, not exceptions."""

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_bedrock_error_returns_error_payload(self, mock_bedrock):
        """Bedrock API exception should produce an error payload."""
        from botocore.exceptions import ClientError

        mock_bedrock.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel",
        )

        result = _invoke_handler(_make_event())

        assert "error" in result, "Error response must contain 'error' key"
        assert "errorType" in result, "Error response must contain 'errorType' key"
        assert isinstance(result["error"], str)

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_malformed_bedrock_response_returns_error_payload(self, mock_bedrock):
        """Invalid JSON from Bedrock should return error payload."""
        mock_bedrock.invoke_model.return_value = _make_bedrock_response("not valid json at all {{{")

        result = _invoke_handler(_make_event())

        assert "error" in result
        assert "errorType" in result

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_error_payload_has_no_extraction_result(self, mock_bedrock):
        """Error payloads must NOT contain extractionResult."""
        mock_bedrock.invoke_model.side_effect = RuntimeError("boom")

        result = _invoke_handler(_make_event())

        assert "extractionResult" not in result

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_error_does_not_raise(self, mock_bedrock):
        """Handler must catch all exceptions and return payload."""
        mock_bedrock.invoke_model.side_effect = Exception("Totally unexpected")

        result = _invoke_handler(_make_event())
        assert isinstance(result, dict)
        assert "error" in result
        # H4 — Error sanitization: no raw exception text in error
        assert result["error"] == "nova_structure_failed"

    def test_missing_required_fields_returns_invalid_event(self):
        """Missing required event fields should return invalid_event."""
        result = _invoke_handler({"bucket": "test-bucket"})
        assert result["error"] == "invalid_event"

    def test_invalid_s3_key_returns_invalid_event(self):
        """Invalid S3 key format should return invalid_event."""
        result = _invoke_handler({
            "textractResult": _TEXTRACT_RESULT,
            "bucket": "test-bucket",
            "key": "../../../etc/passwd",
        })
        assert result["error"] == "invalid_event"

    @patch("novascan.pipeline.nova_structure.bedrock_client")
    def test_error_payload_never_contains_raw_exception(self, mock_bedrock):
        """Error payloads must never contain the raw exception message."""
        mock_bedrock.invoke_model.side_effect = RuntimeError("secret internal error details")

        result = _invoke_handler(_make_event())
        assert "secret internal error details" not in result.get("error", "")
