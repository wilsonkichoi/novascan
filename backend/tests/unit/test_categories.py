"""Tests for category API endpoints.

Validates API contracts from api-contracts.md:
- GET /api/categories returns predefined + custom merged
- POST /api/categories creates custom with auto-slug
- POST /api/categories rejects duplicate slug (409)
- DELETE /api/categories/{slug} removes custom
- DELETE /api/categories/{slug} rejects predefined (403)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
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
    path: str = "/api/categories",
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


def _seed_custom_category(
    table: Any,
    user_id: str = "user-abc-123",
    slug: str = "my-custom-cat",
    display_name: str = "My Custom Cat",
    parent_category: str | None = None,
) -> dict[str, Any]:
    """Insert a custom category record into DynamoDB."""
    now = datetime.now(UTC).isoformat()
    item: dict[str, Any] = {
        "PK": f"USER#{user_id}",
        "SK": f"CUSTOMCAT#{slug}",
        "entityType": "CUSTOMCAT",
        "slug": slug,
        "displayName": display_name,
        "isCustom": True,
        "createdAt": now,
    }
    if parent_category:
        item["parentCategory"] = parent_category
    table.put_item(Item=item)
    return item


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _aws_setup(monkeypatch):
    """Set up mocked AWS environment for category tests."""
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
# GET /api/categories
# ---------------------------------------------------------------------------


class TestListCategories:
    """GET /api/categories returns predefined + custom merged."""

    def test_returns_200(self, _aws_setup):
        """GET /api/categories returns 200."""
        event = _build_apigw_event(method="GET", path="/api/categories")
        response = _invoke_handler(event)
        assert response["statusCode"] == 200, (
            f"Expected 200, got {response['statusCode']}: {response.get('body')}"
        )

    def test_response_contains_categories_array(self, _aws_setup):
        """Response must have a 'categories' array."""
        event = _build_apigw_event(method="GET", path="/api/categories")
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert "categories" in body, "Response must contain 'categories' key"
        assert isinstance(body["categories"], list)

    def test_includes_all_predefined_categories(self, _aws_setup):
        """Response should include all 13 predefined categories."""
        event = _build_apigw_event(method="GET", path="/api/categories")
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        predefined = [c for c in body["categories"] if not c.get("isCustom", False)]
        assert len(predefined) >= 13, (
            f"Expected at least 13 predefined categories, got {len(predefined)}"
        )

    def test_predefined_have_subcategories(self, _aws_setup):
        """Predefined categories should have subcategories."""
        event = _build_apigw_event(method="GET", path="/api/categories")
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        for cat in body["categories"]:
            if not cat.get("isCustom", False):
                assert "subcategories" in cat, (
                    f"Predefined category '{cat.get('slug')}' missing subcategories"
                )
                assert isinstance(cat["subcategories"], list)
                assert len(cat["subcategories"]) > 0, (
                    f"Predefined category '{cat.get('slug')}' has empty subcategories"
                )

    def test_predefined_categories_not_custom(self, _aws_setup):
        """Predefined categories should have isCustom=false."""
        event = _build_apigw_event(method="GET", path="/api/categories")
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        # Find a well-known predefined category
        groceries = next(
            (c for c in body["categories"] if c.get("slug") == "groceries-food"),
            None,
        )
        assert groceries is not None, "groceries-food should be in the response"
        assert groceries["isCustom"] is False, "Predefined categories should have isCustom=false"

    def test_includes_custom_categories(self, _aws_setup):
        """Response merges user's custom categories with predefined ones."""
        table, _ = _aws_setup
        _seed_custom_category(table, slug="my-test-cat", display_name="My Test Cat")

        event = _build_apigw_event(method="GET", path="/api/categories")
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        custom = [c for c in body["categories"] if c.get("isCustom", False)]
        assert len(custom) >= 1, "Should include at least 1 custom category"

        custom_slugs = [c["slug"] for c in custom]
        assert "my-test-cat" in custom_slugs, (
            f"Custom category 'my-test-cat' not found. Custom slugs: {custom_slugs}"
        )

    def test_custom_categories_have_is_custom_true(self, _aws_setup):
        """Custom categories should have isCustom=true."""
        table, _ = _aws_setup
        _seed_custom_category(table, slug="my-custom", display_name="My Custom")

        event = _build_apigw_event(method="GET", path="/api/categories")
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        custom_cat = next(
            (c for c in body["categories"] if c.get("slug") == "my-custom"),
            None,
        )
        assert custom_cat is not None, "Custom category 'my-custom' should be in response"
        assert custom_cat["isCustom"] is True

    def test_category_response_shape(self, _aws_setup):
        """Each category should have slug, displayName, isCustom, subcategories."""
        event = _build_apigw_event(method="GET", path="/api/categories")
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        for cat in body["categories"]:
            assert "slug" in cat, f"Category missing 'slug': {cat}"
            assert "displayName" in cat, f"Category missing 'displayName': {cat}"
            assert "isCustom" in cat, f"Category missing 'isCustom': {cat}"

    def test_custom_categories_scoped_to_user(self, _aws_setup):
        """Custom categories are user-scoped. User B should not see user A's custom categories."""
        table, _ = _aws_setup
        _seed_custom_category(table, user_id="user-A", slug="user-a-cat", display_name="User A Cat")

        # Request as user-B
        event = _build_apigw_event(
            user_id="user-B",
            method="GET",
            path="/api/categories",
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        custom_slugs = [c["slug"] for c in body["categories"] if c.get("isCustom", False)]
        assert "user-a-cat" not in custom_slugs, (
            f"User B should not see user A's custom categories. Custom slugs: {custom_slugs}"
        )


# ---------------------------------------------------------------------------
# POST /api/categories
# ---------------------------------------------------------------------------


class TestCreateCustomCategory:
    """POST /api/categories creates a custom category with auto-slug."""

    def test_returns_201(self, _aws_setup):
        """POST with valid data returns 201 Created."""
        event = _build_apigw_event(
            method="POST",
            path="/api/categories",
            body={"displayName": "My Custom Category"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 201, (
            f"Expected 201, got {response['statusCode']}: {response.get('body')}"
        )

    def test_auto_generates_slug(self, _aws_setup):
        """Slug is auto-generated from displayName (lowercased, spaces -> hyphens)."""
        event = _build_apigw_event(
            method="POST",
            path="/api/categories",
            body={"displayName": "My Custom Category"},
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert "slug" in body, "Response must contain 'slug'"
        assert body["slug"] == "my-custom-category", (
            f"Expected slug 'my-custom-category', got '{body['slug']}'"
        )

    def test_response_shape(self, _aws_setup):
        """POST response matches the api-contracts.md shape."""
        event = _build_apigw_event(
            method="POST",
            path="/api/categories",
            body={"displayName": "Test Cat", "parentCategory": "other"},
        )
        response = _invoke_handler(event)
        body = json.loads(response["body"])

        assert body["slug"] == "test-cat"
        assert body["displayName"] == "Test Cat"
        assert body["isCustom"] is True
        assert body["parentCategory"] == "other"

    def test_created_category_appears_in_list(self, _aws_setup):
        """After POST, the new category should appear in GET /api/categories."""
        # Create
        event = _build_apigw_event(
            method="POST",
            path="/api/categories",
            body={"displayName": "Brand New Cat"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 201

        # List
        list_event = _build_apigw_event(method="GET", path="/api/categories")
        list_response = _invoke_handler(list_event)
        body = json.loads(list_response["body"])

        slugs = [c["slug"] for c in body["categories"]]
        assert "brand-new-cat" in slugs, (
            f"Newly created category not found in list. Slugs: {slugs}"
        )

    def test_parent_category_optional(self, _aws_setup):
        """parentCategory is optional in the request."""
        event = _build_apigw_event(
            method="POST",
            path="/api/categories",
            body={"displayName": "No Parent Cat"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        # parentCategory should be null/None when not provided
        assert body.get("parentCategory") is None

    def test_stored_in_dynamodb(self, _aws_setup):
        """Custom category is stored in DynamoDB with correct key pattern."""
        table, _ = _aws_setup

        event = _build_apigw_event(
            method="POST",
            path="/api/categories",
            body={"displayName": "DDB Test"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 201

        result = table.get_item(
            Key={"PK": "USER#user-abc-123", "SK": "CUSTOMCAT#ddb-test"}
        )
        assert "Item" in result, (
            "Custom category should be stored in DynamoDB with PK=USER#{userId}, SK=CUSTOMCAT#{slug}"
        )


# ---------------------------------------------------------------------------
# POST /api/categories — Error paths
# ---------------------------------------------------------------------------


class TestCreateCustomCategoryErrors:
    """POST /api/categories error handling."""

    def test_409_for_duplicate_slug(self, _aws_setup):
        """POST with a display name that generates an existing slug returns 409 CONFLICT."""
        table, _ = _aws_setup
        # First creation
        event1 = _build_apigw_event(
            method="POST",
            path="/api/categories",
            body={"displayName": "Duplicate Cat"},
        )
        response1 = _invoke_handler(event1)
        assert response1["statusCode"] == 201

        # Second creation with same name
        event2 = _build_apigw_event(
            method="POST",
            path="/api/categories",
            body={"displayName": "Duplicate Cat"},
        )
        response2 = _invoke_handler(event2)
        assert response2["statusCode"] == 409, (
            f"Expected 409 for duplicate slug, got {response2['statusCode']}: {response2.get('body')}"
        )
        body = json.loads(response2["body"])
        assert body["error"]["code"] == "CONFLICT"

    def test_409_for_predefined_category_slug(self, _aws_setup):
        """POST that would generate a predefined category slug returns 409."""
        # "Groceries Food" -> "groceries-food" which is predefined
        event = _build_apigw_event(
            method="POST",
            path="/api/categories",
            body={"displayName": "Groceries Food"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 409, (
            f"Expected 409 for predefined slug collision, got {response['statusCode']}: {response.get('body')}"
        )

    def test_400_for_invalid_parent_category(self, _aws_setup):
        """POST with parentCategory that is not a valid predefined slug returns 400."""
        event = _build_apigw_event(
            method="POST",
            path="/api/categories",
            body={"displayName": "Test Cat", "parentCategory": "nonexistent-parent"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 400, (
            f"Expected 400 for invalid parentCategory, got {response['statusCode']}: {response.get('body')}"
        )

    def test_400_for_empty_display_name(self, _aws_setup):
        """POST with empty displayName returns 400."""
        event = _build_apigw_event(
            method="POST",
            path="/api/categories",
            body={"displayName": ""},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 400, (
            f"Expected 400 for empty displayName, got {response['statusCode']}"
        )

    def test_400_for_missing_display_name(self, _aws_setup):
        """POST without displayName returns 400."""
        event = _build_apigw_event(
            method="POST",
            path="/api/categories",
            body={},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 400, (
            f"Expected 400 for missing displayName, got {response['statusCode']}"
        )

    def test_400_for_too_long_display_name(self, _aws_setup):
        """POST with displayName > 100 characters returns 400."""
        event = _build_apigw_event(
            method="POST",
            path="/api/categories",
            body={"displayName": "A" * 101},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 400, (
            f"Expected 400 for too-long displayName, got {response['statusCode']}"
        )


# ---------------------------------------------------------------------------
# DELETE /api/categories/{slug}
# ---------------------------------------------------------------------------


class TestDeleteCustomCategory:
    """DELETE /api/categories/{slug} removes custom categories."""

    def test_returns_204_for_custom_category(self, _aws_setup):
        """DELETE for an existing custom category returns 204."""
        table, _ = _aws_setup
        _seed_custom_category(table, slug="to-delete", display_name="To Delete")

        event = _build_apigw_event(
            method="DELETE",
            path="/api/categories/to-delete",
            path_params={"slug": "to-delete"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 204, (
            f"Expected 204, got {response['statusCode']}: {response.get('body')}"
        )

    def test_removes_from_dynamodb(self, _aws_setup):
        """After DELETE, the custom category record is removed from DynamoDB."""
        table, _ = _aws_setup
        _seed_custom_category(table, slug="to-delete", display_name="To Delete")

        event = _build_apigw_event(
            method="DELETE",
            path="/api/categories/to-delete",
            path_params={"slug": "to-delete"},
        )
        _invoke_handler(event)

        result = table.get_item(
            Key={"PK": "USER#user-abc-123", "SK": "CUSTOMCAT#to-delete"}
        )
        assert "Item" not in result, (
            "Custom category should be removed from DynamoDB after deletion"
        )

    def test_deleted_category_no_longer_in_list(self, _aws_setup):
        """After DELETE, the category should not appear in GET /api/categories."""
        table, _ = _aws_setup
        _seed_custom_category(table, slug="temp-cat", display_name="Temp Cat")

        # Delete
        event = _build_apigw_event(
            method="DELETE",
            path="/api/categories/temp-cat",
            path_params={"slug": "temp-cat"},
        )
        _invoke_handler(event)

        # List
        list_event = _build_apigw_event(method="GET", path="/api/categories")
        list_response = _invoke_handler(list_event)
        body = json.loads(list_response["body"])

        slugs = [c["slug"] for c in body["categories"]]
        assert "temp-cat" not in slugs, (
            f"Deleted category should not appear in list. Slugs: {slugs}"
        )


# ---------------------------------------------------------------------------
# DELETE /api/categories/{slug} — Error paths
# ---------------------------------------------------------------------------


class TestDeleteCategoryErrors:
    """DELETE /api/categories/{slug} error handling."""

    def test_403_for_predefined_category(self, _aws_setup):
        """DELETE of a predefined category returns 403 FORBIDDEN."""
        event = _build_apigw_event(
            method="DELETE",
            path="/api/categories/groceries-food",
            path_params={"slug": "groceries-food"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 403, (
            f"Expected 403 for deleting predefined category, got {response['statusCode']}: {response.get('body')}"
        )
        body = json.loads(response["body"])
        assert body["error"]["code"] == "FORBIDDEN"

    def test_403_for_various_predefined_categories(self, _aws_setup):
        """DELETE of any predefined category returns 403."""
        for slug in ["dining", "other", "pets", "education"]:
            event = _build_apigw_event(
                method="DELETE",
                path=f"/api/categories/{slug}",
                path_params={"slug": slug},
            )
            response = _invoke_handler(event)
            assert response["statusCode"] == 403, (
                f"Expected 403 for deleting predefined category '{slug}', "
                f"got {response['statusCode']}"
            )

    def test_404_for_nonexistent_custom_category(self, _aws_setup):
        """DELETE for a slug that doesn't exist returns 404."""
        event = _build_apigw_event(
            method="DELETE",
            path="/api/categories/nonexistent-cat",
            path_params={"slug": "nonexistent-cat"},
        )
        response = _invoke_handler(event)
        assert response["statusCode"] == 404, (
            f"Expected 404 for nonexistent custom category, got {response['statusCode']}"
        )

    def test_cannot_delete_other_users_custom_category(self, _aws_setup):
        """User B cannot delete user A's custom category."""
        table, _ = _aws_setup
        _seed_custom_category(table, user_id="user-A", slug="a-cat", display_name="A Cat")

        event = _build_apigw_event(
            user_id="user-B",
            method="DELETE",
            path="/api/categories/a-cat",
            path_params={"slug": "a-cat"},
        )
        response = _invoke_handler(event)
        # User B's partition won't have this category, so it should be 404
        assert response["statusCode"] in (403, 404), (
            f"Expected 403 or 404, got {response['statusCode']}"
        )
