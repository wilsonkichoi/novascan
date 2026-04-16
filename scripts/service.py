# /// script
# requires-python = ">=3.13"
# dependencies = ["boto3"]
# ///
"""NovaScan service pause/resume/status script.

Manages all service components for a given stage:
  - CloudFront distribution (disable/enable)
  - API Gateway HTTP API stage (disable/enable)
  - EventBridge Pipe (stop/start)
  - Cognito self-service sign-up (disable/enable)

Usage:
  uv run scripts/service.py pause prod
  uv run scripts/service.py resume dev
  uv run scripts/service.py status prod
  uv run scripts/service.py pause prod --yes  # skip confirmation
"""

from __future__ import annotations

import argparse
import os
import sys

import boto3

REGION = os.environ.get("AWS_DEFAULT_REGION", os.environ.get("AWS_REGION", "us-east-1"))
STACK_PREFIX = "novascan"


def get_stack_outputs(stage: str) -> dict[str, str]:
    """Query CloudFormation stack outputs for the given stage."""
    cfn = boto3.client("cloudformation", region_name=REGION)
    stack_name = f"{STACK_PREFIX}-{stage}"
    try:
        resp = cfn.describe_stacks(StackName=stack_name)
    except cfn.exceptions.ClientError as e:
        print(f"ERROR: Stack '{stack_name}' not found: {e}")
        sys.exit(1)
    outputs = {}
    for o in resp["Stacks"][0].get("Outputs", []):
        outputs[o["OutputKey"]] = o["OutputValue"]
    return outputs


def get_api_id(stage: str) -> str:
    """Find the API Gateway HTTP API ID by name."""
    apigw = boto3.client("apigatewayv2", region_name=REGION)
    api_name = f"{STACK_PREFIX}-{stage}"
    apis = apigw.get_apis()["Items"]
    for api in apis:
        if api["Name"] == api_name:
            return api["ApiId"]
    print(f"ERROR: API Gateway '{api_name}' not found")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CloudFront
# ---------------------------------------------------------------------------

def cloudfront_status(distribution_id: str) -> str:
    cf = boto3.client("cloudfront", region_name=REGION)
    dist = cf.get_distribution(Id=distribution_id)
    enabled = dist["Distribution"]["DistributionConfig"]["Enabled"]
    status = dist["Distribution"]["Status"]
    return f"{'Enabled' if enabled else 'Disabled'} (Status: {status})"


def cloudfront_set_enabled(distribution_id: str, enabled: bool) -> None:
    cf = boto3.client("cloudfront", region_name=REGION)
    dist = cf.get_distribution(Id=distribution_id)
    config = dist["Distribution"]["DistributionConfig"]
    etag = dist["ETag"]
    if config["Enabled"] == enabled:
        state = "enabled" if enabled else "disabled"
        print(f"  CloudFront {distribution_id} already {state}, skipping")
        return
    config["Enabled"] = enabled
    cf.update_distribution(DistributionConfig=config, Id=distribution_id, IfMatch=etag)
    action = "Enabling" if enabled else "Disabling"
    print(f"  {action} CloudFront {distribution_id} (propagation takes a few minutes)")


# ---------------------------------------------------------------------------
# API Gateway
# ---------------------------------------------------------------------------

def apigw_status(api_id: str) -> str:
    apigw = boto3.client("apigatewayv2", region_name=REGION)
    stages = apigw.get_stages(ApiId=api_id)["Items"]
    for s in stages:
        if s["StageName"] == "$default":
            settings = s.get("DefaultRouteSettings", {})
            burst = settings.get("ThrottlingBurstLimit")
            rate = settings.get("ThrottlingRateLimit")
            if burst == 0 and rate == 0:
                return f"Throttled to 0 (paused) — API ID: {api_id}"
            return f"Active (burst={burst}, rate={rate}) — API ID: {api_id}"
    return f"No $default stage found — API ID: {api_id}"


def apigw_set_throttle(api_id: str, burst: int, rate: float) -> None:
    apigw = boto3.client("apigatewayv2", region_name=REGION)
    apigw.update_stage(
        ApiId=api_id,
        StageName="$default",
        DefaultRouteSettings={
            "ThrottlingBurstLimit": burst,
            "ThrottlingRateLimit": rate,
        },
    )
    if burst == 0:
        print(f"  API Gateway {api_id} throttled to 0 (paused)")
    else:
        print(f"  API Gateway {api_id} throttle set to burst={burst}, rate={rate}")


# ---------------------------------------------------------------------------
# EventBridge Pipe
# ---------------------------------------------------------------------------

def pipe_status(stage: str) -> str:
    pipes = boto3.client("pipes", region_name=REGION)
    pipe_name = f"{STACK_PREFIX}-{stage}-receipt-pipe"
    try:
        resp = pipes.describe_pipe(Name=pipe_name)
        return f"{resp['CurrentState']} (DesiredState: {resp['DesiredState']})"
    except pipes.exceptions.NotFoundException:
        return "Not found"


