"""Tests for Finalize Lambda handler — main/shadow selection, ranking, and persistence.

Validates the spec contract from SPEC.md Section 3 (Processing Flow):
- Main success -> uses main, status confirmed
- Main fail + shadow success -> uses shadow with usedFallback=true
- Both fail -> status failed
- Ranking scores computed for both results
- DynamoDB records: receipt update, pipeline results, line items
- S3 metadata updated
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws


# ---------------------------------------------------------------------------
# Lambda context stub
# ---------------------------------------------------------------------------


@dataclass
class FakeLambdaContext:
    """Minimal Lambda context for Lambda Powertools."""

    function_name: str = "finalize"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:finalize"
    aws_request_id: str = "test-request-id"


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

USER_ID = "user-test-123"
RECEIPT_ID = "01ABC123DEF456GHI789JK"
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
    """Build an ExtractionResult dict matching SPEC Section 7 schema."""
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


def _make_success_pipeline_result(
    extraction: dict[str, Any] | None = None,
    model_id: str = "amazon.nova-lite-v1:0",
    processing_time_ms: int = 2500,
) -> dict[str, Any]:
    """Build a successful pipeline result from Step Functions."""
    if extraction is None:
        extraction = _make_extraction_result()
    return {
        "extractionResult": extraction,
        "modelId": model_id,
        "processingTimeMs": processing_time_ms,
    }


def _make_error_pipeline_result(
    error: str = "Pipeline failed",
    error_type: str = "RuntimeError",
) -> dict[str, Any]:
    """Build an error pipeline result from Step Functions."""
    return {"error": error, "errorType": error_type}


def _make_event(
    main_result: dict[str, Any] | None = None,
    shadow_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the finalize handler event from Step Functions."""
    if main_result is None:
        main_result = _make_success_pipeline_result()
    if shadow_result is None:
        shadow_result = _make_success_pipeline_result(
            extraction=_make_extraction_result(merchant_name="Shadow Store", confidence=0.85),
            model_id="amazon.nova-lite-v1:0",
            processing_time_ms=1800,
        )

    return {
        "bucket": BUCKET,
        "key": KEY,
        "userId": USER_ID,
        "receiptId": RECEIPT_ID,
        "customCategories": [],
        "pipelineResults": [main_result, shadow_result],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _pipeline_env(monkeypatch):
    """Set env vars for the finalize Lambda."""
    monkeypatch.setenv("TABLE_NAME", "novascan-test")
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "novascan-test")
    monkeypatch.setenv("POWERTOOLS_TRACE_DISABLED", "1")
    monkeypatch.setenv("POWERTOOLS_METRICS_NAMESPACE", "NovaScanTest")
    monkeypatch.setenv("DEFAULT_PIPELINE", "ocr-ai")


@pytest.fixture
def aws_resources():
    """Set up mocked DynamoDB table, S3 bucket, and seed a receipt record.

    This fixture provides the full AWS environment for finalize tests:
    - DynamoDB table with the novascan schema
    - S3 bucket with a test image
    - A pre-existing receipt record in 'processing' status (as would exist after upload)
    """
    with mock_aws():
        # Create DynamoDB table
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

        # Seed a receipt in 'processing' state (as created by upload endpoint)
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

        # Create S3 bucket with test image
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        s3.put_object(Bucket=BUCKET, Key=KEY, Body=b"fake-receipt-image")

        yield table, s3


def _invoke_handler(event: dict[str, Any]) -> dict[str, Any]:
    """Import and invoke the finalize handler."""
    from pipeline.finalize import handler

    return handler(event, FakeLambdaContext())


def _get_receipt(table, user_id: str = USER_ID, receipt_id: str = RECEIPT_ID) -> dict[str, Any]:
    """Fetch the receipt record from DynamoDB."""
    result = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"RECEIPT#{receipt_id}"})
    return result.get("Item", {})


