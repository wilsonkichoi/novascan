"""Tests for POST /api/receipts/upload-urls endpoint.

Validates the API contract from api-contracts.md:
- Valid requests create receipt records and return presigned URLs
- Rejects >10 files, invalid contentType, oversized files
- Each receipt gets a unique ULID
- DynamoDB records created with correct PK/SK/status
"""

from __future__ import annotations

import json
import re
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
    method: str = "POST",
    path: str = "/api/receipts/upload-urls",
) -> dict[str, Any]:
    """Build a minimal API Gateway HTTP API v2 event for Lambda Powertools."""
    if isinstance(body, dict):
        body_str = json.dumps(body)
    elif body is None:
        body_str = ""
    else:
        body_str = body

    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {
            "content-type": "application/json",
        },
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
        "body": body_str,
        "isBase64Encoded": False,
    }


def _make_file(
    name: str = "receipt.jpg",
    content_type: str = "image/jpeg",
    file_size: int = 2_048_576,
) -> dict[str, Any]:
    """Build a single file object for the upload request body."""
    return {
        "fileName": name,
        "contentType": content_type,
        "fileSize": file_size,
    }


def _invoke_upload(event: dict[str, Any]) -> dict[str, Any]:
    """Import and invoke the handler, returning the response dict."""
    from api.app import handler

    return handler(event, FakeLambdaContext())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _aws_setup(monkeypatch):
    """Set up mocked AWS environment for upload tests."""
    monkeypatch.setenv("TABLE_NAME", "novascan-test")
    monkeypatch.setenv("RECEIPTS_BUCKET", "novascan-receipts-test")
    monkeypatch.setenv("PRESIGNED_URL_EXPIRY", "900")
    monkeypatch.setenv("POWERTOOLS_SERVICE_NAME", "novascan-test")
    monkeypatch.setenv("POWERTOOLS_TRACE_DISABLED", "1")

    with mock_aws():
        # Create DynamoDB table
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

        # Create S3 bucket
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="novascan-receipts-test")

        yield dynamodb, s3


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestUploadUrlsHappyPath:
    """Valid upload requests should create receipts and return presigned URLs."""

    def test_single_file_returns_201(self, _aws_setup):
        """A valid single-file request returns 201 Created."""
        event = _build_apigw_event(body={"files": [_make_file()]})
        response = _invoke_upload(event)
        assert response["statusCode"] == 201, f"Expected 201, got {response['statusCode']}: {response.get('body')}"

    def test_single_file_response_shape(self, _aws_setup):
        """Response matches the API contract: receipts array with receiptId, uploadUrl, imageKey, expiresIn."""
        event = _build_apigw_event(body={"files": [_make_file()]})
        response = _invoke_upload(event)
        body = json.loads(response["body"])

        assert "receipts" in body, "Response must contain 'receipts' key"
        assert len(body["receipts"]) == 1

        receipt = body["receipts"][0]
        assert "receiptId" in receipt, "Each receipt must have a receiptId"
        assert "uploadUrl" in receipt, "Each receipt must have an uploadUrl"
        assert "imageKey" in receipt, "Each receipt must have an imageKey"
        assert "expiresIn" in receipt, "Each receipt must have an expiresIn"

    def test_receipt_id_is_ulid_format(self, _aws_setup):
        """receiptId should be a ULID (26 characters, Crockford base32)."""
        event = _build_apigw_event(body={"files": [_make_file()]})
        response = _invoke_upload(event)
        body = json.loads(response["body"])
        receipt_id = body["receipts"][0]["receiptId"]

        # ULID is 26 chars of Crockford's Base32
        assert len(receipt_id) == 26, f"ULID should be 26 chars, got {len(receipt_id)}: {receipt_id}"
        assert re.match(r"^[0-9A-Z]{26}$", receipt_id), f"ULID has invalid characters: {receipt_id}"

    def test_each_receipt_gets_unique_ulid(self, _aws_setup):
        """Each file in a batch must get a distinct receiptId."""
        files = [_make_file(name=f"receipt{i}.jpg") for i in range(5)]
        event = _build_apigw_event(body={"files": files})
        response = _invoke_upload(event)
        body = json.loads(response["body"])

        receipt_ids = [r["receiptId"] for r in body["receipts"]]
        assert len(set(receipt_ids)) == 5, f"Expected 5 unique IDs, got duplicates: {receipt_ids}"

    def test_image_key_format(self, _aws_setup):
        """S3 key format must be receipts/{receiptId}.{ext} per spec."""
        event = _build_apigw_event(
            body={
                "files": [
                    _make_file(name="a.jpg", content_type="image/jpeg"),
                    _make_file(name="b.png", content_type="image/png"),
                ]
            }
        )
        response = _invoke_upload(event)
        body = json.loads(response["body"])

        jpg_receipt = body["receipts"][0]
        png_receipt = body["receipts"][1]

        assert jpg_receipt["imageKey"] == f"receipts/{jpg_receipt['receiptId']}.jpg"
        assert png_receipt["imageKey"] == f"receipts/{png_receipt['receiptId']}.png"

    def test_upload_url_is_presigned(self, _aws_setup):
        """uploadUrl must be a presigned S3 URL."""
        event = _build_apigw_event(body={"files": [_make_file()]})
        response = _invoke_upload(event)
        body = json.loads(response["body"])

        upload_url = body["receipts"][0]["uploadUrl"]
        assert "s3" in upload_url.lower() or "amazonaws" in upload_url.lower(), (
            f"uploadUrl doesn't look like a presigned S3 URL: {upload_url}"
        )

    def test_expires_in_value(self, _aws_setup):
        """expiresIn should match the configured presigned URL expiry (900s)."""
        event = _build_apigw_event(body={"files": [_make_file()]})
        response = _invoke_upload(event)
        body = json.loads(response["body"])

        assert body["receipts"][0]["expiresIn"] == 900

    def test_ten_files_accepted(self, _aws_setup):
        """Max 10 files per batch should be accepted."""
        files = [_make_file(name=f"receipt{i}.jpg") for i in range(10)]
        event = _build_apigw_event(body={"files": files})
        response = _invoke_upload(event)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert len(body["receipts"]) == 10

    def test_mixed_jpeg_png_batch(self, _aws_setup):
        """A batch can contain a mix of JPEG and PNG files."""
        files = [
            _make_file(name="a.jpg", content_type="image/jpeg"),
            _make_file(name="b.png", content_type="image/png"),
        ]
        event = _build_apigw_event(body={"files": files})
        response = _invoke_upload(event)
        assert response["statusCode"] == 201


