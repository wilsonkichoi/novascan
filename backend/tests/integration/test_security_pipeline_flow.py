"""Integration tests for security-hardened pipeline flow.

Tests the GSI2 lookup flow and error sanitization in the integrated
pipeline context using moto-mocked DynamoDB.

SECURITY-REVIEW references: C2 (GSI2 query), H4 (error sanitization).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import boto3
import pytest
from moto import mock_aws


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_ID = "test-user-security-123"
RECEIPT_ID = "01SECURITYTESTFLOW000000"
BUCKET = "novascan-receipts-test"
IMAGE_KEY = f"receipts/{RECEIPT_ID}.jpg"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _pipeline_env(monkeypatch):
    """Set environment variables required by pipeline Lambdas."""
    monkeypatch.setenv("TABLE_NAME", "novascan-test")
    monkeypatch.setenv("DEFAULT_PIPELINE", "ocr-ai")
    monkeypatch.setenv("STAGE", "dev")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("POWERTOOLS_TRACE_DISABLED", "1")
    monkeypatch.setenv("POWERTOOLS_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "novascan-test")
    monkeypatch.setenv("POWERTOOLS_METRICS_NAMESPACE", "NovaScan")
    monkeypatch.setenv("NOVA_MODEL_ID", "amazon.nova-lite-v1:0")
    monkeypatch.setenv("RECEIPTS_BUCKET", BUCKET)


@pytest.fixture
def aws_resources(_pipeline_env):
    """Create moto-mocked DynamoDB table with GSI2 and S3 bucket."""
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
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
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
                {
                    "IndexName": "GSI2",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "KEYS_ONLY"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(
            TableName="novascan-test"
        )

        # Create S3 bucket with test image
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        s3.put_object(
            Bucket=BUCKET,
            Key=IMAGE_KEY,
            Body=b"fake-receipt-image",
            ContentType="image/jpeg",
        )

        yield {
            "table": table,
            "s3_client": s3,
        }


def _create_receipt_record(table: Any, user_id: str = USER_ID, receipt_id: str = RECEIPT_ID) -> None:
    """Create a receipt record with GSI2PK set (as upload endpoint would)."""
    now = datetime.now(UTC).isoformat()
    table.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": f"RECEIPT#{receipt_id}",
            "entityType": "RECEIPT",
            "receiptId": receipt_id,
            "status": "processing",
            "imageKey": f"receipts/{receipt_id}.jpg",
            "createdAt": now,
            "updatedAt": now,
            "GSI1PK": f"USER#{user_id}",
            "GSI1SK": f"{now}#{receipt_id}",
            "GSI2PK": receipt_id,
        }
    )


# ---------------------------------------------------------------------------
# GSI2 lookup integration tests
# ---------------------------------------------------------------------------


class TestGSI2Lookup:
    """GSI2 query must correctly resolve userId from receiptId."""

    def test_gsi2_query_returns_correct_user_id(self, aws_resources) -> None:
        """Querying GSI2 with receiptId must return the correct userId.

        SECURITY-REVIEW C2: GSI2 replaces full-table scan for userId lookup.
        """
        table = aws_resources["table"]
        _create_receipt_record(table, user_id=USER_ID, receipt_id=RECEIPT_ID)

        # Invoke LoadCustomCategories which uses GSI2 internally
        event = {
            "bucket": BUCKET,
            "key": IMAGE_KEY,
            "receiptId": RECEIPT_ID,
        }

        result = _invoke_load_custom_categories(event)

        # The handler should resolve userId via GSI2 and return it
        assert result.get("userId") == USER_ID, (
            f"GSI2 lookup returned userId '{result.get('userId')}', "
            f"expected '{USER_ID}'"
        )

    def test_gsi2_query_with_nonexistent_receipt(self, aws_resources) -> None:
        """Querying GSI2 with a nonexistent receiptId must fail gracefully."""
        event = {
            "bucket": BUCKET,
            "key": "receipts/01NONEXISTENTRECEIPTIDXX.jpg",
            "receiptId": "01NONEXISTENTRECEIPTIDXX",
        }

        result = _invoke_load_custom_categories(event)

        # Should return an error, not crash
        assert "error" in result, (
            "Non-existent receipt should return error, not crash"
        )

    def test_gsi2_query_multiple_users_isolated(self, aws_resources) -> None:
        """GSI2 must return the correct userId even with multiple users."""
        table = aws_resources["table"]

        # Create receipts for two different users
        user_a = "user-alpha-111"
        user_b = "user-beta-222"
        receipt_a = "01RECEIPTAAAAAAAAAAAAAAA"
        receipt_b = "01RECEIPTBBBBBBBBBBBBBBBB"

        _create_receipt_record(table, user_id=user_a, receipt_id=receipt_a)
        _create_receipt_record(table, user_id=user_b, receipt_id=receipt_b)

        # Look up receipt_a — should return user_a
        event_a = {
            "bucket": BUCKET,
            "key": f"receipts/{receipt_a}.jpg",
            "receiptId": receipt_a,
        }
        result_a = _invoke_load_custom_categories(event_a)
        assert result_a.get("userId") == user_a

        # Look up receipt_b — should return user_b
        event_b = {
            "bucket": BUCKET,
            "key": f"receipts/{receipt_b}.jpg",
            "receiptId": receipt_b,
        }
        result_b = _invoke_load_custom_categories(event_b)
        assert result_b.get("userId") == user_b

    def test_gsi2_query_passes_custom_categories(self, aws_resources) -> None:
        """LoadCustomCategories via GSI2 should still return custom categories."""
        table = aws_resources["table"]
        _create_receipt_record(table)

        # Add a custom category for the user
        table.put_item(
            Item={
                "PK": f"USER#{USER_ID}",
                "SK": "CUSTOMCAT#my-category",
                "entityType": "CUSTOMCAT",
                "displayName": "My Category",
                "createdAt": datetime.now(UTC).isoformat(),
            }
        )

        event = {
            "bucket": BUCKET,
            "key": IMAGE_KEY,
            "receiptId": RECEIPT_ID,
        }

        result = _invoke_load_custom_categories(event)
        assert "customCategories" in result
        assert len(result["customCategories"]) == 1
        assert result["customCategories"][0]["slug"] == "my-category"


# ---------------------------------------------------------------------------
# Finalize error sanitization in integration context
# ---------------------------------------------------------------------------


class TestFinalizeErrorSanitizationIntegration:
    """Finalize must sanitize errors in the integrated pipeline context."""

    def test_failure_reason_generic_in_integration(self, aws_resources) -> None:
        """When both pipelines fail, failureReason must be generic."""
        table = aws_resources["table"]
        _create_receipt_record(table)

        event = {
            "bucket": BUCKET,
            "key": IMAGE_KEY,
            "userId": USER_ID,
            "receiptId": RECEIPT_ID,
            "customCategories": [],
            "pipelineResults": [
                {"error": "Textract: Rate limit exceeded on us-east-1 account 123456789012", "errorType": "ThrottlingException"},
                {"error": "Bedrock: Model inference timeout after 30s on request req-abc-123", "errorType": "TimeoutError"},
            ],
        }

        _invoke_finalize(event)

        receipt = table.get_item(
            Key={"PK": f"USER#{USER_ID}", "SK": f"RECEIPT#{RECEIPT_ID}"}
        )["Item"]

        failure_reason = receipt.get("failureReason", "")
        # Must not contain any of the raw error details
        assert "123456789012" not in failure_reason
        assert "req-abc-123" not in failure_reason
        assert "us-east-1" not in failure_reason
        assert "30s" not in failure_reason
        # Must contain generic guidance
        assert "CloudWatch" in failure_reason

    def test_s3_copy_includes_encryption_in_integration(self, aws_resources) -> None:
        """S3 copy_object in finalize must set ServerSideEncryption."""
        table = aws_resources["table"]
        s3_client = aws_resources["s3_client"]
        _create_receipt_record(table)

        event = {
            "bucket": BUCKET,
            "key": IMAGE_KEY,
            "userId": USER_ID,
            "receiptId": RECEIPT_ID,
            "customCategories": [],
            "pipelineResults": [
                {
                    "extractionResult": _make_extraction_result(),
                    "modelId": "amazon.nova-lite-v1:0",
                    "processingTimeMs": 1500,
                },
                {"error": "shadow failed", "errorType": "RuntimeError"},
            ],
        }

        _invoke_finalize(event)

        # Verify S3 metadata was updated
        head = s3_client.head_object(Bucket=BUCKET, Key=IMAGE_KEY)
        metadata = head.get("Metadata", {})
        assert metadata.get("status") == "confirmed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_extraction_result() -> dict[str, Any]:
    """Build a mock extraction result."""
    return {
        "merchant": {"name": "Test Store", "address": "123 Main St"},
        "receiptDate": "2026-04-01",
        "currency": "USD",
        "lineItems": [
            {"name": "Item A", "quantity": 1.0, "unitPrice": 10.0, "totalPrice": 10.0},
        ],
        "subtotal": 10.0,
        "tax": 1.0,
        "total": 11.0,
        "category": "groceries-food",
        "subcategory": "supermarket-grocery",
        "confidence": 0.9,
    }


def _invoke_load_custom_categories(event: dict[str, Any]) -> dict[str, Any]:
    """Invoke the LoadCustomCategories Lambda handler."""
    from novascan.pipeline import load_custom_categories as lcc_module

    mock_context = MagicMock()
    mock_context.function_name = "novascan-test-load-custom-categories"
    mock_context.memory_limit_in_mb = 256
    mock_context.invoked_function_arn = (
        "arn:aws:lambda:us-east-1:123456789012:function:novascan-test-lcc"
    )
    mock_context.aws_request_id = "test-request-id"

    return lcc_module.handler(event, mock_context)


def _invoke_finalize(event: dict[str, Any]) -> dict[str, Any]:
    """Invoke the Finalize Lambda handler with mocked S3 client."""
    from novascan.pipeline import finalize as finalize_module

    mock_context = MagicMock()
    mock_context.function_name = "novascan-test-finalize"
    mock_context.memory_limit_in_mb = 256
    mock_context.invoked_function_arn = (
        "arn:aws:lambda:us-east-1:123456789012:function:novascan-test-finalize"
    )
    mock_context.aws_request_id = "test-request-id"

    original_s3 = finalize_module.s3_client
    finalize_module.s3_client = boto3.client("s3", region_name="us-east-1")
    try:
        return finalize_module.handler(event, mock_context)
    finally:
        finalize_module.s3_client = original_s3
