"""Tests for GET /api/receipts endpoint.

Validates the API contract from api-contracts.md:
- Returns user's receipts sorted by date descending (ULID descending)
- Pagination with cursor
- Filters by status, category, date range
- Does not return other users' receipts
"""

from __future__ import annotations

import json
from dataclasses import dataclass
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
    user_id: str = "user-abc-123",
    query_params: dict[str, str] | None = None,
    method: str = "GET",
    path: str = "/api/receipts",
) -> dict[str, Any]:
    """Build a minimal API Gateway HTTP API v2 event for Lambda Powertools."""
    raw_qs = "&".join(f"{k}={v}" for k, v in (query_params or {}).items())

    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": raw_qs,
        "headers": {
            "content-type": "application/json",
        },
        "queryStringParameters": query_params or {},
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "test-api",
            "authorizer": {
                "jwt": {
                    "claims": {"sub": user_id},
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
        "body": None,
        "isBase64Encoded": False,
    }


def _seed_receipt(
    table,
    user_id: str,
    receipt_id: str,
    receipt_date: str = "2026-03-25",
    status: str = "confirmed",
    merchant: str | None = "Test Merchant",
    total: float | None = 25.99,
    category: str | None = "groceries-food",
    subcategory: str | None = "supermarket-grocery",
    image_key: str | None = None,
) -> dict[str, Any]:
    """Insert a receipt record into the test DynamoDB table."""
    if image_key is None:
        image_key = f"receipts/{receipt_id}.jpg"

    item: dict[str, Any] = {
        "PK": f"USER#{user_id}",
        "SK": f"RECEIPT#{receipt_id}",
        "entityType": "RECEIPT",
        "receiptId": receipt_id,
        "status": status,
        "imageKey": image_key,
        "createdAt": f"{receipt_date}T14:30:00Z",
        "updatedAt": f"{receipt_date}T14:30:00Z",
        "GSI1PK": f"USER#{user_id}",
        "GSI1SK": f"{receipt_date}#{receipt_id}",
    }

    if merchant is not None:
        item["merchant"] = merchant
    if total is not None:
        item["total"] = Decimal(str(total))
    if category is not None:
        item["category"] = category
    if subcategory is not None:
        item["subcategory"] = subcategory
    if receipt_date is not None:
        item["receiptDate"] = receipt_date

    table.put_item(Item=item)
    return item


def _invoke_list(event: dict[str, Any]) -> dict[str, Any]:
    """Import and invoke the handler, returning the response dict."""
    from api.app import handler

    return handler(event, FakeLambdaContext())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def aws_env(monkeypatch):
    """Set up mocked AWS environment for list tests."""
    monkeypatch.setenv("TABLE_NAME", "novascan-test")
    monkeypatch.setenv("RECEIPTS_BUCKET", "novascan-receipts-test")
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "novascan-test")
    monkeypatch.setenv("POWERTOOLS_TRACE_DISABLED", "1")

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

        # Create S3 bucket (needed for presigned GET URLs)
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="novascan-receipts-test")

        yield table


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestListReceiptsHappyPath:
    """Basic listing functionality."""

    def test_returns_200(self, aws_env):
        event = _build_apigw_event()
        response = _invoke_list(event)
        assert response["statusCode"] == 200

    def test_empty_list(self, aws_env):
        """A user with no receipts should get an empty list."""
        event = _build_apigw_event()
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert body["receipts"] == []
        assert body["nextCursor"] is None

    def test_returns_user_receipts(self, aws_env):
        """Should return receipts belonging to the authenticated user."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0001")

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert len(body["receipts"]) == 1
        assert body["receipts"][0]["receiptId"] == "01RECEIPT000001AAAAAA0001"

    def test_response_fields_match_contract(self, aws_env):
        """Each receipt in the list should have the expected fields per api-contracts.md."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(
            table,
            user_id,
            "01RECEIPT000001AAAAAA0001",
            receipt_date="2026-03-25",
            status="confirmed",
            merchant="Whole Foods Market",
            total=30.39,
            category="groceries-food",
            subcategory="supermarket-grocery",
        )

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_list(event)
        body = json.loads(response["body"])
        receipt = body["receipts"][0]

        # Required fields per API contract
        assert "receiptId" in receipt
        assert "status" in receipt
        assert "createdAt" in receipt

        # Optional fields that should be present for confirmed receipts
        assert "receiptDate" in receipt
        assert "merchant" in receipt
        assert "total" in receipt
        assert "category" in receipt
        assert "imageUrl" in receipt

    def test_image_url_is_presigned(self, aws_env):
        """imageUrl should be a presigned GET URL per spec."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0001")

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_list(event)
        body = json.loads(response["body"])

        image_url = body["receipts"][0]["imageUrl"]
        assert image_url is not None, "Confirmed receipt should have an imageUrl"
        assert "s3" in image_url.lower() or "amazonaws" in image_url.lower(), (
            "imageUrl should be a presigned S3 URL"
        )

    def test_processing_receipt_null_fields(self, aws_env):
        """Receipts with status=processing should have null OCR fields."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(
            table,
            user_id,
            "01RECEIPT000001AAAAAA0001",
            status="processing",
            merchant=None,
            total=None,
            category=None,
            subcategory=None,
        )

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_list(event)
        body = json.loads(response["body"])
        receipt = body["receipts"][0]

        assert receipt["status"] == "processing"
        assert receipt["merchant"] is None
        assert receipt["total"] is None
        assert receipt["category"] is None


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


