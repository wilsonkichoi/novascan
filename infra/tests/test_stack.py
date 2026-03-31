"""Full stack snapshot test for the NovaScan CDK stack.

Verifies that the synthesized CloudFormation template matches a stored snapshot.
Any infrastructure changes will cause this test to fail, requiring explicit
review and update of the snapshot file.

This test also validates cross-construct wiring and stack outputs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import aws_cdk as cdk
from aws_cdk.assertions import Match, Template

from stacks.novascan_stack import NovascanStack

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"
SNAPSHOT_FILE = SNAPSHOT_DIR / "novascan-dev.template.json"


class TestStackSnapshot:
    """Snapshot test for the full synthesized CloudFormation template."""

    def test_snapshot_matches(self, dev_template_json: dict) -> None:
        """Synthesized template must match the stored snapshot.

        If this test fails after an intentional change, update the snapshot:
            cd infra && uv run pytest --snapshot-update
        Or manually:
            cd infra && uv run python -c "
            from tests.conftest import *; import json, pathlib
            t = dev_template()
            pathlib.Path('tests/snapshots').mkdir(exist_ok=True)
            pathlib.Path('tests/snapshots/novascan-dev.template.json').write_text(
                json.dumps(t.to_json(), indent=2, sort_keys=True))
            "
        """
        if not SNAPSHOT_FILE.exists():
            # First run: create the snapshot
            SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
            SNAPSHOT_FILE.write_text(
                json.dumps(dev_template_json, indent=2, sort_keys=True) + "\n"
            )
            pytest.skip(
                f"Snapshot created at {SNAPSHOT_FILE}. "
                "Re-run tests to verify against the snapshot."
            )

        stored = json.loads(SNAPSHOT_FILE.read_text())
        assert dev_template_json == stored, (
            "CloudFormation template has changed since last snapshot. "
            "Review the diff and update the snapshot if the change is intentional. "
            f"Snapshot file: {SNAPSHOT_FILE}"
        )


class TestStackOutputs:
    """Verify stack outputs are present per SPEC.md Section 13."""

    def test_api_url_output_exists(self, dev_template: Template) -> None:
        """Stack must export the API Gateway URL.

        Spec Section 13: 'Values are sourced from CDK stack outputs at build time'
        VITE_API_URL must be available.
        """
        dev_template.has_output(
            "ApiUrl",
            {"Description": Match.any_value(), "Value": Match.any_value()},
        )

    def test_cloudfront_domain_output_exists(
        self, dev_template: Template
    ) -> None:
        """Stack must export the CloudFront distribution domain.

        Needed for frontend deployment and CORS configuration.
        """
        dev_template.has_output(
            "CloudFrontDomain",
            {"Description": Match.any_value(), "Value": Match.any_value()},
        )

    def test_user_pool_id_output_exists(self, dev_template: Template) -> None:
        """Stack must export the Cognito User Pool ID.

        Spec Section 13: 'VITE_COGNITO_USER_POOL_ID' needed at frontend build time.
        """
        dev_template.has_output(
            "UserPoolId",
            {"Description": Match.any_value(), "Value": Match.any_value()},
        )

    def test_app_client_id_output_exists(self, dev_template: Template) -> None:
        """Stack must export the Cognito App Client ID.

        Spec Section 13: 'VITE_COGNITO_CLIENT_ID' needed at frontend build time.
        """
        dev_template.has_output(
            "AppClientId",
            {"Description": Match.any_value(), "Value": Match.any_value()},
        )


class TestStackComposition:
    """Verify the stack assembles all required AWS resources."""

    def test_has_dynamodb_table(self, dev_template: Template) -> None:
        """Stack must include a DynamoDB table."""
        dev_template.resource_count_is("AWS::DynamoDB::Table", 1)

    def test_has_cognito_user_pool(self, dev_template: Template) -> None:
        """Stack must include a Cognito User Pool."""
        dev_template.resource_count_is("AWS::Cognito::UserPool", 1)

    def test_has_api_gateway(self, dev_template: Template) -> None:
        """Stack must include an API Gateway HTTP API."""
        dev_template.resource_count_is("AWS::ApiGatewayV2::Api", 1)

    def test_has_cloudfront_distribution(self, dev_template: Template) -> None:
        """Stack must include a CloudFront distribution."""
        dev_template.resource_count_is("AWS::CloudFront::Distribution", 1)

    def test_has_lambda_functions(self, dev_template: Template) -> None:
        """Stack must include Lambda functions (API + auth triggers at minimum)."""
        # At minimum: API Lambda + Pre-Sign-Up Lambda = 2
        # Likely more with Post-Confirmation and pipeline Lambdas.
        resources = dev_template.find_resources("AWS::Lambda::Function")
        assert len(resources) >= 2, (
            f"Expected at least 2 Lambda functions (API + Pre-Sign-Up trigger), "
            f"found {len(resources)}"
        )


class TestStageIsolation:
    """Verify that different stages produce independent stacks."""

    def test_dev_and_prod_have_different_stack_ids(self) -> None:
        """Dev and prod stacks must have different construct IDs.

        Spec Section 13: 'Production deployment is isolated from dev
        (separate stack, separate resources)'
        """
        app = cdk.App()
        prod_config = {
            "pipelineMaxConcurrency": 2,
            "presignedUrlExpirySec": 900,
            "maxUploadFiles": 10,
            "maxUploadSizeMb": 10,
            "logLevel": "INFO",
            "defaultPipeline": "ocr-ai",
        }

        dev_stack = NovascanStack(
            app,
            "novascan-dev",
            stage="dev",
            config=prod_config,
            env=cdk.Environment(account="123456789012", region="us-east-1"),
        )
        prod_stack = NovascanStack(
            app,
            "novascan-prod",
            stage="prod",
            config=prod_config,
            env=cdk.Environment(account="123456789012", region="us-east-1"),
        )

        assert dev_stack.stack_name != prod_stack.stack_name, (
            "Dev and prod stacks must have different names for resource isolation"
        )