# ---------------------------------------------------------------------------
# DynamoDB records
# ---------------------------------------------------------------------------


class TestUploadDynamoDBRecords:
    """Upload should create correct DynamoDB records."""

    def test_receipt_record_created(self, _aws_setup):
        """Each uploaded file should create a RECEIPT record in DynamoDB."""
        dynamodb, _ = _aws_setup
        user_id = "user-abc-123"
        event = _build_apigw_event(body={"files": [_make_file()]}, user_id=user_id)
        response = _invoke_upload(event)
        body = json.loads(response["body"])
        receipt_id = body["receipts"][0]["receiptId"]

        table = dynamodb.Table("novascan-test")
        result = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"RECEIPT#{receipt_id}"})

        assert "Item" in result, f"Receipt record not found in DynamoDB for receipt {receipt_id}"
        item = result["Item"]
        assert item["PK"] == f"USER#{user_id}"
        assert item["SK"] == f"RECEIPT#{receipt_id}"

    def test_receipt_status_is_processing(self, _aws_setup):
        """New receipt records must have status=processing per spec."""
        dynamodb, _ = _aws_setup
        user_id = "user-abc-123"
        event = _build_apigw_event(body={"files": [_make_file()]}, user_id=user_id)
        response = _invoke_upload(event)
        body = json.loads(response["body"])
        receipt_id = body["receipts"][0]["receiptId"]

        table = dynamodb.Table("novascan-test")
        item = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"RECEIPT#{receipt_id}"})["Item"]

        assert item["status"] == "processing", f"Expected status=processing, got {item['status']}"

    def test_receipt_has_entity_type(self, _aws_setup):
        """Record should have entityType=RECEIPT for single-table discrimination."""
        dynamodb, _ = _aws_setup
        user_id = "user-abc-123"
        event = _build_apigw_event(body={"files": [_make_file()]}, user_id=user_id)
        response = _invoke_upload(event)
        body = json.loads(response["body"])
        receipt_id = body["receipts"][0]["receiptId"]

        table = dynamodb.Table("novascan-test")
        item = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"RECEIPT#{receipt_id}"})["Item"]

        assert item.get("entityType") == "RECEIPT"

    def test_receipt_has_image_key(self, _aws_setup):
        """Record should contain the imageKey for S3 reference."""
        dynamodb, _ = _aws_setup
        user_id = "user-abc-123"
        event = _build_apigw_event(body={"files": [_make_file()]}, user_id=user_id)
        response = _invoke_upload(event)
        body = json.loads(response["body"])
        receipt_id = body["receipts"][0]["receiptId"]
        expected_key = body["receipts"][0]["imageKey"]

        table = dynamodb.Table("novascan-test")
        item = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"RECEIPT#{receipt_id}"})["Item"]

        assert item["imageKey"] == expected_key

    def test_receipt_has_timestamps(self, _aws_setup):
        """Records must have createdAt and updatedAt ISO 8601 timestamps."""
        dynamodb, _ = _aws_setup
        user_id = "user-abc-123"
        event = _build_apigw_event(body={"files": [_make_file()]}, user_id=user_id)
        response = _invoke_upload(event)
        body = json.loads(response["body"])
        receipt_id = body["receipts"][0]["receiptId"]

        table = dynamodb.Table("novascan-test")
        item = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"RECEIPT#{receipt_id}"})["Item"]

        assert "createdAt" in item, "Receipt record must have createdAt"
        assert "updatedAt" in item, "Receipt record must have updatedAt"
        # Basic ISO 8601 check
        assert "T" in item["createdAt"], "createdAt should be ISO 8601 format"

    def test_receipt_has_gsi1_keys(self, _aws_setup):
        """Receipt records should have GSI1PK and GSI1SK for date-range queries."""
        dynamodb, _ = _aws_setup
        user_id = "user-abc-123"
        event = _build_apigw_event(body={"files": [_make_file()]}, user_id=user_id)
        response = _invoke_upload(event)
        body = json.loads(response["body"])
        receipt_id = body["receipts"][0]["receiptId"]

        table = dynamodb.Table("novascan-test")
        item = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"RECEIPT#{receipt_id}"})["Item"]

        assert item.get("GSI1PK") == f"USER#{user_id}", "GSI1PK should be USER#{userId}"
        assert receipt_id in str(item.get("GSI1SK", "")), "GSI1SK should contain the receipt ULID"

    def test_batch_creates_all_records(self, _aws_setup):
        """All files in a batch should result in individual DynamoDB records."""
        dynamodb, _ = _aws_setup
        user_id = "user-abc-123"
        files = [_make_file(name=f"receipt{i}.jpg") for i in range(3)]
        event = _build_apigw_event(body={"files": files}, user_id=user_id)
        response = _invoke_upload(event)
        body = json.loads(response["body"])

        table = dynamodb.Table("novascan-test")
        for receipt in body["receipts"]:
            result = table.get_item(
                Key={"PK": f"USER#{user_id}", "SK": f"RECEIPT#{receipt['receiptId']}"}
            )
            assert "Item" in result, f"Missing DynamoDB record for receipt {receipt['receiptId']}"


