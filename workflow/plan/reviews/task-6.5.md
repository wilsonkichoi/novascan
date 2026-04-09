# Task 6.5 Review: Monitoring Guide

## Summary
Created `workflow/guides/monitoring.md` -- a practical, copy-pasteable monitoring guide covering CloudWatch log groups, custom metrics, Logs Insights queries, Step Functions debugging, manual alarm setup, and cost monitoring.

## Changes
- **`workflow/guides/monitoring.md`** (new): Full monitoring guide with 7 sections.

## Acceptance Criteria Checklist
- [x] Documents all CloudWatch metrics published by pipeline Lambdas (PipelineCompleted, PipelineLatency, RankingDecision, RankingScoreDelta, ReceiptStatus, UsedFallback) -- Section 2 with dimensions, units, and descriptions sourced from `finalize.py`
- [x] Includes at least 5 CloudWatch Logs Insights queries -- Section 3 has 7 queries (pipeline failures, slow executions, error rates by Lambda, API 4xx/5xx rates, auth failures, fallback usage, cold starts)
- [x] Lists key CloudWatch log groups and how to locate them -- Section 1 with full inventory table plus CLI commands to list and tail logs
- [x] Covers Step Functions console usage for inspecting pipeline executions -- Section 4 with execution filtering, CLI commands, and log correlation workflow
- [x] Includes manual alarm setup instructions (SNS topic + CloudWatch alarm for pipeline failures) -- Section 5 with 5 alarms (pipeline failures, receipt failures, high fallback rate, API Lambda errors, DLQ messages)
- [x] Includes cost monitoring guidance (S3, DynamoDB, Lambda, Textract, Bedrock usage) -- Section 6 with per-service Cost Explorer commands and AWS Budgets setup

## Accuracy Verification
- Metric names, dimensions, units, and namespace (`NovaScan`) verified against `backend/src/novascan/pipeline/finalize.py`
- Lambda function names verified against CDK constructs: `infra/cdkconstructs/pipeline.py`, `infra/cdkconstructs/api.py`, `infra/cdkconstructs/auth.py`
- Log group patterns verified against SPEC.md Section 11
- API Gateway access log group name verified against `infra/cdkconstructs/api.py` (line 190)
- SQS queue names verified against `infra/cdkconstructs/pipeline.py` (lines 129, 138)
- State machine name verified against `infra/cdkconstructs/pipeline.py` (line 461)
- `ReceiptUploaded` metric noted as spec-defined but not yet implemented

## Test Results
```
Acceptance: PASS (file exists)
```