def _query_pipeline_records(table, user_id: str = USER_ID, receipt_id: str = RECEIPT_ID) -> list[dict[str, Any]]:
    """Query all PIPELINE# records for a receipt."""
    result = table.query(
        KeyConditionExpression=(
            boto3.dynamodb.conditions.Key("PK").eq(f"USER#{user_id}")
            & boto3.dynamodb.conditions.Key("SK").begins_with(f"RECEIPT#{receipt_id}#PIPELINE#")
        ),
    )
    return result.get("Items", [])


def _query_line_items(table, user_id: str = USER_ID, receipt_id: str = RECEIPT_ID) -> list[dict[str, Any]]:
    """Query all ITEM# records for a receipt."""
    result = table.query(
        KeyConditionExpression=(
            boto3.dynamodb.conditions.Key("PK").eq(f"USER#{user_id}")
            & boto3.dynamodb.conditions.Key("SK").begins_with(f"RECEIPT#{receipt_id}#ITEM#")
        ),
    )
    return result.get("Items", [])


# ---------------------------------------------------------------------------
# Main success -> uses main
# ---------------------------------------------------------------------------


class TestFinalizeMainSuccess:
    """When main pipeline succeeds, use its result."""

    def test_status_confirmed(self, aws_resources):
        """Receipt status should be 'confirmed' when main succeeds."""
        table, _ = aws_resources
        result = _invoke_handler(_make_event())

        assert result["status"] == "confirmed"

        receipt = _get_receipt(table)
        assert receipt["status"] == "confirmed"

    def test_used_fallback_false(self, aws_resources):
        """usedFallback should be False when main succeeds."""
        table, _ = aws_resources
        result = _invoke_handler(_make_event())

        assert result["usedFallback"] is False

    def test_extracted_data_populated(self, aws_resources):
        """Receipt record should have extracted data from the main result."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        receipt = _get_receipt(table)
        assert receipt.get("merchant") == "Test Store"
        assert receipt.get("category") == "groceries-food"
        assert "total" in receipt

    def test_receipt_date_updated(self, aws_resources):
        """Receipt date from extraction should be persisted."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        receipt = _get_receipt(table)
        assert receipt.get("receiptDate") == "2026-03-25"

    def test_ranking_winner_set(self, aws_resources):
        """rankingWinner should be set based on comparative scoring."""
        table, _ = aws_resources
        result = _invoke_handler(_make_event())

        assert result["rankingWinner"] is not None
        assert result["rankingWinner"] in ("ocr-ai", "ai-multimodal")

        receipt = _get_receipt(table)
        assert receipt.get("rankingWinner") in ("ocr-ai", "ai-multimodal")


# ---------------------------------------------------------------------------
# Main fail + shadow success -> uses shadow with fallback flag
# ---------------------------------------------------------------------------


class TestFinalizeFallback:
    """When main fails but shadow succeeds, use shadow with usedFallback=true."""

    def test_status_confirmed_on_fallback(self, aws_resources):
        """Receipt should still be 'confirmed' when shadow is used."""
        table, _ = aws_resources
        event = _make_event(
            main_result=_make_error_pipeline_result(),
            shadow_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(merchant_name="Shadow Store")
            ),
        )
        result = _invoke_handler(event)

        assert result["status"] == "confirmed"

        receipt = _get_receipt(table)
        assert receipt["status"] == "confirmed"

    def test_used_fallback_true(self, aws_resources):
        """usedFallback should be True when shadow is used."""
        table, _ = aws_resources
        event = _make_event(
            main_result=_make_error_pipeline_result(),
            shadow_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(merchant_name="Shadow Store")
            ),
        )
        result = _invoke_handler(event)

        assert result["usedFallback"] is True

        receipt = _get_receipt(table)
        assert receipt.get("usedFallback") is True

    def test_shadow_data_used(self, aws_resources):
        """Shadow pipeline's extracted data should populate the receipt."""
        table, _ = aws_resources
        event = _make_event(
            main_result=_make_error_pipeline_result(),
            shadow_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(merchant_name="Shadow Store")
            ),
        )
        _invoke_handler(event)

        receipt = _get_receipt(table)
        assert receipt.get("merchant") == "Shadow Store"


