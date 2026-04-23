"""Tests for Finalize Lambda handler — ranking-based selection and persistence.

Validates the spec contract from SPEC.md Section 3 (Processing Flow):
- Highest-scoring pipeline result is selected
- All three pipelines fail -> status failed
- Ranking scores computed for all results
- DynamoDB records: receipt update, pipeline results, line items
- S3 metadata updated
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    ocr_ai_result: dict[str, Any] | None = None,
    ai_multimodal_result: dict[str, Any] | None = None,
    ai_vision_v2_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the finalize handler event from Step Functions.

    pipelineResults order matches PIPELINE_TYPES: [ocr-ai, ai-multimodal, ai-vision-v2].
    """
    if ocr_ai_result is None:
        ocr_ai_result = _make_success_pipeline_result(
            extraction=_make_extraction_result(confidence=0.92),
        )
    if ai_multimodal_result is None:
        ai_multimodal_result = _make_success_pipeline_result(
            extraction=_make_extraction_result(merchant_name="V1 Vision Store", confidence=0.85),
            processing_time_ms=1800,
        )
    if ai_vision_v2_result is None:
        ai_vision_v2_result = _make_success_pipeline_result(
            extraction=_make_extraction_result(merchant_name="V2 Vision Store", confidence=0.88),
            model_id="us.amazon.nova-2-lite-v1:0",
            processing_time_ms=1500,
        )

    return {
        "bucket": BUCKET,
        "key": KEY,
        "userId": USER_ID,
        "receiptId": RECEIPT_ID,
        "customCategories": [],
        "pipelineResults": [ocr_ai_result, ai_multimodal_result, ai_vision_v2_result],
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
    from novascan.pipeline.finalize import handler

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
# Ranking-based selection -> highest score wins
# ---------------------------------------------------------------------------


class TestFinalizeRankingSelection:
    """The pipeline result with the highest ranking score is selected."""

    def test_status_confirmed(self, aws_resources):
        """Receipt status should be 'confirmed' when at least one pipeline succeeds."""
        table, _ = aws_resources
        result = _invoke_handler(_make_event())

        assert result["status"] == "confirmed"

        receipt = _get_receipt(table)
        assert receipt["status"] == "confirmed"

    def test_used_fallback_false(self, aws_resources):
        """usedFallback should always be False under ranking-based selection."""
        table, _ = aws_resources
        result = _invoke_handler(_make_event())

        assert result["usedFallback"] is False

    def test_highest_scoring_result_selected(self, aws_resources):
        """Receipt data should come from the highest-scoring pipeline."""
        table, _ = aws_resources
        # ocr-ai has confidence=0.92 (highest in default event)
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
        assert result["rankingWinner"] in ("ocr-ai", "ai-multimodal", "ai-vision-v2")

        receipt = _get_receipt(table)
        assert receipt.get("rankingWinner") in ("ocr-ai", "ai-multimodal", "ai-vision-v2")


# ---------------------------------------------------------------------------
# Partial pipeline failures -> surviving pipelines compete on ranking
# ---------------------------------------------------------------------------


class TestFinalizePartialFailure:
    """When some pipelines fail, surviving results compete on ranking."""

    def test_status_confirmed_with_one_survivor(self, aws_resources):
        """Receipt should be 'confirmed' if at least one pipeline succeeds."""
        table, _ = aws_resources
        event = _make_event(
            ocr_ai_result=_make_error_pipeline_result(),
            ai_multimodal_result=_make_error_pipeline_result(),
            ai_vision_v2_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(merchant_name="V2 Store"),
                model_id="us.amazon.nova-2-lite-v1:0",
            ),
        )
        result = _invoke_handler(event)

        assert result["status"] == "confirmed"
        receipt = _get_receipt(table)
        assert receipt["status"] == "confirmed"

    def test_sole_survivor_selected(self, aws_resources):
        """When only one pipeline succeeds, its data is used."""
        table, _ = aws_resources
        event = _make_event(
            ocr_ai_result=_make_error_pipeline_result(),
            ai_multimodal_result=_make_error_pipeline_result(),
            ai_vision_v2_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(merchant_name="V2 Store"),
                model_id="us.amazon.nova-2-lite-v1:0",
            ),
        )
        _invoke_handler(event)

        receipt = _get_receipt(table)
        assert receipt.get("merchant") == "V2 Store"

    def test_higher_scoring_survivor_wins(self, aws_resources):
        """When two survive, the higher-scoring one is selected."""
        table, _ = aws_resources
        event = _make_event(
            ocr_ai_result=_make_error_pipeline_result(),
            ai_multimodal_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(merchant_name="V1 Store", confidence=0.60),
            ),
            ai_vision_v2_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(merchant_name="V2 Store", confidence=0.95),
                model_id="us.amazon.nova-2-lite-v1:0",
            ),
        )
        result = _invoke_handler(event)

        assert result["selectedPipeline"] == "ai-vision-v2"
        receipt = _get_receipt(table)
        assert receipt.get("merchant") == "V2 Store"