# ---------------------------------------------------------------------------
# Validation / error paths
# ---------------------------------------------------------------------------


class TestUploadValidation:
    """Invalid requests should return 400 VALIDATION_ERROR."""

    def test_eleven_files_rejected(self, _aws_setup):
        """More than 10 files should return 400."""
        files = [_make_file(name=f"receipt{i}.jpg") for i in range(11)]
        event = _build_apigw_event(body={"files": files})
        response = _invoke_upload(event)

        assert response["statusCode"] == 400, f"Expected 400 for 11 files, got {response['statusCode']}"
        body = json.loads(response["body"])
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_empty_files_rejected(self, _aws_setup):
        """Empty files array should return 400."""
        event = _build_apigw_event(body={"files": []})
        response = _invoke_upload(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_invalid_content_type_rejected(self, _aws_setup):
        """Non-JPEG/PNG content type should return 400."""
        event = _build_apigw_event(
            body={"files": [_make_file(content_type="image/gif")]}
        )
        response = _invoke_upload(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_oversized_file_rejected(self, _aws_setup):
        """File size > 10 MB should return 400."""
        event = _build_apigw_event(
            body={"files": [_make_file(file_size=10_485_761)]}
        )
        response = _invoke_upload(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_zero_file_size_rejected(self, _aws_setup):
        """File size of 0 should return 400."""
        event = _build_apigw_event(
            body={"files": [_make_file(file_size=0)]}
        )
        response = _invoke_upload(event)
        assert response["statusCode"] == 400

    def test_empty_filename_rejected(self, _aws_setup):
        """Empty fileName should return 400."""
        event = _build_apigw_event(
            body={"files": [{"fileName": "", "contentType": "image/jpeg", "fileSize": 1000}]}
        )
        response = _invoke_upload(event)
        assert response["statusCode"] == 400

    def test_missing_body_rejected(self, _aws_setup):
        """No request body should return 400."""
        event = _build_apigw_event(body=None)
        response = _invoke_upload(event)
        assert response["statusCode"] == 400

    def test_malformed_json_rejected(self, _aws_setup):
        """Invalid JSON body should return 400."""
        event = _build_apigw_event(body="not-json{{{")
        response = _invoke_upload(event)
        assert response["statusCode"] == 400

    def test_missing_files_key_rejected(self, _aws_setup):
        """Request body without 'files' key should return 400."""
        event = _build_apigw_event(body={"notfiles": []})
        response = _invoke_upload(event)
        assert response["statusCode"] == 400

    def test_missing_content_type_in_file_rejected(self, _aws_setup):
        """File missing contentType should return 400."""
        event = _build_apigw_event(
            body={"files": [{"fileName": "a.jpg", "fileSize": 1000}]}
        )
        response = _invoke_upload(event)
        assert response["statusCode"] == 400

    def test_filename_too_long_rejected(self, _aws_setup):
        """fileName over 255 characters should return 400."""
        long_name = "a" * 252 + ".jpg"  # 256 chars
        event = _build_apigw_event(
            body={"files": [{"fileName": long_name, "contentType": "image/jpeg", "fileSize": 1000}]}
        )
        response = _invoke_upload(event)
        assert response["statusCode"] == 400


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------


class TestUploadUserIsolation:
    """Upload creates records scoped to the authenticated user."""

    def test_records_scoped_to_user(self, _aws_setup):
        """Receipt PK should contain the authenticated user's ID."""
        dynamodb, _ = _aws_setup
        user_id = "user-unique-456"
        event = _build_apigw_event(body={"files": [_make_file()]}, user_id=user_id)
        response = _invoke_upload(event)
        body = json.loads(response["body"])
        receipt_id = body["receipts"][0]["receiptId"]

        table = dynamodb.Table("novascan-test")
        item = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"RECEIPT#{receipt_id}"})

        assert "Item" in item, "Record should be under the authenticated user's partition"
        assert item["Item"]["PK"] == f"USER#{user_id}"

    def test_different_users_get_separate_records(self, _aws_setup):
        """Two different users uploading should get records in their own partitions."""
        dynamodb, _ = _aws_setup
        table = dynamodb.Table("novascan-test")

        for uid in ("user-1", "user-2"):
            event = _build_apigw_event(body={"files": [_make_file()]}, user_id=uid)
            _invoke_upload(event)

        # Each user should have exactly 1 receipt record
        for uid in ("user-1", "user-2"):
            result = table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(f"USER#{uid}")
                & boto3.dynamodb.conditions.Key("SK").begins_with("RECEIPT#"),
            )
            assert len(result["Items"]) == 1, f"User {uid} should have exactly 1 receipt"
