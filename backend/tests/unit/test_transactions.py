"""Tests for GET /api/transactions endpoint.

Validates the API contract from api-contracts.md:
- Date range filter works
- Category filter works
- Merchant search partial match (case-insensitive)
- Sort by date/amount/merchant + asc/desc
- Pagination with cursor
- totalCount correct
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
    path: str = "/api/transactions",
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


def _invoke_transactions(event: dict[str, Any]) -> dict[str, Any]:
    """Import and invoke the handler, returning the response dict."""
    from novascan.api.app import handler

    return handler(event, FakeLambdaContext())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def aws_env(monkeypatch):
    """Set up mocked AWS environment for transaction tests."""
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

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="novascan-receipts-test")

        yield table


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


class TestTransactionsResponseShape:
    """Verify the response matches the API contract structure."""

    def test_returns_200(self, aws_env):
        event = _build_apigw_event()
        response = _invoke_transactions(event)
        assert response["statusCode"] == 200

    def test_response_has_required_fields(self, aws_env):
        """All required fields from the API contract should be present."""
        event = _build_apigw_event()
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert "transactions" in body, "Response missing 'transactions' field"
        assert "nextCursor" in body, "Response missing 'nextCursor' field"
        assert "totalCount" in body, "Response missing 'totalCount' field"

    def test_empty_list(self, aws_env):
        """A user with no receipts should get an empty list."""
        event = _build_apigw_event()
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert body["transactions"] == []
        assert body["nextCursor"] is None
        assert body["totalCount"] == 0

    def test_transaction_item_shape(self, aws_env):
        """Each transaction item should have the expected fields per api-contracts."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001",
                      merchant="Whole Foods", total=30.39, category="groceries-food",
                      subcategory="supermarket-grocery")

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 1
        txn = body["transactions"][0]

        required_fields = [
            "receiptId", "receiptDate", "merchant", "total",
            "category", "categoryDisplay", "status",
        ]
        for field in required_fields:
            assert field in txn, f"Transaction missing required field: {field}"

    def test_total_is_numeric(self, aws_env):
        """Total should be a number (float), not a string."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", total=30.39)

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        total = body["transactions"][0]["total"]
        assert isinstance(total, (int, float)), f"total should be numeric, got {type(total)}: {total}"
        assert total == pytest.approx(30.39)


# ---------------------------------------------------------------------------
# Date range filter
# ---------------------------------------------------------------------------


class TestTransactionsDateFilter:
    """Date range filtering behavior."""

    def test_filter_by_date_range(self, aws_env):
        """startDate and endDate should filter to transactions within the range."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", receipt_date="2026-03-10")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002", receipt_date="2026-03-20")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003", receipt_date="2026-03-30")

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"startDate": "2026-03-15", "endDate": "2026-03-25"},
        )
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 1
        assert body["transactions"][0]["receiptDate"] == "2026-03-20"

    def test_filter_by_start_date_only(self, aws_env):
        """startDate alone should return transactions on or after that date."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", receipt_date="2026-03-10")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002", receipt_date="2026-03-20")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003", receipt_date="2026-03-30")

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"startDate": "2026-03-20"},
        )
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        dates = [t["receiptDate"] for t in body["transactions"]]
        assert all(d >= "2026-03-20" for d in dates), f"All dates should be >= 2026-03-20, got: {dates}"
        assert len(body["transactions"]) == 2

    def test_filter_by_end_date_only(self, aws_env):
        """endDate alone should return transactions on or before that date."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", receipt_date="2026-03-10")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002", receipt_date="2026-03-20")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003", receipt_date="2026-03-30")

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"endDate": "2026-03-20"},
        )
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        dates = [t["receiptDate"] for t in body["transactions"]]
        assert all(d <= "2026-03-20" for d in dates), f"All dates should be <= 2026-03-20, got: {dates}"

    def test_inclusive_date_range(self, aws_env):
        """Transactions on both the start and end dates should be included."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", receipt_date="2026-03-15")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002", receipt_date="2026-03-20")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003", receipt_date="2026-03-25")

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"startDate": "2026-03-15", "endDate": "2026-03-25"},
        )
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 3, (
            f"All 3 transactions should be in range (inclusive), got {len(body['transactions'])}"
        )


# ---------------------------------------------------------------------------
# Category filter
# ---------------------------------------------------------------------------


class TestTransactionsCategoryFilter:
    """Category filter behavior."""

    def test_filter_by_category(self, aws_env):
        """category filter should return only matching transactions."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", category="groceries-food")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002", category="dining-restaurants")

        event = _build_apigw_event(user_id=user_id, query_params={"category": "groceries-food"})
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 1
        assert body["transactions"][0]["category"] == "groceries-food"

    def test_category_filter_no_match(self, aws_env):
        """Category filter with no matching transactions should return empty."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", category="groceries-food")

        event = _build_apigw_event(user_id=user_id, query_params={"category": "transportation"})
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 0


# ---------------------------------------------------------------------------
# Status filter
# ---------------------------------------------------------------------------


class TestTransactionsStatusFilter:
    """Status filter behavior."""

    def test_filter_by_status(self, aws_env):
        """status filter should return only matching transactions."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", status="confirmed")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002", status="processing",
                      merchant=None, total=None, category=None, subcategory=None)
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003", status="failed")

        event = _build_apigw_event(user_id=user_id, query_params={"status": "confirmed"})
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert all(t["status"] == "confirmed" for t in body["transactions"])
        assert len(body["transactions"]) == 1

    def test_filter_by_status_processing(self, aws_env):
        """status=processing should return only processing transactions."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", status="confirmed")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002", status="processing",
                      merchant=None, total=None, category=None, subcategory=None)

        event = _build_apigw_event(user_id=user_id, query_params={"status": "processing"})
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 1
        assert body["transactions"][0]["status"] == "processing"


# ---------------------------------------------------------------------------
# Merchant search
# ---------------------------------------------------------------------------


class TestTransactionsMerchantSearch:
    """Merchant search: partial, case-insensitive match."""

    def test_partial_merchant_match(self, aws_env):
        """merchant search should match partial names."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", merchant="Whole Foods Market")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002", merchant="Target")

        event = _build_apigw_event(user_id=user_id, query_params={"merchant": "whole"})
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 1
        assert body["transactions"][0]["merchant"] == "Whole Foods Market"

    def test_case_insensitive_merchant_search(self, aws_env):
        """Merchant search should be case-insensitive."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", merchant="Whole Foods Market")

        event = _build_apigw_event(user_id=user_id, query_params={"merchant": "WHOLE FOODS"})
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 1
        assert body["transactions"][0]["merchant"] == "Whole Foods Market"

    def test_merchant_search_no_match(self, aws_env):
        """Merchant search with no matching name should return empty."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", merchant="Whole Foods Market")

        event = _build_apigw_event(user_id=user_id, query_params={"merchant": "costco"})
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 0

    def test_merchant_search_substring(self, aws_env):
        """Merchant search should match substrings within the name."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", merchant="Whole Foods Market")

        event = _build_apigw_event(user_id=user_id, query_params={"merchant": "foods"})
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 1


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


class TestTransactionsSorting:
    """Sort by date/amount/merchant + asc/desc."""

    def test_default_sort_by_date_desc(self, aws_env):
        """Default sort should be by date descending."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", receipt_date="2026-03-10", merchant="A")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003", receipt_date="2026-03-30", merchant="C")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002", receipt_date="2026-03-20", merchant="B")

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        dates = [t["receiptDate"] for t in body["transactions"]]
        assert dates == sorted(dates, reverse=True), (
            f"Default sort should be date desc, got: {dates}"
        )

    def test_sort_by_date_asc(self, aws_env):
        """sortBy=date, sortOrder=asc should return oldest first."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", receipt_date="2026-03-10")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003", receipt_date="2026-03-30")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002", receipt_date="2026-03-20")

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"sortBy": "date", "sortOrder": "asc"},
        )
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        dates = [t["receiptDate"] for t in body["transactions"]]
        assert dates == sorted(dates), f"Expected date ascending, got: {dates}"

    def test_sort_by_amount_desc(self, aws_env):
        """sortBy=amount, sortOrder=desc should return highest amount first."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001",
                      receipt_date="2026-03-10", total=10.00)
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002",
                      receipt_date="2026-03-20", total=100.00)
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003",
                      receipt_date="2026-03-30", total=50.00)

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"sortBy": "amount", "sortOrder": "desc"},
        )
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        amounts = [t["total"] for t in body["transactions"]]
        assert amounts == sorted(amounts, reverse=True), (
            f"Expected amount descending, got: {amounts}"
        )

    def test_sort_by_amount_asc(self, aws_env):
        """sortBy=amount, sortOrder=asc should return lowest amount first."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001",
                      receipt_date="2026-03-10", total=10.00)
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002",
                      receipt_date="2026-03-20", total=100.00)
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003",
                      receipt_date="2026-03-30", total=50.00)

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"sortBy": "amount", "sortOrder": "asc"},
        )
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        amounts = [t["total"] for t in body["transactions"]]
        assert amounts == sorted(amounts), f"Expected amount ascending, got: {amounts}"

    def test_sort_by_merchant_desc(self, aws_env):
        """sortBy=merchant, sortOrder=desc should sort alphabetically descending."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001",
                      receipt_date="2026-03-10", merchant="Apple Store")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002",
                      receipt_date="2026-03-20", merchant="Whole Foods")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003",
                      receipt_date="2026-03-30", merchant="Costco")

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"sortBy": "merchant", "sortOrder": "desc"},
        )
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        merchants = [t["merchant"] for t in body["transactions"]]
        assert merchants == sorted(merchants, reverse=True), (
            f"Expected merchant descending, got: {merchants}"
        )

    def test_sort_by_merchant_asc(self, aws_env):
        """sortBy=merchant, sortOrder=asc should sort alphabetically ascending."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001",
                      receipt_date="2026-03-10", merchant="Whole Foods")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002",
                      receipt_date="2026-03-20", merchant="Apple Store")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003",
                      receipt_date="2026-03-30", merchant="Costco")

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"sortBy": "merchant", "sortOrder": "asc"},
        )
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        merchants = [t["merchant"] for t in body["transactions"]]
        assert merchants == sorted(merchants), f"Expected merchant ascending, got: {merchants}"


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestTransactionsPagination:
    """Cursor-based pagination behavior."""

    def test_default_limit(self, aws_env):
        """Default limit is 50 per spec."""
        table = aws_env
        user_id = "user-abc-123"

        for i in range(5):
            rid = f"01TXTEST0000000000000000000{i+1}"
            _seed_receipt(table, user_id, rid, receipt_date=f"2026-03-{20+i:02d}")

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 5

    def test_custom_limit(self, aws_env):
        """limit parameter restricts the number of results."""
        table = aws_env
        user_id = "user-abc-123"

        for i in range(5):
            rid = f"01TXTEST0000000000000000000{i+1}"
            _seed_receipt(table, user_id, rid, receipt_date=f"2026-03-{20+i:02d}")

        event = _build_apigw_event(user_id=user_id, query_params={"limit": "2"})
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) <= 2

    def test_cursor_returns_next_page(self, aws_env):
        """Using the nextCursor from a response should return the next page."""
        table = aws_env
        user_id = "user-abc-123"

        for i in range(5):
            rid = f"01TXTEST0000000000000000000{i+1}"
            _seed_receipt(table, user_id, rid, receipt_date=f"2026-03-{20+i:02d}")

        # First page
        event1 = _build_apigw_event(user_id=user_id, query_params={"limit": "2"})
        response1 = _invoke_transactions(event1)
        body1 = json.loads(response1["body"])

        assert body1["nextCursor"] is not None, "Should have nextCursor when there are more results"

        # Second page
        event2 = _build_apigw_event(
            user_id=user_id,
            query_params={"limit": "2", "cursor": body1["nextCursor"]},
        )
        response2 = _invoke_transactions(event2)
        body2 = json.loads(response2["body"])

        # Pages should have different transactions
        page1_ids = {t["receiptId"] for t in body1["transactions"]}
        page2_ids = {t["receiptId"] for t in body2["transactions"]}
        assert page1_ids.isdisjoint(page2_ids), "Pages should not overlap"

    def test_no_cursor_when_all_results_returned(self, aws_env):
        """nextCursor should be null when there are no more results."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001")

        event = _build_apigw_event(user_id=user_id, query_params={"limit": "100"})
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert body["nextCursor"] is None

    def test_limit_clamped_to_1(self, aws_env):
        """limit=0 should be clamped to at least 1."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001")

        event = _build_apigw_event(user_id=user_id, query_params={"limit": "0"})
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert response["statusCode"] == 200
        assert len(body["transactions"]) == 1

    def test_limit_clamped_to_100(self, aws_env):
        """limit > 100 should be clamped to 100 per spec."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001")

        event = _build_apigw_event(user_id=user_id, query_params={"limit": "999"})
        response = _invoke_transactions(event)

        assert response["statusCode"] == 200