# ---------------------------------------------------------------------------
# All three fail -> status failed
# ---------------------------------------------------------------------------


class TestFinalizeAllFailed:
    """When all three pipelines fail, receipt status is 'failed'."""

    def test_status_failed(self, aws_resources):
        """Receipt status should be 'failed' when all pipelines error."""
        table, _ = aws_resources
        event = _make_event(
            ocr_ai_result=_make_error_pipeline_result(error="Textract timed out"),
            ai_multimodal_result=_make_error_pipeline_result(error="Bedrock crashed"),
            ai_vision_v2_result=_make_error_pipeline_result(error="Nova 2 Lite error"),
        )
        result = _invoke_handler(event)

        assert result["status"] == "failed"

        receipt = _get_receipt(table)
        assert receipt["status"] == "failed"

    def test_used_fallback_false_when_all_fail(self, aws_resources):
        """usedFallback should be False — all failed."""
        table, _ = aws_resources
        event = _make_event(
            ocr_ai_result=_make_error_pipeline_result(),
            ai_multimodal_result=_make_error_pipeline_result(),
            ai_vision_v2_result=_make_error_pipeline_result(),
        )
        result = _invoke_handler(event)

        assert result["usedFallback"] is False

    def test_failure_reason_set(self, aws_resources):
        """Failed receipts should include a failureReason attribute per SPEC."""
        table, _ = aws_resources
        event = _make_event(
            ocr_ai_result=_make_error_pipeline_result(error="Textract error"),
            ai_multimodal_result=_make_error_pipeline_result(error="Bedrock error"),
            ai_vision_v2_result=_make_error_pipeline_result(error="Nova 2 error"),
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
        """When all fail, no line items should be created."""
        table, _ = aws_resources
        event = _make_event(
            ocr_ai_result=_make_error_pipeline_result(),
            ai_multimodal_result=_make_error_pipeline_result(),
            ai_vision_v2_result=_make_error_pipeline_result(),
        )
        _invoke_handler(event)

        items = _query_line_items(table)
        assert len(items) == 0, "No line items should exist when all pipelines fail"


# ---------------------------------------------------------------------------
# Pipeline results stored
# ---------------------------------------------------------------------------


class TestFinalizePipelineRecords:
    """All three pipeline results stored as PIPELINE# records in DynamoDB."""

    def test_three_pipeline_records_created(self, aws_resources):
        """All three pipeline records should be created."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        records = _query_pipeline_records(table)
        assert len(records) == 3, (
            f"Expected 3 pipeline records, got {len(records)}"
        )

    def test_pipeline_record_sk_format(self, aws_resources):
        """Pipeline records should have SK matching RECEIPT#{ulid}#PIPELINE#{type}."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        records = _query_pipeline_records(table)
        sks = sorted([r["SK"] for r in records])

        expected_ocr = f"RECEIPT#{RECEIPT_ID}#PIPELINE#ocr-ai"
        expected_multi = f"RECEIPT#{RECEIPT_ID}#PIPELINE#ai-multimodal"
        expected_v2 = f"RECEIPT#{RECEIPT_ID}#PIPELINE#ai-vision-v2"

        assert expected_ocr in sks, f"Missing ocr-ai pipeline record. Found: {sks}"
        assert expected_multi in sks, f"Missing ai-multimodal pipeline record. Found: {sks}"
        assert expected_v2 in sks, f"Missing ai-vision-v2 pipeline record. Found: {sks}"

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
        """Pipeline records should be stored even when pipelines errored."""
        table, _ = aws_resources
        event = _make_event(
            ocr_ai_result=_make_error_pipeline_result(),
            ai_multimodal_result=_make_error_pipeline_result(),
            ai_vision_v2_result=_make_error_pipeline_result(),
        )
        _invoke_handler(event)

        records = _query_pipeline_records(table)
        assert len(records) == 3, "Pipeline records should be stored even on failure"

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
        """If winning extraction has no line items, no ITEM# records should be created."""
        table, _ = aws_resources
        empty_extraction = _make_extraction_result(line_items=[], confidence=0.95)
        event = _make_event(
            ocr_ai_result=_make_success_pipeline_result(extraction=empty_extraction),
            ai_multimodal_result=_make_error_pipeline_result(),
            ai_vision_v2_result=_make_error_pipeline_result(),
        )
        _invoke_handler(event)

        items = _query_line_items(table)
        assert len(items) == 0

    def test_surviving_pipeline_line_items_created(self, aws_resources):
        """Line items from the highest-scoring surviving pipeline should be created."""
        table, _ = aws_resources
        v2_items = [
            {"name": "V2 Item 1", "quantity": 1, "unitPrice": 5.00, "totalPrice": 5.00},
        ]
        event = _make_event(
            ocr_ai_result=_make_error_pipeline_result(),
            ai_multimodal_result=_make_error_pipeline_result(),
            ai_vision_v2_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(line_items=v2_items),
                model_id="us.amazon.nova-2-lite-v1:0",
            ),
        )
        _invoke_handler(event)

        items = _query_line_items(table)
        assert len(items) == 1
        assert items[0]["name"] == "V2 Item 1"


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
        """S3 metadata should also be updated when all pipelines fail."""
        _, s3 = aws_resources
        event = _make_event(
            ocr_ai_result=_make_error_pipeline_result(),
            ai_multimodal_result=_make_error_pipeline_result(),
            ai_vision_v2_result=_make_error_pipeline_result(),
        )
        _invoke_handler(event)

        head = s3.head_object(Bucket=BUCKET, Key=KEY)
        metadata = head.get("Metadata", {})
        assert metadata.get("status") == "failed"