def pipe_set_state(stage: str, desired: str) -> None:
    pipes = boto3.client("pipes", region_name=REGION)
    pipe_name = f"{STACK_PREFIX}-{stage}-receipt-pipe"
    try:
        resp = pipes.describe_pipe(Name=pipe_name)
        current = resp["CurrentState"]
        if desired == "STOPPED" and current in ("STOPPED", "STOPPING"):
            print(f"  Pipe {pipe_name} already {current}, skipping")
            return
        if desired == "RUNNING" and current in ("RUNNING", "STARTING"):
            print(f"  Pipe {pipe_name} already {current}, skipping")
            return
        if desired == "STOPPED":
            pipes.stop_pipe(Name=pipe_name)
            print(f"  Stopping pipe {pipe_name}")
        else:
            pipes.start_pipe(Name=pipe_name)
            print(f"  Starting pipe {pipe_name}")
    except pipes.exceptions.NotFoundException:
        print(f"  Pipe {pipe_name} not found, skipping")


# ---------------------------------------------------------------------------
# Cognito
# ---------------------------------------------------------------------------

def cognito_status(user_pool_id: str) -> str:
    cognito = boto3.client("cognito-idp", region_name=REGION)
    resp = cognito.describe_user_pool(UserPoolId=user_pool_id)
    policies = resp["UserPool"].get("Policies", {})
    signup = policies.get("SignUpPolicy", {})
    allowed = signup.get("AllowedFirstAuthFactors")
    # Check AdminCreateUserConfig for self-registration
    admin_config = resp["UserPool"].get("AdminCreateUserConfig", {})
    allow_self = admin_config.get("AllowAdminCreateUserOnly", False)
    if allow_self:
        return "Self-service sign-up: Disabled (admin-only)"
    return "Self-service sign-up: Enabled"


def cognito_set_signup(user_pool_id: str, allow_self_signup: bool) -> None:
    cognito = boto3.client("cognito-idp", region_name=REGION)
    cognito.update_user_pool(
        UserPoolId=user_pool_id,
        AdminCreateUserConfig={
            "AllowAdminCreateUserOnly": not allow_self_signup,
        },
    )
    state = "Enabled" if allow_self_signup else "Disabled"
    print(f"  Cognito {user_pool_id} self-service sign-up: {state}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

# Default throttle values matching CDK config (infra/cdkconstructs/api.py M5)
API_DEFAULT_BURST = 10
API_DEFAULT_RATE = 5.0


def cmd_status(stage: str) -> None:
    print(f"\n=== NovaScan {stage} Service Status ===\n")
    outputs = get_stack_outputs(stage)

    distribution_id = outputs.get("DistributionId", "")
    user_pool_id = outputs.get("UserPoolId", "")
    api_id = get_api_id(stage)

    print(f"CloudFront:  {cloudfront_status(distribution_id)}")
    print(f"API Gateway: {apigw_status(api_id)}")
    print(f"Pipe:        {pipe_status(stage)}")
    print(f"Cognito:     {cognito_status(user_pool_id)}")
    print()


def cmd_pause(stage: str, yes: bool) -> None:
    print(f"\n=== Pausing NovaScan {stage} ===\n")
    outputs = get_stack_outputs(stage)
    distribution_id = outputs.get("DistributionId", "")
    api_id = get_api_id(stage)

    print("This will:")
    print(f"  1. Disable CloudFront distribution ({distribution_id})")
    print(f"  2. Throttle API Gateway to 0 ({api_id})")
    print(f"  3. Stop EventBridge Pipe ({STACK_PREFIX}-{stage}-receipt-pipe)")
    print()

    if not yes:
        confirm = input(f"Pause {stage}? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    print("\nStep 1/3: CloudFront")
    cloudfront_set_enabled(distribution_id, False)

    print("Step 2/3: API Gateway")
    apigw_set_throttle(api_id, 0, 0)

    print("Step 3/3: EventBridge Pipe")
    pipe_set_state(stage, "STOPPED")

    print(f"\nDone. NovaScan {stage} is paused.")
    print("Note: CloudFront disable takes a few minutes to propagate.")


def cmd_resume(stage: str, yes: bool) -> None:
    print(f"\n=== Resuming NovaScan {stage} ===\n")
    outputs = get_stack_outputs(stage)
    distribution_id = outputs.get("DistributionId", "")
    api_id = get_api_id(stage)

    print("This will:")
    print(f"  1. Start EventBridge Pipe ({STACK_PREFIX}-{stage}-receipt-pipe)")
    print(f"  2. Restore API Gateway throttle ({api_id})")
    print(f"  3. Enable CloudFront distribution ({distribution_id})")
    print()

    if not yes:
        confirm = input(f"Resume {stage}? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    print("\nStep 1/3: EventBridge Pipe")
    pipe_set_state(stage, "RUNNING")

    print("Step 2/3: API Gateway")
    apigw_set_throttle(api_id, API_DEFAULT_BURST, API_DEFAULT_RATE)

    print("Step 3/3: CloudFront")
    cloudfront_set_enabled(distribution_id, True)

    print(f"\nDone. NovaScan {stage} is resuming.")
    print("Note: CloudFront enable takes a few minutes to propagate.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pause, resume, or check status of NovaScan services",
    )
    parser.add_argument(
        "action",
        choices=["pause", "resume", "status"],
        help="Action to perform",
    )
    parser.add_argument(
        "stage",
        choices=["dev", "prod"],
        help="Target stage",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    if args.action == "status":
        cmd_status(args.stage)
    elif args.action == "pause":
        cmd_pause(args.stage, args.yes)
    elif args.action == "resume":
        cmd_resume(args.stage, args.yes)


if __name__ == "__main__":
    main()