# ---------------------------------------------------------------------------
# totalCount
# ---------------------------------------------------------------------------


class TestTransactionsTotalCount:
    """Verify totalCount field."""

    def test_total_count_matches_all_results(self, aws_env):
        """totalCount should reflect the total number of matching transactions."""
        table = aws_env
        user_id = "user-abc-123"
        for i in range(5):
            _seed_receipt(table, user_id, f"01TXTEST0000000000000000000{i+1}",
                          receipt_date=f"2026-03-{20+i:02d}")

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert body["totalCount"] == 5

    def test_total_count_with_filters(self, aws_env):
        """totalCount should reflect filtered results, not total receipts."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001",
                      status="confirmed", category="groceries-food")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002",
                      status="confirmed", category="dining-restaurants")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003",
                      status="processing", category=None, merchant=None,
                      total=None, subcategory=None)

        event = _build_apigw_event(user_id=user_id, query_params={"category": "groceries-food"})
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert body["totalCount"] == 1

    def test_total_count_zero_when_no_match(self, aws_env):
        """totalCount should be 0 when no transactions match."""
        event = _build_apigw_event()
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert body["totalCount"] == 0

    def test_total_count_with_pagination(self, aws_env):
        """totalCount should be the total across all pages, not just the current page."""
        table = aws_env
        user_id = "user-abc-123"
        for i in range(5):
            _seed_receipt(table, user_id, f"01TXTEST0000000000000000000{i+1}",
                          receipt_date=f"2026-03-{20+i:02d}")

        event = _build_apigw_event(user_id=user_id, query_params={"limit": "2"})
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) <= 2
        assert body["totalCount"] == 5, (
            f"totalCount should be 5 (all matching), got {body['totalCount']}"
        )


# ---------------------------------------------------------------------------
# Combined filters
# ---------------------------------------------------------------------------


class TestTransactionsCombinedFilters:
    """Multiple filters applied together (AND)."""

    def test_date_and_category_filter(self, aws_env):
        """Date range + category filter should both be applied."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001",
                      receipt_date="2026-03-10", category="groceries-food")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002",
                      receipt_date="2026-03-20", category="groceries-food")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003",
                      receipt_date="2026-03-20", category="dining-restaurants")

        event = _build_apigw_event(
            user_id=user_id,
            query_params={
                "startDate": "2026-03-15",
                "endDate": "2026-03-25",
                "category": "groceries-food",
            },
        )
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 1
        assert body["transactions"][0]["category"] == "groceries-food"
        assert body["transactions"][0]["receiptDate"] == "2026-03-20"

    def test_status_and_merchant_filter(self, aws_env):
        """Status + merchant search should both be applied."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001",
                      status="confirmed", merchant="Whole Foods Market")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000002",
                      status="confirmed", merchant="Target")
        _seed_receipt(table, user_id, "01TXTEST00000000000000000003",
                      status="processing", merchant="Whole Foods Market",
                      total=None, category=None, subcategory=None)

        event = _build_apigw_event(
            user_id=user_id,
            query_params={"status": "confirmed", "merchant": "whole"},
        )
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 1
        assert body["transactions"][0]["merchant"] == "Whole Foods Market"
        assert body["transactions"][0]["status"] == "confirmed"


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------


class TestTransactionsUserIsolation:
    """A user should only see their own transactions."""

    def test_does_not_return_other_users_transactions(self, aws_env):
        """User A should not see User B's transactions."""
        table = aws_env
        _seed_receipt(table, "user-A", "01TXTEST00000000000000000001", merchant="User A Store")
        _seed_receipt(table, "user-B", "01TXTEST00000000000000000002", merchant="User B Store")

        event = _build_apigw_event(user_id="user-A")
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert len(body["transactions"]) == 1
        assert body["transactions"][0]["merchant"] == "User A Store"

    def test_empty_for_new_user(self, aws_env):
        """A user with no data should get an empty transaction list."""
        table = aws_env
        _seed_receipt(table, "user-other", "01TXTEST00000000000000000001")

        event = _build_apigw_event(user_id="user-empty")
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        assert body["transactions"] == []
        assert body["totalCount"] == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestTransactionsEdgeCases:
    """Edge cases and boundary conditions."""

    def test_non_numeric_limit_uses_default(self, aws_env):
        """A non-numeric limit value should fall back to the default."""
        event = _build_apigw_event(query_params={"limit": "abc"})
        response = _invoke_transactions(event)

        assert response["statusCode"] == 200

    def test_invalid_cursor_returns_400(self, aws_env):
        """An invalid cursor should return 400."""
        event = _build_apigw_event(query_params={"cursor": "not-valid!!!"})
        response = _invoke_transactions(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert body["error"]["message"] == "Invalid pagination cursor"

    def test_cursor_targeting_other_user_returns_400(self, aws_env):
        """A cursor with GSI1PK for another user must be rejected."""
        import base64

        tampered_cursor = base64.urlsafe_b64encode(
            json.dumps({
                "GSI1PK": "USER#attacker-user",
                "GSI1SK": "2026-03-25#01TXTEST00000000000000000001",
                "PK": "USER#attacker-user",
                "SK": "RECEIPT#01TXTEST00000000000000000001",
            }).encode()
        ).decode()
        event = _build_apigw_event(query_params={"cursor": tampered_cursor})
        response = _invoke_transactions(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"]["message"] == "Invalid pagination cursor"

    def test_processing_receipt_null_fields(self, aws_env):
        """Processing receipts should have null merchant/total/category per spec."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001",
                      status="processing", merchant=None, total=None,
                      category=None, subcategory=None)

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        txn = body["transactions"][0]
        assert txn["status"] == "processing"
        assert txn["merchant"] is None
        assert txn["total"] is None
        assert txn["category"] is None

    def test_category_display_name_included(self, aws_env):
        """categoryDisplay should be present for confirmed transactions."""
        table = aws_env
        user_id = "user-abc-123"
        _seed_receipt(table, user_id, "01TXTEST00000000000000000001", category="groceries-food")

        event = _build_apigw_event(user_id=user_id)
        response = _invoke_transactions(event)
        body = json.loads(response["body"])

        txn = body["transactions"][0]
        assert "categoryDisplay" in txn
        assert txn["categoryDisplay"] is not None
        assert isinstance(txn["categoryDisplay"], str)
