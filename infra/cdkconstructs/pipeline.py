"""Pipeline construct: SQS, EventBridge Pipes, Step Functions, and pipeline Lambdas.

Creates:
- SQS queue (receives S3 ObjectCreated events from receipts bucket)
- S3 event notification on receipts bucket for receipts/ prefix -> SQS
- EventBridge Pipe: SQS -> Step Functions (with input transformer)
- Step Functions state machine (LoadCustomCategories -> Parallel -> Finalize)
- Five pipeline Lambda functions (load_custom_categories, textract_extract,
  nova_structure, bedrock_extract, finalize)
- IAM roles for EventBridge Pipe and all Lambdas

See: SPEC.md Section 3 (Processing Flow), Section 4 (Pipeline State Machine).

Note on concurrency: Neither EventBridge Pipes (SQS source) nor Step Functions
expose a max-concurrent-executions setting as of 2026-04. Pipeline concurrency
is unbounded — acceptable at MVP scale. Textract throttling (5 TPS limit) is
handled via Step Functions retry config on the TextractExtract step.
"""

import json
import pathlib
import shutil
import subprocess
import tempfile
from typing import Any

import aws_cdk as cdk
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_logs as logs
import aws_cdk.aws_pipes as pipes
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_s3_notifications as s3n
import aws_cdk.aws_sqs as sqs
import aws_cdk.aws_stepfunctions as sfn
import aws_cdk.aws_stepfunctions_tasks as tasks
import jsii
from constructs import Construct

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "backend"


# ---------------------------------------------------------------------------
# Lambda bundling (reusable pattern from api.py)
# ---------------------------------------------------------------------------

