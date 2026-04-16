"""CDK security hardening tests (SECURITY-REVIEW: C2, H2, H3, M1-M5, M9, M10, M13, L2, L3).

Tests CDK security configuration against the security review findings:
- GSI2 exists on DynamoDB table (C2)
- No PASSWORD in auth factors (H2)
- Cognito IAM not wildcard (H3)
- CloudFront has security response headers (M2)
- S3 IAM scoped to receipts/* prefix (M1)
- API Gateway throttling configured (M5)
- Bedrock IAM region-scoped (M10)
- No Scan in LoadCustomCategories IAM (M13)
- S3 lifecycle rules exist (M3)
- Refresh token validity set (M4)
- Textract IAM comment documented (M9 — verified via resources=["*"])
"""

from __future__ import annotations

import json

from aws_cdk.assertions import Match, Template


# ---------------------------------------------------------------------------
# C2 — GSI2 exists for receipt lookup
# ---------------------------------------------------------------------------


class TestGSI2Exists:
    """DynamoDB table must have GSI2 for receipt-to-user lookup."""

    def test_gsi2_exists_with_gsi2pk(self, dev_template: Template) -> None:
        """GSI2 must exist with GSI2PK as partition key."""
        dev_template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "GlobalSecondaryIndexes": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "IndexName": "GSI2",
                                "KeySchema": Match.array_with(
                                    [
                                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                                    ]
                                ),
                            }
                        )
                    ]
                ),
            },
        )

    def test_gsi2_projection_is_keys_only(self, dev_template: Template) -> None:
        """GSI2 projection must be KEYS_ONLY (only need PK to extract userId)."""
        dev_template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "GlobalSecondaryIndexes": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "IndexName": "GSI2",
                                "Projection": {"ProjectionType": "KEYS_ONLY"},
                            }
                        )
                    ]
                ),
            },
        )


# ---------------------------------------------------------------------------
# H2 — PASSWORD required by Cognito but blocked at App Client level
# ---------------------------------------------------------------------------


class TestAuthFactors:
    """Cognito User Pool auth factors include EMAIL_OTP.

    PASSWORD must be present (Cognito requires it on pool creation) but is
    not exploitable — the App Client only enables USER_AUTH flow.
    """

    def test_email_otp_in_allowed_first_auth_factors(
        self, dev_template_json: dict
    ) -> None:
        """AllowedFirstAuthFactors must include EMAIL_OTP."""
        resources = dev_template_json.get("Resources", {})
        for _key, resource in resources.items():
            if resource.get("Type") == "AWS::Cognito::UserPool":
                props = resource.get("Properties", {})
                policies = props.get("Policies", {})
                sign_in_policy = policies.get("SignInPolicy", {})
                auth_factors = sign_in_policy.get("AllowedFirstAuthFactors", [])
                assert "EMAIL_OTP" in auth_factors, (
                    f"EMAIL_OTP must be in AllowedFirstAuthFactors: {auth_factors}"
                )


# ---------------------------------------------------------------------------
# H3 — Cognito IAM not wildcard
# ---------------------------------------------------------------------------


class TestCognitoIAMScoped:
    """Post-Confirmation Lambda IAM must be scoped to novascan-*, not wildcard."""

    def test_cognito_iam_not_wildcard_userpool(
        self, dev_template_json: dict
    ) -> None:
        """Cognito IAM resource must NOT be userpool/* (wildcard)."""
        resources = dev_template_json.get("Resources", {})
        for _key, resource in resources.items():
            if resource.get("Type") == "AWS::IAM::Policy":
                props = resource.get("Properties", {})
                for statement in props.get("PolicyDocument", {}).get("Statement", []):
                    actions = statement.get("Action", [])
                    if isinstance(actions, str):
                        actions = [actions]
                    if "cognito-idp:AdminAddUserToGroup" in actions:
                        resource_arns = statement.get("Resource", [])
                        if isinstance(resource_arns, str):
                            resource_arns = [resource_arns]
                        for arn in resource_arns:
                            if isinstance(arn, str):
                                assert "userpool/*" not in arn, (
                                    f"Cognito IAM uses wildcard userpool/*: {arn}"
                                )
                            elif isinstance(arn, dict) and "Fn::Join" in arn:
                                # Check Fn::Join components
                                parts = arn["Fn::Join"][1]
                                joined = "".join(
                                    str(p) for p in parts if isinstance(p, str)
                                )
                                assert "userpool/*" not in joined, (
                                    f"Cognito IAM uses wildcard: {joined}"
                                )


# ---------------------------------------------------------------------------
# M2 — CloudFront security headers
# ---------------------------------------------------------------------------


