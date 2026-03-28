"""Shared pytest fixtures for backend tests.

Sets up AWS credential mocking and moto-based service fixtures
for DynamoDB and S3.
"""

import boto3
import pytest
from moto import mock_aws


@pytest.fixture(autouse=True)
def _aws_env(monkeypatch):
    """Mock AWS credentials and region for all tests.

    This runs automatically for every test to prevent accidental
    calls to real AWS services.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("TABLE_NAME", "novascan-test")


@pytest.fixture
def dynamodb_table():
    """Create a moto-mocked DynamoDB table matching the NovaScan schema.

    Yields the boto3 Table resource. The table is torn down automatically
    when the mock context exits.
    """
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
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
        table.meta.client.get_waiter("table_exists").wait(TableName="novascan-test")
        yield table


@pytest.fixture
def s3_bucket():
    """Create a moto-mocked S3 bucket for receipt image storage.

    Yields the bucket name. The bucket is torn down automatically
    when the mock context exits.
    """
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "novascan-receipts-test"
        s3.create_bucket(Bucket=bucket_name)
        yield bucket_name
