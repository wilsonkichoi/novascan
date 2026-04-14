"""Tests for Textract Extract Lambda handler.

Validates the spec contract from SPEC.md Section 3 (Processing Flow):
- Receives S3 bucket/key, calls Textract AnalyzeExpense, returns raw output
- On Textract API error, returns error payload (not raises)
- Error payload contains error message and errorType
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Lambda context stub
# ---------------------------------------------------------------------------


@dataclass
class FakeLambdaContext:
    """Minimal Lambda context for Lambda Powertools."""

    function_name: str = "textract-extract"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:textract-extract"
    aws_request_id: str = "test-request-id"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _pipeline_env(monkeypatch):
    """Set env vars for pipeline Lambdas and disable tracing/metrics."""
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "novascan-test")
    monkeypatch.setenv("POWERTOOLS_TRACE_DISABLED", "1")
    monkeypatch.setenv("POWERTOOLS_METRICS_NAMESPACE", "NovaScanTest")
    monkeypatch.setenv("RECEIPTS_BUCKET", "my-bucket")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_textract_response(expense_documents: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build a Textract AnalyzeExpense API response."""
    if expense_documents is None:
        expense_documents = [
            {
                "SummaryFields": [
                    {
                        "Type": {"Text": "VENDOR_NAME"},
                        "ValueDetection": {"Text": "Test Store", "Confidence": 99.5},
                    },
                    {
                        "Type": {"Text": "TOTAL"},
                        "ValueDetection": {"Text": "25.99", "Confidence": 98.2},
                    },
                ],
                "LineItemGroups": [
                    {
                        "LineItems": [
                            {
                                "LineItemExpenseFields": [
                                    {
                                        "Type": {"Text": "ITEM"},
                                        "ValueDetection": {"Text": "Widget"},
                                    },
                                    {
                                        "Type": {"Text": "PRICE"},
                                        "ValueDetection": {"Text": "25.99"},
                                    },
                                ]
                            }
                        ]
                    }
                ],
            }
        ]
    return {"ExpenseDocuments": expense_documents}


def _invoke_handler(event: dict[str, Any]) -> dict[str, Any]:
    """Import and invoke the textract_extract handler."""
    from novascan.pipeline.textract_extract import handler

    return handler(event, FakeLambdaContext())


# ---------------------------------------------------------------------------
# Successful extraction
# ---------------------------------------------------------------------------


class TestTextractExtractSuccess:
    """Textract AnalyzeExpense succeeds and returns raw ExpenseDocuments."""

    @patch("novascan.pipeline.textract_extract.textract_client")
    def test_returns_expense_documents(self, mock_client):
        """Successful extraction returns expenseDocuments from Textract."""
        mock_client.analyze_expense.return_value = _make_textract_response()

        result = _invoke_handler({"bucket": "my-bucket", "key": "receipts/01ABC123DEF456GHI789JKLM90.jpg"})

        assert "expenseDocuments" in result, "Success response must contain expenseDocuments"
        assert isinstance(result["expenseDocuments"], list)
        assert len(result["expenseDocuments"]) > 0

    @patch("novascan.pipeline.textract_extract.textract_client")
    def test_passes_through_bucket_and_key(self, mock_client):
        """Success response echoes back the bucket and key for downstream use."""
        mock_client.analyze_expense.return_value = _make_textract_response()

        result = _invoke_handler({"bucket": "my-bucket", "key": "receipts/01ABC123DEF456GHI789JKLM90.jpg"})

        assert result.get("bucket") == "my-bucket"
        assert result.get("key") == "receipts/01ABC123DEF456GHI789JKLM90.jpg"

    @patch("novascan.pipeline.textract_extract.textract_client")
    def test_no_error_key_on_success(self, mock_client):
        """A successful response must NOT contain 'error' or 'errorType'."""
        mock_client.analyze_expense.return_value = _make_textract_response()

        result = _invoke_handler({"bucket": "my-bucket", "key": "receipts/01ABC123DEF456GHI789JKLM90.jpg"})

        assert "error" not in result, "Success response must not have 'error' key"
        assert "errorType" not in result

    @patch("novascan.pipeline.textract_extract.textract_client")
    def test_calls_textract_with_correct_s3_ref(self, mock_client):
        """Handler should pass the S3 reference to Textract AnalyzeExpense."""
        mock_client.analyze_expense.return_value = _make_textract_response()

        _invoke_handler({"bucket": "my-bucket", "key": "receipts/01ABC123DEF456GHI789JKLM90.jpg"})

        mock_client.analyze_expense.assert_called_once()
        call_args = mock_client.analyze_expense.call_args
        document = call_args[1].get("Document") or call_args[0][0] if call_args[0] else call_args[1]["Document"]
        s3_obj = document["S3Object"]
        assert s3_obj["Bucket"] == "my-bucket"
        assert s3_obj["Name"] == "receipts/01ABC123DEF456GHI789JKLM90.jpg"

    @patch("novascan.pipeline.textract_extract.textract_client")
    def test_empty_expense_documents_returned(self, mock_client):
        """Textract returning empty ExpenseDocuments is still a success."""
        mock_client.analyze_expense.return_value = {"ExpenseDocuments": []}

        result = _invoke_handler({"bucket": "my-bucket", "key": "receipts/01ABC123DEF456GHI789JKLM90.jpg"})

        assert "expenseDocuments" in result
        assert result["expenseDocuments"] == []
        assert "error" not in result