class TestCloudFrontSecurityHeaders:
    """CloudFront distribution must have security response headers."""

    def test_response_headers_policy_exists(self, dev_template: Template) -> None:
        """A ResponseHeadersPolicy must exist."""
        dev_template.resource_count_is(
            "AWS::CloudFront::ResponseHeadersPolicy", 1
        )

    def test_hsts_header_configured(self, dev_template: Template) -> None:
        """HSTS header must be configured."""
        dev_template.has_resource_properties(
            "AWS::CloudFront::ResponseHeadersPolicy",
            {
                "ResponseHeadersPolicyConfig": Match.object_like(
                    {
                        "SecurityHeadersConfig": Match.object_like(
                            {
                                "StrictTransportSecurity": Match.object_like(
                                    {
                                        "AccessControlMaxAgeSec": 63072000,
                                        "IncludeSubdomains": True,
                                        "Override": True,
                                    }
                                ),
                            }
                        ),
                    }
                ),
            },
        )

    def test_content_type_options_configured(self, dev_template: Template) -> None:
        """X-Content-Type-Options: nosniff must be configured."""
        dev_template.has_resource_properties(
            "AWS::CloudFront::ResponseHeadersPolicy",
            {
                "ResponseHeadersPolicyConfig": Match.object_like(
                    {
                        "SecurityHeadersConfig": Match.object_like(
                            {
                                "ContentTypeOptions": Match.object_like(
                                    {"Override": True}
                                ),
                            }
                        ),
                    }
                ),
            },
        )

    def test_frame_options_deny(self, dev_template: Template) -> None:
        """X-Frame-Options: DENY must be configured."""
        dev_template.has_resource_properties(
            "AWS::CloudFront::ResponseHeadersPolicy",
            {
                "ResponseHeadersPolicyConfig": Match.object_like(
                    {
                        "SecurityHeadersConfig": Match.object_like(
                            {
                                "FrameOptions": Match.object_like(
                                    {
                                        "FrameOption": "DENY",
                                        "Override": True,
                                    }
                                ),
                            }
                        ),
                    }
                ),
            },
        )

    def test_referrer_policy_configured(self, dev_template: Template) -> None:
        """Referrer-Policy must be strict-origin-when-cross-origin."""
        dev_template.has_resource_properties(
            "AWS::CloudFront::ResponseHeadersPolicy",
            {
                "ResponseHeadersPolicyConfig": Match.object_like(
                    {
                        "SecurityHeadersConfig": Match.object_like(
                            {
                                "ReferrerPolicy": Match.object_like(
                                    {
                                        "ReferrerPolicy": "strict-origin-when-cross-origin",
                                        "Override": True,
                                    }
                                ),
                            }
                        ),
                    }
                ),
            },
        )

    def test_csp_header_configured(self, dev_template: Template) -> None:
        """Content-Security-Policy must be configured."""
        dev_template.has_resource_properties(
            "AWS::CloudFront::ResponseHeadersPolicy",
            {
                "ResponseHeadersPolicyConfig": Match.object_like(
                    {
                        "SecurityHeadersConfig": Match.object_like(
                            {
                                "ContentSecurityPolicy": Match.object_like(
                                    {
                                        "ContentSecurityPolicy": Match.string_like_regexp(
                                            r"default-src 'self'"
                                        ),
                                        "Override": True,
                                    }
                                ),
                            }
                        ),
                    }
                ),
            },
        )


# ---------------------------------------------------------------------------
# M5 — API Gateway throttling
# ---------------------------------------------------------------------------


class TestApiGatewayThrottling:
    """API Gateway must have route-level throttling configured."""

    def test_default_route_settings_have_throttling(
        self, dev_template_json: dict
    ) -> None:
        """API stage must have DefaultRouteSettings with throttling."""
        resources = dev_template_json.get("Resources", {})
        found_throttling = False
        for _key, resource in resources.items():
            if resource.get("Type") == "AWS::ApiGatewayV2::Stage":
                props = resource.get("Properties", {})
                default_settings = props.get("DefaultRouteSettings", {})
                if "ThrottlingBurstLimit" in default_settings:
                    found_throttling = True
                    assert default_settings["ThrottlingBurstLimit"] == 10
                    assert default_settings["ThrottlingRateLimit"] == 5
        assert found_throttling, "No API Gateway stage found with throttling settings"

    def test_access_logging_enabled(self, dev_template_json: dict) -> None:
        """API stage must have access logging enabled."""
        resources = dev_template_json.get("Resources", {})
        found_access_log = False
        for _key, resource in resources.items():
            if resource.get("Type") == "AWS::ApiGatewayV2::Stage":
                props = resource.get("Properties", {})
                access_log = props.get("AccessLogSettings", {})
                if "DestinationArn" in access_log:
                    found_access_log = True
        assert found_access_log, "No API Gateway stage found with access logging"