@jsii.implements(cdk.ILocalBundling)
class _UvLocalBundling:
    """Bundles pipeline Lambda locally using uv."""

    def __init__(self, backend_dir: pathlib.Path) -> None:
        self._backend_dir = backend_dir

    def try_bundle(self, output_dir: str, *args: Any, **kwargs: Any) -> bool:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                req_file = f"{tmp}/requirements.txt"
                subprocess.run(
                    ["uv", "export", "--frozen", "--no-dev", "--no-editable", "-o", req_file],
                    cwd=self._backend_dir,
                    check=True,
                    capture_output=True,
                )
                subprocess.run(
                    [
                        "uv", "pip", "install", "--no-cache",
                        "--python-platform", "manylinux2014_x86_64",
                        "--python-version", "3.13",
                        "-r", req_file, "--target", output_dir,
                    ],
                    cwd=self._backend_dir,
                    check=True,
                    capture_output=True,
                )
            # Copy all pipeline code — pipeline Lambdas import from novascan.*
            shutil.copytree(
                self._backend_dir / "src" / "novascan",
                output_dir,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("auth", "api", "__pycache__"),
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False


def _pipeline_lambda_code() -> lambda_.Code:
    """Build Lambda code asset for pipeline functions."""
    return lambda_.Code.from_asset(
        str(BACKEND_DIR),
        bundling=cdk.BundlingOptions(
            image=cdk.DockerImage.from_registry(
                "ghcr.io/astral-sh/uv:python3.13-bookworm-slim"
            ),
            command=[
                "bash",
                "-c",
                "uv export --frozen --no-dev --no-editable -o /tmp/requirements.txt && "
                "uv pip install --no-cache -r /tmp/requirements.txt --target /asset-output && "
                "cp -au src/novascan/. /asset-output/ && "
                "rm -rf /asset-output/auth /asset-output/api /asset-output/__pycache__",
            ],
            local=_UvLocalBundling(BACKEND_DIR),
        ),
    )


# ---------------------------------------------------------------------------
# Pipeline Construct
# ---------------------------------------------------------------------------

class PipelineConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        stage: str,
        config: dict[str, Any],
        table: dynamodb.ITable,
        receipts_bucket: s3.IBucket,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self._stage = stage
        self._config = config

        # --- SQS Dead Letter Queue for poison messages ---
        self.dlq = sqs.Queue(
            self,
            "ReceiptDLQ",
            queue_name=f"novascan-{stage}-receipt-pipeline-dlq",
            retention_period=cdk.Duration.days(14),
            enforce_ssl=True,
        )

        # --- SQS Queue for S3 event notifications ---
        self.queue = sqs.Queue(
            self,
            "ReceiptQueue",
            queue_name=f"novascan-{stage}-receipt-pipeline",
            visibility_timeout=cdk.Duration.seconds(900),
            retention_period=cdk.Duration.days(4),
            enforce_ssl=True,
            dead_letter_queue=sqs.DeadLetterQueue(
                queue=self.dlq,
                max_receive_count=3,
            ),
        )

        # Allow S3 to send messages to this queue
        self.queue.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("s3.amazonaws.com")],
                actions=["sqs:SendMessage"],
                resources=[self.queue.queue_arn],
                conditions={
                    "ArnLike": {
                        "aws:SourceArn": receipts_bucket.bucket_arn,
                    },
                },
            )
        )

        # --- S3 event notification: ObjectCreated on receipts/ prefix -> SQS ---
        receipts_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.SqsDestination(self.queue),
            s3.NotificationKeyFilter(prefix="receipts/"),
        )

        # --- Pipeline Lambda functions ---
        code = _pipeline_lambda_code()

        common_lambda_props = {
            "runtime": lambda_.Runtime.PYTHON_3_13,
            "code": code,
            "timeout": cdk.Duration.seconds(120),
            "memory_size": 512,
            "tracing": lambda_.Tracing.ACTIVE,
            "environment": {
                "TABLE_NAME": table.table_name,
                "LOG_LEVEL": config.get("logLevel", "INFO"),
                "STAGE": stage,
                "POWERTOOLS_LOG_LEVEL": config.get("logLevel", "INFO"),
            },
        }

        self.load_custom_categories_fn = lambda_.Function(
            self,
            "LoadCustomCategoriesFn",
            function_name=f"novascan-{stage}-load-custom-categories",
            handler="pipeline.load_custom_categories.handler",
            description="Pipeline: load user's custom categories from DynamoDB",
            environment={
                **common_lambda_props["environment"],
                "POWERTOOLS_SERVICE_NAME": "novascan-load-custom-categories",
                "RECEIPTS_BUCKET": receipts_bucket.bucket_name,
            },
            **{k: v for k, v in common_lambda_props.items() if k != "environment"},
        )
        # Scoped IAM: only Query (for GSI2 lookup) and GetItem (for custom
        # categories) — no Scan permission (SECURITY-REVIEW M13).
        self.load_custom_categories_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:Query", "dynamodb:GetItem"],
                resources=[
                    table.table_arn,
                    f"{table.table_arn}/index/*",
                ],
            )
        )

        self.textract_extract_fn = lambda_.Function(
            self,
            "TextractExtractFn",
            function_name=f"novascan-{stage}-textract-extract",
            handler="pipeline.textract_extract.handler",
            description="Pipeline: extract expense data via Textract AnalyzeExpense",
            environment={
                **common_lambda_props["environment"],
                "POWERTOOLS_SERVICE_NAME": "novascan-textract-extract",
                "RECEIPTS_BUCKET": receipts_bucket.bucket_name,
            },
            **{k: v for k, v in common_lambda_props.items() if k != "environment"},
        )
        # Textract needs S3 read + Textract permissions
        receipts_bucket.grant_read(self.textract_extract_fn)
        self.textract_extract_fn.add_to_role_policy(
            iam.PolicyStatement(
                # M9 — Textract does not support resource-level permissions.
                # resources=["*"] is required per AWS documentation:
                # https://docs.aws.amazon.com/textract/latest/dg/security_iam_service-with-iam.html
                actions=["textract:AnalyzeExpense"],
                resources=["*"],
            )
        )

        self.nova_structure_fn = lambda_.Function(
            self,
            "NovaStructureFn",
            function_name=f"novascan-{stage}-nova-structure",
            handler="pipeline.nova_structure.handler",
            description="Pipeline: structure Textract output via Bedrock Nova",
            environment={
                **common_lambda_props["environment"],
                "POWERTOOLS_SERVICE_NAME": "novascan-nova-structure",
                "RECEIPTS_BUCKET": receipts_bucket.bucket_name,
            },
            **{k: v for k, v in common_lambda_props.items() if k != "environment"},
        )
        # Nova needs S3 read + Bedrock invoke
        receipts_bucket.grant_read(self.nova_structure_fn)
        self.nova_structure_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                # M10 — Bedrock ARN scoped to deployment region
                resources=[
                    f"arn:aws:bedrock:{cdk.Aws.REGION}::foundation-model/amazon.nova-lite-v1:0",
                    f"arn:aws:bedrock:{cdk.Aws.REGION}::foundation-model/amazon.nova-pro-v1:0",
                ],
            )
        )

        self.bedrock_extract_fn = lambda_.Function(
            self,
            "BedrockExtractFn",
            function_name=f"novascan-{stage}-bedrock-extract",
            handler="pipeline.bedrock_extract.handler",
            description="Pipeline: direct multimodal extraction via Bedrock Nova",
            environment={
                **common_lambda_props["environment"],
                "POWERTOOLS_SERVICE_NAME": "novascan-bedrock-extract",
                "RECEIPTS_BUCKET": receipts_bucket.bucket_name,
            },
            **{k: v for k, v in common_lambda_props.items() if k != "environment"},
        )
        # Bedrock extract needs S3 read + Bedrock invoke
        receipts_bucket.grant_read(self.bedrock_extract_fn)
        self.bedrock_extract_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                # M10 — Bedrock ARN scoped to deployment region
                resources=[
                    f"arn:aws:bedrock:{cdk.Aws.REGION}::foundation-model/amazon.nova-lite-v1:0",
                    f"arn:aws:bedrock:{cdk.Aws.REGION}::foundation-model/amazon.nova-pro-v1:0",
                ],
            )
        )

        self.finalize_fn = lambda_.Function(
            self,
            "FinalizeFn",
            function_name=f"novascan-{stage}-finalize",
            handler="pipeline.finalize.handler",
            description="Pipeline: finalize — select result, rank, persist to DynamoDB/S3",
            timeout=cdk.Duration.seconds(60),
            environment={
                **common_lambda_props["environment"],
                "POWERTOOLS_SERVICE_NAME": "novascan-finalize",
                "DEFAULT_PIPELINE": config.get("defaultPipeline", "ocr-ai"),
                "RECEIPTS_BUCKET": receipts_bucket.bucket_name,
            },
            **{
                k: v
                for k, v in common_lambda_props.items()
                if k not in ("environment", "timeout")
            },
        )
        # Finalize needs DynamoDB read/write, S3 read/write (copy_object), CloudWatch Metrics
        table.grant_read_write_data(self.finalize_fn)
        receipts_bucket.grant_read_write(self.finalize_fn)
        self.finalize_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "cloudwatch:namespace": "NovaScan",
                    },
                },
            )
        )

        # --- Step Functions State Machine ---
        self.state_machine = self._build_state_machine(stage)

        # --- EventBridge Pipe: SQS -> Step Functions ---
        self._build_pipe(stage, config)

    def _build_state_machine(self, stage: str) -> sfn.StateMachine:
        """Build the receipt processing state machine.

        Flow:
            LoadCustomCategories -> Parallel(Main, Shadow) -> Finalize
        """

        # Step 1: LoadCustomCategories
        load_categories = tasks.LambdaInvoke(
            self,
            "LoadCustomCategories",
            lambda_function=self.load_custom_categories_fn,
            payload_response_only=True,
            result_path="$",
        )

        # Step 2a: Main pipeline (OCR-AI) — TextractExtract -> NovaStructure
        textract_extract = tasks.LambdaInvoke(
            self,
            "TextractExtract",
            lambda_function=self.textract_extract_fn,
            payload=sfn.TaskInput.from_object({
                "bucket": sfn.JsonPath.string_at("$.bucket"),
                "key": sfn.JsonPath.string_at("$.key"),
            }),
            payload_response_only=True,
            result_path="$.textractResult",
        )
        textract_extract.add_retry(
            errors=["Textract.ThrottlingException", "Textract.ProvisionedThroughputExceededException"],
            interval=cdk.Duration.seconds(5),
            max_attempts=3,
            backoff_rate=2.0,
        )
        textract_extract.add_catch(
            handler=sfn.Pass(
                self,
                "TextractExtractError",
                result=sfn.Result.from_object({
                    "error": "TextractExtract failed",
                    "errorType": "CatchAll",
                }),
                result_path="$.textractResult",
            ),
            errors=["States.ALL"],
            result_path="$.textractResult",
        )

        nova_structure = tasks.LambdaInvoke(
            self,
            "NovaStructure",
            lambda_function=self.nova_structure_fn,
            payload=sfn.TaskInput.from_object({
                "textractResult": sfn.JsonPath.object_at("$.textractResult"),
                "bucket": sfn.JsonPath.string_at("$.bucket"),
                "key": sfn.JsonPath.string_at("$.key"),
                "customCategories": sfn.JsonPath.object_at("$.customCategories"),
            }),
            payload_response_only=True,
            result_path="$",
        )
        nova_structure.add_catch(
            handler=sfn.Pass(
                self,
                "NovaStructureError",
                result=sfn.Result.from_object({
                    "error": "NovaStructure failed",
                    "errorType": "CatchAll",
                }),
                result_path="$",
            ),
            errors=["States.ALL"],
            result_path="$",
        )

        main_branch = textract_extract.next(nova_structure)

        # Step 2b: Shadow pipeline (AI-multimodal) — BedrockExtract
        bedrock_extract = tasks.LambdaInvoke(
            self,
            "BedrockExtract",
            lambda_function=self.bedrock_extract_fn,
            payload=sfn.TaskInput.from_object({
                "bucket": sfn.JsonPath.string_at("$.bucket"),
                "key": sfn.JsonPath.string_at("$.key"),
                "customCategories": sfn.JsonPath.object_at("$.customCategories"),
            }),
            payload_response_only=True,
            result_path="$",
        )
        bedrock_extract.add_catch(
            handler=sfn.Pass(
                self,
                "BedrockExtractError",
                result=sfn.Result.from_object({
                    "error": "BedrockExtract failed",
                    "errorType": "CatchAll",
                }),
                result_path="$",
            ),
            errors=["States.ALL"],
            result_path="$",
        )

        shadow_branch = bedrock_extract

        # Parallel state — runs main and shadow concurrently
        parallel = sfn.Parallel(
            self,
            "ParallelPipelines",
            result_path="$.pipelineResults",
        )
        parallel.branch(main_branch)
        parallel.branch(shadow_branch)

        # Step 3: Finalize
        finalize = tasks.LambdaInvoke(
            self,
            "Finalize",
            lambda_function=self.finalize_fn,
            payload=sfn.TaskInput.from_object({
                "bucket": sfn.JsonPath.string_at("$.bucket"),
                "key": sfn.JsonPath.string_at("$.key"),
                "userId": sfn.JsonPath.string_at("$.userId"),
                "receiptId": sfn.JsonPath.string_at("$.receiptId"),
                "customCategories": sfn.JsonPath.object_at("$.customCategories"),
                "pipelineResults": sfn.JsonPath.object_at("$.pipelineResults"),
            }),
            payload_response_only=True,
        )

        # Chain: LoadCustomCategories -> Parallel -> Finalize
        definition = load_categories.next(parallel).next(finalize)

        sfn_log_group = logs.LogGroup(
            self,
            "SfnLogGroup",
            log_group_name=f"/aws/vendedlogs/states/novascan-{stage}-receipt-pipeline",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        return sfn.StateMachine(
            self,
            "PipelineStateMachine",
            state_machine_name=f"novascan-{stage}-receipt-pipeline",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=cdk.Duration.minutes(15),
            tracing_enabled=True,
            logs=sfn.LogOptions(
                destination=sfn_log_group,
                level=sfn.LogLevel.ERROR,
            ),
        )

    def _build_pipe(self, stage: str, config: dict[str, Any]) -> None:
        """Build EventBridge Pipe: SQS -> Step Functions.

        Uses L1 CfnPipe since there's no L2 construct for EventBridge Pipes.
        The SQS message contains the S3 event notification. The input
        transformer extracts bucket and key from the S3 event record.
        """
        # IAM role for the pipe
        pipe_role = iam.Role(
            self,
            "PipeRole",
            role_name=f"novascan-{stage}-pipe-role",
            assumed_by=iam.ServicePrincipal("pipes.amazonaws.com"),
        )

        # Allow pipe to read from SQS
        self.queue.grant_consume_messages(pipe_role)

        # Allow pipe to start Step Functions executions
        pipe_role.add_to_policy(
            iam.PolicyStatement(
                actions=["states:StartExecution"],
                resources=[self.state_machine.state_machine_arn],
            )
        )

        # --- Pipe logging ---
        pipe_log_group = logs.LogGroup(
            self,
            "PipeLogGroup",
            log_group_name=f"/aws/vendedlogs/pipes/novascan-{stage}-receipt-pipe",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )
        pipe_log_group.grant_write(pipe_role)

        # The SQS message body contains the S3 event notification as a JSON
        # string. EventBridge Pipes can parse the body and extract fields using
        # JSONPath when the source is SQS.
        #
        # For SQS sources, Pipes automatically parses the message body as JSON.
        # We extract bucket and key directly rather than passing the raw body,
        # which avoids JSON escaping issues with <$.body> string interpolation.
        #
        # S3 event structure:
        # { "Records": [{ "s3": { "bucket": { "name": "..." }, "object": { "key": "..." } } }] }
        input_template = json.dumps({
            "bucket": "<$.body.Records[0].s3.bucket.name>",
            "key": "<$.body.Records[0].s3.object.key>",
        })

        pipes.CfnPipe(
            self,
            "ReceiptPipe",
            name=f"novascan-{stage}-receipt-pipe",
            role_arn=pipe_role.role_arn,
            source=self.queue.queue_arn,
            target=self.state_machine.state_machine_arn,
            source_parameters=pipes.CfnPipe.PipeSourceParametersProperty(
                sqs_queue_parameters=pipes.CfnPipe.PipeSourceSqsQueueParametersProperty(
                    batch_size=1,
                ),
            ),
            target_parameters=pipes.CfnPipe.PipeTargetParametersProperty(
                step_function_state_machine_parameters=(
                    pipes.CfnPipe.PipeTargetStateMachineParametersProperty(
                        invocation_type="FIRE_AND_FORGET",
                    )
                ),
                input_template=input_template,
            ),
            description=f"NovaScan receipt pipeline pipe ({stage})",
            log_configuration=pipes.CfnPipe.PipeLogConfigurationProperty(
                cloudwatch_logs_log_destination=pipes.CfnPipe.CloudwatchLogsLogDestinationProperty(
                    log_group_arn=pipe_log_group.log_group_arn,
                ),
                level="ERROR",
            ),
        )