# ---------------------------------------------------------------------------
# Both fail -> status failed
# ---------------------------------------------------------------------------


class TestFinalizeBothFailed:
    """When both pipelines fail, receipt status is 'failed'."""

    def test_status_failed(self, aws_resources):
        """Receipt status should be 'failed' when both pipelines error."""
        table, _ = aws_resources
        event = _make_event(
            main_result=_make_error_pipeline_result(error="Textract timed out"),
            shadow_result=_make_error_pipeline_result(error="Bedrock crashed"),
        )
        result = _invoke_handler(event)

        assert result["status"] == "failed"

        receipt = _get_receipt(table)
        assert receipt["status"] == "failed"

    def test_used_fallback_false_when_both_fail(self, aws_resources):
        """usedFallback should be False — no fallback was used, both failed."""
        table, _ = aws_resources
        event = _make_event(
            main_result=_make_error_pipeline_result(),
            shadow_result=_make_error_pipeline_result(),
        )
        result = _invoke_handler(event)

        assert result["usedFallback"] is False

    def test_failure_reason_set(self, aws_resources):
        """Failed receipts should include a failureReason attribute per SPEC."""
        table, _ = aws_resources
        event = _make_event(
            main_result=_make_error_pipeline_result(error="Textract error"),
            shadow_result=_make_error_pipeline_result(error="Bedrock error"),
        )
        _invoke_handler(event)

        receipt = _get_receipt(table)
        assert "failureReason" in receipt, "Failed receipt must have failureReason"
        assert isinstance(receipt["failureReason"], str)
        assert len(receipt["failureReason"]) > 0
        # H4 — Failure reason must be generic, not containing raw error text
        assert "Textract error" not in receipt["failureReason"]
        assert "Bedrock error" not in receipt["failureReason"]
        assert "CloudWatch" in receipt["failureReason"]

    def test_no_line_items_created(self, aws_resources):
        """When both fail, no line items should be created."""
        table, _ = aws_resources
        event = _make_event(
            main_result=_make_error_pipeline_result(),
            shadow_result=_make_error_pipeline_result(),
        )
        _invoke_handler(event)

        items = _query_line_items(table)
        assert len(items) == 0, "No line items should exist when both pipelines fail"


# ---------------------------------------------------------------------------
# Pipeline results stored
# ---------------------------------------------------------------------------


class TestFinalizePipelineRecords:
    """Both pipeline results stored as PIPELINE# records in DynamoDB."""

    def test_two_pipeline_records_created(self, aws_resources):
        """Both ocr-ai and ai-multimodal pipeline records should be created."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        records = _query_pipeline_records(table)
        assert len(records) == 2, (
            f"Expected 2 pipeline records (ocr-ai + ai-multimodal), got {len(records)}"
        )

    def test_pipeline_record_sk_format(self, aws_resources):
        """Pipeline records should have SK matching RECEIPT#{ulid}#PIPELINE#{type}."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        records = _query_pipeline_records(table)
        sks = sorted([r["SK"] for r in records])

        expected_ocr = f"RECEIPT#{RECEIPT_ID}#PIPELINE#ocr-ai"
        expected_multi = f"RECEIPT#{RECEIPT_ID}#PIPELINE#ai-multimodal"

        assert expected_ocr in sks, f"Missing ocr-ai pipeline record. Found: {sks}"
        assert expected_multi in sks, f"Missing ai-multimodal pipeline record. Found: {sks}"

    def test_pipeline_record_has_entity_type(self, aws_resources):
        """Pipeline records should have entityType=PIPELINE."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        records = _query_pipeline_records(table)
        for rec in records:
            assert rec.get("entityType") == "PIPELINE", (
                f"Pipeline record missing entityType=PIPELINE: {rec.get('SK')}"
            )

    def test_pipeline_record_has_ranking_score(self, aws_resources):
        """Successful pipeline records should have a rankingScore."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        records = _query_pipeline_records(table)
        for rec in records:
            assert "rankingScore" in rec, (
                f"Pipeline record missing rankingScore: {rec.get('SK')}"
            )
            score = float(rec["rankingScore"])
            assert 0.0 <= score <= 1.0, f"rankingScore {score} out of range"

    def test_pipeline_records_stored_even_on_failure(self, aws_resources):
        """Pipeline records should be stored even when the pipeline errored."""
        table, _ = aws_resources
        event = _make_event(
            main_result=_make_error_pipeline_result(),
            shadow_result=_make_error_pipeline_result(),
        )
        _invoke_handler(event)

        records = _query_pipeline_records(table)
        assert len(records) == 2, "Pipeline records should be stored even on failure"

    def test_pipeline_record_has_model_id(self, aws_resources):
        """Pipeline records should store the modelId used."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        records = _query_pipeline_records(table)
        for rec in records:
            assert "modelId" in rec

    def test_pipeline_record_has_processing_time(self, aws_resources):
        """Pipeline records should store processingTimeMs."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        records = _query_pipeline_records(table)
        for rec in records:
            assert "processingTimeMs" in rec