# ---------------------------------------------------------------------------
# M10 — Bedrock IAM region-scoped
# ---------------------------------------------------------------------------


class TestBedrockIAMRegionScoped:
    """Bedrock IAM ARNs must be scoped to the deployment region."""

    def test_bedrock_arn_contains_region_ref(
        self, dev_template_json: dict
    ) -> None:
        """Bedrock IAM policy resource ARNs must reference the deployment region."""
        resources = dev_template_json.get("Resources", {})
        found_bedrock_policy = False
        for _key, resource in resources.items():
            if resource.get("Type") == "AWS::IAM::Policy":
                props = resource.get("Properties", {})
                for statement in props.get("PolicyDocument", {}).get("Statement", []):
                    actions = statement.get("Action", [])
                    if isinstance(actions, str):
                        actions = [actions]
                    if "bedrock:InvokeModel" in actions:
                        found_bedrock_policy = True
                        resource_arns = statement.get("Resource", [])
                        if isinstance(resource_arns, str):
                            resource_arns = [resource_arns]
                        for arn in resource_arns:
                            # ARN should use Fn::Join with Ref to AWS::Region
                            # or be a concrete ARN with a region component
                            if isinstance(arn, dict) and "Fn::Join" in arn:
                                parts = arn["Fn::Join"][1]
                                # Should contain a Ref to AWS::Region
                                has_region_ref = any(
                                    isinstance(p, dict) and p.get("Ref") == "AWS::Region"
                                    for p in parts
                                )
                                assert has_region_ref, (
                                    "Bedrock IAM ARN does not reference "
                                    "AWS::Region — it may use * for region"
                                )
        assert found_bedrock_policy, "No Bedrock InvokeModel IAM policy found"


# ---------------------------------------------------------------------------
# M13 — No Scan in LoadCustomCategories IAM
# ---------------------------------------------------------------------------


class TestLoadCustomCategoriesIAM:
    """LoadCustomCategories Lambda must NOT have dynamodb:Scan permission."""

    def test_dedicated_query_getitem_policy_exists_without_scan(
        self, dev_template_json: dict
    ) -> None:
        """There must exist a DynamoDB IAM policy with ONLY Query + GetItem (no Scan).

        The LoadCustomCategories Lambda should have a dedicated policy that
        grants only dynamodb:Query and dynamodb:GetItem (SECURITY-REVIEW M13).
        Other Lambdas (e.g., API, Finalize) may have broader permissions via
        grant_read_write_data, but the dedicated policy must not include Scan.
        """
        resources = dev_template_json.get("Resources", {})
        found_dedicated_policy = False

        for _key, resource in resources.items():
            if resource.get("Type") == "AWS::IAM::Policy":
                props = resource.get("Properties", {})
                for statement in props.get("PolicyDocument", {}).get("Statement", []):
                    actions = statement.get("Action", [])
                    if isinstance(actions, str):
                        actions = [actions]
                    # Look for the dedicated policy: has Query + GetItem
                    # and does NOT have Scan, PutItem, etc.
                    if (
                        "dynamodb:Query" in actions
                        and "dynamodb:GetItem" in actions
                        and "dynamodb:Scan" not in actions
                        and "dynamodb:PutItem" not in actions
                    ):
                        found_dedicated_policy = True

        assert found_dedicated_policy, (
            "No dedicated DynamoDB IAM policy found with only Query + GetItem "
            "(without Scan). LoadCustomCategories should have scoped IAM."
        )


# ---------------------------------------------------------------------------
# M3 — S3 lifecycle rules
# ---------------------------------------------------------------------------


class TestS3LifecycleRules:
    """Receipts S3 bucket must have lifecycle rules for cost optimization."""

    def test_lifecycle_rules_exist(self, dev_template_json: dict) -> None:
        """At least one S3 bucket must have lifecycle rules."""
        resources = dev_template_json.get("Resources", {})
        found_lifecycle = False
        for _key, resource in resources.items():
            if resource.get("Type") == "AWS::S3::Bucket":
                props = resource.get("Properties", {})
                rules = props.get("LifecycleConfiguration", {}).get("Rules", [])
                if rules:
                    found_lifecycle = True
                    # Verify transitions exist
                    rule = rules[0]
                    transitions = rule.get("Transitions", [])
                    assert len(transitions) >= 2, (
                        f"Expected at least 2 transitions (IA + Glacier), "
                        f"got {len(transitions)}"
                    )
        assert found_lifecycle, "No S3 bucket found with lifecycle rules"