class TestListReceiptsSorting:
    """Results should be sorted by ULID descending (most recent first)."""

    def test_sorted_by_date_descending(self, aws_env):
        """Receipts should appear most recent first."""
        table = aws_env
        user_id = "user-abc-123"

        # Seed in non-date order; ULIDs are chosen so lexicographic order matches date
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0001", receipt_date="2026-03-20", merchant="Old")
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0003", receipt_date="2026-03-25", merchant="Recent")
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0002", receipt_date="2026-03-22", merchant="Middle")

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_list(event)
        body = json.loads(response["body"])
        dates = [r["receiptDate"] for r in body["receipts"]]

        # Most recent first
        assert dates == sorted(dates, reverse=True), (
            f"Expected dates in descending order, got: {dates}"
        )


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestListReceiptsPagination:
    """Cursor-based pagination behavior."""

    def test_default_limit(self, aws_env):
        """Default limit is 50 per spec. No more than that returned."""
        table = aws_env
        user_id = "user-abc-123"

        # Seed 5 receipts (testing that limit mechanics work, not seeding 50+)
        for i in range(5):
            rid = f"01RECEIPT00000{i:01d}AAAAAA000{i}"
            _seed_receipt(table, user_id, rid, receipt_date=f"2026-03-{20+i:02d}")

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert len(body["receipts"]) == 5

    def test_custom_limit(self, aws_env):
        """limit parameter restricts the number of results."""
        table = aws_env
        user_id = "user-abc-123"

        for i in range(5):
            rid = f"01RECEIPT00000{i:01d}AAAAAA000{i}"
            _seed_receipt(table, user_id, rid, receipt_date=f"2026-03-{20+i:02d}")

        event = _build_apigw_event(user_id=user_id, query_params={"limit": "2"})
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert len(body["receipts"]) <= 2

    def test_cursor_returns_next_page(self, aws_env):
        """Using the nextCursor from a response should return the next page."""
        table = aws_env
        user_id = "user-abc-123"

        for i in range(5):
            rid = f"01RECEIPT00000{i:01d}AAAAAA000{i}"
            _seed_receipt(table, user_id, rid, receipt_date=f"2026-03-{20+i:02d}")

        # First page
        event1 = _build_apigw_event(user_id=user_id, query_params={"limit": "2"})
        response1 = _invoke_list(event1)
        body1 = json.loads(response1["body"])

        assert body1["nextCursor"] is not None, "Should have a nextCursor when there are more results"

        # Second page
        event2 = _build_apigw_event(
            user_id=user_id,
            query_params={"limit": "2", "cursor": body1["nextCursor"]},
        )
        response2 = _invoke_list(event2)
        body2 = json.loads(response2["body"])

        # Pages should have different receipts
        page1_ids = {r["receiptId"] for r in body1["receipts"]}
        page2_ids = {r["receiptId"] for r in body2["receipts"]}
        assert page1_ids.isdisjoint(page2_ids), "Pages should not overlap"

    def test_no_cursor_when_all_results_returned(self, aws_env):
        """nextCursor should be null when there are no more results."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0001")

        event = _build_apigw_event(user_id=user_id, query_params={"limit": "100"})
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert body["nextCursor"] is None

    def test_limit_minimum_clamped_to_1(self, aws_env):
        """limit=0 or negative should be clamped to at least 1."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0001")

        event = _build_apigw_event(user_id=user_id, query_params={"limit": "0"})
        response = _invoke_list(event)
        body = json.loads(response["body"])

        # Should still return results (clamped to 1)
        assert response["statusCode"] == 200
        assert len(body["receipts"]) == 1

    def test_limit_maximum_clamped_to_100(self, aws_env):
        """limit > 100 should be clamped to 100 per spec."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0001")

        event = _build_apigw_event(user_id=user_id, query_params={"limit": "999"})
        response = _invoke_list(event)

        # Should not error — just caps at 100
        assert response["statusCode"] == 200

    def test_invalid_cursor_returns_400(self, aws_env):
        """An invalid cursor should return 400 VALIDATION_ERROR with generic message."""
        event = _build_apigw_event(query_params={"cursor": "not-a-valid-cursor!!!"})
        response = _invoke_list(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"]["code"] == "VALIDATION_ERROR"
        # Error message must be generic — no internal details (M7 mitigation)
        assert body["error"]["message"] == "Invalid pagination cursor"

    def test_cursor_with_wrong_keys_returns_400(self, aws_env):
        """A cursor with extra/missing keys should return 400."""
        import base64

        bad_cursor = base64.urlsafe_b64encode(
            json.dumps({"GSI1PK": "USER#user-abc-123", "extra": "key"}).encode()
        ).decode()
        event = _build_apigw_event(query_params={"cursor": bad_cursor})
        response = _invoke_list(event)

        assert response["statusCode"] == 400

    def test_cursor_targeting_other_user_returns_400(self, aws_env):
        """A cursor with GSI1PK for another user must be rejected (H1 mitigation)."""
        import base64

        tampered_cursor = base64.urlsafe_b64encode(
            json.dumps({
                "GSI1PK": "USER#attacker-user",
                "GSI1SK": "2026-03-25#01RECEIPT000001AAAAAA0001",
                "PK": "USER#attacker-user",
                "SK": "RECEIPT#01RECEIPT000001AAAAAA0001",
            }).encode()
        ).decode()
        event = _build_apigw_event(query_params={"cursor": tampered_cursor})
        response = _invoke_list(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"]["message"] == "Invalid pagination cursor"


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class TestListReceiptsFilters:
    """Filter parameters: status, category, date range."""

    def test_filter_by_status(self, aws_env):
        """status=confirmed should return only confirmed receipts."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0001", status="confirmed")
        _seed_receipt(
            table, user_id, "01RECEIPT000001AAAAAA0002",
            status="processing", merchant=None, total=None, category=None, subcategory=None,
        )
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0003", status="failed")

        event = _build_apigw_event(user_id=user_id, query_params={"status": "confirmed"})
        response = _invoke_list(event)
        body = json.loads(response["body"])

        statuses = [r["status"] for r in body["receipts"]]
        assert all(s == "confirmed" for s in statuses), f"Expected only confirmed, got: {statuses}"
        assert len(body["receipts"]) == 1

    def test_filter_by_status_processing(self, aws_env):
        """status=processing should return only processing receipts."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0001", status="confirmed")
        _seed_receipt(
            table, user_id, "01RECEIPT000001AAAAAA0002",
            status="processing", merchant=None, total=None, category=None, subcategory=None,
        )

        event = _build_apigw_event(user_id=user_id, query_params={"status": "processing"})
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert len(body["receipts"]) == 1
        assert body["receipts"][0]["status"] == "processing"

    def test_filter_by_category(self, aws_env):
        """category filter should return only matching receipts."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0001", category="groceries-food")
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0002", category="dining-restaurants")

        event = _build_apigw_event(user_id=user_id, query_params={"category": "groceries-food"})
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert len(body["receipts"]) == 1
        assert body["receipts"][0]["category"] == "groceries-food"

    def test_filter_by_date_range(self, aws_env):
        """startDate and endDate should filter to receipts within the range."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0001", receipt_date="2026-03-10")
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0002", receipt_date="2026-03-20")
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0003", receipt_date="2026-03-30")

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"startDate": "2026-03-15", "endDate": "2026-03-25"},
        )
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert len(body["receipts"]) == 1
        assert body["receipts"][0]["receiptDate"] == "2026-03-20"

    def test_filter_by_start_date_only(self, aws_env):
        """startDate alone should return receipts on or after that date."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0001", receipt_date="2026-03-10")
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0002", receipt_date="2026-03-20")
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0003", receipt_date="2026-03-30")

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"startDate": "2026-03-20"},
        )
        response = _invoke_list(event)
        body = json.loads(response["body"])

        dates = [r["receiptDate"] for r in body["receipts"]]
        assert all(d >= "2026-03-20" for d in dates), f"All dates should be >= 2026-03-20, got: {dates}"
        assert len(body["receipts"]) == 2

    def test_filter_by_end_date_only(self, aws_env):
        """endDate alone should return receipts on or before that date."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0001", receipt_date="2026-03-10")
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0002", receipt_date="2026-03-20")
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0003", receipt_date="2026-03-30")

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"endDate": "2026-03-20"},
        )
        response = _invoke_list(event)
        body = json.loads(response["body"])

        dates = [r["receiptDate"] for r in body["receipts"]]
        assert all(d <= "2026-03-20" for d in dates), f"All dates should be <= 2026-03-20, got: {dates}"

    def test_combined_filters(self, aws_env):
        """Multiple filters should be applied together (AND)."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(
            table, user_id, "01RECEIPT000001AAAAAA0001",
            receipt_date="2026-03-20", status="confirmed", category="groceries-food",
        )
        _seed_receipt(
            table, user_id, "01RECEIPT000001AAAAAA0002",
            receipt_date="2026-03-20", status="confirmed", category="dining-restaurants",
        )
        _seed_receipt(
            table, user_id, "01RECEIPT000001AAAAAA0003",
            receipt_date="2026-03-20", status="processing",
            category=None, merchant=None, total=None, subcategory=None,
        )

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"status": "confirmed", "category": "groceries-food"},
        )
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert len(body["receipts"]) == 1
        assert body["receipts"][0]["status"] == "confirmed"
        assert body["receipts"][0]["category"] == "groceries-food"


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------


