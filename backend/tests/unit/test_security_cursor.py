"""Security tests for pagination cursor tampering (SECURITY-REVIEW H1 + M7).

Tests the security contract for cursor validation in the list receipts
endpoint. Validates that:
- Tampered cursors (wrong GSI1PK, extra keys, missing keys) return 400
- Valid cursors are accepted
- Error messages are generic (no internal details leaked)
"""

from __future__ import annotations

import base64
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

USER_ID = "user-abc-123"
OTHER_USER_ID = "user-attacker-999"


def _build_apigw_event(
    user_id: str = USER_ID,
    query_params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a minimal API Gateway HTTP API v2 event."""
    raw_qs = "&".join(f"{k}={v}" for k, v in (query_params or {}).items())
    return {
        "version": "2.0",
        "routeKey": "GET /api/receipts",
        "rawPath": "/api/receipts",
        "rawQueryString": raw_qs,
        "headers": {"content-type": "application/json"},
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
                "method": "GET",
                "path": "/api/receipts",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "test",
            },
            "requestId": "test-request-id",
            "routeKey": "GET /api/receipts",
            "stage": "$default",
            "time": "01/Jan/2026:00:00:00 +0000",
            "timeEpoch": 1767225600000,
        },
        "body": None,
        "isBase64Encoded": False,
    }


def _encode_cursor(data: dict[str, Any]) -> str:
    """Base64-encode a dict as a cursor."""
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


def _invoke_list(event: dict[str, Any]) -> dict[str, Any]:
    """Import and invoke the handler."""
    from api.app import handler

    return handler(event, FakeLambdaContext())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def aws_env(monkeypatch):
    """Set up mocked AWS environment."""
    monkeypatch.setenv("TABLE_NAME", "novascan-test")
    monkeypatch.setenv("RECEIPTS_BUCKET", "novascan-receipts-test")
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
        yield


# ---------------------------------------------------------------------------
# Tampered cursor rejection
# ---------------------------------------------------------------------------


class TestCursorTampering:
    """Cursors targeting other users or with wrong structure must be rejected."""

    def test_cursor_with_other_users_gsi1pk_rejected(self, aws_env):
        """A cursor with GSI1PK pointing to another user must return 400."""
        tampered = _encode_cursor({
            "GSI1PK": f"USER#{OTHER_USER_ID}",
            "GSI1SK": "2026-03-25#01RECEIPT000001AAAAAA0001",
            "PK": f"USER#{OTHER_USER_ID}",
            "SK": "RECEIPT#01RECEIPT000001AAAAAA0001",
        })
        event = _build_apigw_event(query_params={"cursor": tampered})
        response = _invoke_list(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"]["message"] == "Invalid pagination cursor"

    def test_cursor_with_mismatched_pk_rejected(self, aws_env):
        """A cursor where PK doesn't match the authenticated user must return 400."""
        tampered = _encode_cursor({
            "GSI1PK": f"USER#{USER_ID}",
            "GSI1SK": "2026-03-25#01RECEIPT000001AAAAAA0001",
            "PK": f"USER#{OTHER_USER_ID}",
            "SK": "RECEIPT#01RECEIPT000001AAAAAA0001",
        })
        event = _build_apigw_event(query_params={"cursor": tampered})
        response = _invoke_list(event)

        assert response["statusCode"] == 400

    def test_cursor_with_extra_keys_rejected(self, aws_env):
        """A cursor with extra unexpected keys must return 400."""
        tampered = _encode_cursor({
            "GSI1PK": f"USER#{USER_ID}",
            "GSI1SK": "2026-03-25#01RECEIPT000001AAAAAA0001",
            "PK": f"USER#{USER_ID}",
            "SK": "RECEIPT#01RECEIPT000001AAAAAA0001",
            "EXTRA_KEY": "injected_value",
        })
        event = _build_apigw_event(query_params={"cursor": tampered})
        response = _invoke_list(event)

        assert response["statusCode"] == 400

    def test_cursor_with_missing_keys_rejected(self, aws_env):
        """A cursor missing required keys must return 400."""
        tampered = _encode_cursor({
            "GSI1PK": f"USER#{USER_ID}",
            "GSI1SK": "2026-03-25#01RECEIPT000001AAAAAA0001",
            # Missing PK and SK
        })
        event = _build_apigw_event(query_params={"cursor": tampered})
        response = _invoke_list(event)

        assert response["statusCode"] == 400

    def test_cursor_with_only_gsi1pk_rejected(self, aws_env):
        """A cursor with only GSI1PK must return 400."""
        tampered = _encode_cursor({
            "GSI1PK": f"USER#{USER_ID}",
        })
        event = _build_apigw_event(query_params={"cursor": tampered})
        response = _invoke_list(event)

        assert response["statusCode"] == 400

    def test_non_base64_cursor_rejected(self, aws_env):
        """A non-base64 cursor must return 400."""
        event = _build_apigw_event(query_params={"cursor": "not-valid-base64!!!"})
        response = _invoke_list(event)

        assert response["statusCode"] == 400

    def test_non_json_cursor_rejected(self, aws_env):
        """A base64-encoded non-JSON cursor must return 400."""
        cursor = base64.urlsafe_b64encode(b"this is not json").decode()
        event = _build_apigw_event(query_params={"cursor": cursor})
        response = _invoke_list(event)

        assert response["statusCode"] == 400

    def test_cursor_with_array_instead_of_object_rejected(self, aws_env):
        """A cursor that decodes to an array instead of object must return 400."""
        cursor = base64.urlsafe_b64encode(b'["not", "an", "object"]').decode()
        event = _build_apigw_event(query_params={"cursor": cursor})
        response = _invoke_list(event)

        assert response["statusCode"] == 400


# ---------------------------------------------------------------------------
# Error message sanitization (M7)
# ---------------------------------------------------------------------------


class TestCursorErrorSanitization:
    """Error messages from cursor validation must be generic."""

    def test_error_message_is_generic(self, aws_env):
        """Error message must say 'Invalid pagination cursor', nothing else."""
        tampered = _encode_cursor({
            "GSI1PK": f"USER#{OTHER_USER_ID}",
            "GSI1SK": "2026-03-25#01RECEIPT000001AAAAAA0001",
            "PK": f"USER#{OTHER_USER_ID}",
            "SK": "RECEIPT#01RECEIPT000001AAAAAA0001",
        })
        event = _build_apigw_event(query_params={"cursor": tampered})
        response = _invoke_list(event)
        body = json.loads(response["body"])

        # Must be generic — no internal details
        assert body["error"]["message"] == "Invalid pagination cursor"
        # Must NOT contain user IDs, key names, or stack traces
        body_str = json.dumps(body)
        assert OTHER_USER_ID not in body_str
        assert "GSI1PK" not in body_str
        assert "Traceback" not in body_str

    def test_error_code_is_validation_error(self, aws_env):
        """Error code must be VALIDATION_ERROR."""
        event = _build_apigw_event(query_params={"cursor": "garbage"})
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_missing_keys_error_is_generic(self, aws_env):
        """Missing keys error must not reveal expected key structure."""
        tampered = _encode_cursor({"only": "one_key"})
        event = _build_apigw_event(query_params={"cursor": tampered})
        response = _invoke_list(event)
        body = json.loads(response["body"])

        assert body["error"]["message"] == "Invalid pagination cursor"
        # Must not reveal expected key names
        body_str = json.dumps(body)
        assert "GSI1PK" not in body_str
        assert "GSI1SK" not in body_str


# ---------------------------------------------------------------------------
# Valid cursor acceptance
# ---------------------------------------------------------------------------


class TestValidCursorAccepted:
    """Properly formed cursors for the authenticated user must be accepted."""

    def test_valid_cursor_returns_200(self, aws_env):
        """A properly formed cursor for the current user must not return 400."""
        valid_cursor = _encode_cursor({
            "GSI1PK": f"USER#{USER_ID}",
            "GSI1SK": "2026-03-25#01RECEIPT000001AAAAAA0001",
            "PK": f"USER#{USER_ID}",
            "SK": "RECEIPT#01RECEIPT000001AAAAAA0001",
        })
        event = _build_apigw_event(query_params={"cursor": valid_cursor})
        response = _invoke_list(event)

        # Should be 200 (empty result set, since no data seeded), not 400
        assert response["statusCode"] == 200

    def test_no_cursor_returns_200(self, aws_env):
        """Request without cursor must return 200."""
        event = _build_apigw_event()
        response = _invoke_list(event)

        assert response["statusCode"] == 200
