# /// script
# requires-python = ">=3.13"
# dependencies = ["boto3"]
# ///
"""NovaScan admin user creation script.

Creates a new user in the Cognito User Pool and assigns them to a group.
The user receives an email invitation from Cognito.

Usage:
  cd infra && uv run scripts/add_user.py --stage prod --email user@example.com
  cd infra && uv run scripts/add_user.py --stage dev --email admin@example.com --group admin
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import boto3

REGION = os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", "us-east-1"))
STACK_PREFIX = "novascan"
VALID_GROUPS = ("user", "staff", "admin")


def get_user_pool_id(stage: str) -> str:
    """Read UserPoolId from CDK outputs file, falling back to CloudFormation."""
    outputs_file = Path(__file__).parent.parent / f"cdk-outputs-{stage}.json"
    if outputs_file.exists():
        with open(outputs_file) as f:
            data = json.load(f)
        stack_key = f"{STACK_PREFIX}-{stage}"
        pool_id = data.get(stack_key, {}).get("UserPoolId")
        if pool_id:
            return pool_id

    # Fallback: query CloudFormation directly
    cfn = boto3.client("cloudformation", region_name=REGION)
    stack_name = f"{STACK_PREFIX}-{stage}"
    try:
        resp = cfn.describe_stacks(StackName=stack_name)
    except cfn.exceptions.ClientError as e:
        print(f"ERROR: Stack '{stack_name}' not found: {e}")
        sys.exit(1)
    for o in resp["Stacks"][0].get("Outputs", []):
        if o["OutputKey"] == "UserPoolId":
            return o["OutputValue"]
    print(f"ERROR: UserPoolId not found in stack '{stack_name}' outputs")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a NovaScan user")
    parser.add_argument("--stage", required=True, choices=["dev", "prod"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--group", default="user", choices=VALID_GROUPS)
    args = parser.parse_args()

    user_pool_id = get_user_pool_id(args.stage)
    cognito = boto3.client("cognito-idp", region_name=REGION)

    print(f"Creating user {args.email} in {args.stage} (pool: {user_pool_id})")

    try:
        cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=args.email,
            UserAttributes=[
                {"Name": "email", "Value": args.email},
                {"Name": "email_verified", "Value": "true"},
            ],
            DesiredDeliveryMediums=["EMAIL"],
        )
    except cognito.exceptions.UsernameExistsException:
        print(f"User {args.email} already exists — skipping creation.")
    except Exception as e:
        print(f"ERROR creating user: {e}")
        sys.exit(1)

    try:
        cognito.admin_add_user_to_group(
            UserPoolId=user_pool_id,
            Username=args.email,
            GroupName=args.group,
        )
    except Exception as e:
        print(f"ERROR adding user to group: {e}")
        sys.exit(1)

    print(f"Done. {args.email} added to '{args.group}' group.")
    print("The user will receive an email invitation from Cognito.")


if __name__ == "__main__":
    main()
