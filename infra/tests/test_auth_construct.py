"""Tests for the Auth construct against SPEC.md Section 3 (Auth Flow, RBAC).

Verifies:
- Cognito User Pool exists
- Three groups created: user, staff, admin
- Pre-Sign-Up Lambda trigger attached
- App Client auth flows include USER_AUTH (passwordless)

Spec references:
- Section 3: Auth Flow, RBAC
- Milestone 1 acceptance criteria: Cognito User Pool, three groups, Pre-Sign-Up auto-confirms
"""

from __future__ import annotations

import pytest
import aws_cdk as cdk
from aws_cdk.assertions import Match, Template

from stacks.novascan_stack import NovascanStack
from tests.conftest import DEV_CONFIG


class TestCognitoUserPool:
    """Cognito User Pool configuration per SPEC.md Section 3."""

    def test_user_pool_exists(self, dev_template: Template) -> None:
        """At least one Cognito User Pool must be created."""
        dev_template.resource_count_is("AWS::Cognito::UserPool", 1)

    def test_pre_signup_lambda_trigger_attached(
        self, dev_template: Template
    ) -> None:
        """User Pool must have a Pre-Sign-Up Lambda trigger.

        Spec Section 3: 'Pre-Sign-Up Lambda auto-confirms + auto-verifies email'
        """
        dev_template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "LambdaConfig": {
                    "PreSignUp": Match.any_value(),
                },
            },
        )


class TestCognitoGroups:
    """Cognito User Pool Groups per SPEC.md Section 3 RBAC."""

    def test_three_groups_created(self, dev_template: Template) -> None:
        """Three Cognito groups must be created: user, staff, admin.

        Spec Section 3 RBAC table: user, staff, admin groups.
        Milestone 1 AC: 'Cognito User Pool has three groups: user, staff, admin'
        """
        dev_template.resource_count_is("AWS::Cognito::UserPoolGroup", 3)

    def test_user_group_exists(self, dev_template: Template) -> None:
        """The 'user' group must exist.

        Spec Section 3: 'Default: New users are assigned to the user group'
        """
        dev_template.has_resource_properties(
            "AWS::Cognito::UserPoolGroup",
            {"GroupName": "user"},
        )

    def test_staff_group_exists(self, dev_template: Template) -> None:
        """The 'staff' group must exist.

        Spec Section 3 RBAC: staff role for pipeline comparison.
        """
        dev_template.has_resource_properties(
            "AWS::Cognito::UserPoolGroup",
            {"GroupName": "staff"},
        )

    def test_admin_group_exists(self, dev_template: Template) -> None:
        """The 'admin' group must exist.

        Spec Section 3 RBAC: admin role for user management.
        """
        dev_template.has_resource_properties(
            "AWS::Cognito::UserPoolGroup",
            {"GroupName": "admin"},
        )

    def test_group_precedence_admin_highest(self, dev_template: Template) -> None:
        """Admin group should have lowest precedence number (highest priority).

        Spec Section 3: 'Group precedence: admin=0, staff=1, user=2'
        """
        dev_template.has_resource_properties(
            "AWS::Cognito::UserPoolGroup",
            {"GroupName": "admin", "Precedence": 0},
        )

    def test_group_precedence_staff(self, dev_template: Template) -> None:
        """Staff group should have precedence 1.

        Spec Section 3: 'Group precedence: admin=0, staff=1, user=2'
        """
        dev_template.has_resource_properties(
            "AWS::Cognito::UserPoolGroup",
            {"GroupName": "staff", "Precedence": 1},
        )

    def test_group_precedence_user_lowest(self, dev_template: Template) -> None:
        """User group should have precedence 2 (lowest priority).

        Spec Section 3: 'Group precedence: admin=0, staff=1, user=2'
        """
        dev_template.has_resource_properties(
            "AWS::Cognito::UserPoolGroup",
            {"GroupName": "user", "Precedence": 2},
        )


class TestCognitoAppClient:
    """Cognito App Client configuration per SPEC.md Section 3."""

    def test_app_client_exists(self, dev_template: Template) -> None:
        """At least one Cognito User Pool Client must be created."""
        dev_template.resource_count_is("AWS::Cognito::UserPoolClient", 1)

    def test_app_client_supports_user_auth_flow(
        self, dev_template: Template
    ) -> None:
        """App Client must support USER_AUTH flow for passwordless email OTP.

        Spec Section 3: 'InitiateAuth (USER_AUTH flow, email as username)'
        The ALLOW_USER_AUTH auth flow is required for passwordless OTP.
        """
        dev_template.has_resource_properties(
            "AWS::Cognito::UserPoolClient",
            {
                "ExplicitAuthFlows": Match.array_with(
                    ["ALLOW_USER_AUTH"]
                ),
            },
        )

    def test_refresh_token_validity_7_days(self, dev_template: Template) -> None:
        """Refresh token validity must be set to 7 days (10080 minutes).

        Security hardening M4: Explicit refresh token TTL.
        CDK stores Duration.days(7) as 10080 minutes internally.
        """
        dev_template.has_resource_properties(
            "AWS::Cognito::UserPoolClient",
            {
                "RefreshTokenValidity": 10080,
                "TokenValidityUnits": Match.object_like(
                    {"RefreshToken": "minutes"}
                ),
            },
        )


class TestAuthSecurityHardening:
    """Security hardening tests for Auth construct (H2, H3, M4)."""

    def test_email_otp_only_no_password(self, dev_template: Template) -> None:
        """AllowedFirstAuthFactors must contain only EMAIL_OTP, no PASSWORD.

        Security hardening H2: PASSWORD auth factor must be removed.
        """
        dev_template.has_resource_properties(
            "AWS::Cognito::UserPool",
            {
                "Policies": Match.object_like(
                    {
                        "SignInPolicy": {
                            "AllowedFirstAuthFactors": ["EMAIL_OTP"],
                        }
                    }
                ),
            },
        )

    def test_cognito_iam_scoped_not_wildcard(self, dev_template: Template) -> None:
        """Post-Confirmation Lambda IAM policy must scope Cognito ARN to novascan-*.

        Security hardening H3: IAM resource must not use userpool/* wildcard.
        """
        dev_template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": Match.object_like(
                    {
                        "Statement": Match.array_with(
                            [
                                Match.object_like(
                                    {
                                        "Action": "cognito-idp:AdminAddUserToGroup",
                                        "Resource": {
                                            "Fn::Join": [
                                                "",
                                                Match.array_with(
                                                    [
                                                        Match.string_like_regexp(
                                                            ".*:cognito-idp:.*:userpool/novascan-\\*"
                                                        ),
                                                    ]
                                                ),
                                            ],
                                        },
                                    }
                                ),
                            ]
                        ),
                    }
                ),
            },
        )


class TestAuthDependencyCycle:
    """Verify Auth construct has no circular dependencies."""

    def test_no_circular_dependencies(self) -> None:
        """Template must synthesize without circular dependency errors.

        A valid CloudFormation template must have no resource dependency cycles.
        Template.from_stack() (without skip_cyclical_dependencies_check)
        validates this.
        """
        app = cdk.App()
        stack = NovascanStack(
            app,
            "novascan-cycle-check",
            stage="dev",
            config=DEV_CONFIG,
            env=cdk.Environment(account="123456789012", region="us-east-1"),
        )
        # This should NOT raise -- if it does, there's a dependency cycle
        Template.from_stack(stack)
