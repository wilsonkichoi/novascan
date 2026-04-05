# Task 3.5 Review: Pipeline CDK Construct

**Date:** 2026-04-04
**Role:** devops-engineer
**Status:** done

## Summary

Implemented the full pipeline CDK construct that wires the receipt processing infrastructure:
- SQS queue receiving S3 ObjectCreated events from the receipts bucket (`receipts/` prefix)
- EventBridge Pipe (L1 CfnPipe) connecting SQS to Step Functions state machine
- Step Functions state machine with the full pipeline flow
- Five pipeline Lambda functions with proper IAM permissions
- Enhanced LoadCustomCategories Lambda to handle the S3 event parsing and userId lookup

## Files Modified

| File | Change |
|------|--------|
| `infra/cdkconstructs/pipeline.py` | Full pipeline construct: SQS, Pipe, SFN, 5 Lambdas, IAM |
| `infra/stacks/novascan_stack.py` | Pass table + receipts_bucket props to PipelineConstruct |
| `backend/src/novascan/pipeline/load_custom_categories.py` | Parse S3 event from Pipe, extract receiptId, look up userId |

## Architecture Decisions

### S3 -> SQS -> EventBridge Pipe -> Step Functions

The data flow:
1. S3 ObjectCreated event on `receipts/` prefix -> SQS queue
2. EventBridge Pipe reads SQS message, passes `{"s3EventBody": "<$.body>"}` to Step Functions
3. LoadCustomCategories Lambda parses the S3 event body, extracts bucket/key, resolves receiptId and userId
4. Parallel branches run OCR-AI (Textract -> Nova) and AI-multimodal (Bedrock) concurrently
5. Finalize Lambda selects result, ranks, persists to DynamoDB/S3

### userId Resolution Without a GSI

The S3 event only provides the key (`receipts/{receiptId}.{ext}`). The upload API stores the receipt record with `PK=USER#{userId}` but does not encode userId in the S3 key or object metadata.

Solution: LoadCustomCategories does a DynamoDB Scan with FilterExpression on `receiptId` and `entityType=RECEIPT` to find the owning user. This is acceptable at MVP scale (single user, low volume). For production scale, options are:
1. Add a GSI on `receiptId`
2. Encode userId in the S3 key (`receipts/{userId}/{receiptId}.{ext}`)
3. Set `x-amz-meta-user-id` as presigned URL condition in the upload API

### MaximumConcurrency Gap (Documented)

`CfnPipe` (AWS::Pipes::Pipe) does not expose a `MaximumConcurrency` property in CloudFormation as of 2026-04. The `pipelineMaxConcurrency` config value from `cdk.json` cannot be enforced at the Pipe level. Concurrency is controlled indirectly via SQS `batch_size=1` and the SQS visibility timeout (900s matches Lambda timeout).

### Lambda Bundling

Reused the uv-based bundling pattern from `api.py` with a separate asset that excludes `auth/` and `api/` directories (pipeline Lambdas don't need those modules). All 5 pipeline Lambdas share a single code asset to reduce build time and S3 asset storage.

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| S3 event notification on receipts bucket for `ObjectCreated` on `receipts/` prefix | PASS |
| SQS queue receives S3 events | PASS |
| EventBridge Pipe: SQS -> Step Functions with CfnPipe | PASS |
| MaximumConcurrency verified as unsupported, gap documented | PASS |
| State machine: LoadCustomCategories -> Parallel -> Finalize | PASS |
| Parallel branches: Main (TextractExtract -> NovaStructure) and Shadow (BedrockExtract) | PASS |
| Each step has Catch -> error payload | PASS |
| Pipeline Lambdas have correct IAM permissions | PASS |
| Finalize has DynamoDB write, S3 write, CloudWatch Metrics | PASS |
| `cdk synth` produces valid template | PASS |

## Test Results

```
SQS queues: 1
Step Functions state machines: 1
EventBridge Pipes: 1
Lambda functions: 10 (5 pipeline + 5 existing)
S3 notifications: 1

State machine flow:
  LoadCustomCategories -> ParallelPipelines -> Finalize
  Branch 0: TextractExtract -> NovaStructure (with error catches)
  Branch 1: BedrockExtract (with error catch)

Backend tests: 144 passed
Ruff lint: All checks passed
```

## Spec Gaps Discovered

1. **userId not in S3 event** -- SPEC assumes userId is available in pipeline input but doesn't specify how it arrives when triggered by S3 event notification. Resolved with DynamoDB scan (MVP) -- needs GSI for production.
2. **MaximumConcurrency not available** -- CloudFormation/CDK does not support this property on EventBridge Pipes. Documented as gap; using SQS batch_size=1 as workaround.
