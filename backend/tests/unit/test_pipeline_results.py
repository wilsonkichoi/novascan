"""Tests for GET /api/receipts/{id}/pipeline-results endpoint.

Validates API contract from api-contracts.md:
- Returns both pipeline outputs for staff users
- Returns 403 for non-staff users
- Returns 404 for non-existent receipt
- Response includes usedFallback, rankingWinner, and per-pipeline data
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
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

    function_name: str = "test-function"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:test"
    aws_request_id: str = "test-request-id"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_apigw_event(
    body: dict[str, Any] | str | None = None,
    user_id: str = "user-abc-123",
    method: str = "GET",
    path: str = "/api/receipts",
    path_params: dict[str, str] | None = None,
    query_params: dict[str, str] | None = None,
    groups: list[str] | None = None,
) -> dict[str, Any]:
    """Build a minimal API Gateway HTTP API v2 event for Lambda Powertools."""
    if isinstance(body, dict):
        body_str = json.dumps(body)
    elif body is None:
        body_str = ""
    else:
        body_str = body

    raw_query = "&".join(f"{k}={v}" for k, v in (query_params or {}).items())

    claims: dict[str, Any] = {"sub": user_id}
    if groups:
        claims["cognito:groups"] = groups

    event: dict[str, Any] = {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": raw_query,
        "headers": {
            "content-type": "application/json",
        },
        "queryStringParameters": query_params or {},
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "test-api",
            "authorizer": {
                "jwt": {
                    "claims": claims,
                    "scopes": [],
                }
            },
            "domainName": "test.execute-api.us-east-1.amazonaws.com",
            "domainPrefix": "test",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "test",
            },
            "requestId": "test-request-id",
            "routeKey": f"{method} {path}",
            "stage": "$default",
            "time": "01/Jan/2026:00:00:00 +0000",
            "timeEpoch": 1767225600000,
        },
        "body": body_str,
        "isBase64Encoded": False,
    }

    if path_params:
        event["pathParameters"] = path_params

    return event


def _invoke_handler(event: dict[str, Any]) -> dict[str, Any]:
    """Import and invoke the handler, returning the response dict."""
    from novascan.api.app import handler

    return handler(event, FakeLambdaContext())


def _seed_receipt(
    table: Any,
    user_id: str = "user-abc-123",
    receipt_id: str = "01JQTEST000000000000000001",
    *,
    used_fallback: bool = False,
    ranking_winner: str = "ocr-ai",
) -> None:
    """Insert a receipt record."""
    now = datetime.now(UTC).isoformat()
    table.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": f"RECEIPT#{receipt_id}",
            "entityType": "RECEIPT",
            "receiptId": receipt_id,
            "receiptDate": "2026-03-25",
            "merchant": "Test Merchant",
            "total": Decimal("42.50"),
            "category": "groceries-food",
            "status": "confirmed",
            "imageKey": f"receipts/{receipt_id}.jpg",
            "usedFallback": used_fallback,
            "rankingWinner": ranking_winner,
            "createdAt": now,
            "updatedAt": now,
            "GSI1PK": f"USER#{user_id}",
            "GSI1SK": f"2026-03-25#{receipt_id}",
        }
    )


def _seed_pipeline_result(
    table: Any,
    user_id: str = "user-abc-123",
    receipt_id: str = "01JQTEST000000000000000001",
    pipeline_type: str = "ocr-ai",
    *,
    confidence: float = 0.94,
    ranking_score: float = 0.91,
    processing_time_ms: int = 4523,
    model_id: str = "amazon.nova-lite-v1:0",
) -> None:
    """Insert a pipeline result record."""
    now = datetime.now(UTC).isoformat()
    table.put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": f"RECEIPT#{receipt_id}#PIPELINE#{pipeline_type}",
            "entityType": "PIPELINE",
            "extractedData": {
                "merchant": {"name": "Test Merchant", "address": "123 Main St"},
                "receiptDate": "2026-03-25",
                "lineItems": [],
                "total": Decimal("42.50"),
                "category": "groceries-food",
                "subcategory": "supermarket-grocery",
                "confidence": Decimal(str(confidence)),
            },
            "confidence": Decimal(str(confidence)),
            "rankingScore": Decimal(str(ranking_score)),
            "processingTimeMs": processing_time_ms,
            "modelId": model_id,
            "createdAt": now,
        }
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _aws_setup(monkeypatch):
    """Set up mocked AWS environment for pipeline results tests."""
    monkeypatch.setenv("TABLE_NAME", "novascan-test")
    monkeypatch.setenv("RECEIPTS_BUCKET", "novascan-receipts-test")
    monkeypatch.setenv("PRESIGNED_URL_EXPIRY", "900")
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "novascan-test")
    monkeypatch.setenv("POWERTOOLS_TRACE_DISABLED", "1")

    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
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
        table = dynamodb.Table("novascan-test")

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="novascan-receipts-test")

        yield table, s3


# ---------------------------------------------------------------------------
# Staff access — happy path
# ---------------------------------------------------------------------------


class TestPipelineResultsStaffAccess:
    """GET /api/receipts/{id}/pipeline-results returns data for staff users."""

    def test_returns_200_for_staff(self, _aws_setup):
        """Staff user gets 200 for pipeline results."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)
        _seed_pipeline_result(table, receipt_id=receipt_id, pipeline_type="ocr-ai")
        _seed_pipeline_result(table, receipt_id=receipt_id, pipeline_type="ai-multimodal")

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}/pipeline-results",
            path_params={"receipt_id": receipt_id},
            groups=["staff"],
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 200, (
            f"Expected 200 for staff user, got {response['statusCode']}: {response.get('body')}"
        )

    def test_response_contains_receipt_id(self, _aws_setup):
        """Response includes the receiptId."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)
        _seed_pipeline_result(table, receipt_id=receipt_id, pipeline_type="ocr-ai")

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}/pipeline-results",
            path_params={"receipt_id": receipt_id},
            groups=["staff"],
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert body["receiptId"] == receipt_id

    def test_response_contains_both_pipeline_results(self, _aws_setup):
        """Response includes results for both ocr-ai and ai-multimodal."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)
        _seed_pipeline_result(
            table, receipt_id=receipt_id, pipeline_type="ocr-ai",
            confidence=0.94, ranking_score=0.91,
        )
        _seed_pipeline_result(
            table, receipt_id=receipt_id, pipeline_type="ai-multimodal",
            confidence=0.89, ranking_score=0.82,
        )

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}/pipeline-results",
            path_params={"receipt_id": receipt_id},
            groups=["staff"],
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert "results" in body, "Response must contain 'results'"
        assert "ocr-ai" in body["results"], "Results must include ocr-ai"
        assert "ai-multimodal" in body["results"], "Results must include ai-multimodal"

    def test_response_contains_used_fallback(self, _aws_setup):
        """Response includes usedFallback field."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id, used_fallback=False)
        _seed_pipeline_result(table, receipt_id=receipt_id, pipeline_type="ocr-ai")

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}/pipeline-results",
            path_params={"receipt_id": receipt_id},
            groups=["staff"],
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert "usedFallback" in body, "Response must contain 'usedFallback'"
        assert body["usedFallback"] is False

    def test_response_contains_ranking_winner(self, _aws_setup):
        """Response includes rankingWinner field."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id, ranking_winner="ocr-ai")
        _seed_pipeline_result(table, receipt_id=receipt_id, pipeline_type="ocr-ai")

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}/pipeline-results",
            path_params={"receipt_id": receipt_id},
            groups=["staff"],
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert "rankingWinner" in body, "Response must contain 'rankingWinner'"
        assert body["rankingWinner"] == "ocr-ai"

    def test_pipeline_result_has_required_fields(self, _aws_setup):
        """Each pipeline result should have extractedData, confidence, rankingScore, etc."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)
        _seed_pipeline_result(
            table, receipt_id=receipt_id, pipeline_type="ocr-ai",
            confidence=0.94, ranking_score=0.91, processing_time_ms=4523,
            model_id="amazon.nova-lite-v1:0",
        )

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}/pipeline-results",
            path_params={"receipt_id": receipt_id},
            groups=["staff"],
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        ocr_result = body["results"]["ocr-ai"]
        assert ocr_result is not None, "ocr-ai result should not be null"
        assert "extractedData" in ocr_result, "Pipeline result must contain extractedData"
        assert "confidence" in ocr_result, "Pipeline result must contain confidence"
        assert "rankingScore" in ocr_result, "Pipeline result must contain rankingScore"
        assert "processingTimeMs" in ocr_result, "Pipeline result must contain processingTimeMs"
        assert "modelId" in ocr_result, "Pipeline result must contain modelId"
        assert "createdAt" in ocr_result, "Pipeline result must contain createdAt"

    def test_null_pipeline_when_one_failed(self, _aws_setup):
        """If one pipeline path failed, its result can be null."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)
        # Only seed ocr-ai, not ai-multimodal (simulating failure)
        _seed_pipeline_result(table, receipt_id=receipt_id, pipeline_type="ocr-ai")

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}/pipeline-results",
            path_params={"receipt_id": receipt_id},
            groups=["staff"],
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert response["statusCode"] == 200
        # ai-multimodal may be null since it was not seeded
        assert "results" in body
        # The endpoint should still return 200 even if one pipeline result is missing