# ---------------------------------------------------------------------------
# Textract API errors
# ---------------------------------------------------------------------------


class TestTextractExtractErrors:
    """Textract API failures return error payloads, not exceptions."""

    @patch("novascan.pipeline.textract_extract.textract_client")
    def test_api_error_returns_error_payload(self, mock_client):
        """Textract API exception should produce an error payload."""
        from botocore.exceptions import ClientError

        mock_client.analyze_expense.side_effect = ClientError(
            {"Error": {"Code": "InvalidS3ObjectException", "Message": "S3 object not found"}},
            "AnalyzeExpense",
        )

        result = _invoke_handler({"bucket": "my-bucket", "key": "receipts/01ABC123DEF456GHI789JKLM90.jpg"})

        assert "error" in result, "Error response must contain 'error' key"
        assert "errorType" in result, "Error response must contain 'errorType' key"
        assert isinstance(result["error"], str)
        assert isinstance(result["errorType"], str)
        # H4 — Error sanitization: no raw exception text in error
        assert result["error"] == "textract_extract_failed"

    @patch("novascan.pipeline.textract_extract.textract_client")
    def test_throttling_error_returns_error_payload(self, mock_client):
        """Textract throttling should return an error payload."""
        from botocore.exceptions import ClientError

        mock_client.analyze_expense.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "AnalyzeExpense",
        )

        result = _invoke_handler({"bucket": "my-bucket", "key": "receipts/01ABC123DEF456GHI789JKLM90.jpg"})

        assert "error" in result
        assert "errorType" in result

    @patch("novascan.pipeline.textract_extract.textract_client")
    def test_generic_exception_returns_error_payload(self, mock_client):
        """Any unhandled exception should still return an error payload."""
        mock_client.analyze_expense.side_effect = RuntimeError("Unexpected failure")

        result = _invoke_handler({"bucket": "my-bucket", "key": "receipts/01ABC123DEF456GHI789JKLM90.jpg"})

        assert "error" in result
        assert result["errorType"] == "RuntimeError"
        # H4 — Error sanitization: error message should NOT contain raw exception text
        assert result["error"] == "textract_extract_failed"

    @patch("novascan.pipeline.textract_extract.textract_client")
    def test_error_payload_has_no_expense_documents(self, mock_client):
        """Error payloads should NOT contain expenseDocuments."""
        mock_client.analyze_expense.side_effect = RuntimeError("fail")

        result = _invoke_handler({"bucket": "my-bucket", "key": "receipts/01ABC123DEF456GHI789JKLM90.jpg"})

        assert "expenseDocuments" not in result

    @patch("novascan.pipeline.textract_extract.textract_client")
    def test_error_does_not_raise(self, mock_client):
        """Handler must catch exceptions and return payload — never raise."""
        from botocore.exceptions import ClientError

        mock_client.analyze_expense.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Textract died"}},
            "AnalyzeExpense",
        )

        # This should not raise — it should return an error dict
        result = _invoke_handler({"bucket": "my-bucket", "key": "receipts/01ABC123DEF456GHI789JKLM90.jpg"})
        assert isinstance(result, dict)
        assert "error" in result

    def test_missing_bucket_returns_invalid_event(self):
        """Missing bucket should return invalid_event immediately."""
        result = _invoke_handler({"key": "receipts/01ABC123DEF456GHI789JKLM90.jpg"})
        assert result["error"] == "invalid_event"

    def test_missing_key_returns_invalid_event(self):
        """Missing key should return invalid_event immediately."""
        result = _invoke_handler({"bucket": "my-bucket"})
        assert result["error"] == "invalid_event"

    def test_invalid_s3_key_format_returns_invalid_event(self):
        """Invalid S3 key format should return invalid_event."""
        result = _invoke_handler({"bucket": "my-bucket", "key": "../../../etc/passwd"})
        assert result["error"] == "invalid_event"

    def test_bucket_mismatch_returns_invalid_event(self):
        """Bucket mismatch with RECEIPTS_BUCKET should return invalid_event."""
        result = _invoke_handler({"bucket": "wrong-bucket", "key": "receipts/01ABC123DEF456GHI789JKLM90.jpg"})
        assert result["error"] == "invalid_event"