class TestListReceiptsUserIsolation:
    """A user should only see their own receipts."""

    def test_does_not_return_other_users_receipts(self, aws_env):
        """User A should not see User B's receipts."""
        table = aws_env
        _seed_receipt(table, "user-A", "01RECEIPT000001AAAAAA0001", merchant="User A Store")
        _seed_receipt(table, "user-B", "01RECEIPT000001AAAAAA0002", merchant="User B Store")

        event = _build_apigw_event(user_id="user-A")
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert len(body["receipts"]) == 1
        assert body["receipts"][0]["merchant"] == "User A Store"

    def test_user_with_no_receipts_gets_empty_list(self, aws_env):
        """A user with no data should get an empty list, not other users' data."""
        table = aws_env
        _seed_receipt(table, "user-other", "01RECEIPT000001AAAAAA0001")

        event = _build_apigw_event(user_id="user-empty")
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert body["receipts"] == []

    def test_multiple_users_isolated(self, aws_env):
        """Each user sees only their own receipts even when multiple exist."""
        table = aws_env

        for uid in ("user-1", "user-2", "user-3"):
            for i in range(3):
                rid = f"01RECEIPT0000{uid[-1]}{i}AAAAAA000{i}"
                _seed_receipt(table, uid, rid, merchant=f"{uid} Merchant {i}")

        for uid in ("user-1", "user-2", "user-3"):
            event = _build_apigw_event(user_id=uid)
            response = _invoke_list(event)
            body = json.loads(response["body"])

            assert len(body["receipts"]) == 3, f"User {uid} should have 3 receipts"
            for r in body["receipts"]:
                assert uid in r["merchant"], f"User {uid} got receipt from wrong user: {r['merchant']}"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestListReceiptsEdgeCases:
    """Edge cases and boundary conditions."""

    def test_non_numeric_limit_uses_default(self, aws_env):
        """A non-numeric limit value should fall back to the default (50)."""
        event = _build_apigw_event(query_params={"limit": "abc"})
        response = _invoke_list(event)

        # Should not error — falls back to default
        assert response["statusCode"] == 200

    def test_response_has_next_cursor_key(self, aws_env):
        """Response should always include the nextCursor key."""
        event = _build_apigw_event()
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert "nextCursor" in body
        assert "receipts" in body

    def test_total_is_numeric(self, aws_env):
        """Total should be a number (float), not a string, in the response."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01RECEIPT000001AAAAAA0001", total=30.39)

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_list(event)
        body = json.loads(response["body"])

        total = body["receipts"][0]["total"]
        assert isinstance(total, (int, float)), f"total should be numeric, got {type(total)}: {total}"
        assert total == pytest.approx(30.39)
