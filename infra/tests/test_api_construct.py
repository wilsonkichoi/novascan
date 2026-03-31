"""Tests for the API construct against SPEC.md Sections 3, 6, 13.

Verifies:
- API Gateway HTTP API exists
- Cognito authorizer attached
- Lambda function exists
- CORS configuration matches spec

Spec references:
- Section 3: Architecture (API Gateway HTTP API with JWT authorizer)
- Section 6: API Contracts (base path /api)
- Section 13: CORS Configuration
"""

from __future__ import annotations

from aws_cdk.assertions import Match, Template


class TestHttpApi:
    """API Gateway HTTP API per SPEC.md Section 3."""

    def test_http_api_exists(self, dev_template: Template) -> None:
        """At least one API Gateway v2 HTTP API must be created.

        Spec Section 3: 'API Gateway HTTP API'
        """
        dev_template.resource_count_is("AWS::ApiGatewayV2::Api", 1)

    def test_http_api_protocol_is_http(self, dev_template: Template) -> None:
        """API must use HTTP protocol (not WebSocket).

        Spec Section 14: 'No WebSocket -- polling for status updates'
        """
        dev_template.has_resource_properties(
            "AWS::ApiGatewayV2::Api",
            {"ProtocolType": "HTTP"},
        )

    def test_cors_allowed_methods(self, dev_template: Template) -> None:
        """CORS must allow GET, POST, PUT, DELETE, OPTIONS.

        Spec Section 13: 'Allowed methods: GET, POST, PUT, DELETE, OPTIONS'
        """
        dev_template.has_resource_properties(
            "AWS::ApiGatewayV2::Api",
            {
                "CorsConfiguration": {
                    "AllowMethods": Match.array_with(
                        ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
                    ),
                },
            },
        )

    def test_cors_allowed_headers(self, dev_template: Template) -> None:
        """CORS must allow Authorization and Content-Type headers.

        Spec Section 13: 'Allowed headers: Authorization, Content-Type'
        """
        dev_template.has_resource_properties(
            "AWS::ApiGatewayV2::Api",
            {
                "CorsConfiguration": {
                    "AllowHeaders": Match.array_with(
                        ["Authorization", "Content-Type"]
                    ),
                },
            },
        )

    def test_cors_max_age(self, dev_template: Template) -> None:
        """CORS max age must be 86400 seconds (24 hours).

        Spec Section 13: 'Max age: 86400 (24 hours)'
        """
        dev_template.has_resource_properties(
            "AWS::ApiGatewayV2::Api",
            {
                "CorsConfiguration": {
                    "MaxAge": 86400,
                },
            },
        )


class TestCognitoAuthorizer:
    """Cognito JWT authorizer on the API per SPEC.md Section 3."""

    def test_authorizer_exists(self, dev_template: Template) -> None:
        """At least one API Gateway v2 authorizer must be created.

        Spec Section 3: 'API Gateway Cognito authorizer validates the JWT'
        """
        dev_template.resource_count_is("AWS::ApiGatewayV2::Authorizer", 1)

    def test_authorizer_type_is_jwt(self, dev_template: Template) -> None:
        """Authorizer must be JWT type for Cognito token validation.

        Spec Section 3: 'JWT validated on every API request via Cognito authorizer'
        """
        dev_template.has_resource_properties(
            "AWS::ApiGatewayV2::Authorizer",
            {"AuthorizerType": "JWT"},
        )


class TestApiLambda:
    """API Lambda function per SPEC.md Section 3."""

    def test_lambda_functions_exist(self, dev_template: Template) -> None:
        """At least one Lambda function must be created for the API.

        Spec Section 3: 'Single API Lambda handles all REST endpoints'
        The stack creates multiple Lambda functions (API + auth triggers).
        """
        resources = dev_template.find_resources("AWS::Lambda::Function")
        assert len(resources) >= 1, (
            "Expected at least 1 Lambda function for the API handler, "
            f"found {len(resources)}"
        )

    def test_api_lambda_has_python_runtime(self, dev_template: Template) -> None:
        """API Lambda must use a Python runtime.

        Spec Section 9: 'Python 3.13+ via uv'
        """
        dev_template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "Runtime": Match.string_like_regexp(r"python3\.\d+"),
            },
        )
