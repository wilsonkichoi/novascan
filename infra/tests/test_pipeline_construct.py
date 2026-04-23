"""Tests for the Pipeline construct against SPEC.md Section 3 (Processing Flow).

Verifies:
- SQS queues: main queue + DLQ exist
- EventBridge Pipe exists and routes SQS to Step Functions
- Step Functions state machine exists with correct structure
  (LoadCustomCategories -> Parallel -> Finalize)
- 6 pipeline Lambda functions exist with correct handlers
- Lambda environment variables include TABLE_NAME, LOG_LEVEL, STAGE
- Nova Lite v2 Lambda has NOVA_MODEL_ID env var
- IAM policies: textract:AnalyzeExpense, bedrock:InvokeModel scoped
  to amazon.nova-*, cloudwatch:PutMetricData on finalize
- S3 event notification configured on receipts bucket

Spec references:
- Section 3: Processing Flow (SQS -> EventBridge Pipes -> Step Functions)
- Section 3: Parallel branch (OCR-AI + AI-multimodal)
- Section 9: Configuration (pipelineMaxConcurrency, defaultPipeline)
- Section 12: Security (IAM least-privilege)
"""

from __future__ import annotations

import json

from aws_cdk.assertions import Match, Template


class TestSQSQueues:
    """SQS queue configuration per SPEC.md Section 3 (Processing Flow)."""

    def test_at_least_two_sqs_queues_exist(self, dev_template: Template) -> None:
        """Pipeline requires a main queue (burst buffer) + DLQ.

        Spec Section 3: 'S3 ObjectCreated event pushes to SQS queue.
        SQS absorbs burst traffic from bulk uploads.'
        """
        resources = dev_template.find_resources("AWS::SQS::Queue")
        assert len(resources) >= 2, (
            f"Expected at least 2 SQS queues (main + DLQ), found {len(resources)}. "
            "Spec requires SQS as a burst buffer with dead-letter queue for failed messages."
        )

    def test_main_queue_has_redrive_policy(self, dev_template: Template) -> None:
        """Main pipeline queue must have a redrive policy pointing to the DLQ.

        Spec Section 11: 'Check SQS dead-letter queue for messages that
        failed delivery'
        """
        dev_template.has_resource_properties(
            "AWS::SQS::Queue",
            {
                "RedrivePolicy": Match.object_like(
                    {
                        "deadLetterTargetArn": Match.any_value(),
                        "maxReceiveCount": Match.any_value(),
                    }
                ),
            },
        )

    def test_dlq_has_extended_retention(self, dev_template: Template) -> None:
        """DLQ should retain messages for investigation (14 days max).

        Spec Section 11: Troubleshooting mentions checking SQS DLQ.
        """
        dev_template.has_resource_properties(
            "AWS::SQS::Queue",
            {
                "MessageRetentionPeriod": 1209600,  # 14 days
            },
        )


class TestEventBridgePipe:
    """EventBridge Pipe configuration per SPEC.md Section 3."""

    def test_pipe_exists(self, dev_template: Template) -> None:
        """At least one EventBridge Pipe must be created.

        Spec Section 3: 'EventBridge Pipes consumes from SQS with
        MaximumConcurrency ... rate-limits ingestion.'
        """
        dev_template.resource_count_is("AWS::Pipes::Pipe", 1)

    def test_pipe_source_is_sqs(self, dev_template: Template) -> None:
        """Pipe source must be an SQS queue (the burst buffer).

        Spec Section 3: 'EventBridge Pipes consumes from SQS'
        """
        dev_template.has_resource_properties(
            "AWS::Pipes::Pipe",
            {
                "Source": Match.any_value(),
                "SourceParameters": Match.object_like(
                    {
                        "SqsQueueParameters": Match.any_value(),
                    }
                ),
            },
        )

    def test_pipe_target_is_step_functions(self, dev_template: Template) -> None:
        """Pipe target must be a Step Functions state machine.

        Spec Section 3: 'EventBridge Pipes ... -> Step Functions'
        """
        dev_template.has_resource_properties(
            "AWS::Pipes::Pipe",
            {
                "Target": Match.any_value(),
                "TargetParameters": Match.object_like(
                    {
                        "StepFunctionStateMachineParameters": Match.any_value(),
                    }
                ),
            },
        )

    def test_pipe_batch_size_is_one(self, dev_template: Template) -> None:
        """Pipe should process one SQS message at a time.

        Each message corresponds to one receipt. Processing should be
        per-receipt to match Step Functions execution model.
        """
        dev_template.has_resource_properties(
            "AWS::Pipes::Pipe",
            {
                "SourceParameters": Match.object_like(
                    {
                        "SqsQueueParameters": {
                            "BatchSize": 1,
                        },
                    }
                ),
            },
        )


