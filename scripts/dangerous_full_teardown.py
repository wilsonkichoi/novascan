# /// script
# requires-python = ">=3.13"
# dependencies = ["boto3"]
# ///
"""Full teardown of a NovaScan stage, including retained resources.

CDK destroy leaves prod resources with RemovalPolicy.RETAIN:
  - DynamoDB table (deletion_protection must be disabled first)
  - S3 frontend bucket
  - S3 receipts bucket
  - Cognito User Pool

This script:
  1. Fetches stack outputs to discover resource names
  2. Runs `cdk destroy` to remove the CloudFormation stack
  3. Deletes the retained resources that CDK left behind

Usage:
  uv run scripts/teardown.py dev
  uv run scripts/teardown.py prod
  uv run scripts/teardown.py prod --yes   # skip confirmation
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", "us-east-1"))
STACK_PREFIX = "novascan"
REPO_ROOT = Path(__file__).resolve().parent.parent


def get_stack_outputs(stage: str) -> dict[str, str] | None:
    """Query CloudFormation stack outputs. Returns None if stack doesn't exist."""
    cfn = boto3.client("cloudformation", region_name=REGION)
    stack_name = f"{STACK_PREFIX}-{stage}"
    try:
        resp = cfn.describe_stacks(StackName=stack_name)
    except ClientError:
        return None
    outputs = {}
    for o in resp["Stacks"][0].get("Outputs", []):
        outputs[o["OutputKey"]] = o["OutputValue"]
    return outputs


def empty_and_delete_bucket(bucket_name: str) -> None:
    """Empty all objects (including versions) and delete an S3 bucket."""
    s3 = boto3.resource("s3", region_name=REGION)
    bucket = s3.Bucket(bucket_name)
    try:
        bucket.load()
    except ClientError:
        print(f"  Bucket {bucket_name} not found, skipping")
        return
    print(f"  Emptying {bucket_name}...")
    bucket.object_versions.all().delete()
    bucket.objects.all().delete()
    bucket.delete()
    print(f"  Deleted {bucket_name}")


def delete_dynamodb_table(table_name: str) -> None:
    """Disable deletion protection and delete a DynamoDB table."""
    dynamodb = boto3.client("dynamodb", region_name=REGION)
    try:
        dynamodb.describe_table(TableName=table_name)
    except ClientError:
        print(f"  Table {table_name} not found, skipping")
        return
    print(f"  Disabling deletion protection on {table_name}...")
    dynamodb.update_table(
        TableName=table_name,
        DeletionProtectionEnabled=False,
    )
    waiter = dynamodb.get_waiter("table_exists")
    waiter.wait(TableName=table_name)
    print(f"  Deleting {table_name}...")
    dynamodb.delete_table(TableName=table_name)
    print(f"  Deleted {table_name}")


def delete_user_pool(user_pool_id: str) -> None:
    """Delete a Cognito User Pool."""
    cognito = boto3.client("cognito-idp", region_name=REGION)
    try:
        cognito.describe_user_pool(UserPoolId=user_pool_id)
    except ClientError:
        print(f"  User Pool {user_pool_id} not found, skipping")
        return
    # Must delete the domain first if one exists
    try:
        resp = cognito.describe_user_pool(UserPoolId=user_pool_id)
        domain = resp["UserPool"].get("Domain")
        if domain:
            print(f"  Deleting Cognito domain {domain}...")
            cognito.delete_user_pool_domain(UserPoolDomain=domain, UserPoolId=user_pool_id)
    except ClientError:
        pass
    print(f"  Deleting User Pool {user_pool_id}...")
    cognito.delete_user_pool(UserPoolId=user_pool_id)
    print(f"  Deleted {user_pool_id}")


def run_cdk_destroy(stage: str) -> bool:
    """Run cdk destroy. Returns True if successful."""
    print(f"\n==> Running cdk destroy for {STACK_PREFIX}-{stage}...")
    result = subprocess.run(
        ["uv", "run", "cdk", "destroy", "--context", f"stage={stage}", "--force"],
        cwd=REPO_ROOT / "infra",
    )
    return result.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Full teardown of a NovaScan stage")
    parser.add_argument("stage", choices=["dev", "prod"], help="Stage to tear down")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    stage = args.stage
    outputs = get_stack_outputs(stage)

    if outputs is None:
        print(f"Stack {STACK_PREFIX}-{stage} not found. Nothing to tear down.")
        sys.exit(0)

    table_name = f"{STACK_PREFIX}-{stage}"
    receipts_bucket = outputs.get("ReceiptsBucketName", "")
    frontend_bucket = outputs.get("FrontendBucketName", "")
    user_pool_id = outputs.get("UserPoolId", "")

    print(f"\n=== Full Teardown: {STACK_PREFIX}-{stage} ===\n")
    print("This will permanently delete:")
    print(f"  CloudFormation stack: {STACK_PREFIX}-{stage}")
    print(f"  DynamoDB table:       {table_name}")
    print(f"  S3 bucket:            {receipts_bucket}")
    print(f"  S3 bucket:            {frontend_bucket}")
    print(f"  Cognito User Pool:    {user_pool_id}")
    print("\n  WARNING: All data will be lost. There is no recovery.\n")

    if not args.yes:
        confirm = input(f"Destroy {stage}? Type 'yes' to confirm: ").strip()
        if confirm != "yes":
            print("Aborted.")
            sys.exit(0)

    # Step 1: cdk destroy (removes the stack and non-retained resources)
    if not run_cdk_destroy(stage):
        print("ERROR: cdk destroy failed. Retained resources were NOT cleaned up.")
        sys.exit(1)

    # Step 2: Clean up retained resources (prod only — dev uses DESTROY policy)
    if stage == "prod":
        print("\n==> Cleaning up retained resources...\n")
        delete_dynamodb_table(table_name)
        empty_and_delete_bucket(receipts_bucket)
        empty_and_delete_bucket(frontend_bucket)
        delete_user_pool(user_pool_id)

    print(f"\n=== Teardown complete: {STACK_PREFIX}-{stage} ===")


if __name__ == "__main__":
    main()
