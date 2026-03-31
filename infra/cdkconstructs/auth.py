"""Auth construct: Cognito User Pool, App Client, Groups, and Lambda triggers.

Creates:
- Cognito User Pool with email-only sign-in
- App Client with USER_AUTH and REFRESH_TOKEN auth flows
- Three Cognito Groups: user (2), staff (1), admin (0)
- Pre-Sign-Up Lambda trigger (auto-confirm + auto-verify email)
- Post-Confirmation Lambda trigger (add user to 'user' group)

See: SPEC.md Section 3 (Auth Flow, RBAC).
"""

import pathlib
from typing import Any

import aws_cdk as cdk
import aws_cdk.aws_cognito as cognito
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda as lambda_
from constructs import Construct

# Path to the backend source code (relative to this file -> infra/cdkconstructs/ -> ../../backend/src/novascan)
BACKEND_AUTH_CODE_PATH = str(
    pathlib.Path(__file__).resolve().parent.parent.parent / "backend" / "src" / "novascan" / "auth"
)


class AuthConstruct(Construct):
    def __init__(
        self, scope: Construct, id: str, *, stage: str, config: dict[str, Any], **kwargs: Any
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # --- Pre-Sign-Up Lambda ---
        pre_signup_fn = lambda_.Function(
            self,
            "PreSignUpFn",
            function_name=f"novascan-{stage}-pre-signup",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="pre_signup.handler",
            code=lambda_.Code.from_asset(
                BACKEND_AUTH_CODE_PATH,
                exclude=["post_confirmation.py", "__pycache__"],
            ),
            timeout=cdk.Duration.seconds(10),
            memory_size=128,
            description="Cognito Pre-Sign-Up trigger: no-op placeholder for future validation",
        )

        # --- Post-Confirmation Lambda (needs User Pool ID, set below) ---
        post_confirmation_fn = lambda_.Function(
            self,
            "PostConfirmationFn",
            function_name=f"novascan-{stage}-post-confirmation",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="post_confirmation.handler",
            code=lambda_.Code.from_asset(
                BACKEND_AUTH_CODE_PATH,
                exclude=["pre_signup.py", "__pycache__"],
            ),
            timeout=cdk.Duration.seconds(10),
            memory_size=128,
            description="Cognito Post-Confirmation trigger: add user to 'user' group",
        )

        # --- Cognito User Pool ---
        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"novascan-{stage}",
            sign_in_aliases=cognito.SignInAliases(email=True),
            self_sign_up_enabled=True,
            removal_policy=cdk.RemovalPolicy.DESTROY if stage == "dev" else cdk.RemovalPolicy.RETAIN,
            lambda_triggers=cognito.UserPoolTriggers(
                pre_sign_up=pre_signup_fn,
                post_confirmation=post_confirmation_fn,
            ),
        )

        # Enable EMAIL_OTP as an allowed first auth factor.
        # CDK L2 doesn't expose SignInPolicy yet — use CloudFormation escape hatch.
        cfn_user_pool = self.user_pool.node.default_child
        cfn_user_pool.add_property_override(
            "Policies.SignInPolicy.AllowedFirstAuthFactors", ["EMAIL_OTP", "PASSWORD"]
        )

        # Grant Post-Confirmation Lambda permission to add users to groups.
        # Use a constructed ARN with wildcard instead of self.user_pool.user_pool_arn
        # to break the circular dependency: IAM Policy -> User Pool -> Lambda -> Policy.
        user_pool_wildcard_arn = cdk.Stack.of(self).format_arn(
            service="cognito-idp",
            resource="userpool",
            resource_name="*",
            arn_format=cdk.ArnFormat.SLASH_RESOURCE_NAME,
        )
        post_confirmation_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cognito-idp:AdminAddUserToGroup"],
                resources=[user_pool_wildcard_arn],
            )
        )

        # --- App Client ---
        self.app_client = self.user_pool.add_client(
            "AppClient",
            user_pool_client_name=f"novascan-{stage}-app",
            auth_flows=cognito.AuthFlow(
                user=True,
                custom=False,
                user_password=False,
                user_srp=False,
            ),
            generate_secret=False,
        )

        # --- Cognito Groups ---
        # Precedence: lower number = higher priority
        cognito.CfnUserPoolGroup(
            self,
            "AdminGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="admin",
            description="Full administrative access",
            precedence=0,
        )

        cognito.CfnUserPoolGroup(
            self,
            "StaffGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="staff",
            description="Staff access with pipeline comparison features",
            precedence=1,
        )

        cognito.CfnUserPoolGroup(
            self,
            "UserGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="user",
            description="Default group for all users",
            precedence=2,
        )

        # --- Exports for other constructs ---
        self.user_pool_id = self.user_pool.user_pool_id
        self.user_pool_arn = self.user_pool.user_pool_arn
        self.app_client_id = self.app_client.user_pool_client_id