# ---------------------------------------------------------------------------
# Line items created
# ---------------------------------------------------------------------------


class TestFinalizeLineItems:
    """Line items from the selected result are created as ITEM# records."""

    def test_line_items_created(self, aws_resources):
        """Selected result's line items should become ITEM# records in DynamoDB."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        items = _query_line_items(table)
        assert len(items) == 2, f"Expected 2 line items, got {len(items)}"

    def test_line_item_sk_format(self, aws_resources):
        """Line items SK should be RECEIPT#{ulid}#ITEM#{nnn} (3-digit padded)."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        items = _query_line_items(table)
        sks = sorted([it["SK"] for it in items])

        expected_001 = f"RECEIPT#{RECEIPT_ID}#ITEM#001"
        expected_002 = f"RECEIPT#{RECEIPT_ID}#ITEM#002"
        assert expected_001 in sks, f"Missing ITEM#001. Found: {sks}"
        assert expected_002 in sks, f"Missing ITEM#002. Found: {sks}"

    def test_line_item_has_entity_type(self, aws_resources):
        """Line item records should have entityType=ITEM."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        items = _query_line_items(table)
        for item in items:
            assert item.get("entityType") == "ITEM"

    def test_line_item_has_name(self, aws_resources):
        """Line item records should have the item name."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        items = _query_line_items(table)
        names = {item["name"] for item in items}
        assert "Item A" in names
        assert "Item B" in names

    def test_line_item_has_prices(self, aws_resources):
        """Line item records should have unitPrice and totalPrice."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        items = _query_line_items(table)
        for item in items:
            assert "unitPrice" in item
            assert "totalPrice" in item

    def test_no_line_items_when_extraction_empty(self, aws_resources):
        """If extraction has no line items, no ITEM# records should be created."""
        table, _ = aws_resources
        event = _make_event(
            main_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(line_items=[])
            ),
        )
        _invoke_handler(event)

        items = _query_line_items(table)
        assert len(items) == 0

    def test_fallback_line_items_created(self, aws_resources):
        """Line items from shadow result should be created on fallback."""
        table, _ = aws_resources
        shadow_items = [
            {"name": "Shadow Item 1", "quantity": 1, "unitPrice": 5.00, "totalPrice": 5.00},
        ]
        event = _make_event(
            main_result=_make_error_pipeline_result(),
            shadow_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(line_items=shadow_items)
            ),
        )
        _invoke_handler(event)

        items = _query_line_items(table)
        assert len(items) == 1
        assert items[0]["name"] == "Shadow Item 1"


# ---------------------------------------------------------------------------
# S3 metadata updated
# ---------------------------------------------------------------------------


