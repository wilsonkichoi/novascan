from typing import Any

import aws_cdk as cdk
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_s3 as s3
from constructs import Construct


class StorageConstruct(Construct):
    def __init__(
        self, scope: Construct, id: str, *, stage: str, config: dict[str, Any], **kwargs: Any
    ) -> None:
        super().__init__(scope, id, **kwargs)

        is_prod = stage == "prod"

        # --- DynamoDB Single Table ---
        self.table = dynamodb.Table(
            self,
            "Table",
            table_name=f"novascan-{stage}",
            partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True,
            ),
            deletion_protection=is_prod,
            removal_policy=cdk.RemovalPolicy.RETAIN if is_prod else cdk.RemovalPolicy.DESTROY,
            encryption=dynamodb.TableEncryption.DEFAULT,
        )

        # GSI1: Receipts by date — sparse index (only RECEIPT entities carry GSI1PK/GSI1SK)
        self.table.add_global_secondary_index(
            index_name="GSI1",
            partition_key=dynamodb.Attribute(name="GSI1PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="GSI1SK", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # GSI2: Receipt lookup by receiptId — used by pipeline to resolve userId
        # from receiptId without a full table scan (SECURITY-REVIEW C2).
        # KEYS_ONLY projection: we only need PK to extract userId.
        self.table.add_global_secondary_index(
            index_name="GSI2",
            partition_key=dynamodb.Attribute(name="GSI2PK", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.KEYS_ONLY,
        )

        # --- S3 Frontend Assets Bucket ---
        self.frontend_bucket = s3.Bucket(
            self,
            "FrontendBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=cdk.RemovalPolicy.RETAIN if is_prod else cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=not is_prod,
        )

        # --- S3 Receipts Bucket ---
        # L2 — TODO: Upgrade to CUSTOMER_MANAGED encryption with KMS key + rotation
        # for production use. Deferred for personal MVP (~$1/month + complexity).
        # To upgrade: change encryption to BucketEncryption.KMS_MANAGED or
        # provide an explicit KMS key with auto-rotation enabled.
        self.receipts_bucket = s3.Bucket(
            self,
            "ReceiptsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            removal_policy=cdk.RemovalPolicy.RETAIN if is_prod else cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=not is_prod,
            # M3 — S3 lifecycle rules for cost optimization
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="InfrequentAccessAt90Days",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=cdk.Duration.days(90),
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=cdk.Duration.days(365),
                        ),
                    ],
                    expiration=cdk.Duration.days(2555),  # ~7 years
                ),
            ],
        )

    @property
    def table_name(self) -> str:
        return self.table.table_name

    @property
    def table_arn(self) -> str:
        return self.table.table_arn

    @property
    def receipts_bucket_name(self) -> str:
        return self.receipts_bucket.bucket_name
