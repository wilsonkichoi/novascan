# Task 3.7 Review: Pipeline CDK + Integration Tests

**Status:** done
**Role:** qa-engineer
**Date:** 2026-04-04

## Test Summary

| Suite | File | Tests | Status |
|-------|------|-------|--------|
| CDK construct tests | `infra/tests/test_pipeline_construct.py` | 25 | all pass |
| Integration tests | `backend/tests/integration/test_pipeline_flow.py` | 31 | all pass |
| **Total** | | **56** | **all pass** |

## CDK Tests (25 tests)

### TestSQSQueues (3 tests)
- At least 2 SQS queues exist (main + DLQ)
- Main queue has redrive policy
- DLQ has 14-day retention

### TestEventBridgePipe (4 tests)
- Pipe exists (exactly 1)
- Source is SQS with SqsQueueParameters
- Target is Step Functions
- Batch size is 1

### TestStepFunctionsStateMachine (7 tests)
- State machine exists (exactly 1)
- Starts with LoadCustomCategories
- Has Parallel state
- Parallel has exactly 2 branches
- Both branches have Catch blocks
- Has Finalize state after Parallel
- LoadCustomCategories transitions to Parallel

### TestPipelineLambdaFunctions (6 tests)
- All 5 pipeline Lambda handlers present
- All have TABLE_NAME env var
- All have LOG_LEVEL env var
- All have STAGE env var
- Finalize has DEFAULT_PIPELINE env var (ocr-ai)
- All use Python 3.x runtime

### TestIAMPermissions (4 tests)
- textract:AnalyzeExpense permission exists
- bedrock:InvokeModel permission scoped to nova-*
- cloudwatch:PutMetricData permission exists
- Bedrock permissions verified scoped to Nova models

### TestS3EventNotification (1 test)
- S3BucketNotifications custom resource exists

## Integration Tests (31 tests)

### TestMainSuccessPath (14 tests)
- Receipt status updated to confirmed
- Merchant populated from main pipeline
- Total, category populated
- usedFallback not set
- Both pipeline results stored (2 records)
- Pipeline results have entityType=PIPELINE
- Pipeline results have rankingScore in [0,1]
- rankingWinner set on receipt
- Line items created (correct count)
- Line item SK format RECEIPT#{ulid}#ITEM#{nnn}
- Line items have entityType=ITEM
- Line items contain extraction data (name, quantity, prices)
- S3 metadata updated (status, receipt-id, processed-at)

### TestFallbackPath (6 tests)
- Receipt confirmed with fallback
- usedFallback=true set
- Receipt data from shadow pipeline
- Both pipeline results stored
- Failed pipeline record has error info
- Line items created from shadow result

### TestBothFailPath (5 tests)
- Receipt status=failed
- failureReason populated
- No line items created
- usedFallback not set
- Both error pipeline results stored

### TestLoadCustomCategories (3 tests)
- Loads user's custom categories from DynamoDB
- Empty list for user with no custom categories
- Passes through pipeline input fields (bucket, key, userId, receiptId)

### TestReceiptDateGSI (1 test)
- GSI1SK updated with receiptDate from extraction

### TestPipelineResultSKFormat (1 test)
- SK follows RECEIPT#{ulid}#PIPELINE#{type} pattern

### TestDefaultPipelineConfig (1 test)
- DEFAULT_PIPELINE=ai-multimodal swaps main/shadow correctly

## Bugs Found

No bugs found. Task 3.6 previously identified and fixed a critical DynamoDB reserved keyword bug in finalize.py, which this integration test suite validates is resolved.

## Notes

- CDK snapshot updated to reflect pipeline construct additions from task 3.5
- Integration tests use moto `mock_aws` for DynamoDB and S3
- Finalize Lambda's module-level `s3_client` is swapped with a moto client during tests
- All tests are independent (each creates its own receipt record within the mock context)
- MaximumConcurrency on EventBridge Pipes is not tested because it is not supported in CloudFormation (documented gap in PROGRESS.md)
