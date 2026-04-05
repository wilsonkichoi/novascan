"""Integration tests for the end-to-end pipeline flow.

Tests the complete pipeline data flow from receipt creation through finalize,
verifying DynamoDB records are created and updated correctly.

Uses moto for DynamoDB/S3 and mocks Textract/Bedrock boto3 clients.

Spec references:
- Section 3: Processing Flow (LoadCustomCategories -> Parallel -> Finalize)
- Section 5: Database Schema (receipt, line item, pipeline result entities)
- Section 7: Receipt Extraction Schema
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws


# --- Fixtures ---


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
    monkeypatch.setenv("RECEIPTS_BUCKET", "novascan-receipts-test")


@pytest.fixture
def aws_resources(_pipeline_env):
    """Create moto-mocked DynamoDB table and S3 bucket.

    Yields a dict with table and bucket_name for use in tests.
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
        table.meta.client.get_waiter("table_exists").wait(
            TableName="novascan-test"
        )

        # Create S3 bucket and upload a fake receipt image
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "novascan-receipts-test"
        s3.create_bucket(Bucket=bucket_name)
        s3.put_object(
            Bucket=bucket_name,
            Key="receipts/01ABC123.jpg",
            Body=b"fake-image-bytes",
            ContentType="image/jpeg",
        )

        yield {
            "table": table,
            "bucket_name": bucket_name,
            "s3_client": s3,
        }


USER_ID = "test-user-uuid-1234"
RECEIPT_ID = "01ABC123"
BUCKET = "novascan-receipts-test"
IMAGE_KEY = "receipts/01ABC123.jpg"


def _create_receipt_record(table: Any, status: str = "processing") -> None:
    """Create an initial receipt record in DynamoDB as the upload flow would.

    Spec Section 3: Receipt starts in 'processing' status after upload.
    """
    now = datetime.now(UTC).isoformat()
    table.put_item(
        Item={
            "PK": f"USER#{USER_ID}",
            "SK": f"RECEIPT#{RECEIPT_ID}",
            "entityType": "RECEIPT",
            "status": status,
            "imageKey": IMAGE_KEY,
            "createdAt": now,
            "updatedAt": now,
            "GSI1PK": f"USER#{USER_ID}",
            "GSI1SK": f"{now}#{RECEIPT_ID}",
        }
    )


