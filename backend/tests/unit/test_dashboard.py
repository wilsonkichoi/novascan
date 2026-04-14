"""Tests for GET /api/dashboard/summary endpoint.

Validates the API contract from api-contracts.md:
- Monthly/weekly totals computed from confirmed receipts only
- Percentage change vs previous month/week
- Top categories sorted by total descending (up to 5)
- Receipt count breakdown (confirmed, processing, failed)
- Null change when no prior data
- month query param defaults to current month (YYYY-MM)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
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
    path: str = "/api/dashboard/summary",
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


def _invoke_dashboard(event: dict[str, Any]) -> dict[str, Any]:
    """Import and invoke the handler, returning the response dict."""
    from novascan.api.app import handler

    return handler(event, FakeLambdaContext())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def aws_env(monkeypatch):
    """Set up mocked AWS environment for dashboard tests."""
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


class TestDashboardResponseShape:
    """Verify the response matches the API contract structure."""

    def test_returns_200(self, aws_env):
        event = _build_apigw_event()
        response = _invoke_dashboard(event)
        assert response["statusCode"] == 200

    def test_response_has_required_fields(self, aws_env):
        """All required fields from the API contract should be present."""
        event = _build_apigw_event()
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        required_fields = [
            "month",
            "totalSpent",
            "previousMonthTotal",
            "monthlyChangePercent",
            "weeklySpent",
            "previousWeekTotal",
            "weeklyChangePercent",
            "receiptCount",
            "confirmedCount",
            "processingCount",
            "failedCount",
            "topCategories",
            "recentActivity",
        ]
        for field in required_fields:
            assert field in body, f"Response missing required field: {field}"

    def test_top_categories_shape(self, aws_env):
        """topCategories items should have the expected structure."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        dt = today.isoformat()
        _seed_receipt(table, user_id, "01DASHTEST0000000000000001", receipt_date=dt,
                      category="groceries-food", total=50.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": today.strftime("%Y-%m")})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert len(body["topCategories"]) >= 1
        cat = body["topCategories"][0]
        assert "category" in cat, "topCategories item missing 'category'"
        assert "categoryDisplay" in cat, "topCategories item missing 'categoryDisplay'"
        assert "total" in cat, "topCategories item missing 'total'"
        assert "percent" in cat, "topCategories item missing 'percent'"

    def test_recent_activity_shape(self, aws_env):
        """recentActivity items should have the expected structure."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        dt = today.isoformat()
        _seed_receipt(table, user_id, "01DASHTEST0000000000000001", receipt_date=dt,
                      merchant="Test Store", total=42.50, category="groceries-food")

        event = _build_apigw_event(user_id=user_id, query_params={"month": today.strftime("%Y-%m")})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert len(body["recentActivity"]) >= 1
        activity = body["recentActivity"][0]
        assert "receiptId" in activity, "recentActivity item missing 'receiptId'"
        assert "merchant" in activity, "recentActivity item missing 'merchant'"
        assert "total" in activity, "recentActivity item missing 'total'"
        assert "category" in activity, "recentActivity item missing 'category'"
        assert "receiptDate" in activity, "recentActivity item missing 'receiptDate'"
        assert "status" in activity, "recentActivity item missing 'status'"


# ---------------------------------------------------------------------------
# Monthly totals
# ---------------------------------------------------------------------------


class TestDashboardMonthlyTotals:
    """Verify monthly spending aggregation."""

    def test_monthly_total_sums_confirmed_receipts(self, aws_env):
        """totalSpent should sum totals of confirmed receipts in the target month."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        month_str = today.strftime("%Y-%m")
        # Use dates within the current month
        dt1 = today.replace(day=1).isoformat()
        dt2 = today.replace(day=min(2, 28)).isoformat()

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date=dt1, status="confirmed", total=100.50)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000002",
                      receipt_date=dt2, status="confirmed", total=200.25)

        event = _build_apigw_event(user_id=user_id, query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["totalSpent"] == pytest.approx(300.75), (
            f"Expected totalSpent=300.75, got {body['totalSpent']}"
        )

    def test_only_confirmed_receipts_in_totals(self, aws_env):
        """Processing and failed receipts should NOT be included in totalSpent."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        month_str = today.strftime("%Y-%m")
        dt = today.replace(day=1).isoformat()

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date=dt, status="confirmed", total=50.00)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000002",
                      receipt_date=dt, status="processing", total=100.00,
                      merchant=None, category=None, subcategory=None)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000003",
                      receipt_date=dt, status="failed", total=75.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["totalSpent"] == pytest.approx(50.00), (
            f"Only confirmed receipts should count. Expected 50.00, got {body['totalSpent']}"
        )

    def test_zero_total_when_no_confirmed_receipts(self, aws_env):
        """totalSpent should be 0 when there are no confirmed receipts in the month."""
        user_id = "user-abc-123"
        today = date.today()
        month_str = today.strftime("%Y-%m")

        event = _build_apigw_event(user_id=user_id, query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["totalSpent"] == 0 or body["totalSpent"] == pytest.approx(0.0), (
            f"Expected totalSpent=0, got {body['totalSpent']}"
        )

    def test_month_query_param_selects_target_month(self, aws_env):
        """The month query param should select the target month, not the current month."""
        table = aws_env
        user_id = "user-abc-123"

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date="2026-01-15", status="confirmed", total=100.00)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000002",
                      receipt_date="2026-02-15", status="confirmed", total=200.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": "2026-01"})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["month"] == "2026-01"
        assert body["totalSpent"] == pytest.approx(100.00), (
            f"Expected totalSpent=100.00 for Jan, got {body['totalSpent']}"
        )

    def test_default_month_is_current(self, aws_env):
        """Without month param, should default to the current month."""
        today = date.today()
        expected_month = today.strftime("%Y-%m")

        event = _build_apigw_event()
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["month"] == expected_month, (
            f"Expected default month={expected_month}, got {body['month']}"
        )


# ---------------------------------------------------------------------------
# Monthly change percent
# ---------------------------------------------------------------------------


class TestDashboardMonthlyChange:
    """Verify percentage change vs previous month."""

    def test_positive_change(self, aws_env):
        """Spending increase should show positive monthlyChangePercent."""
        table = aws_env
        user_id = "user-abc-123"

        # Previous month
        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date="2026-01-15", status="confirmed", total=100.00)
        # Target month (increased)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000002",
                      receipt_date="2026-02-15", status="confirmed", total=150.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": "2026-02"})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["monthlyChangePercent"] is not None
        assert body["monthlyChangePercent"] > 0, (
            f"Spending increase should be positive, got {body['monthlyChangePercent']}"
        )
        # 50% increase (100 -> 150)
        assert body["monthlyChangePercent"] == pytest.approx(50.0), (
            f"Expected 50% change, got {body['monthlyChangePercent']}"
        )

    def test_negative_change(self, aws_env):
        """Spending decrease should show negative monthlyChangePercent."""
        table = aws_env
        user_id = "user-abc-123"

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date="2026-01-15", status="confirmed", total=200.00)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000002",
                      receipt_date="2026-02-15", status="confirmed", total=100.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": "2026-02"})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["monthlyChangePercent"] is not None
        assert body["monthlyChangePercent"] < 0, (
            f"Spending decrease should be negative, got {body['monthlyChangePercent']}"
        )
        # -50% decrease (200 -> 100)
        assert body["monthlyChangePercent"] == pytest.approx(-50.0), (
            f"Expected -50% change, got {body['monthlyChangePercent']}"
        )

    def test_null_change_when_no_prior_data(self, aws_env):
        """monthlyChangePercent should be null when there is no previous month data."""
        table = aws_env
        user_id = "user-abc-123"

        # Only data in target month, nothing in previous month
        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date="2026-03-15", status="confirmed", total=100.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": "2026-03"})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["monthlyChangePercent"] is None, (
            f"Expected null change with no prior data, got {body['monthlyChangePercent']}"
        )

    def test_previous_month_total_returned(self, aws_env):
        """previousMonthTotal should reflect the previous month's confirmed total."""
        table = aws_env
        user_id = "user-abc-123"

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date="2026-01-15", status="confirmed", total=250.00)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000002",
                      receipt_date="2026-02-15", status="confirmed", total=100.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": "2026-02"})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["previousMonthTotal"] == pytest.approx(250.00), (
            f"Expected previousMonthTotal=250.00, got {body['previousMonthTotal']}"
        )


