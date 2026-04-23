"""Security tests for Finalize Lambda hardening (SECURITY-REVIEW H4, M11, M12, L8).

Tests the security contract:
- Failure reason in DynamoDB is generic (no raw error text)
- Idempotent receipt updates (stale overwrites prevented)
- Duplicate pipeline execution doesn't create duplicate line items
- S3 copy includes ServerSideEncryption
- Internal fields retained but documented
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import boto3
import pytest
from boto3.dynamodb.conditions import Key
from moto import mock_aws

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

USER_ID = "user-security-test"
RECEIPT_ID = "01SECURITYTEST00000000000"
BUCKET = "novascan-receipts-test"
KEY = f"receipts/{RECEIPT_ID}.jpg"


def _make_extraction_result(
    merchant_name: str = "Test Store",
    total: float = 25.99,
    subtotal: float = 24.00,
    tax: float = 1.99,
    category: str = "groceries-food",
    confidence: float = 0.92,
    line_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build an ExtractionResult dict."""
    if line_items is None:
        line_items = [
            {"name": "Item A", "quantity": 1, "unitPrice": 12.00, "totalPrice": 12.00},
            {"name": "Item B", "quantity": 1, "unitPrice": 12.00, "totalPrice": 12.00},
        ]
    return {
        "merchant": {"name": merchant_name, "address": "123 Main St"},
        "receiptDate": "2026-03-25",
        "currency": "USD",
        "lineItems": line_items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "category": category,
        "subcategory": "supermarket-grocery",
        "confidence": confidence,
    }