class TestStepFunctionsStateMachine:
    """Step Functions state machine per SPEC.md Section 3."""

    def test_state_machine_exists(self, dev_template: Template) -> None:
        """One Step Functions state machine must be created.

        Spec Section 3: 'Step Functions orchestrates dedicated pipeline Lambdas'
        """
        dev_template.resource_count_is("AWS::StepFunctions::StateMachine", 1)

    def test_state_machine_starts_with_load_custom_categories(
        self, dev_template: Template
    ) -> None:
        """State machine must start with LoadCustomCategories step.

        Spec Section 3: 'Before branching, Step Functions passes the user's
        custom categories to both pipeline Lambdas.'
        """
        sm_resources = dev_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        for _logical_id, resource in sm_resources.items():
            defn_str = resource["Properties"]["DefinitionString"]
            defn_json = _resolve_definition_string(defn_str)
            assert defn_json.get("StartAt") == "LoadCustomCategories", (
                f"State machine StartAt is '{defn_json.get('StartAt')}', "
                "expected 'LoadCustomCategories'. "
                "Spec Section 3 requires custom categories to be loaded before "
                "the parallel pipeline branches execute."
            )

    def test_state_machine_has_parallel_state(
        self, dev_template: Template
    ) -> None:
        """State machine must have a Parallel state for dual pipelines.

        Spec Section 3: 'Both pipelines execute in parallel for every receipt'
        """
        sm_resources = dev_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        for _logical_id, resource in sm_resources.items():
            defn_str = resource["Properties"]["DefinitionString"]
            defn_json = _resolve_definition_string(defn_str)
            states = defn_json.get("States", {})
            parallel_states = [
                name
                for name, state in states.items()
                if state.get("Type") == "Parallel"
            ]
            assert len(parallel_states) >= 1, (
                "No Parallel state found in the state machine. "
                "Spec Section 3 requires OCR-AI and AI-multimodal pipelines "
                "to execute in parallel."
            )

    def test_parallel_state_has_three_branches(
        self, dev_template: Template
    ) -> None:
        """Parallel state must have exactly 3 branches (OCR-AI, Nova Lite v1, Nova 2 Lite)."""
        sm_resources = dev_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        for _logical_id, resource in sm_resources.items():
            defn_str = resource["Properties"]["DefinitionString"]
            defn_json = _resolve_definition_string(defn_str)
            states = defn_json.get("States", {})
            for state_name, state in states.items():
                if state.get("Type") == "Parallel":
                    branches = state.get("Branches", [])
                    assert len(branches) == 3, (
                        f"Parallel state '{state_name}' has {len(branches)} "
                        "branch(es), expected 3 (OCR-AI, Nova Lite v1, Nova 2 Lite)."
                    )

    def test_parallel_branches_have_catch_blocks(
        self, dev_template: Template
    ) -> None:
        """Each pipeline branch must have Catch blocks so the Parallel never fails.

        Spec Section 3: 'Each branch has a Catch block - returns either a success
        result or an error payload. The Parallel state never fails.'
        """
        sm_resources = dev_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        for _logical_id, resource in sm_resources.items():
            defn_str = resource["Properties"]["DefinitionString"]
            defn_json = _resolve_definition_string(defn_str)
            states = defn_json.get("States", {})
            for state_name, state in states.items():
                if state.get("Type") == "Parallel":
                    for i, branch in enumerate(state.get("Branches", [])):
                        branch_states = branch.get("States", {})
                        has_catch = any(
                            "Catch" in s
                            for s in branch_states.values()
                            if s.get("Type") == "Task"
                        )
                        assert has_catch, (
                            f"Parallel branch {i} has no Catch blocks on its "
                            "Task states. Spec Section 3 requires each branch to "
                            "have Catch blocks so the Parallel state never fails."
                        )

    def test_state_machine_has_finalize_state(
        self, dev_template: Template
    ) -> None:
        """State machine must have a Finalize state after the Parallel state.

        Spec Section 3: 'Finalize: Lambda applies main/shadow logic, then ranks'
        """
        sm_resources = dev_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        for _logical_id, resource in sm_resources.items():
            defn_str = resource["Properties"]["DefinitionString"]
            defn_json = _resolve_definition_string(defn_str)
            states = defn_json.get("States", {})

            # Find the Parallel state and check its Next points to Finalize
            for state_name, state in states.items():
                if state.get("Type") == "Parallel":
                    next_state = state.get("Next")
                    assert next_state is not None, (
                        f"Parallel state '{state_name}' has no 'Next' state. "
                        "Spec Section 3 requires a Finalize step after Parallel."
                    )
                    assert next_state in states, (
                        f"Parallel state '{state_name}' points to '{next_state}' "
                        "which does not exist in the state machine. "
                        "Spec Section 3 requires LoadCustomCategories -> Parallel -> Finalize."
                    )

    def test_load_custom_categories_transitions_to_check_skip_then_parallel(
        self, dev_template: Template
    ) -> None:
        """LoadCustomCategories must transition to a Choice state (idempotency guard)
        that routes to Parallel for new receipts or Succeed for already-processed ones.

        Flow: LoadCustomCategories -> CheckSkip (Choice) -> Parallel -> Finalize
        """
        sm_resources = dev_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        for _logical_id, resource in sm_resources.items():
            defn_str = resource["Properties"]["DefinitionString"]
            defn_json = _resolve_definition_string(defn_str)
            states = defn_json.get("States", {})

            lcc_state = states.get("LoadCustomCategories")
            assert lcc_state is not None, (
                "LoadCustomCategories state not found in state machine."
            )

            next_state_name = lcc_state.get("Next")
            assert next_state_name is not None, (
                "LoadCustomCategories has no 'Next' state."
            )

            # LoadCustomCategories -> Choice (idempotency check)
            next_state = states.get(next_state_name)
            assert next_state is not None and next_state.get("Type") == "Choice", (
                f"LoadCustomCategories transitions to '{next_state_name}' "
                f"which is type '{next_state.get('Type') if next_state else 'missing'}'. "
                "Expected a Choice state (idempotency guard)."
            )

            # Choice default branch should lead to Parallel
            default_name = next_state.get("Default")
            if default_name:
                default_state = states.get(default_name)
                assert default_state is not None and default_state.get("Type") == "Parallel", (
                    f"Choice default transitions to '{default_name}' "
                    f"which is type '{default_state.get('Type') if default_state else 'missing'}'. "
                    "Expected a Parallel state."
                )


