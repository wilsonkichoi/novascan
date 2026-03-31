"""Tests for the Storage construct against SPEC.md Section 5 (Database Schema).

Verifies:
- DynamoDB table key schema (PK/SK as strings)
- GSI1 key schema (GSI1PK/GSI1SK)
- Billing mode: PAY_PER_REQUEST (on-demand)
- Point-in-time recovery: enabled
- S3 receipt bucket exists with BlockPublicAccess

Spec references:
- Section 5: Database Schema
- Section 12: Security (S3 encryption, BlockPublicAccess)
"""

from __future__ import annotations

from aws_cdk.assertions import Match, Template


class TestDynamoDBTable:
    """DynamoDB table configuration per SPEC.md Section 5."""

    def test_table_exists(self, dev_template: Template) -> None:
        """At least one DynamoDB table must be created."""
        dev_template.resource_count_is("AWS::DynamoDB::Table", 1)

    def test_table_key_schema_has_pk_and_sk(self, dev_template: Template) -> None:
        """Table must have PK (HASH) and SK (RANGE) as the key schema.

        Spec: 'PK' is partition key, 'SK' is sort key.
        """
        dev_template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "KeySchema": Match.array_with(
                    [
                        {"AttributeName": "PK", "KeyType": "HASH"},
                        {"AttributeName": "SK", "KeyType": "RANGE"},
                    ]
                ),
            },
        )

    def test_table_pk_and_sk_are_string_type(self, dev_template: Template) -> None:
        """PK and SK must be string (S) type attributes.

        Spec: PK = 'USER#{userId}', SK varies by entity -- all string patterns.
        """
        dev_template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "AttributeDefinitions": Match.array_with(
                    [
                        {"AttributeName": "PK", "AttributeType": "S"},
                        {"AttributeName": "SK", "AttributeType": "S"},
                    ]
                ),
            },
        )

    def test_gsi1_exists_with_correct_key_schema(
        self, dev_template: Template
    ) -> None:
        """GSI1 must exist with GSI1PK (HASH) and GSI1SK (RANGE).

        Spec Section 5: 'Global Secondary Index: GSI1 (Receipts by Date)'
        GSI1PK = USER#{userId}, GSI1SK = {receiptDate}#{ulid}
        """
        dev_template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "GlobalSecondaryIndexes": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "KeySchema": [
                                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                                ],
                            }
                        )
                    ]
                ),
            },
        )

    def test_gsi1_keys_are_string_type(self, dev_template: Template) -> None:
        """GSI1PK and GSI1SK must be string (S) type attributes."""
        dev_template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "AttributeDefinitions": Match.array_with(
                    [
                        {"AttributeName": "GSI1PK", "AttributeType": "S"},
                        {"AttributeName": "GSI1SK", "AttributeType": "S"},
                    ]
                ),
            },
        )

    def test_gsi1_projection_is_all(self, dev_template: Template) -> None:
        """GSI1 projection must be ALL.

        Spec Section 5: 'Projection: ALL (project all receipt attributes into GSI)'
        """
        dev_template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "GlobalSecondaryIndexes": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "KeySchema": [
                                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                                ],
                                "Projection": {"ProjectionType": "ALL"},
                            }
                        )
                    ]
                ),
            },
        )

    def test_billing_mode_is_on_demand(self, dev_template: Template) -> None:
        """Table must use PAY_PER_REQUEST (on-demand) billing mode.

        Spec Section 5: 'Billing mode: Pay-per-request (on-demand)'
        """
        dev_template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {"BillingMode": "PAY_PER_REQUEST"},
        )

    def test_point_in_time_recovery_enabled(self, dev_template: Template) -> None:
        """PITR must be enabled.

        Spec Section 5: 'Point-in-time recovery: Enabled'
        Spec Section 12: 'DynamoDB point-in-time recovery enabled'
        """
        dev_template.has_resource_properties(
            "AWS::DynamoDB::Table",
            {
                "PointInTimeRecoverySpecification": {
                    "PointInTimeRecoveryEnabled": True,
                },
            },
        )


class TestS3Buckets:
    """S3 bucket configuration per SPEC.md."""

    def test_receipt_bucket_blocks_public_access(
        self, dev_template: Template
    ) -> None:
        """Receipt image bucket must block all public access.

        Spec Section 12: 'S3 receipt bucket: private, no public access,
        BlockPublicAccess enabled'
        """
        # At least one S3 bucket should have BlockPublicAccessConfiguration
        # set to block everything.
        dev_template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
            },
        )