class TestFinalizeS3Metadata:
    """S3 object metadata should be updated after finalization."""

    def test_s3_metadata_updated_on_success(self, aws_resources):
        """S3 object should have status, receipt-id, and processed-at metadata."""
        _, s3 = aws_resources
        _invoke_handler(_make_event())

        head = s3.head_object(Bucket=BUCKET, Key=KEY)
        metadata = head.get("Metadata", {})

        assert metadata.get("status") == "confirmed", (
            f"S3 metadata 'status' should be 'confirmed', got: {metadata}"
        )
        assert metadata.get("receipt-id") == RECEIPT_ID
        assert "processed-at" in metadata

    def test_s3_metadata_updated_on_failure(self, aws_resources):
        """S3 metadata should also be updated when both pipelines fail."""
        _, s3 = aws_resources
        event = _make_event(
            main_result=_make_error_pipeline_result(),
            shadow_result=_make_error_pipeline_result(),
        )
        _invoke_handler(event)

        head = s3.head_object(Bucket=BUCKET, Key=KEY)
        metadata = head.get("Metadata", {})
        assert metadata.get("status") == "failed"


# ---------------------------------------------------------------------------
# Ranking winner logic
# ---------------------------------------------------------------------------


class TestFinalizeRankingWinner:
    """rankingWinner is set based on comparative ranking scores."""

    def test_ranking_winner_is_higher_scoring_pipeline(self, aws_resources):
        """rankingWinner should be the pipeline with the higher ranking score."""
        table, _ = aws_resources
        # Main pipeline has higher confidence -> should score higher
        event = _make_event(
            main_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(confidence=0.98)
            ),
            shadow_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(confidence=0.50)
            ),
        )
        result = _invoke_handler(event)

        # The default pipeline order is ocr-ai (main), ai-multimodal (shadow)
        # Main has much higher confidence, so ocr-ai should win
        assert result["rankingWinner"] == "ocr-ai"

    def test_ranking_winner_stored_in_receipt(self, aws_resources):
        """rankingWinner should be persisted on the receipt record."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        receipt = _get_receipt(table)
        assert "rankingWinner" in receipt
        assert receipt["rankingWinner"] in ("ocr-ai", "ai-multimodal")

    def test_ranking_winner_independent_of_selection(self, aws_resources):
        """rankingWinner is about scoring, NOT about which result was selected.
        Even on fallback, the winner should reflect the higher score."""
        table, _ = aws_resources

        # Shadow is the only one that succeeds, but we still set rankingWinner
        # based on the shadow's score (only one with a score)
        event = _make_event(
            main_result=_make_error_pipeline_result(),
            shadow_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(confidence=0.85)
            ),
        )
        result = _invoke_handler(event)

        # Only shadow has a score, so it should be the winner
        assert result["rankingWinner"] == "ai-multimodal"

    def test_ranking_winner_none_when_both_fail(self, aws_resources):
        """When both fail, rankingWinner should be None."""
        table, _ = aws_resources
        event = _make_event(
            main_result=_make_error_pipeline_result(),
            shadow_result=_make_error_pipeline_result(),
        )
        result = _invoke_handler(event)

        assert result["rankingWinner"] is None


# ---------------------------------------------------------------------------
# Return value contract
# ---------------------------------------------------------------------------


class TestFinalizeReturnValue:
    """Handler return value matches the expected contract."""

    def test_return_has_receipt_id(self, aws_resources):
        result = _invoke_handler(_make_event())
        assert result["receiptId"] == RECEIPT_ID

    def test_return_has_status(self, aws_resources):
        result = _invoke_handler(_make_event())
        assert result["status"] in ("confirmed", "failed")

    def test_return_has_used_fallback(self, aws_resources):
        result = _invoke_handler(_make_event())
        assert "usedFallback" in result
        assert isinstance(result["usedFallback"], bool)

    def test_return_has_ranking_winner(self, aws_resources):
        result = _invoke_handler(_make_event())
        assert "rankingWinner" in result

    def test_return_has_selected_pipeline(self, aws_resources):
        result = _invoke_handler(_make_event())
        assert "selectedPipeline" in result
        assert result["selectedPipeline"] in ("ocr-ai", "ai-multimodal")