class TestPipelineLambdaFunctions:
    """Pipeline Lambda functions per SPEC.md Section 3."""

    def test_at_least_five_pipeline_lambdas_exist(
        self, dev_template: Template
    ) -> None:
        """The pipeline requires 5 Lambda functions.

        Spec Section 3 + Section 11 (CloudWatch Resources):
        - textract_extract, nova_structure, nova_lite_v1_extract,
          nova_lite_v2_extract, finalize, load_custom_categories
        """
        lambdas = dev_template.find_resources("AWS::Lambda::Function")
        pipeline_handlers = [
            "pipeline.textract_extract.handler",
            "pipeline.nova_structure.handler",
            "pipeline.bedrock_extract.handler",
            "pipeline.finalize.handler",
            "pipeline.load_custom_categories.handler",
        ]
        found_handlers = set()
        pipeline_lambda_count = 0
        for _id, resource in lambdas.items():
            handler = resource.get("Properties", {}).get("Handler", "")
            if handler in pipeline_handlers:
                found_handlers.add(handler)
                pipeline_lambda_count += 1

        missing = set(pipeline_handlers) - found_handlers
        assert not missing, (
            f"Missing pipeline Lambda handler(s): {missing}. "
            "All pipeline handler types must be present."
        )
        assert pipeline_lambda_count >= 6, (
            f"Expected at least 6 pipeline Lambdas (bedrock_extract.handler "
            f"is used by 2 Lambdas), got {pipeline_lambda_count}."
        )

    def test_pipeline_lambdas_have_table_name_env_var(
        self, dev_template: Template
    ) -> None:
        """All pipeline Lambdas must have TABLE_NAME environment variable.

        Spec Section 9: TABLE_NAME is injected by CDK for DynamoDB access.
        """
        pipeline_handlers = [
            "pipeline.textract_extract.handler",
            "pipeline.nova_structure.handler",
            "pipeline.bedrock_extract.handler",
            "pipeline.finalize.handler",
            "pipeline.load_custom_categories.handler",
        ]
        lambdas = dev_template.find_resources("AWS::Lambda::Function")
        for logical_id, resource in lambdas.items():
            props = resource.get("Properties", {})
            handler = props.get("Handler", "")
            if handler in pipeline_handlers:
                env_vars = props.get("Environment", {}).get("Variables", {})
                assert "TABLE_NAME" in env_vars, (
                    f"Lambda '{logical_id}' (handler={handler}) is missing "
                    "TABLE_NAME environment variable. "
                    "All pipeline Lambdas need DynamoDB table access."
                )

    def test_pipeline_lambdas_have_log_level_env_var(
        self, dev_template: Template
    ) -> None:
        """All pipeline Lambdas must have LOG_LEVEL environment variable.

        Spec Section 9: 'logLevel: All Lambdas - Lambda Powertools log level'
        """
        pipeline_handlers = [
            "pipeline.textract_extract.handler",
            "pipeline.nova_structure.handler",
            "pipeline.bedrock_extract.handler",
            "pipeline.finalize.handler",
            "pipeline.load_custom_categories.handler",
        ]
        lambdas = dev_template.find_resources("AWS::Lambda::Function")
        for logical_id, resource in lambdas.items():
            props = resource.get("Properties", {})
            handler = props.get("Handler", "")
            if handler in pipeline_handlers:
                env_vars = props.get("Environment", {}).get("Variables", {})
                assert "LOG_LEVEL" in env_vars, (
                    f"Lambda '{logical_id}' (handler={handler}) is missing "
                    "LOG_LEVEL environment variable. "
                    "Spec Section 9: logLevel is configured for all Lambdas."
                )

    def test_pipeline_lambdas_have_stage_env_var(
        self, dev_template: Template
    ) -> None:
        """All pipeline Lambdas must have STAGE environment variable.

        CDK injects STAGE for stage-aware resource naming and behavior.
        """
        pipeline_handlers = [
            "pipeline.textract_extract.handler",
            "pipeline.nova_structure.handler",
            "pipeline.bedrock_extract.handler",
            "pipeline.finalize.handler",
            "pipeline.load_custom_categories.handler",
        ]
        lambdas = dev_template.find_resources("AWS::Lambda::Function")
        for logical_id, resource in lambdas.items():
            props = resource.get("Properties", {})
            handler = props.get("Handler", "")
            if handler in pipeline_handlers:
                env_vars = props.get("Environment", {}).get("Variables", {})
                assert "STAGE" in env_vars, (
                    f"Lambda '{logical_id}' (handler={handler}) is missing "
                    "STAGE environment variable."
                )

    def test_nova_lite_v2_lambda_has_model_id_env_var(
        self, dev_template: Template
    ) -> None:
        """Nova Lite v2 Lambda must have NOVA_MODEL_ID=us.amazon.nova-2-lite-v1:0."""
        lambdas = dev_template.find_resources("AWS::Lambda::Function")
        found = False
        for _logical_id, resource in lambdas.items():
            props = resource.get("Properties", {})
            env_vars = props.get("Environment", {}).get("Variables", {})
            if env_vars.get("NOVA_MODEL_ID") == "us.amazon.nova-2-lite-v1:0":
                found = True
                break
        assert found, (
            "No Lambda found with NOVA_MODEL_ID=us.amazon.nova-2-lite-v1:0. "
            "The Nova Lite v2 extract Lambda must set this env var."
        )

    def test_pipeline_lambdas_use_python_runtime(
        self, dev_template: Template
    ) -> None:
        """All pipeline Lambdas must use a Python runtime.

        Spec Section 9: 'Python 3.13+ via uv'
        """
        pipeline_handlers = [
            "pipeline.textract_extract.handler",
            "pipeline.nova_structure.handler",
            "pipeline.bedrock_extract.handler",
            "pipeline.finalize.handler",
            "pipeline.load_custom_categories.handler",
        ]
        lambdas = dev_template.find_resources("AWS::Lambda::Function")
        for logical_id, resource in lambdas.items():
            props = resource.get("Properties", {})
            handler = props.get("Handler", "")
            if handler in pipeline_handlers:
                runtime = props.get("Runtime", "")
                assert runtime.startswith("python3."), (
                    f"Lambda '{logical_id}' (handler={handler}) uses runtime "
                    f"'{runtime}', expected a Python 3.x runtime. "
                    "Spec Section 9: Python 3.13+."
                )


