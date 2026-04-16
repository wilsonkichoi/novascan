#!/usr/bin/env python3
"""Deploy script for NovaScan frontend, backend, or both."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VALID_STAGES = ("dev", "prod")
VALID_TARGETS = ("frontend", "backend", "all")


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """Run a command, streaming output. Exit on failure."""
    import os

    full_env = {**os.environ, **(env or {})}
    result = subprocess.run(cmd, cwd=cwd, env=full_env)
    if result.returncode != 0:
        sys.exit(result.returncode)


def get_stack_outputs(stage: str) -> dict[str, str]:
    """Query CloudFormation for live stack outputs."""
    stack_name = f"novascan-{stage}"
    print(f"==> Fetching stack outputs from CloudFormation ({stack_name})...")
    result = subprocess.run(
        ["aws", "cloudformation", "describe-stacks", "--stack-name", stack_name,
         "--query", "Stacks[0].Outputs", "--output", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(
            f"Error: could not describe stack '{stack_name}'. "
            f"Is the stack deployed?\n{result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)
    raw = json.loads(result.stdout)
    return {item["OutputKey"]: item["OutputValue"] for item in raw}


def deploy_backend(stage: str) -> None:
    print(f"==> Deploying backend/infra ({stage})...")
    run(
        ["uv", "run", "cdk", "deploy", "--context", f"stage={stage}",
         "--outputs-file", f"cdk-outputs-{stage}.json"],
        cwd=REPO_ROOT / "infra",
    )
    print("==> Backend deploy complete.")


def deploy_frontend(stage: str) -> None:
    outputs = get_stack_outputs(stage)

    print(f"==> Building frontend ({stage})...")
    run(
        ["npm", "run", "build"],
        cwd=REPO_ROOT / "frontend",
        env={
            "VITE_API_URL": outputs["ApiUrl"],
            "VITE_COGNITO_USER_POOL_ID": outputs["UserPoolId"],
            "VITE_COGNITO_CLIENT_ID": outputs["AppClientId"],
            "VITE_AWS_REGION": "us-east-1",
        },
    )

    bucket = outputs["FrontendBucketName"]
    print(f"==> Syncing to S3 ({bucket})...")
    run(
        ["aws", "s3", "sync", str(REPO_ROOT / "frontend" / "dist"),
         f"s3://{bucket}/", "--delete"],
    )

    distribution_id = outputs["DistributionId"]
    print(f"==> Invalidating CloudFront ({distribution_id})...")
    run(
        ["aws", "cloudfront", "create-invalidation",
         "--distribution-id", distribution_id, "--paths", "/*"],
    )

    print("==> Frontend deploy complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy NovaScan")
    parser.add_argument("target", choices=VALID_TARGETS,
                        help="What to deploy: frontend, backend, or all")
    parser.add_argument("stage", choices=VALID_STAGES,
                        help="Deployment stage: dev or prod")
    args = parser.parse_args()

    if args.target in ("backend", "all"):
        deploy_backend(args.stage)
    if args.target in ("frontend", "all"):
        deploy_frontend(args.stage)


if __name__ == "__main__":
    main()
