"""Tests for receipt CRUD API endpoints.

Validates API contracts from api-contracts.md:
- GET /api/receipts/{id} returns receipt with line items
- PUT /api/receipts/{id} updates only provided fields
- DELETE /api/receipts/{id} removes DDB records + S3 image
- PUT /api/receipts/{id}/items replaces all line items
- 404 for non-existent receipt
- 403 for wrong user (data isolation)
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
    from api.app import handler

    return handler(event, FakeLambdaContext())


def _seed_receipt(
    table: Any,
    user_id: str = "user-abc-123",
    receipt_id: str = "01JQTEST000000000000000001",
    *,
    status: str = "confirmed",
    merchant: str = "Test Merchant",
    total: float = 42.50,
    category: str = "groceries-food",
    subcategory: str = "supermarket-grocery",
    receipt_date: str = "2026-03-25",
    image_key: str | None = None,
) -> dict[str, Any]:
    """Insert a receipt record into DynamoDB. Returns the item dict."""
    now = datetime.now(UTC).isoformat()
    if image_key is None:
        image_key = f"receipts/{receipt_id}.jpg"
    item = {
        "PK": f"USER#{user_id}",
        "SK": f"RECEIPT#{receipt_id}",
        "entityType": "RECEIPT",
        "receiptId": receipt_id,
        "receiptDate": receipt_date,
        "merchant": merchant,
        "total": Decimal(str(total)),
        "category": category,
        "categoryDisplay": "Groceries & Food",
        "subcategory": subcategory,
        "subcategoryDisplay": "Supermarket / Grocery",
        "status": status,
        "imageKey": image_key,
        "createdAt": now,
        "updatedAt": now,
        "GSI1PK": f"USER#{user_id}",
        "GSI1SK": f"{receipt_date}#{receipt_id}",
    }
    table.put_item(Item=item)
    return item


def _seed_line_item(
    table: Any,
    user_id: str = "user-abc-123",
    receipt_id: str = "01JQTEST000000000000000001",
    sort_order: int = 1,
    *,
    name: str = "Organic Milk",
    quantity: float = 1,
    unit_price: float = 5.99,
    total_price: float = 5.99,
    subcategory: str | None = "dairy-cheese-eggs",
) -> dict[str, Any]:
    """Insert a line item record. Returns the item dict."""
    padded = str(sort_order).zfill(3)
    item: dict[str, Any] = {
        "PK": f"USER#{user_id}",
        "SK": f"RECEIPT#{receipt_id}#ITEM#{padded}",
        "entityType": "ITEM",
        "sortOrder": sort_order,
        "name": name,
        "quantity": Decimal(str(quantity)),
        "unitPrice": Decimal(str(unit_price)),
        "totalPrice": Decimal(str(total_price)),
    }
    if subcategory:
        item["subcategory"] = subcategory
        item["subcategoryDisplay"] = "Dairy, Cheese & Eggs"
    table.put_item(Item=item)
    return item


def _seed_pipeline_result(
    table: Any,
    user_id: str = "user-abc-123",
    receipt_id: str = "01JQTEST000000000000000001",
    pipeline_type: str = "ocr-ai",
) -> dict[str, Any]:
    """Insert a pipeline result record. Returns the item dict."""
    now = datetime.now(UTC).isoformat()
    item = {
        "PK": f"USER#{user_id}",
        "SK": f"RECEIPT#{receipt_id}#PIPELINE#{pipeline_type}",
        "entityType": "PIPELINE",
        "extractedData": {
            "merchant": {"name": "Test Merchant"},
            "total": Decimal("42.50"),
        },
        "confidence": Decimal("0.94"),
        "rankingScore": Decimal("0.91"),
        "processingTimeMs": 4523,
        "modelId": "amazon.nova-lite-v1:0",
        "createdAt": now,
    }
    table.put_item(Item=item)
    return item


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _aws_setup(monkeypatch):
    """Set up mocked AWS environment for receipt CRUD tests."""
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
# GET /api/receipts/{id} — Happy path
# ---------------------------------------------------------------------------


class TestGetReceiptDetail:
    """GET /api/receipts/{id} returns full receipt with line items."""

    def test_returns_200_for_existing_receipt(self, _aws_setup):
        """GET for an existing receipt returns 200."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 200, (
            f"Expected 200, got {response['statusCode']}: {response.get('body')}"
        )

    def test_response_contains_required_fields(self, _aws_setup):
        """Response must contain all fields from the API contract."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        required_fields = [
            "receiptId", "status", "lineItems", "createdAt",
        ]
        for field in required_fields:
            assert field in body, f"Response missing required field '{field}'"

    def test_response_includes_receipt_data(self, _aws_setup):
        """Response includes merchant, total, category, etc. from seeded data."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id, merchant="Whole Foods", total=30.39)

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert body["receiptId"] == receipt_id
        assert body["merchant"] == "Whole Foods"
        assert body["total"] == pytest.approx(30.39, abs=0.01)
        assert body["status"] == "confirmed"

    def test_response_includes_line_items(self, _aws_setup):
        """GET detail returns line items belonging to the receipt."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)
        _seed_line_item(table, receipt_id=receipt_id, sort_order=1, name="Milk")
        _seed_line_item(table, receipt_id=receipt_id, sort_order=2, name="Bread")

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert isinstance(body["lineItems"], list)
        assert len(body["lineItems"]) == 2, (
            f"Expected 2 line items, got {len(body['lineItems'])}"
        )

    def test_line_items_have_required_fields(self, _aws_setup):
        """Each line item must have sortOrder, name, quantity, unitPrice, totalPrice."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)
        _seed_line_item(table, receipt_id=receipt_id, sort_order=1, name="Item A")

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])
        item = body["lineItems"][0]

        for field in ["sortOrder", "name", "quantity", "unitPrice", "totalPrice"]:
            assert field in item, f"Line item missing required field '{field}'"

    def test_response_includes_image_url(self, _aws_setup):
        """Response should include a presigned imageUrl for the receipt image."""
        table, s3 = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        image_key = f"receipts/{receipt_id}.jpg"
        _seed_receipt(table, receipt_id=receipt_id, image_key=image_key)
        # Put an object so presigned URL generation can work
        s3.put_object(
            Bucket="novascan-receipts-test",
            Key=image_key,
            Body=b"fake-image-data",
        )

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert "imageUrl" in body, "Response should include imageUrl"
        assert body["imageUrl"] is not None, "imageUrl should not be null"

    def test_receipt_with_no_line_items(self, _aws_setup):
        """A receipt with no line items returns an empty lineItems array."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert body["lineItems"] == [], (
            f"Expected empty lineItems, got {body['lineItems']}"
        )


# ---------------------------------------------------------------------------
# GET /api/receipts/{id} — Error paths
# ---------------------------------------------------------------------------


class TestGetReceiptErrors:
    """GET /api/receipts/{id} error handling."""

    def test_404_for_nonexistent_receipt(self, _aws_setup):
        """GET for a non-existent receipt ID returns 404 NOT_FOUND."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST999999999999999999"

        event = _build_apigw_event(
            method="GET",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 404, (
            f"Expected 404 for non-existent receipt, got {response['statusCode']}"
        )
        body = json.loads(response["body"])
        assert body["error"]["code"] == "NOT_FOUND"

    def test_403_for_other_users_receipt(self, _aws_setup):
        """GET for another user's receipt returns 404 (user isolation via PK scoping).

        Per spec: all DynamoDB queries scoped to PK = USER#{authenticated userId}.
        Accessing another user's receipt returns 404 (not 403) because the
        query won't find it in the authenticated user's partition.
        """
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        # Receipt belongs to user-other
        _seed_receipt(table, user_id="user-other", receipt_id=receipt_id)

        # Authenticated as user-abc-123
        event = _build_apigw_event(
            user_id="user-abc-123",
            method="GET",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        # Because queries are scoped by PK=USER#{userId}, user-abc-123
        # simply won't find user-other's receipt. This should be 404.
        assert response["statusCode"] in (403, 404), (
            f"Expected 403 or 404 for another user's receipt, got {response['statusCode']}"
        )


# ---------------------------------------------------------------------------
# PUT /api/receipts/{id} — Partial update
# ---------------------------------------------------------------------------


class TestUpdateReceipt:
    """PUT /api/receipts/{id} updates only provided fields."""

    def test_returns_200_on_valid_update(self, _aws_setup):
        """PUT with valid fields returns 200."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)

        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
            body={"merchant": "Updated Merchant"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 200, (
            f"Expected 200, got {response['statusCode']}: {response.get('body')}"
        )

    def test_updates_only_provided_fields(self, _aws_setup):
        """Only fields in the request body are updated; others remain unchanged."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(
            table,
            receipt_id=receipt_id,
            merchant="Original Merchant",
            total=42.50,
            category="groceries-food",
        )

        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
            body={"merchant": "New Merchant"},
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert body["merchant"] == "New Merchant", "merchant should be updated"
        assert body["total"] == pytest.approx(42.50, abs=0.01), (
            "total should remain unchanged when not in request body"
        )

    def test_returns_full_receipt_object(self, _aws_setup):
        """PUT response has the same shape as GET /api/receipts/{id}."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)

        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
            body={"merchant": "Updated"},
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert "receiptId" in body
        assert "status" in body
        assert "createdAt" in body

    def test_can_update_category(self, _aws_setup):
        """PUT can update the category field."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id, category="groceries-food")

        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
            body={"category": "dining", "subcategory": "restaurant-dine-in"},
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert body["category"] == "dining"

    def test_can_update_multiple_fields(self, _aws_setup):
        """PUT can update multiple fields in one request."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)

        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
            body={
                "merchant": "Updated Merchant",
                "total": 99.99,
                "receiptDate": "2026-04-01",
            },
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert body["merchant"] == "Updated Merchant"
        assert body["total"] == pytest.approx(99.99, abs=0.01)
        assert body["receiptDate"] == "2026-04-01"


# ---------------------------------------------------------------------------
# PUT /api/receipts/{id} — Error paths
# ---------------------------------------------------------------------------


class TestUpdateReceiptErrors:
    """PUT /api/receipts/{id} error handling."""

    def test_404_for_nonexistent_receipt(self, _aws_setup):
        """PUT to a non-existent receipt returns 404."""
        table, _ = _aws_setup

        event = _build_apigw_event(
            method="PUT",
            path="/api/receipts/01JQTEST999999999999999999",
            path_params={"receipt_id": "01JQTEST999999999999999999"},
            body={"merchant": "Updated"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 404, (
            f"Expected 404, got {response['statusCode']}"
        )

    def test_403_for_other_users_receipt(self, _aws_setup):
        """PUT to another user's receipt should fail (user isolation)."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, user_id="user-other", receipt_id=receipt_id)

        event = _build_apigw_event(
            user_id="user-abc-123",
            method="PUT",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
            body={"merchant": "Hacked"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] in (403, 404), (
            f"Expected 403 or 404 for cross-user update, got {response['statusCode']}"
        )

    def test_400_for_invalid_subcategory_slug(self, _aws_setup):
        """PUT with a valid category but invalid subcategory returns 400.

        Per api-contracts.md: "400 VALIDATION_ERROR — invalid category or subcategory slug".
        The implementation allows unknown category slugs (since custom categories exist),
        but validates subcategories against the parent category's known subcategory list.
        """
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)

        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
            body={"category": "groceries-food", "subcategory": "nonexistent-subcategory"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 400, (
            f"Expected 400 for invalid subcategory, got {response['statusCode']}: {response.get('body')}"
        )


# ---------------------------------------------------------------------------
# DELETE /api/receipts/{id}
# ---------------------------------------------------------------------------


class TestDeleteReceipt:
    """DELETE /api/receipts/{id} hard deletes receipt, items, pipeline results, and S3 image."""

    def test_returns_204_on_success(self, _aws_setup):
        """DELETE for an existing receipt returns 204 No Content."""
        table, s3 = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        image_key = f"receipts/{receipt_id}.jpg"
        _seed_receipt(table, receipt_id=receipt_id, image_key=image_key)
        s3.put_object(Bucket="novascan-receipts-test", Key=image_key, Body=b"img")

        event = _build_apigw_event(
            method="DELETE",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 204, (
            f"Expected 204, got {response['statusCode']}"
        )

    def test_removes_receipt_from_dynamodb(self, _aws_setup):
        """After DELETE, the receipt record should not exist in DynamoDB."""
        table, s3 = _aws_setup
        user_id = "user-abc-123"
        receipt_id = "01JQTEST000000000000000001"
        image_key = f"receipts/{receipt_id}.jpg"
        _seed_receipt(table, user_id=user_id, receipt_id=receipt_id, image_key=image_key)
        s3.put_object(Bucket="novascan-receipts-test", Key=image_key, Body=b"img")

        event = _build_apigw_event(
            method="DELETE",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        _invoke_handler(event)

        result = table.get_item(
            Key={"PK": f"USER#{user_id}", "SK": f"RECEIPT#{receipt_id}"}
        )
        assert "Item" not in result, "Receipt record should be deleted from DynamoDB"

    def test_removes_line_items_from_dynamodb(self, _aws_setup):
        """After DELETE, line items for the receipt should also be removed."""
        table, s3 = _aws_setup
        user_id = "user-abc-123"
        receipt_id = "01JQTEST000000000000000001"
        image_key = f"receipts/{receipt_id}.jpg"
        _seed_receipt(table, user_id=user_id, receipt_id=receipt_id, image_key=image_key)
        _seed_line_item(table, user_id=user_id, receipt_id=receipt_id, sort_order=1)
        _seed_line_item(table, user_id=user_id, receipt_id=receipt_id, sort_order=2)
        s3.put_object(Bucket="novascan-receipts-test", Key=image_key, Body=b"img")

        event = _build_apigw_event(
            method="DELETE",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        _invoke_handler(event)

        # Check line items are gone
        from boto3.dynamodb.conditions import Key

        result = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
            & Key("SK").begins_with(f"RECEIPT#{receipt_id}#ITEM#"),
        )
        assert len(result["Items"]) == 0, (
            f"Expected 0 line items after delete, got {len(result['Items'])}"
        )

    def test_removes_s3_image(self, _aws_setup):
        """After DELETE, the S3 image should be removed."""
        table, s3 = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        image_key = f"receipts/{receipt_id}.jpg"
        _seed_receipt(table, receipt_id=receipt_id, image_key=image_key)
        s3.put_object(Bucket="novascan-receipts-test", Key=image_key, Body=b"img")

        event = _build_apigw_event(
            method="DELETE",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        _invoke_handler(event)

        # S3 head_object should fail with 404
        from botocore.exceptions import ClientError

        with pytest.raises(ClientError) as exc_info:
            s3.head_object(Bucket="novascan-receipts-test", Key=image_key)
        assert exc_info.value.response["Error"]["Code"] == "404", (
            "S3 image should be deleted after receipt deletion"
        )

    def test_removes_pipeline_results(self, _aws_setup):
        """After DELETE, pipeline result records should also be removed."""
        table, s3 = _aws_setup
        user_id = "user-abc-123"
        receipt_id = "01JQTEST000000000000000001"
        image_key = f"receipts/{receipt_id}.jpg"
        _seed_receipt(table, user_id=user_id, receipt_id=receipt_id, image_key=image_key)
        _seed_pipeline_result(table, user_id=user_id, receipt_id=receipt_id, pipeline_type="ocr-ai")
        _seed_pipeline_result(table, user_id=user_id, receipt_id=receipt_id, pipeline_type="ai-multimodal")
        s3.put_object(Bucket="novascan-receipts-test", Key=image_key, Body=b"img")

        event = _build_apigw_event(
            method="DELETE",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        _invoke_handler(event)

        from boto3.dynamodb.conditions import Key

        result = table.query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
            & Key("SK").begins_with(f"RECEIPT#{receipt_id}#PIPELINE#"),
        )
        assert len(result["Items"]) == 0, (
            f"Expected 0 pipeline results after delete, got {len(result['Items'])}"
        )


# ---------------------------------------------------------------------------
# DELETE /api/receipts/{id} — Error paths
# ---------------------------------------------------------------------------


class TestDeleteReceiptErrors:
    """DELETE /api/receipts/{id} error handling."""

    def test_404_for_nonexistent_receipt(self, _aws_setup):
        """DELETE for a non-existent receipt returns 404."""
        table, _ = _aws_setup

        event = _build_apigw_event(
            method="DELETE",
            path="/api/receipts/01JQTEST999999999999999999",
            path_params={"receipt_id": "01JQTEST999999999999999999"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 404, (
            f"Expected 404, got {response['statusCode']}"
        )

    def test_403_for_other_users_receipt(self, _aws_setup):
        """DELETE of another user's receipt should fail."""
        table, s3 = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        image_key = f"receipts/{receipt_id}.jpg"
        _seed_receipt(table, user_id="user-other", receipt_id=receipt_id, image_key=image_key)
        s3.put_object(Bucket="novascan-receipts-test", Key=image_key, Body=b"img")

        event = _build_apigw_event(
            user_id="user-abc-123",
            method="DELETE",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] in (403, 404), (
            f"Expected 403 or 404, got {response['statusCode']}"
        )


# ---------------------------------------------------------------------------
# PUT /api/receipts/{id}/items — Bulk replace line items
# ---------------------------------------------------------------------------


class TestPutLineItems:
    """PUT /api/receipts/{id}/items replaces all line items."""

    def test_returns_200_on_success(self, _aws_setup):
        """PUT items with valid data returns 200."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)

        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}/items",
            path_params={"receipt_id": receipt_id},
            body={
                "items": [
                    {
                        "sortOrder": 1,
                        "name": "Milk",
                        "quantity": 1,
                        "unitPrice": 5.99,
                        "totalPrice": 5.99,
                    }
                ]
            },
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 200, (
            f"Expected 200, got {response['statusCode']}: {response.get('body')}"
        )

    def test_replaces_all_existing_items(self, _aws_setup):
        """PUT items removes old items and inserts new ones.

        Uses different sort orders for old and new items to avoid a moto
        batch_writer limitation where delete+put on the same key causes
        the delete to win (not a real AWS issue).
        """
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        user_id = "user-abc-123"
        _seed_receipt(table, user_id=user_id, receipt_id=receipt_id)
        _seed_line_item(table, user_id=user_id, receipt_id=receipt_id, sort_order=1, name="Old Item 1")
        _seed_line_item(table, user_id=user_id, receipt_id=receipt_id, sort_order=2, name="Old Item 2")

        # New items use sort orders 3 and 4 to avoid colliding with old items'
        # DynamoDB keys in moto's batch_writer
        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}/items",
            path_params={"receipt_id": receipt_id},
            body={
                "items": [
                    {
                        "sortOrder": 3,
                        "name": "New Item A",
                        "quantity": 2,
                        "unitPrice": 3.50,
                        "totalPrice": 7.00,
                    }
                ]
            },
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        # Response should contain only the new item
        assert len(body["lineItems"]) == 1, (
            f"Expected 1 line item after replace, got {len(body['lineItems'])}"
        )
        assert body["lineItems"][0]["name"] == "New Item A"

    def test_empty_items_clears_all(self, _aws_setup):
        """PUT items with empty array removes all line items."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        user_id = "user-abc-123"
        _seed_receipt(table, user_id=user_id, receipt_id=receipt_id)
        _seed_line_item(table, user_id=user_id, receipt_id=receipt_id, sort_order=1)

        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}/items",
            path_params={"receipt_id": receipt_id},
            body={"items": []},
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert body["lineItems"] == [], (
            f"Expected empty lineItems after clearing, got {body['lineItems']}"
        )

    def test_returns_full_receipt_object(self, _aws_setup):
        """PUT items response is the full receipt object with updated line items."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)

        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}/items",
            path_params={"receipt_id": receipt_id},
            body={
                "items": [
                    {
                        "sortOrder": 1,
                        "name": "Test Item",
                        "quantity": 1,
                        "unitPrice": 10.00,
                        "totalPrice": 10.00,
                        "subcategory": "dairy-cheese-eggs",
                    }
                ]
            },
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert "receiptId" in body, "Response should contain receiptId"
        assert "lineItems" in body, "Response should contain lineItems"
        assert body["receiptId"] == receipt_id

    def test_items_with_subcategory(self, _aws_setup):
        """Line items can include optional subcategory."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)

        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}/items",
            path_params={"receipt_id": receipt_id},
            body={
                "items": [
                    {
                        "sortOrder": 1,
                        "name": "Organic Milk",
                        "quantity": 1,
                        "unitPrice": 5.99,
                        "totalPrice": 5.99,
                        "subcategory": "dairy-cheese-eggs",
                    }
                ]
            },
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert response["statusCode"] == 200
        item = body["lineItems"][0]
        assert item["subcategory"] == "dairy-cheese-eggs"


# ---------------------------------------------------------------------------
# PUT /api/receipts/{id}/items — Error paths
# ---------------------------------------------------------------------------


class TestPutLineItemsErrors:
    """PUT /api/receipts/{id}/items error handling."""

    def test_404_for_nonexistent_receipt(self, _aws_setup):
        """PUT items for a non-existent receipt returns 404."""
        table, _ = _aws_setup

        event = _build_apigw_event(
            method="PUT",
            path="/api/receipts/01JQTEST999999999999999999/items",
            path_params={"receipt_id": "01JQTEST999999999999999999"},
            body={
                "items": [
                    {
                        "sortOrder": 1,
                        "name": "Item",
                        "quantity": 1,
                        "unitPrice": 1.00,
                        "totalPrice": 1.00,
                    }
                ]
            },
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 404, (
            f"Expected 404, got {response['statusCode']}"
        )

    def test_400_for_invalid_item_data(self, _aws_setup):
        """PUT items with invalid data (e.g., negative quantity) returns 400."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)

        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}/items",
            path_params={"receipt_id": receipt_id},
            body={
                "items": [
                    {
                        "sortOrder": 1,
                        "name": "Item",
                        "quantity": -1,
                        "unitPrice": 1.00,
                        "totalPrice": 1.00,
                    }
                ]
            },
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 400, (
            f"Expected 400 for negative quantity, got {response['statusCode']}"
        )

    def test_400_for_empty_item_name(self, _aws_setup):
        """PUT items with empty name returns 400."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)

        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}/items",
            path_params={"receipt_id": receipt_id},
            body={
                "items": [
                    {
                        "sortOrder": 1,
                        "name": "",
                        "quantity": 1,
                        "unitPrice": 1.00,
                        "totalPrice": 1.00,
                    }
                ]
            },
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 400, (
            f"Expected 400 for empty name, got {response['statusCode']}"
        )

    def test_400_for_too_many_items(self, _aws_setup):
        """PUT items with > 100 items returns 400 per spec."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, receipt_id=receipt_id)

        items = [
            {
                "sortOrder": i,
                "name": f"Item {i}",
                "quantity": 1,
                "unitPrice": 1.00,
                "totalPrice": 1.00,
            }
            for i in range(1, 102)  # 101 items
        ]
        event = _build_apigw_event(
            method="PUT",
            path=f"/api/receipts/{receipt_id}/items",
            path_params={"receipt_id": receipt_id},
            body={"items": items},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 400, (
            f"Expected 400 for >100 items, got {response['statusCode']}"
        )


# ---------------------------------------------------------------------------
# User isolation (cross-cutting)
# ---------------------------------------------------------------------------


class TestUserIsolation:
    """No user can read, edit, or delete another user's receipts."""

    def test_user_cannot_read_other_users_receipt(self, _aws_setup):
        """User A cannot GET user B's receipt."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, user_id="user-B", receipt_id=receipt_id)

        event = _build_apigw_event(
            user_id="user-A",
            method="GET",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] in (403, 404), (
            f"User A should not access user B's receipt, got {response['statusCode']}"
        )

    def test_user_cannot_update_other_users_receipt(self, _aws_setup):
        """User A cannot PUT user B's receipt."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, user_id="user-B", receipt_id=receipt_id)

        event = _build_apigw_event(
            user_id="user-A",
            method="PUT",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
            body={"merchant": "Hacked"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] in (403, 404)

    def test_user_cannot_delete_other_users_receipt(self, _aws_setup):
        """User A cannot DELETE user B's receipt."""
        table, s3 = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, user_id="user-B", receipt_id=receipt_id)
        s3.put_object(
            Bucket="novascan-receipts-test",
            Key=f"receipts/{receipt_id}.jpg",
            Body=b"img",
        )

        event = _build_apigw_event(
            user_id="user-A",
            method="DELETE",
            path=f"/api/receipts/{receipt_id}",
            path_params={"receipt_id": receipt_id},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] in (403, 404)

    def test_user_cannot_update_other_users_line_items(self, _aws_setup):
        """User A cannot PUT items on user B's receipt."""
        table, _ = _aws_setup
        receipt_id = "01JQTEST000000000000000001"
        _seed_receipt(table, user_id="user-B", receipt_id=receipt_id)

        event = _build_apigw_event(
            user_id="user-A",
            method="PUT",
            path=f"/api/receipts/{receipt_id}/items",
            path_params={"receipt_id": receipt_id},
            body={
                "items": [
                    {
                        "sortOrder": 1,
                        "name": "Hacked Item",
                        "quantity": 1,
                        "unitPrice": 1.00,
                        "totalPrice": 1.00,
                    }
                ]
            },
        )
        response = _invoke_handler(event)
        assert response["statusCode"] in (403, 404)