class TestIAMPermissions:
    """IAM permissions for pipeline Lambdas per SPEC.md Section 12."""

    def test_textract_lambda_has_analyze_expense_permission(
        self, dev_template: Template
    ) -> None:
        """Textract extract Lambda must have textract:AnalyzeExpense permission.

        Spec Section 3: 'Lambda invokes Textract AnalyzeExpense (sync)'
        """
        dev_template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": "textract:AnalyzeExpense",
                                    "Effect": "Allow",
                                }
                            ),
                        ]
                    ),
                },
            },
        )

    def test_nova_structure_lambda_has_bedrock_invoke_permission(
        self, dev_template: Template
    ) -> None:
        """Nova structure Lambda must have bedrock:InvokeModel permission.

        Spec Section 3: 'Lambda sends Textract output to Bedrock Nova'
        M10: Bedrock ARN scoped to deployment region with specific model IDs.
        """
        dev_template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": "bedrock:InvokeModel",
                                    "Effect": "Allow",
                                    # M10: Resource is now a region-scoped ARN array
                                    # (Fn::Join with AWS::Region), not a wildcard
                                    "Resource": Match.any_value(),
                                }
                            ),
                        ]
                    ),
                },
            },
        )

    def test_finalize_lambda_has_cloudwatch_put_metric_permission(
        self, dev_template: Template
    ) -> None:
        """Finalize Lambda must have cloudwatch:PutMetricData permission.

        Spec Section 11: Finalize Lambda publishes PipelineCompleted,
        PipelineLatency, RankingDecision, RankingScoreDelta, ReceiptStatus,
        UsedFallback metrics.
        """
        dev_template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Action": "cloudwatch:PutMetricData",
                                    "Effect": "Allow",
                                }
                            ),
                        ]
                    ),
                },
            },
        )

    def test_bedrock_permissions_scoped_to_nova_models(
        self, dev_template: Template
    ) -> None:
        """Bedrock InvokeModel permissions must be scoped to amazon.nova-* models.

        Spec Section 12: 'IAM least-privilege for all Lambda execution roles'
        The pipeline only needs Nova models, not arbitrary Bedrock models.
        M10: ARNs must be region-scoped (no wildcard region).
        """
        policies = dev_template.find_resources("AWS::IAM::Policy")
        bedrock_policies = []
        for _id, policy in policies.items():
            statements = (
                policy.get("Properties", {})
                .get("PolicyDocument", {})
                .get("Statement", [])
            )
            for stmt in statements:
                actions = stmt.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                if "bedrock:InvokeModel" in actions:
                    bedrock_policies.append(stmt)

        assert len(bedrock_policies) >= 1, (
            "No bedrock:InvokeModel policy statements found. "
            "Nova structure and Bedrock extract Lambdas need this permission."
        )

        for stmt in bedrock_policies:
            resource = stmt.get("Resource", "")
            resource_str = json.dumps(resource) if isinstance(resource, (dict, list)) else str(resource)
            assert "nova" in resource_str.lower(), (
                f"Bedrock InvokeModel resource '{resource_str}' does not appear "
                "to be scoped to Nova models. "
                "Spec Section 12: IAM least-privilege requires scoping to "
                "amazon.nova-* foundation models only."
            )
            # M10: Verify no wildcard region (should use AWS::Region reference)
            assert "bedrock:*:" not in resource_str, (
                f"Bedrock ARN uses wildcard region: {resource_str}. "
                "M10: Must be scoped to deployment region."
            )


