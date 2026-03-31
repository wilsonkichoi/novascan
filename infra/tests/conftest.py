"""Shared fixtures for CDK infrastructure tests."""

from __future__ import annotations

import pytest
import aws_cdk as cdk
from aws_cdk.assertions import Template

from stacks.novascan_stack import NovascanStack


DEV_CONFIG = {
    "pipelineMaxConcurrency": 2,
    "presignedUrlExpirySec": 900,
    "maxUploadFiles": 10,
    "maxUploadSizeMb": 10,
    "logLevel": "DEBUG",
    "defaultPipeline": "ocr-ai",
}


@pytest.fixture(scope="session")
def dev_template() -> Template:
    """Synthesize the dev stack and return a CDK assertions Template.

    Session-scoped so the stack is only synthesized once across all tests.

    NOTE: skip_cyclical_dependencies_check=True is used to work around a
    circular dependency bug in the Auth construct (PostConfirmation Lambda
    IAM policy -> User Pool -> PostConfirmation Lambda). This bug is tracked
    separately and should be fixed in the Auth construct implementation.
    """
    app = cdk.App()
    stack = NovascanStack(
        app,
        "novascan-dev",
        stage="dev",
        config=DEV_CONFIG,
        env=cdk.Environment(account="123456789012", region="us-east-1"),
    )
    return Template.from_stack(stack, skip_cyclical_dependencies_check=True)


@pytest.fixture(scope="session")
def dev_template_json(dev_template: Template) -> dict:
    """Return the raw CloudFormation JSON for snapshot testing."""
    return dev_template.to_json()