# ---------------------------------------------------------------------------
# Ranking winner logic
# ---------------------------------------------------------------------------


class TestFinalizeRankingWinner:
    """rankingWinner is the pipeline with the highest ranking score."""

    def test_ranking_winner_is_highest_scoring_pipeline(self, aws_resources):
        """rankingWinner should be the pipeline with the highest ranking score."""
        table, _ = aws_resources
        event = _make_event(
            ocr_ai_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(confidence=0.50)
            ),
            ai_multimodal_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(confidence=0.60)
            ),
            ai_vision_v2_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(confidence=0.98),
                model_id="us.amazon.nova-2-lite-v1:0",
            ),
        )
        result = _invoke_handler(event)

        assert result["rankingWinner"] == "ai-vision-v2"

    def test_ranking_winner_stored_in_receipt(self, aws_resources):
        """rankingWinner should be persisted on the receipt record."""
        table, _ = aws_resources
        _invoke_handler(_make_event())

        receipt = _get_receipt(table)
        assert "rankingWinner" in receipt
        assert receipt["rankingWinner"] in ("ocr-ai", "ai-multimodal", "ai-vision-v2")

    def test_sole_survivor_is_winner(self, aws_resources):
        """When only one pipeline succeeds, it is the ranking winner."""
        table, _ = aws_resources
        event = _make_event(
            ocr_ai_result=_make_error_pipeline_result(),
            ai_multimodal_result=_make_error_pipeline_result(),
            ai_vision_v2_result=_make_success_pipeline_result(
                extraction=_make_extraction_result(confidence=0.85),
                model_id="us.amazon.nova-2-lite-v1:0",
            ),
        )
        result = _invoke_handler(event)

        assert result["rankingWinner"] == "ai-vision-v2"

    def test_ranking_winner_none_when_all_fail(self, aws_resources):
        """When all fail, rankingWinner should be None."""
        table, _ = aws_resources
        event = _make_event(
            ocr_ai_result=_make_error_pipeline_result(),
            ai_multimodal_result=_make_error_pipeline_result(),
            ai_vision_v2_result=_make_error_pipeline_result(),
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
        assert result["selectedPipeline"] in ("ocr-ai", "ai-multimodal", "ai-vision-v2")