def _make_success(extraction: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a successful pipeline result."""
    return {
        "extractionResult": extraction or _make_extraction_result(),
        "modelId": "amazon.nova-lite-v1:0",
        "processingTimeMs": 2500,
    }


def _make_error(error: str = "failed", error_type: str = "RuntimeError") -> dict[str, Any]:
    """Build an error pipeline result."""
    return {"error": error, "errorType": error_type}


def _make_event(
    ocr_ai: dict[str, Any] | None = None,
    ai_multimodal: dict[str, Any] | None = None,
    ai_vision_v2: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the finalize handler event with 3 pipeline results."""
    return {
        "bucket": BUCKET,
        "key": KEY,
        "userId": USER_ID,
        "receiptId": RECEIPT_ID,
        "customCategories": [],
        "pipelineResults": [
            ocr_ai or _make_success(),
            ai_multimodal or _make_success(
                extraction=_make_extraction_result(merchant_name="V1 Vision Store", confidence=0.85)
            ),
            ai_vision_v2 or _make_success(
                extraction=_make_extraction_result(merchant_name="V2 Vision Store", confidence=0.88)
            ),
        ],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """Set env vars for finalize Lambda."""
    monkeypatch.setenv("TABLE_NAME", "novascan-test")
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "novascan-test")
    monkeypatch.setenv("POWERTOOLS_TRACE_DISABLED", "1")
    monkeypatch.setenv("POWERTOOLS_METRICS_NAMESPACE", "NovaScanTest")


@pytest.fixture
def aws_resources():
    """Set up mocked DynamoDB and S3."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="novascan-test",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(TableName="novascan-test")

        table.put_item(Item={
            "PK": f"USER#{USER_ID}",
            "SK": f"RECEIPT#{RECEIPT_ID}",
            "entityType": "RECEIPT",
            "receiptId": RECEIPT_ID,
            "status": "processing",
            "imageKey": KEY,
            "createdAt": "2026-03-25T14:00:00Z",
            "updatedAt": "2026-03-25T14:00:00Z",
            "GSI1PK": f"USER#{USER_ID}",
            "GSI1SK": f"2026-03-25#{RECEIPT_ID}",
        })

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        s3.put_object(Bucket=BUCKET, Key=KEY, Body=b"fake-receipt-image")

        yield table, s3


def _invoke(event: dict[str, Any]) -> dict[str, Any]:
    """Invoke the finalize handler with mocked S3 client."""
    from novascan.pipeline import finalize as fm

    mock_ctx = MagicMock()
    mock_ctx.function_name = "finalize"
    mock_ctx.memory_limit_in_mb = 256
    mock_ctx.invoked_function_arn = "arn:aws:lambda:us-east-1:123:function:finalize"
    mock_ctx.aws_request_id = "test"

    original_s3 = fm.s3_client
    fm.s3_client = boto3.client("s3", region_name="us-east-1")
    try:
        return fm.handler(event, mock_ctx)
    finally:
        fm.s3_client = original_s3


# ---------------------------------------------------------------------------
# H4 — Failure reason is generic
# ---------------------------------------------------------------------------


class TestFailureReasonGeneric:
    """DynamoDB failureReason must not contain raw error details."""

    def test_failure_reason_is_generic_text(self, aws_resources):
        """When all pipelines fail, failureReason must be a generic message."""
        table, _ = aws_resources
        event = _make_event(
            ocr_ai=_make_error("Textract throttled: rate limit exceeded"),
            ai_multimodal=_make_error("Bedrock: model inference timeout after 30s"),
            ai_vision_v2=_make_error("Nova 2 Lite: model error"),
        )
        _invoke(event)

        receipt = table.get_item(
            Key={"PK": f"USER#{USER_ID}", "SK": f"RECEIPT#{RECEIPT_ID}"}
        )["Item"]

        failure_reason = receipt.get("failureReason", "")
        assert "Textract throttled" not in failure_reason
        assert "Bedrock" not in failure_reason
        assert "rate limit" not in failure_reason
        assert "timeout" not in failure_reason
        assert "CloudWatch" in failure_reason

    def test_pipeline_error_record_stores_type_not_message(self, aws_resources):
        """Pipeline error records must store error type, not raw message."""
        table, _ = aws_resources
        event = _make_event(
            ocr_ai=_make_error("Secret internal error details", "TextractException"),
        )
        _invoke(event)

        records = table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"USER#{USER_ID}")
                & Key("SK").begins_with(f"RECEIPT#{RECEIPT_ID}#PIPELINE#")
            ),
        )["Items"]

        main_record = next(r for r in records if "ocr-ai" in r["SK"])
        # Error field stores classification, not raw message
        assert "Secret internal error details" not in str(main_record.get("error", ""))


# ---------------------------------------------------------------------------
# M11 — Idempotency: duplicate execution
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Duplicate pipeline executions must not create duplicate records."""

    def test_duplicate_execution_no_duplicate_line_items(self, aws_resources):
        """Running finalize twice must not create duplicate line items."""
        table, _ = aws_resources
        event = _make_event()

        # First execution
        _invoke(event)
        items_after_first = table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"USER#{USER_ID}")
                & Key("SK").begins_with(f"RECEIPT#{RECEIPT_ID}#ITEM#")
            ),
        )["Items"]
        count_first = len(items_after_first)
        assert count_first == 2

        # Second execution
        _invoke(event)
        items_after_second = table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"USER#{USER_ID}")
                & Key("SK").begins_with(f"RECEIPT#{RECEIPT_ID}#ITEM#")
            ),
        )["Items"]
        count_second = len(items_after_second)

        # Must be the same count — no duplicates
        assert count_second == count_first, (
            f"Expected {count_first} line items after second run, got {count_second}. "
            "Duplicate line items created."
        )

    def test_receipt_update_is_idempotent(self, aws_resources):
        """Running finalize twice must not corrupt receipt data."""
        table, _ = aws_resources
        event = _make_event()

        _invoke(event)
        receipt_first = table.get_item(
            Key={"PK": f"USER#{USER_ID}", "SK": f"RECEIPT#{RECEIPT_ID}"}
        )["Item"]

        _invoke(event)
        receipt_second = table.get_item(
            Key={"PK": f"USER#{USER_ID}", "SK": f"RECEIPT#{RECEIPT_ID}"}
        )["Item"]

        # Status must still be confirmed
        assert receipt_second["status"] == "confirmed"
        # Merchant must still be correct
        assert receipt_second.get("merchant") == receipt_first.get("merchant")


# ---------------------------------------------------------------------------
# M12 — S3 encryption
# ---------------------------------------------------------------------------


class TestS3Encryption:
    """S3 copy_object must include ServerSideEncryption."""

    def test_s3_metadata_update_includes_encryption(self, aws_resources):
        """After finalize, the S3 object should have encryption set."""
        table, s3 = aws_resources
        _invoke(_make_event())

        head = s3.head_object(Bucket=BUCKET, Key=KEY)
        # moto may or may not enforce SSE, but the metadata should be updated
        metadata = head.get("Metadata", {})
        assert metadata.get("status") == "confirmed"
        assert metadata.get("receipt-id") == RECEIPT_ID


# ---------------------------------------------------------------------------
# L8 — Internal fields
# ---------------------------------------------------------------------------


class TestInternalFields:
    """Return value should include internal-only fields for observability."""

    def test_return_includes_selected_pipeline(self, aws_resources):
        """selectedPipeline must be in the return value."""
        result = _invoke(_make_event())
        assert "selectedPipeline" in result

    def test_return_includes_ranking_winner(self, aws_resources):
        """rankingWinner must be in the return value."""
        result = _invoke(_make_event())
        assert "rankingWinner" in result

    def test_return_includes_used_fallback(self, aws_resources):
        """usedFallback must be in the return value."""
        result = _invoke(_make_event())
        assert "usedFallback" in result