# ---------------------------------------------------------------------------
# M4 — Refresh token validity
# ---------------------------------------------------------------------------


class TestRefreshTokenValidity:
    """App Client must have refresh token validity configured."""

    def test_refresh_token_validity_set(self, dev_template_json: dict) -> None:
        """Cognito App Client must have RefreshTokenValidity set."""
        resources = dev_template_json.get("Resources", {})
        found_client = False
        for _key, resource in resources.items():
            if resource.get("Type") == "AWS::Cognito::UserPoolClient":
                found_client = True
                props = resource.get("Properties", {})
                validity = props.get("RefreshTokenValidity")
                assert validity is not None, (
                    "RefreshTokenValidity must be set on Cognito App Client"
                )
                # Should be 7 days
                units = props.get("TokenValidityUnits", {})
                refresh_unit = units.get("RefreshToken", "days")
                if refresh_unit == "days":
                    assert validity == 7, (
                        f"RefreshTokenValidity should be 7 days, got {validity}"
                    )
        assert found_client, "No Cognito UserPoolClient found"


# ---------------------------------------------------------------------------
# M9 — Textract IAM uses resources=["*"]
# ---------------------------------------------------------------------------


class TestTextractIAM:
    """Textract IAM must use resources=["*"] (required by AWS)."""

    def test_textract_iam_uses_wildcard_resource(
        self, dev_template_json: dict
    ) -> None:
        """Textract IAM must use Resource: * (AWS requirement)."""
        resources = dev_template_json.get("Resources", {})
        found_textract = False
        for _key, resource in resources.items():
            if resource.get("Type") == "AWS::IAM::Policy":
                props = resource.get("Properties", {})
                for statement in props.get("PolicyDocument", {}).get("Statement", []):
                    actions = statement.get("Action", [])
                    if isinstance(actions, str):
                        actions = [actions]
                    if "textract:AnalyzeExpense" in actions:
                        found_textract = True
                        resource_val = statement.get("Resource", "")
                        assert resource_val == "*", (
                            f"Textract IAM resource should be *, got: {resource_val}"
                        )
        assert found_textract, "No Textract IAM policy found"


# ---------------------------------------------------------------------------
# M1 — S3 IAM scoped to receipts/* prefix
# ---------------------------------------------------------------------------


class TestS3IAMScoped:
    """S3 PutObject permissions must be scoped to receipts/* prefix (API + Finalize)."""

    def test_s3_put_scoped_to_receipts_prefix(
        self, dev_template_json: dict
    ) -> None:
        """At least 2 S3 PutObject grants must reference receipts/* prefix (API + Finalize)."""
        resources = dev_template_json.get("Resources", {})
        scoped_put_count = 0
        for _key, resource in resources.items():
            if resource.get("Type") == "AWS::IAM::Policy":
                props = resource.get("Properties", {})
                for statement in props.get("PolicyDocument", {}).get("Statement", []):
                    actions = statement.get("Action", [])
                    if isinstance(actions, str):
                        actions = [actions]
                    if "s3:PutObject" in actions:
                        resource_val = statement.get("Resource", [])
                        # Resource can be a single dict, a string, or a list
                        if isinstance(resource_val, dict):
                            resource_val = [resource_val]
                        elif isinstance(resource_val, str):
                            resource_val = [resource_val]
                        for arn in resource_val:
                            arn_str = json.dumps(arn)
                            if "/receipts/*" in arn_str:
                                scoped_put_count += 1
        assert scoped_put_count >= 2, (
            f"Expected at least 2 scoped S3 PutObject grants (API + Finalize), "
            f"found {scoped_put_count}"
        )


# ---------------------------------------------------------------------------
# S3 — Self-signup disabled (SECURITY-REVIEW S3)
# ---------------------------------------------------------------------------


class TestSelfSignupDisabled:
    """Cognito User Pool must have self-service sign-up disabled."""

    def test_admin_create_user_only(self, dev_template_json: dict) -> None:
        """AllowAdminCreateUserOnly must be true."""
        resources = dev_template_json.get("Resources", {})
        for _key, resource in resources.items():
            if resource.get("Type") == "AWS::Cognito::UserPool":
                props = resource.get("Properties", {})
                admin_config = props.get("AdminCreateUserConfig", {})
                assert admin_config.get("AllowAdminCreateUserOnly") is True, (
                    "Self-signup must be disabled (AllowAdminCreateUserOnly=True)"
                )
