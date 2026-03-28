#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.novascan_stack import NovascanStack

app = cdk.App()

stage = app.node.try_get_context("stage")
if not stage:
    raise ValueError("Missing required context: -c stage=dev|prod")

config = app.node.try_get_context("config")
if not config or stage not in config:
    raise ValueError(f"Missing config for stage '{stage}' in cdk.json context")

stage_config = config[stage]

NovascanStack(
    app,
    f"novascan-{stage}",
    stage=stage,
    config=stage_config,
    env=cdk.Environment(
        account="<YOUR-AWS-ACCOUNT-ID>",
        region="us-east-1",
    ),
)

app.synth()