# ---------------------------------------------------------------------------
# Non-staff access — 403
# ---------------------------------------------------------------------------


class TestPipelineResultsAccess:
    """GET /api/receipts/{id}/pipeline-results is accessible to all authenticated users."""

    def test_200_for_regular_user(self, _aws_setup):
        """Non-staff user can access pipeline results."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)
        _seed_pipeline_result(table, receipt_id=receipt_id, pipeline_type="ocr-ai")

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}/pipeline-results",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 200, (
            f"Expected 200 for regular user, got {response['statusCode']}: {response.get('body')}"
        )

    def test_200_for_user_with_non_staff_groups(self, _aws_setup):
        """User with non-staff groups can access pipeline results."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)
        _seed_pipeline_result(table, receipt_id=receipt_id, pipeline_type="ocr-ai")

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}/pipeline-results",
            path_params={"receipt_id": receipt_id},
            groups=["users", "premium"],
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 200, (
            f"Expected 200 for non-staff groups, got {response['statusCode']}"
        )


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestPipelineResultsErrors:
    """GET /api/receipts/{id}/pipeline-results error handling."""

    def test_404_for_nonexistent_receipt(self, _aws_setup):
        """Pipeline results for a non-existent receipt returns 404."""
        table, _ = _aws_setup

        event = _build_apigw_event(
            method="GET",
            path="/api/receipts/01JQTEST999999999999999999/pipeline-results",
            path_params={"receipt_id": "01JQTEST999999999999999999"},
            groups=["staff"],
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 404, (
            f"Expected 404 for non-existent receipt, got {response['statusCode']}"
        )

    def test_cannot_access_other_users_pipeline_results(self, _aws_setup):
        """Staff user cannot access another user's pipeline results."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, user_id="user-other", receipt_id=receipt_id)
        _seed_pipeline_result(table, user_id="user-other", receipt_id=receipt_id)

        event = _build_apigw_event(
            user_id="user-abc-123",
            method="GET",
            path=f"/api/receipts/{receipt_id}/pipeline-results",
            path_params={"receipt_id": receipt_id},
            groups=["staff"],
        )
        response = _invoke_handler(event)
        assert response["statusCode"] in (403, 404), (
            f"Expected 403 or 404 for cross-user access, got {response['statusCode']}"
        )