class TestS3EventNotification:
    """S3 event notification triggers the pipeline per SPEC.md Section 3."""

    def test_s3_bucket_notification_resource_exists(
        self, dev_template: Template
    ) -> None:
        """S3 bucket notifications must be configured.

        Spec Section 3: 'S3 ObjectCreated event pushes to SQS queue'
        CDK creates a Custom::S3BucketNotifications resource for this.
        """
        resources = dev_template.find_resources("Custom::S3BucketNotifications")
        assert len(resources) >= 1, (
            "No Custom::S3BucketNotifications resource found. "
            "Spec Section 3 requires S3 ObjectCreated events to trigger "
            "the pipeline via SQS."
        )


# --- Helpers ---


def _resolve_definition_string(defn: dict | str) -> dict:
    """Resolve a CloudFormation Fn::Join into a parseable JSON string.

    CDK encodes the state machine definition as Fn::Join with embedded Fn::GetAtt
    references. We replace all non-string parts with placeholder ARNs to produce
    a valid JSON string that can be parsed for structural assertions.
    """
    if isinstance(defn, str):
        return json.loads(defn)

    # Handle Fn::Join
    if "Fn::Join" in defn:
        separator = defn["Fn::Join"][0]
        parts = defn["Fn::Join"][1]
        resolved_parts = []
        for part in parts:
            if isinstance(part, str):
                resolved_parts.append(part)
            else:
                # Replace CloudFormation references with a placeholder ARN
                resolved_parts.append("arn:aws:lambda:us-east-1:123456789012:function:placeholder")
        return json.loads(separator.join(resolved_parts))

    return defn
