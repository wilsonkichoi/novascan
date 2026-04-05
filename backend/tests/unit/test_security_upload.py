"""Security tests for upload endpoint hardening (SECURITY-REVIEW M6, L4).

Tests the security contract:
- Presigned URL includes ContentLength parameter
- ValidationError responses are sanitized (no raw Pydantic str(e))
- GSI2PK is set on receipt creation
"""

from __future__ import annotations

import json
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
) -> dict[str, Any]:
    """Build a minimal API Gateway HTTP API v2 event."""
    if isinstance(body, dict):
        body_str = json.dumps(body)
    elif body is None:
        body_str = ""
    else:
        body_str = body

    return {
        "version": "2.0",
        "routeKey": "POST /api/receipts/upload-urls",
        "rawPath": "/api/receipts/upload-urls",
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
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
                "method": "POST",
                "path": "/api/receipts/upload-urls",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "test",
            },
            "requestId": "test-request-id",
            "routeKey": "POST /api/receipts/upload-urls",
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
    """Build a single file object."""
    return {
        "fileName": name,
        "contentType": content_type,
        "fileSize": file_size,
    }


def _invoke_upload(event: dict[str, Any]) -> dict[str, Any]:
    """Import and invoke the handler."""
    from api.app import handler

    return handler(event, FakeLambdaContext())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _aws_setup(monkeypatch):
    """Set up mocked AWS environment."""
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
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="novascan-receipts-test")

        yield dynamodb, s3


# ---------------------------------------------------------------------------
# M6 — Presigned URL includes ContentLength
# ---------------------------------------------------------------------------


class TestPresignedUrlContentLength:
    """Presigned URL must include ContentLength in the presigned params.

    Note: moto's presigned URL generation may not embed Content-Length
    the same way AWS does. We verify the code path by mocking
    generate_presigned_url and checking the Params dict.
    """

    def test_presigned_url_params_include_content_length(self, _aws_setup):
        """The generate_presigned_url call must include ContentLength in Params."""
        from unittest.mock import MagicMock

        captured_params = []

        def spy_generate(*args, **kwargs):
            # generate_presigned_url("put_object", Params={...}, ExpiresIn=...)
            params = kwargs.get("Params", args[1] if len(args) > 1 else {})
            captured_params.append(params)
            return "https://fake-bucket.s3.amazonaws.com/fake-key?Signature=abc"

        import api.upload as upload_module
        original_s3 = upload_module.s3_client
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url = spy_generate
        upload_module.s3_client = mock_s3

        try:
            event = _build_apigw_event(
                body={"files": [_make_file(file_size=2_048_576)]}
            )
            response = _invoke_upload(event)
            assert response["statusCode"] == 201

            assert len(captured_params) >= 1
            params = captured_params[0]
            assert "ContentLength" in params, (
                f"ContentLength not in presigned URL Params: {params}"
            )
            assert params["ContentLength"] == 2_048_576
        finally:
            upload_module.s3_client = original_s3

    def test_different_file_sizes_produce_different_presigned_params(self, _aws_setup):
        """Different file sizes should result in different ContentLength params."""
        from unittest.mock import MagicMock

        captured_lengths = []

        def spy_generate(*args, **kwargs):
            params = kwargs.get("Params", args[1] if len(args) > 1 else {})
            captured_lengths.append(params.get("ContentLength"))
            return "https://fake-bucket.s3.amazonaws.com/fake-key?Signature=abc"

        import api.upload as upload_module
        original_s3 = upload_module.s3_client
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url = spy_generate
        upload_module.s3_client = mock_s3

        try:
            event1 = _build_apigw_event(body={"files": [_make_file(file_size=1000)]})
            _invoke_upload(event1)

            event2 = _build_apigw_event(body={"files": [_make_file(file_size=2000)]})
            _invoke_upload(event2)

            assert 1000 in captured_lengths
            assert 2000 in captured_lengths
        finally:
            upload_module.s3_client = original_s3


# ---------------------------------------------------------------------------
# L4 — ValidationError sanitization
# ---------------------------------------------------------------------------


class TestValidationErrorSanitization:
    """Pydantic ValidationError must be sanitized — no raw str(e) leaked."""

    def test_oversized_file_error_is_sanitized(self, _aws_setup):
        """Oversized file error should have structured field-level errors."""
        event = _build_apigw_event(
            body={"files": [_make_file(file_size=10_485_761)]}
        )
        response = _invoke_upload(event)
        assert response["statusCode"] == 400

        body = json.loads(response["body"])
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "details" in body["error"]
        assert isinstance(body["error"]["details"], list)

        # Each error should have field and message, not raw Pydantic text
        for err in body["error"]["details"]:
            assert "field" in err
            assert "message" in err

    def test_eleven_files_error_is_sanitized(self, _aws_setup):
        """Too many files error should be sanitized."""
        files = [_make_file(name=f"r{i}.jpg") for i in range(11)]
        event = _build_apigw_event(body={"files": files})
        response = _invoke_upload(event)
        body = json.loads(response["body"])

        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "details" in body["error"]

    def test_invalid_content_type_error_is_sanitized(self, _aws_setup):
        """Invalid content type error should be sanitized."""
        event = _build_apigw_event(
            body={"files": [_make_file(content_type="image/gif")]}
        )
        response = _invoke_upload(event)
        body = json.loads(response["body"])

        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "details" in body["error"]

    def test_error_does_not_contain_pydantic_repr(self, _aws_setup):
        """Error response must not contain Pydantic internal repr."""
        event = _build_apigw_event(
            body={"files": [_make_file(file_size=10_485_761)]}
        )
        response = _invoke_upload(event)
        body_str = response["body"]

        # Must not contain Pydantic internal formatting
        assert "validation error for" not in body_str.lower()
        assert "input_value" not in body_str
        assert "url_type" not in body_str

    def test_malformed_json_returns_generic_error(self, _aws_setup):
        """Malformed JSON should return a generic error, not a traceback."""
        event = _build_apigw_event(body="not-valid-json{{{")
        response = _invoke_upload(event)
        body = json.loads(response["body"])

        assert response["statusCode"] == 400
        assert body["error"]["code"] == "VALIDATION_ERROR"
        # Must not contain traceback or internal error details
        assert "Traceback" not in response["body"]


# ---------------------------------------------------------------------------
# GSI2PK set on receipt creation
# ---------------------------------------------------------------------------


class TestGSI2PKOnCreation:
    """Upload must set GSI2PK = receiptId on receipt DynamoDB records."""

    def test_receipt_has_gsi2pk(self, _aws_setup):
        """Created receipt must have GSI2PK = receiptId."""
        dynamodb, _ = _aws_setup
        user_id = "user-abc-123"
        event = _build_apigw_event(body={"files": [_make_file()]}, user_id=user_id)
        response = _invoke_upload(event)
        body = json.loads(response["body"])
        receipt_id = body["receipts"][0]["receiptId"]

        table = dynamodb.Table("novascan-test")
        item = table.get_item(
            Key={"PK": f"USER#{user_id}", "SK": f"RECEIPT#{receipt_id}"}
        )["Item"]

        assert item.get("GSI2PK") == receipt_id, (
            f"GSI2PK should be '{receipt_id}', got '{item.get('GSI2PK')}'"
        )