def _make_extraction_result(
    merchant_name: str = "Test Store",
    total: float = 25.99,
    subtotal: float = 22.99,
    tax: float = 3.00,
    confidence: float = 0.92,
    category: str = "groceries-food",
    subcategory: str = "supermarket-grocery",
    line_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a mock extraction result matching SPEC Section 7 schema."""
    if line_items is None:
        line_items = [
            {
                "name": "Milk",
                "quantity": 1.0,
                "unitPrice": 4.99,
                "totalPrice": 4.99,
                "subcategory": "dairy-cheese-eggs",
            },
            {
                "name": "Bread",
                "quantity": 2.0,
                "unitPrice": 3.50,
                "totalPrice": 7.00,
                "subcategory": "breads-bakery",
            },
            {
                "name": "Apples",
                "quantity": 1.0,
                "unitPrice": 5.00,
                "totalPrice": 5.00,
                "subcategory": "produce",
            },
        ]
    return {
        "merchant": {
            "name": merchant_name,
            "address": "123 Main St, Anytown, USA",
            "phone": "555-0100",
        },
        "receiptDate": "2026-04-01",
        "currency": "USD",
        "lineItems": line_items,
        "subtotal": subtotal,
        "tax": tax,
        "tip": None,
        "total": total,
        "category": category,
        "subcategory": subcategory,
        "paymentMethod": "Visa ending 1234",
        "confidence": confidence,
    }


def _make_success_pipeline_result(
    extraction: dict[str, Any] | None = None,
    model_id: str = "amazon.nova-lite-v1:0",
    processing_time_ms: int = 1500,
) -> dict[str, Any]:
    """Build a successful pipeline result payload."""
    if extraction is None:
        extraction = _make_extraction_result()
    return {
        "extractionResult": extraction,
        "modelId": model_id,
        "processingTimeMs": processing_time_ms,
    }


def _make_error_pipeline_result(
    error: str = "Service error",
    error_type: str = "TextractException",
) -> dict[str, Any]:
    """Build a failed pipeline result payload."""
    return {
        "error": error,
        "errorType": error_type,
    }


def _build_finalize_event(
    main_result: dict[str, Any],
    shadow_result: dict[str, Any],
) -> dict[str, Any]:
    """Build the event that Step Functions sends to the Finalize Lambda.

    Spec Section 3: Finalize receives both pipeline results after Parallel.
    """
    return {
        "bucket": BUCKET,
        "key": IMAGE_KEY,
        "userId": USER_ID,
        "receiptId": RECEIPT_ID,
        "customCategories": [],
        "pipelineResults": [main_result, shadow_result],
    }


def _get_receipt(table: Any) -> dict[str, Any]:
    """Get the receipt record from DynamoDB."""
    response = table.get_item(
        Key={"PK": f"USER#{USER_ID}", "SK": f"RECEIPT#{RECEIPT_ID}"}
    )
    return response.get("Item", {})


def _get_pipeline_results(table: Any) -> list[dict[str, Any]]:
    """Get pipeline result records from DynamoDB."""
    from boto3.dynamodb.conditions import Key

    response = table.query(
        KeyConditionExpression=(
            Key("PK").eq(f"USER#{USER_ID}")
            & Key("SK").begins_with(f"RECEIPT#{RECEIPT_ID}#PIPELINE#")
        )
    )
    return response.get("Items", [])


def _get_line_items(table: Any) -> list[dict[str, Any]]:
    """Get line item records from DynamoDB."""
    from boto3.dynamodb.conditions import Key

    response = table.query(
        KeyConditionExpression=(
            Key("PK").eq(f"USER#{USER_ID}")
            & Key("SK").begins_with(f"RECEIPT#{RECEIPT_ID}#ITEM#")
        )
    )
    return response.get("Items", [])


# --- Test Classes ---


class TestMainSuccessPath:
    """End-to-end pipeline flow when main pipeline succeeds.

    Spec Section 3: 'If main succeeded -> use main result to populate the receipt'
    """

    def test_receipt_status_updated_to_confirmed(self, aws_resources) -> None:
        """Receipt status must transition from 'processing' to 'confirmed'.

        Spec Section 3: 'Receipt status transitions: processing -> confirmed'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_success_pipeline_result(
            extraction=_make_extraction_result(
                merchant_name="Test Store Alt",
                confidence=0.85,
            )
        )
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        receipt = _get_receipt(table)
        assert receipt["status"] == "confirmed", (
            f"Receipt status is '{receipt['status']}', expected 'confirmed'. "
            "Spec Section 3: processing -> confirmed when main succeeds."
        )

    def test_receipt_merchant_populated_from_main(self, aws_resources) -> None:
        """Receipt merchant must be populated from the main pipeline result.

        Spec Section 3: 'Main pipeline result populates the receipt record.'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_success_pipeline_result(
            extraction=_make_extraction_result(merchant_name="Shadow Store")
        )
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        receipt = _get_receipt(table)
        assert receipt.get("merchant") == "Test Store", (
            f"Receipt merchant is '{receipt.get('merchant')}', expected 'Test Store'. "
            "Main pipeline result should populate the receipt, not shadow."
        )

    def test_receipt_total_populated(self, aws_resources) -> None:
        """Receipt total must be populated from extraction data.

        Spec Section 5: Receipt has total (N) attribute.
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_error_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        receipt = _get_receipt(table)
        assert receipt.get("total") == Decimal("25.99"), (
            f"Receipt total is '{receipt.get('total')}', expected Decimal('25.99'). "
            "Spec Section 5: total is a numeric attribute."
        )

    def test_receipt_category_populated(self, aws_resources) -> None:
        """Receipt category must be populated from extraction data.

        Spec Section 5: Receipt has category (S) attribute.
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_error_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        receipt = _get_receipt(table)
        assert receipt.get("category") == "groceries-food", (
            f"Receipt category is '{receipt.get('category')}', "
            "expected 'groceries-food'."
        )

    def test_receipt_used_fallback_is_not_set(self, aws_resources) -> None:
        """usedFallback must not be set when main pipeline succeeds.

        Spec Section 3: 'If main succeeded -> use main result'
        (no fallback scenario)
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_success_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        receipt = _get_receipt(table)
        # usedFallback should either be absent or False
        assert receipt.get("usedFallback") is not True, (
            "usedFallback is True but main pipeline succeeded. "
            "Spec Section 3: usedFallback only set when main fails and "
            "shadow is used."
        )

    def test_pipeline_results_stored_in_dynamodb(self, aws_resources) -> None:
        """Both pipeline results must be stored regardless of selection.

        Spec Section 3: 'Stores both pipeline results (with rankingScore)
        in DynamoDB regardless of outcome'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_success_pipeline_result(
            extraction=_make_extraction_result(confidence=0.80)
        )
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        pipeline_records = _get_pipeline_results(table)
        assert len(pipeline_records) == 2, (
            f"Found {len(pipeline_records)} pipeline result records, expected 2. "
            "Spec Section 3: Both pipeline results stored regardless of outcome."
        )

        # Check both pipeline types are stored
        pipeline_types = {
            r["SK"].split("#PIPELINE#")[1] for r in pipeline_records
        }
        assert "ocr-ai" in pipeline_types, (
            "Missing ocr-ai pipeline result record in DynamoDB."
        )
        assert "ai-multimodal" in pipeline_types, (
            "Missing ai-multimodal pipeline result record in DynamoDB."
        )

    def test_pipeline_results_have_entity_type(self, aws_resources) -> None:
        """Pipeline result records must have entityType = PIPELINE.

        Spec Section 5: entityType discriminator attribute on all entities.
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_success_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        for record in _get_pipeline_results(table):
            assert record.get("entityType") == "PIPELINE", (
                f"Pipeline record entityType is '{record.get('entityType')}', "
                "expected 'PIPELINE'. "
                "Spec Section 5: entityType is a discriminator attribute."
            )

    def test_pipeline_results_have_ranking_scores(self, aws_resources) -> None:
        """Pipeline results must include rankingScore when extraction succeeded.

        Spec Section 3: 'Runs rank_results on both pipeline outputs.
        Computes a composite rankingScore (0-1).'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_success_pipeline_result(
            extraction=_make_extraction_result(confidence=0.80)
        )
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        for record in _get_pipeline_results(table):
            assert "rankingScore" in record, (
                f"Pipeline record {record['SK']} is missing rankingScore. "
                "Spec Section 3: Ranking computed for both pipeline outputs."
            )
            score = float(record["rankingScore"])
            assert 0.0 <= score <= 1.0, (
                f"rankingScore {score} is outside [0, 1]. "
                "Spec Section 3: composite rankingScore (0-1)."
            )

    def test_ranking_winner_set_on_receipt(self, aws_resources) -> None:
        """Receipt must have rankingWinner set.

        Spec Section 5: 'rankingWinner: Which pipeline scored higher in ranking'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_success_pipeline_result(
            extraction=_make_extraction_result(confidence=0.80)
        )
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        receipt = _get_receipt(table)
        assert receipt.get("rankingWinner") in ("ocr-ai", "ai-multimodal"), (
            f"rankingWinner is '{receipt.get('rankingWinner')}', "
            "expected 'ocr-ai' or 'ai-multimodal'. "
            "Spec Section 5: rankingWinner indicates which pipeline scored higher."
        )

    def test_line_items_created_in_dynamodb(self, aws_resources) -> None:
        """Line items must be created as separate ITEM entities.

        Spec Section 5: 'Line Item | USER#{userId} | RECEIPT#{ulid}#ITEM#{nnn}'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        extraction = _make_extraction_result()
        main_result = _make_success_pipeline_result(extraction=extraction)
        shadow_result = _make_error_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        line_items = _get_line_items(table)
        expected_count = len(extraction["lineItems"])
        assert len(line_items) == expected_count, (
            f"Found {len(line_items)} line items, expected {expected_count}. "
            "Spec Section 5: Each line item stored as RECEIPT#{ulid}#ITEM#{nnn}."
        )

    def test_line_items_have_correct_sk_format(self, aws_resources) -> None:
        """Line item SK must follow RECEIPT#{ulid}#ITEM#{nnn} pattern.

        Spec Section 5: '{nnn} - three-digit zero-padded line item sort order'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_error_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        line_items = _get_line_items(table)
        for i, item in enumerate(sorted(line_items, key=lambda x: x["SK"])):
            expected_suffix = f"#ITEM#{i + 1:03d}"
            assert item["SK"].endswith(expected_suffix), (
                f"Line item SK '{item['SK']}' does not end with "
                f"'{expected_suffix}'. "
                "Spec Section 5: nnn is three-digit zero-padded."
            )

    def test_line_items_have_entity_type(self, aws_resources) -> None:
        """Line item records must have entityType = ITEM.

        Spec Section 5: entityType discriminator attribute.
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_error_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        for item in _get_line_items(table):
            assert item.get("entityType") == "ITEM", (
                f"Line item entityType is '{item.get('entityType')}', "
                "expected 'ITEM'."
            )

    def test_line_items_contain_extraction_data(self, aws_resources) -> None:
        """Line items must contain name, quantity, unitPrice, totalPrice.

        Spec Section 5: Line Item Attributes.
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_error_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        line_items = _get_line_items(table)
        first_item = sorted(line_items, key=lambda x: x["SK"])[0]

        assert first_item.get("name") == "Milk", (
            f"First line item name is '{first_item.get('name')}', expected 'Milk'."
        )
        assert first_item.get("quantity") == Decimal("1"), (
            f"First line item quantity is '{first_item.get('quantity')}', "
            "expected Decimal('1')."
        )
        assert first_item.get("unitPrice") == Decimal("4.99"), (
            f"First line item unitPrice is '{first_item.get('unitPrice')}', "
            "expected Decimal('4.99')."
        )
        assert first_item.get("totalPrice") == Decimal("4.99"), (
            f"First line item totalPrice is '{first_item.get('totalPrice')}', "
            "expected Decimal('4.99')."
        )

    def test_s3_metadata_updated(self, aws_resources) -> None:
        """S3 object metadata must be updated after processing.

        Spec Section 3: 'Updates S3 object metadata (x-amz-meta-status,
        x-amz-meta-receipt-id, x-amz-meta-processed-at) via copy_object'
        """
        table = aws_resources["table"]
        s3_client = aws_resources["s3_client"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_error_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        head = s3_client.head_object(
            Bucket=BUCKET,
            Key=IMAGE_KEY,
        )
        metadata = head.get("Metadata", {})
        assert metadata.get("status") == "confirmed", (
            f"S3 metadata status is '{metadata.get('status')}', "
            "expected 'confirmed'. "
            "Spec Section 3: S3 metadata updated with receipt status."
        )
        assert metadata.get("receipt-id") == RECEIPT_ID, (
            f"S3 metadata receipt-id is '{metadata.get('receipt-id')}', "
            f"expected '{RECEIPT_ID}'."
        )
        assert "processed-at" in metadata, (
            "S3 metadata is missing 'processed-at'. "
            "Spec Section 3: x-amz-meta-processed-at must be set."
        )


class TestFallbackPath:
    """Pipeline flow when main fails but shadow succeeds.

    Spec Section 3: 'If main failed but shadow succeeded -> use shadow result,
    set usedFallback: true'
    """

    def test_receipt_confirmed_with_fallback(self, aws_resources) -> None:
        """Receipt status must be 'confirmed' when fallback succeeds.

        Spec Section 3: 'If main failed but shadow succeeded -> ... confirmed'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_error_pipeline_result(
            error="Textract service error",
            error_type="TextractException",
        )
        shadow_result = _make_success_pipeline_result(
            extraction=_make_extraction_result(merchant_name="Fallback Store")
        )
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        receipt = _get_receipt(table)
        assert receipt["status"] == "confirmed", (
            f"Receipt status is '{receipt['status']}', expected 'confirmed'. "
            "Spec Section 3: Shadow fallback still results in confirmed status."
        )

    def test_used_fallback_flag_set(self, aws_resources) -> None:
        """usedFallback must be True when shadow result is used.

        Spec Section 5: 'usedFallback: true if main pipeline failed and
        shadow result was used'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_error_pipeline_result()
        shadow_result = _make_success_pipeline_result(
            extraction=_make_extraction_result(merchant_name="Fallback Store")
        )
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        receipt = _get_receipt(table)
        assert receipt.get("usedFallback") is True, (
            f"usedFallback is '{receipt.get('usedFallback')}', expected True. "
            "Spec Section 5: usedFallback must be true when shadow result used."
        )

    def test_receipt_populated_from_shadow(self, aws_resources) -> None:
        """Receipt data must come from the shadow pipeline when main fails.

        Spec Section 3: 'If main failed but shadow succeeded -> use shadow result'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_error_pipeline_result()
        shadow_result = _make_success_pipeline_result(
            extraction=_make_extraction_result(merchant_name="Shadow Store")
        )
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        receipt = _get_receipt(table)
        assert receipt.get("merchant") == "Shadow Store", (
            f"Receipt merchant is '{receipt.get('merchant')}', "
            "expected 'Shadow Store'. "
            "When main fails, shadow result should populate the receipt."
        )

    def test_both_pipeline_results_stored_on_fallback(
        self, aws_resources
    ) -> None:
        """Both pipeline results stored even when main failed.

        Spec Section 3: 'Stores both pipeline results in DynamoDB
        regardless of outcome'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_error_pipeline_result()
        shadow_result = _make_success_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        pipeline_records = _get_pipeline_results(table)
        assert len(pipeline_records) == 2, (
            f"Found {len(pipeline_records)} pipeline records, expected 2. "
            "Both results must be stored even when one pipeline fails."
        )

    def test_failed_pipeline_result_has_error_info(
        self, aws_resources
    ) -> None:
        """Failed pipeline result record should contain error information.

        For debugging: the error payload from the failed pipeline should be
        preserved in the pipeline result record.
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_error_pipeline_result(
            error="Textract throttled",
            error_type="ThrottlingException",
        )
        shadow_result = _make_success_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        pipeline_records = _get_pipeline_results(table)
        # Find the main pipeline record (ocr-ai, since DEFAULT_PIPELINE=ocr-ai)
        main_record = next(
            (r for r in pipeline_records if "ocr-ai" in r["SK"]), None
        )
        assert main_record is not None, "ocr-ai pipeline record not found."
        assert "error" in main_record, (
            "Failed pipeline result record should contain 'error' field "
            "for debugging purposes."
        )

    def test_line_items_created_from_shadow(self, aws_resources) -> None:
        """Line items must be created from shadow result when main fails.

        The selected result (shadow in this case) should generate line items.
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        shadow_extraction = _make_extraction_result(merchant_name="Shadow Store")
        main_result = _make_error_pipeline_result()
        shadow_result = _make_success_pipeline_result(extraction=shadow_extraction)
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        line_items = _get_line_items(table)
        expected_count = len(shadow_extraction["lineItems"])
        assert len(line_items) == expected_count, (
            f"Found {len(line_items)} line items from shadow fallback, "
            f"expected {expected_count}."
        )


class TestBothFailPath:
    """Pipeline flow when both pipelines fail.

    Spec Section 3: 'If both failed -> set status to failed'
    """

    def test_receipt_status_set_to_failed(self, aws_resources) -> None:
        """Receipt status must be 'failed' when both pipelines fail.

        Spec Section 3: 'Receipt status transitions: processing -> failed'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_error_pipeline_result(
            error="Textract error", error_type="TextractException"
        )
        shadow_result = _make_error_pipeline_result(
            error="Bedrock error", error_type="BedrockException"
        )
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        receipt = _get_receipt(table)
        assert receipt["status"] == "failed", (
            f"Receipt status is '{receipt['status']}', expected 'failed'. "
            "Spec Section 3: Both pipelines failed -> status is 'failed'."
        )

    def test_failure_reason_populated(self, aws_resources) -> None:
        """Receipt must have failureReason when both pipelines fail.

        Spec Section 5: 'failureReason: Error message if failed'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_error_pipeline_result(
            error="Textract error", error_type="TextractException"
        )
        shadow_result = _make_error_pipeline_result(
            error="Bedrock error", error_type="BedrockException"
        )
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        receipt = _get_receipt(table)
        failure_reason = receipt.get("failureReason", "")
        assert failure_reason, (
            "Receipt failureReason is empty. "
            "Spec Section 5: Failed receipts must include a failureReason."
        )
        assert "Textract error" in failure_reason or "Bedrock error" in failure_reason, (
            f"failureReason '{failure_reason}' does not mention the actual errors. "
            "It should include information about what went wrong."
        )

    def test_no_line_items_created_on_failure(self, aws_resources) -> None:
        """No line items should be created when both pipelines fail.

        If there's no extraction result, there should be no line items.
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_error_pipeline_result()
        shadow_result = _make_error_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        line_items = _get_line_items(table)
        assert len(line_items) == 0, (
            f"Found {len(line_items)} line items but expected 0. "
            "No line items should be created when both pipelines fail."
        )

    def test_used_fallback_not_set_on_both_fail(self, aws_resources) -> None:
        """usedFallback should not be True when both pipelines fail.

        Spec Section 5: usedFallback is only set when shadow is used as fallback.
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_error_pipeline_result()
        shadow_result = _make_error_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        receipt = _get_receipt(table)
        assert receipt.get("usedFallback") is not True, (
            "usedFallback should not be True when both pipelines failed. "
            "Fallback only applies when shadow succeeds."
        )

    def test_both_error_pipeline_results_stored(self, aws_resources) -> None:
        """Both failed pipeline results must still be stored.

        Spec Section 3: 'Stores both pipeline results in DynamoDB
        regardless of outcome'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_error_pipeline_result()
        shadow_result = _make_error_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        pipeline_records = _get_pipeline_results(table)
        assert len(pipeline_records) == 2, (
            f"Found {len(pipeline_records)} pipeline records, expected 2. "
            "Both results must be stored even when both fail."
        )


class TestLoadCustomCategories:
    """Integration test for LoadCustomCategories Lambda.

    Spec Section 3: 'Before branching, Step Functions passes the user's
    custom categories to both pipeline Lambdas.'
    """

    def test_loads_custom_categories_for_user(self, aws_resources) -> None:
        """Custom categories are returned when user has some.

        Spec Section 8: Custom categories stored as CUSTOMCAT#{slug} entities.
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        # Create custom categories
        table.put_item(
            Item={
                "PK": f"USER#{USER_ID}",
                "SK": "CUSTOMCAT#costco-runs",
                "entityType": "CUSTOMCAT",
                "displayName": "Costco Runs",
                "parentCategory": "groceries-food",
                "createdAt": datetime.now(UTC).isoformat(),
            }
        )
        table.put_item(
            Item={
                "PK": f"USER#{USER_ID}",
                "SK": "CUSTOMCAT#coffee-shops",
                "entityType": "CUSTOMCAT",
                "displayName": "Coffee Shops",
                "createdAt": datetime.now(UTC).isoformat(),
            }
        )

        event = {
            "bucket": BUCKET,
            "key": IMAGE_KEY,
            "userId": USER_ID,
            "receiptId": RECEIPT_ID,
        }

        result = _invoke_load_custom_categories(event)

        assert "customCategories" in result, (
            "Response missing customCategories field."
        )
        categories = result["customCategories"]
        assert len(categories) == 2, (
            f"Expected 2 custom categories, found {len(categories)}."
        )

        slugs = {c["slug"] for c in categories}
        assert "costco-runs" in slugs, "Missing 'costco-runs' category."
        assert "coffee-shops" in slugs, "Missing 'coffee-shops' category."

    def test_empty_categories_for_new_user(self, aws_resources) -> None:
        """Returns empty list when user has no custom categories.

        Spec Section 8: 'If the user has no custom categories, only the
        predefined taxonomy is used.'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        event = {
            "bucket": BUCKET,
            "key": IMAGE_KEY,
            "userId": USER_ID,
            "receiptId": RECEIPT_ID,
        }

        result = _invoke_load_custom_categories(event)

        assert "customCategories" in result, (
            "Response missing customCategories field."
        )
        assert len(result["customCategories"]) == 0, (
            f"Expected 0 custom categories for new user, "
            f"found {len(result['customCategories'])}."
        )

    def test_passes_through_pipeline_input_fields(self, aws_resources) -> None:
        """LoadCustomCategories must pass through bucket, key, userId, receiptId.

        These fields are needed by the downstream pipeline Lambdas.
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        event = {
            "bucket": BUCKET,
            "key": IMAGE_KEY,
            "userId": USER_ID,
            "receiptId": RECEIPT_ID,
        }

        result = _invoke_load_custom_categories(event)

        assert result.get("bucket") == BUCKET, (
            f"bucket is '{result.get('bucket')}', expected '{BUCKET}'."
        )
        assert result.get("key") == IMAGE_KEY, (
            f"key is '{result.get('key')}', expected '{IMAGE_KEY}'."
        )
        assert result.get("userId") == USER_ID, (
            f"userId is '{result.get('userId')}', expected '{USER_ID}'."
        )
        assert result.get("receiptId") == RECEIPT_ID, (
            f"receiptId is '{result.get('receiptId')}', expected '{RECEIPT_ID}'."
        )


class TestReceiptDateGSI:
    """Verify that receipt date from extraction updates the GSI1SK.

    Spec Section 5: GSI1SK = {receiptDate}#{ulid}. Finalize should update
    this when receiptDate is extracted from the receipt.
    """

    def test_gsi1sk_updated_with_receipt_date(self, aws_resources) -> None:
        """GSI1SK must be updated when receiptDate is extracted.

        Spec Section 5: 'GSI1SK sorts by receiptDate then by ULID'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)

        extraction = _make_extraction_result()
        assert extraction["receiptDate"] == "2026-04-01"  # sanity check

        main_result = _make_success_pipeline_result(extraction=extraction)
        shadow_result = _make_error_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        receipt = _get_receipt(table)
        gsi1sk = receipt.get("GSI1SK", "")
        assert gsi1sk.startswith("2026-04-01"), (
            f"GSI1SK is '{gsi1sk}', expected to start with '2026-04-01'. "
            "Spec Section 5: GSI1SK = receiptDate#{ulid} for date-sorted queries."
        )
        assert RECEIPT_ID in gsi1sk, (
            f"GSI1SK '{gsi1sk}' does not contain receiptId '{RECEIPT_ID}'. "
            "Spec Section 5: GSI1SK = {receiptDate}#{ulid}."
        )


class TestPipelineResultSKFormat:
    """Verify pipeline result SK format matches spec.

    Spec Section 5: SK = RECEIPT#{ulid}#PIPELINE#{type} where type is
    'ocr-ai' or 'ai-multimodal'.
    """

    def test_pipeline_result_sk_format(self, aws_resources) -> None:
        """Pipeline result SK must follow RECEIPT#{ulid}#PIPELINE#{type} pattern."""
        table = aws_resources["table"]
        _create_receipt_record(table)

        main_result = _make_success_pipeline_result()
        shadow_result = _make_success_pipeline_result()
        event = _build_finalize_event(main_result, shadow_result)

        _invoke_finalize(event)

        pipeline_records = _get_pipeline_results(table)
        for record in pipeline_records:
            sk = record["SK"]
            assert sk.startswith(f"RECEIPT#{RECEIPT_ID}#PIPELINE#"), (
                f"Pipeline result SK '{sk}' does not match expected format "
                f"'RECEIPT#{RECEIPT_ID}#PIPELINE#{{type}}'."
            )
            pipeline_type = sk.split("#PIPELINE#")[1]
            assert pipeline_type in ("ocr-ai", "ai-multimodal"), (
                f"Pipeline type '{pipeline_type}' in SK is not 'ocr-ai' or "
                "'ai-multimodal'. Spec Section 5: type is ocr-ai or ai-multimodal."
            )


class TestDefaultPipelineConfig:
    """Verify that DEFAULT_PIPELINE config controls main/shadow assignment.

    Spec Section 9: 'defaultPipeline: Which pipeline is main vs shadow'
    """

    def test_ai_multimodal_as_default_pipeline(self, aws_resources, monkeypatch) -> None:
        """When DEFAULT_PIPELINE=ai-multimodal, shadow becomes ocr-ai.

        Spec Section 3: 'Which pipeline is main vs shadow is controlled by
        defaultPipeline in cdk.json'
        """
        table = aws_resources["table"]
        _create_receipt_record(table)
        monkeypatch.setenv("DEFAULT_PIPELINE", "ai-multimodal")

        # Need to reimport to pick up the env var change
        import importlib
        import novascan.pipeline.finalize as finalize_module
        original_default = finalize_module.DEFAULT_PIPELINE
        finalize_module.DEFAULT_PIPELINE = "ai-multimodal"

        try:
            # When DEFAULT_PIPELINE=ai-multimodal:
            # pipelineResults[0] is main = ai-multimodal
            # pipelineResults[1] is shadow = ocr-ai
            main_result = _make_success_pipeline_result(
                extraction=_make_extraction_result(merchant_name="AI Multimodal Store")
            )
            shadow_result = _make_success_pipeline_result(
                extraction=_make_extraction_result(merchant_name="OCR-AI Store")
            )
            event = _build_finalize_event(main_result, shadow_result)

            _invoke_finalize(event)

            receipt = _get_receipt(table)
            # When ai-multimodal is main and succeeds, receipt should use it
            assert receipt.get("merchant") == "AI Multimodal Store", (
                f"Receipt merchant is '{receipt.get('merchant')}', "
                "expected 'AI Multimodal Store'. "
                "When DEFAULT_PIPELINE=ai-multimodal, the first result (main) "
                "should be used."
            )
        finally:
            finalize_module.DEFAULT_PIPELINE = original_default


# --- Helpers ---


def _invoke_finalize(event: dict[str, Any]) -> dict[str, Any]:
    """Invoke the Finalize Lambda handler with mocked S3 client.

    The finalize handler uses a module-level s3_client which we need to
    replace with the moto-mocked client for S3 metadata updates.
    """
    from novascan.pipeline import finalize as finalize_module

    mock_context = MagicMock()
    mock_context.function_name = "novascan-test-finalize"
    mock_context.memory_limit_in_mb = 256
    mock_context.invoked_function_arn = (
        "arn:aws:lambda:us-east-1:123456789012:function:novascan-test-finalize"
    )
    mock_context.aws_request_id = "test-request-id"

    # Replace the module-level s3_client with a moto client
    original_s3 = finalize_module.s3_client
    finalize_module.s3_client = boto3.client("s3", region_name="us-east-1")
    try:
        return finalize_module.handler(event, mock_context)
    finally:
        finalize_module.s3_client = original_s3


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