# ---------------------------------------------------------------------------
# Weekly totals
# ---------------------------------------------------------------------------


class TestDashboardWeeklyTotals:
    """Verify weekly spending aggregation.

    Per spec: weekly is current calendar week (Monday-Sunday) regardless of month param.
    """

    def test_weekly_total_sums_current_week(self, aws_env):
        """weeklySpent should sum confirmed receipts in the current calendar week."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        # Get the Monday of this week
        monday = today - timedelta(days=today.weekday())
        dt = monday.isoformat()

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date=dt, status="confirmed", total=75.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": today.strftime("%Y-%m")})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["weeklySpent"] >= 75.00, (
            f"Expected weeklySpent to include 75.00, got {body['weeklySpent']}"
        )

    def test_null_weekly_change_when_no_prior_week(self, aws_env):
        """weeklyChangePercent should be null when there is no previous week data."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        dt = monday.isoformat()

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date=dt, status="confirmed", total=75.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": today.strftime("%Y-%m")})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        # If no previous week data, should be null
        if body["previousWeekTotal"] == 0 or body["previousWeekTotal"] is None:
            assert body["weeklyChangePercent"] is None, (
                f"Expected null weeklyChangePercent with no prior week, got {body['weeklyChangePercent']}"
            )

    def test_weekly_change_positive(self, aws_env):
        """Spending increase from previous week should be positive."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        # Current week Monday
        current_monday = today - timedelta(days=today.weekday())
        # Previous week Monday
        prev_monday = current_monday - timedelta(days=7)

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date=prev_monday.isoformat(), status="confirmed", total=50.00)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000002",
                      receipt_date=current_monday.isoformat(), status="confirmed", total=100.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": today.strftime("%Y-%m")})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        if body["weeklyChangePercent"] is not None:
            assert body["weeklyChangePercent"] > 0, (
                f"Expected positive weekly change, got {body['weeklyChangePercent']}"
            )


# ---------------------------------------------------------------------------
# Receipt count breakdown
# ---------------------------------------------------------------------------


class TestDashboardReceiptCounts:
    """Verify receipt count breakdown by status."""

    def test_receipt_count_is_total(self, aws_env):
        """receiptCount should be the total of all receipts in the month, all statuses."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        month_str = today.strftime("%Y-%m")
        dt = today.replace(day=1).isoformat()

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date=dt, status="confirmed", total=50.00)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000002",
                      receipt_date=dt, status="processing", total=None,
                      merchant=None, category=None, subcategory=None)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000003",
                      receipt_date=dt, status="failed", total=None)

        event = _build_apigw_event(user_id=user_id, query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["receiptCount"] == 3, (
            f"Expected receiptCount=3, got {body['receiptCount']}"
        )
        assert body["confirmedCount"] == 1, (
            f"Expected confirmedCount=1, got {body['confirmedCount']}"
        )
        assert body["processingCount"] == 1, (
            f"Expected processingCount=1, got {body['processingCount']}"
        )
        assert body["failedCount"] == 1, (
            f"Expected failedCount=1, got {body['failedCount']}"
        )

    def test_zero_counts_when_empty(self, aws_env):
        """All counts should be 0 when user has no receipts."""
        today = date.today()
        month_str = today.strftime("%Y-%m")

        event = _build_apigw_event(query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["receiptCount"] == 0
        assert body["confirmedCount"] == 0
        assert body["processingCount"] == 0
        assert body["failedCount"] == 0


# ---------------------------------------------------------------------------
# Top categories
# ---------------------------------------------------------------------------


class TestDashboardTopCategories:
    """Verify top categories aggregation."""

    def test_top_categories_sorted_by_total_descending(self, aws_env):
        """topCategories should be sorted by total in descending order."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        month_str = today.strftime("%Y-%m")
        dt = today.replace(day=1).isoformat()

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date=dt, category="groceries-food", total=100.00)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000002",
                      receipt_date=dt, category="dining-restaurants", total=300.00)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000003",
                      receipt_date=dt, category="transportation", total=50.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        cats = body["topCategories"]
        totals = [c["total"] for c in cats]
        assert totals == sorted(totals, reverse=True), (
            f"topCategories should be sorted by total descending: {totals}"
        )

    def test_top_categories_limited_to_5(self, aws_env):
        """topCategories should return at most 5 categories."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        month_str = today.strftime("%Y-%m")
        dt = today.replace(day=1).isoformat()

        categories = [
            "groceries-food", "dining-restaurants", "transportation",
            "housing-utilities", "health-medical", "shopping-retail",
            "entertainment-recreation",
        ]
        for i, cat in enumerate(categories):
            _seed_receipt(table, user_id, f"01DASHTEST000000000000000{i+1}",
                          receipt_date=dt, category=cat, total=float((i + 1) * 10))

        event = _build_apigw_event(user_id=user_id, query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert len(body["topCategories"]) <= 5, (
            f"Expected at most 5 topCategories, got {len(body['topCategories'])}"
        )

    def test_top_categories_percent_adds_up(self, aws_env):
        """Percent values in topCategories should be reasonable fractions of totalSpent."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        month_str = today.strftime("%Y-%m")
        dt = today.replace(day=1).isoformat()

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date=dt, category="groceries-food", total=60.00)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000002",
                      receipt_date=dt, category="dining-restaurants", total=40.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        cats = body["topCategories"]
        assert len(cats) == 2

        # Total is 100, so groceries = 60%, dining = 40%
        groceries = next(c for c in cats if c["category"] == "groceries-food")
        dining = next(c for c in cats if c["category"] == "dining-restaurants")
        assert groceries["percent"] == pytest.approx(60.0), (
            f"Expected groceries 60%, got {groceries['percent']}"
        )
        assert dining["percent"] == pytest.approx(40.0), (
            f"Expected dining 40%, got {dining['percent']}"
        )

    def test_no_top_categories_when_no_confirmed_receipts(self, aws_env):
        """topCategories should be empty when there are no confirmed receipts."""
        today = date.today()
        month_str = today.strftime("%Y-%m")

        event = _build_apigw_event(query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["topCategories"] == [], (
            f"Expected empty topCategories, got {body['topCategories']}"
        )

    def test_categories_aggregate_multiple_receipts(self, aws_env):
        """Multiple receipts in the same category should be summed."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        month_str = today.strftime("%Y-%m")
        dt = today.replace(day=1).isoformat()

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date=dt, category="groceries-food", total=50.00)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000002",
                      receipt_date=dt, category="groceries-food", total=30.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        cats = body["topCategories"]
        assert len(cats) == 1
        assert cats[0]["category"] == "groceries-food"
        assert cats[0]["total"] == pytest.approx(80.00), (
            f"Expected aggregated total 80.00, got {cats[0]['total']}"
        )


# ---------------------------------------------------------------------------
# Recent activity
# ---------------------------------------------------------------------------


class TestDashboardRecentActivity:
    """Verify recent activity list."""

    def test_recent_activity_limited_to_5(self, aws_env):
        """recentActivity should return at most 5 receipts."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        month_str = today.strftime("%Y-%m")

        for i in range(7):
            dt = today.replace(day=min(i + 1, 28)).isoformat()
            _seed_receipt(table, user_id, f"01DASHTEST000000000000000{i+1}",
                          receipt_date=dt, total=float(10 * (i + 1)))

        event = _build_apigw_event(user_id=user_id, query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert len(body["recentActivity"]) <= 5, (
            f"Expected at most 5 recentActivity, got {len(body['recentActivity'])}"
        )

    def test_empty_recent_activity_when_no_receipts(self, aws_env):
        """recentActivity should be empty when user has no receipts."""
        today = date.today()
        month_str = today.strftime("%Y-%m")

        event = _build_apigw_event(query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["recentActivity"] == []


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------


class TestDashboardUserIsolation:
    """Verify that dashboard data is scoped to the authenticated user."""

    def test_does_not_include_other_users_data(self, aws_env):
        """User A's dashboard should not include User B's receipts."""
        table = aws_env
        today = date.today()
        month_str = today.strftime("%Y-%m")
        dt = today.replace(day=1).isoformat()

        _seed_receipt(table, "user-A", "01DASHTEST0000000000000001",
                      receipt_date=dt, total=100.00)
        _seed_receipt(table, "user-B", "01DASHTEST0000000000000002",
                      receipt_date=dt, total=500.00)

        event = _build_apigw_event(user_id="user-A", query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["totalSpent"] == pytest.approx(100.00), (
            f"User A should only see their own total 100.00, got {body['totalSpent']}"
        )
        assert body["receiptCount"] == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestDashboardEdgeCases:
    """Edge cases and boundary conditions."""

    def test_receipts_outside_target_month_excluded(self, aws_env):
        """Receipts from a different month should not be in totalSpent."""
        table = aws_env
        user_id = "user-abc-123"

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date="2026-01-15", status="confirmed", total=100.00)
        _seed_receipt(table, user_id, "01DASHTEST0000000000000002",
                      receipt_date="2026-02-15", status="confirmed", total=200.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": "2026-01"})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert body["totalSpent"] == pytest.approx(100.00), (
            f"Only Jan receipts should count. Expected 100.00, got {body['totalSpent']}"
        )

    def test_total_is_numeric(self, aws_env):
        """totalSpent should be numeric, not a string."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        month_str = today.strftime("%Y-%m")
        dt = today.replace(day=1).isoformat()

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date=dt, total=42.50)

        event = _build_apigw_event(user_id=user_id, query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        assert isinstance(body["totalSpent"], (int, float)), (
            f"totalSpent should be numeric, got {type(body['totalSpent'])}"
        )

    def test_category_display_name_included(self, aws_env):
        """topCategories should include categoryDisplay field per api-contracts."""
        table = aws_env
        user_id = "user-abc-123"
        today = date.today()
        month_str = today.strftime("%Y-%m")
        dt = today.replace(day=1).isoformat()

        _seed_receipt(table, user_id, "01DASHTEST0000000000000001",
                      receipt_date=dt, category="groceries-food", total=50.00)

        event = _build_apigw_event(user_id=user_id, query_params={"month": month_str})
        response = _invoke_dashboard(event)
        body = json.loads(response["body"])

        cat = body["topCategories"][0]
        assert cat["categoryDisplay"] is not None
        assert isinstance(cat["categoryDisplay"], str)
        assert len(cat["categoryDisplay"]) > 0
