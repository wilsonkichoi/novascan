# NovaScan Monitoring Guide

Operational monitoring for the NovaScan serverless stack using CloudWatch, Step Functions console, and AWS CLI.

All resource names follow the pattern `novascan-{stage}-{resource}`. Replace `{stage}` with `dev` or `prod` throughout this guide.

## Table of Contents

1. [CloudWatch Log Groups](#1-cloudwatch-log-groups)
2. [Custom CloudWatch Metrics](#2-custom-cloudwatch-metrics)
3. [CloudWatch Logs Insights Queries](#3-cloudwatch-logs-insights-queries)
4. [Step Functions Console](#4-step-functions-console)
5. [Manual Alarm Setup](#5-manual-alarm-setup)
6. [Cost Monitoring](#6-cost-monitoring)
7. [Quick Reference](#7-quick-reference)

---

## 1. CloudWatch Log Groups

Every Lambda function and API Gateway stage writes structured JSON logs. Lambda log groups are auto-created on first invocation. The API Gateway access log group is created by CDK.

### Log Group Inventory

| Component | Log Group | Source |
|-----------|-----------|--------|
| API Lambda | `/aws/lambda/novascan-{stage}-api` | Powertools Logger (JSON) |
| Textract Extract Lambda | `/aws/lambda/novascan-{stage}-textract-extract` | Powertools Logger (JSON) |
| Nova Structure Lambda | `/aws/lambda/novascan-{stage}-nova-structure` | Powertools Logger (JSON) |
| Nova Lite v1 Extract Lambda | `/aws/lambda/novascan-{stage}-nova-lite-v1-extract` | Powertools Logger (JSON) |
| Nova Lite v2 Extract Lambda | `/aws/lambda/novascan-{stage}-nova-lite-v2-extract` | Powertools Logger (JSON) |
| Load Custom Categories Lambda | `/aws/lambda/novascan-{stage}-load-custom-categories` | Powertools Logger (JSON) |
| Finalize Lambda | `/aws/lambda/novascan-{stage}-finalize` | Powertools Logger (JSON) |
| Pre-Sign-Up Lambda | `/aws/lambda/novascan-{stage}-pre-signup` | Powertools Logger (JSON) |
| Post-Confirmation Lambda | `/aws/lambda/novascan-{stage}-post-confirmation` | Powertools Logger (JSON) |
| API Gateway Access Logs | `/aws/apigateway/novascan-{stage}-access` | API Gateway structured access log |
| EventBridge Pipe | `/aws/vendedlogs/pipes/novascan-{stage}-receipt-pipe` | Pipe errors (ERROR level only) |
| Step Functions State Machine | `/aws/vendedlogs/states/novascan-{stage}-receipt-pipeline` | Execution errors (ERROR level only) |

### Log Format

All pipeline and API Lambdas use Lambda Powertools `Logger` with `@logger.inject_lambda_context`. Logs are structured JSON with these standard fields:

- `level` -- log level (INFO, WARNING, ERROR)
- `message` -- log message
- `timestamp` -- ISO 8601 timestamp
- `service` -- Powertools service name (e.g., `novascan-api`, `novascan-finalize`)
- `function_name` -- Lambda function name
- `function_request_id` -- AWS request ID (use for correlation)
- `cold_start` -- boolean, true on first invocation of a new execution environment
- `xray_trace_id` -- X-Ray trace ID for cross-service correlation

Additional fields are added via `extra={}` in log calls (e.g., `receipt_id`, `user_id`, `pipeline_type`).

### Locating Log Groups via AWS CLI

List all NovaScan log groups for a stage:

```bash
STAGE=dev
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/lambda/novascan-${STAGE}" \
  --query 'logGroups[].logGroupName' \
  --output table
```

Tail logs from a specific Lambda in real time:

```bash
STAGE=dev
FUNCTION=finalize
aws logs tail "/aws/lambda/novascan-${STAGE}-${FUNCTION}" --follow --format short
```

---

## 2. Custom CloudWatch Metrics

All custom metrics are published by the **Finalize Lambda** (`backend/src/novascan/pipeline/finalize.py`) using Lambda Powertools `Metrics` with `single_metric()` context manager.

**Namespace:** `NovaScan`

### Metric Reference

| Metric Name | Unit | Dimensions | Description |
|-------------|------|------------|-------------|
| `PipelineCompleted` | Count | `PipelineType` (`ocr-ai` or `ai-multimodal`), `Outcome` (`success` or `failure`) | Emitted once per pipeline per receipt. Tracks success/failure rate for each pipeline type. |
| `PipelineLatency` | Milliseconds | `PipelineType` (`ocr-ai` or `ai-multimodal`) | Processing time for successful pipeline executions. Only emitted when the pipeline succeeds and reports `processingTimeMs`. |
| `RankingDecision` | Count | `Winner` (`ocr-ai`, `ai-multimodal`, or `ai-vision-v2`) | Which pipeline scored highest in ranking-based selection. Emitted when at least one pipeline produces a result. |
| `ReceiptStatus` | Count | `Status` (`confirmed` or `failed`) | Final receipt status after ranking-based selection. One event per receipt. |

**Note:** The spec defines a `ReceiptUploaded` metric, but it is not yet implemented. It is planned for the API upload handler.

Additionally, the `@metrics.log_metrics(capture_cold_start_metric=True)` decorator on the Finalize handler publishes a `ColdStart` metric (dimension `function_name`) automatically.

### Querying Metrics via AWS CLI

List all available metrics in the NovaScan namespace:

```bash
aws cloudwatch list-metrics --namespace NovaScan --output table
```

Get pipeline failure count for the last 24 hours:

```bash
aws cloudwatch get-metric-statistics \
  --namespace NovaScan \
  --metric-name PipelineCompleted \
  --dimensions Name=PipelineType,Value=ocr-ai Name=Outcome,Value=failure \
  --start-time "$(date -u -v-1d +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 3600 \
  --statistics Sum
```

Get p50/p95/p99 pipeline latency for the last hour:

```bash
aws cloudwatch get-metric-statistics \
  --namespace NovaScan \
  --metric-name PipelineLatency \
  --dimensions Name=PipelineType,Value=ocr-ai \
  --start-time "$(date -u -v-1H +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 3600 \
  --extended-statistics p50 p95 p99
```

---

## 3. CloudWatch Logs Insights Queries

Run these in the CloudWatch console (Logs > Logs Insights) or via AWS CLI. Select the appropriate log group(s) before running.

### Query 1: Pipeline Failures (Last 24 Hours)

**Log groups:** `/aws/lambda/novascan-{stage}-finalize`

Finds all receipts where both pipelines failed (status = "failed").

```
fields @timestamp, receipt_id, main_type, shadow_type
| filter message = "Both pipelines failed"
| sort @timestamp desc
| limit 50
```

### Query 2: Slow Pipeline Executions (> 10 Seconds)

**Log groups:** `/aws/lambda/novascan-{stage}-finalize`

Finds finalized receipts and extracts processing time from structured log data. Useful for identifying receipts that took unusually long.

```
fields @timestamp, receipt_id, status, used_fallback, selected_pipeline
| filter message = "Finalize completed"
| filter @duration > 10000
| sort @duration desc
| limit 50
```

### Query 3: Error Rates by Lambda Function (Last 6 Hours)

**Log groups:** All pipeline Lambda log groups (select all five).

Counts ERROR-level log entries grouped by Lambda function name over the last 6 hours.

```
fields @timestamp, function_name, message
| filter level = "ERROR"
| stats count(*) as error_count by function_name
| sort error_count desc
```

### Query 4: API Gateway 4xx/5xx Response Rates

**Log groups:** `/aws/apigateway/novascan-{stage}-access`

Counts HTTP error responses by status code. API Gateway access logs use a different schema from Lambda Powertools logs.

```
fields @timestamp, status, path, httpMethod
| filter status >= 400
| stats count(*) as error_count by status, httpMethod, path
| sort error_count desc
| limit 50
```

### Query 5: Authentication Failures

**Log groups:** `/aws/lambda/novascan-{stage}-pre-signup`

Finds sign-up rejections from the Pre-Sign-Up trigger (e.g., domain restrictions, validation failures).

```
fields @timestamp, message, level
| filter level = "WARNING" or level = "ERROR"
| sort @timestamp desc
| limit 50
```

### Query 6: Fallback Usage (Shadow Pipeline Promoted)

**Log groups:** `/aws/lambda/novascan-{stage}-finalize`

Lists receipts where the main pipeline failed and the shadow pipeline was used as fallback.

```
fields @timestamp, receipt_id, main_type, shadow_type
| filter message = "Main pipeline failed, using shadow fallback"
| sort @timestamp desc
| limit 50
```

### Query 7: Cold Starts by Function

**Log groups:** All Lambda log groups.

Identifies cold starts across all functions, useful for understanding latency spikes.

```
fields @timestamp, function_name, @duration
| filter cold_start = true
| stats count(*) as cold_starts, avg(@duration) as avg_cold_start_ms by function_name
| sort cold_starts desc
```

### Query 8: Pipeline Skipped (Idempotency Guard)

**Log groups:** `/aws/lambda/novascan-{stage}-load-custom-categories`

Lists receipts where the pipeline was skipped because the receipt was already processed. This happens when S3 `copy_object` (from Finalize) re-triggers the pipeline for an already-completed receipt.

```
fields @timestamp, receipt_id, message
| filter message = "Receipt already processed, skipping pipeline"
| sort @timestamp desc
| limit 50
```

If this fires frequently, it's normal — the idempotency guard is working. If it never fires, that's also fine (no re-triggers occurred).

### Running Queries via AWS CLI

```bash
STAGE=dev
LOG_GROUP="/aws/lambda/novascan-${STAGE}-finalize"
QUERY='fields @timestamp, receipt_id | filter message = "Both pipelines failed" | sort @timestamp desc | limit 20'

# Start the query
QUERY_ID=$(aws logs start-query \
  --log-group-name "$LOG_GROUP" \
  --start-time "$(date -u -v-1d +%s)" \
  --end-time "$(date -u +%s)" \
  --query-string "$QUERY" \
  --output text)

# Wait a few seconds, then get results
aws logs get-query-results --query-id "$QUERY_ID"
```

---

## 4. Step Functions Console

The Step Functions console is the primary tool for debugging individual receipt pipeline executions.

### State Machine

- **Name:** `novascan-{stage}-receipt-pipeline`
- **Flow:** LoadCustomCategories -> Parallel(TextractExtract -> NovaStructure, NovaLiteV1Extract, NovaLiteV2Extract) -> Finalize
- **Timeout:** 15 minutes

### Inspecting Executions

1. Open the AWS Step Functions console.
2. Select the state machine `novascan-{stage}-receipt-pipeline`.
3. Click on an execution to see the visual workflow with pass/fail per state.
4. Click any state to inspect:
   - **Input:** What data was passed to this step.
   - **Output:** What the Lambda returned (or the error payload if it failed).
   - **Exception:** Error type and message if the step failed.

### Filtering Executions

The Step Functions console supports filtering by status:

- **Running** -- currently in progress.
- **Succeeded** -- completed without errors.
- **Failed** -- a state failed and was not caught (rare; most errors are caught and passed to Finalize).
- **Timed Out** -- exceeded the 15-minute timeout.
- **Aborted** -- manually stopped.

### Listing Executions via CLI

```bash
STAGE=dev
STATE_MACHINE_ARN=$(aws stepfunctions list-state-machines \
  --query "stateMachines[?name=='novascan-${STAGE}-receipt-pipeline'].stateMachineArn" \
  --output text)

# List recent failed executions
aws stepfunctions list-executions \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --status-filter FAILED \
  --max-results 10

# Get execution history for a specific execution
aws stepfunctions get-execution-history \
  --execution-arn "arn:aws:states:us-east-1:ACCOUNT_ID:execution:novascan-${STAGE}-receipt-pipeline:EXECUTION_ID" \
  --reverse-order
```

### Correlating Step Functions with CloudWatch Logs

Each Lambda invocation within a Step Functions execution has a unique `function_request_id`. To find the logs for a specific step:

1. In the Step Functions console, click the failed state and note the Lambda request ID from the output/error tab.
2. In CloudWatch Logs Insights, query the corresponding Lambda log group:

```
fields @timestamp, message, level
| filter function_request_id = "REQUEST_ID_HERE"
| sort @timestamp asc
```

### SQS Dead Letter Queue

Messages that fail delivery 3 times land in the DLQ: `novascan-{stage}-receipt-pipeline-dlq` (14-day retention).

Check DLQ depth:

```bash
STAGE=dev
aws sqs get-queue-attributes \
  --queue-url "https://sqs.us-east-1.amazonaws.com/$(aws sts get-caller-identity --query Account --output text)/novascan-${STAGE}-receipt-pipeline-dlq" \
  --attribute-names ApproximateNumberOfMessages \
  --output table
```

---

## 5. Manual Alarm Setup

NovaScan does not deploy CloudWatch alarms via CDK (no custom dashboards for MVP). Set them up manually for production.

### Step 1: Create an SNS Topic

```bash
STAGE=prod
TOPIC_ARN=$(aws sns create-topic \
  --name "novascan-${STAGE}-alerts" \
  --output text --query TopicArn)

echo "Topic ARN: $TOPIC_ARN"
```

### Step 2: Subscribe Your Email

```bash
aws sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol email \
  --notification-endpoint "your-email@example.com"
```

Check your email and confirm the subscription.

### Step 3: Create Alarms

**Alarm: Pipeline Failures (any pipeline, any outcome=failure)**

Triggers when 3 or more pipeline failures occur in a 5-minute window.

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "novascan-${STAGE}-pipeline-failures" \
  --alarm-description "NovaScan pipeline failure rate exceeds threshold" \
  --namespace NovaScan \
  --metric-name PipelineCompleted \
  --dimensions Name=PipelineType,Value=ocr-ai Name=Outcome,Value=failure \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 3 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions "$TOPIC_ARN"
```

**Alarm: Receipt Processing Failures (both pipelines failed)**

Triggers when any receipt ends in "failed" status (both pipelines failed).

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "novascan-${STAGE}-receipt-failures" \
  --alarm-description "NovaScan receipts failing (both pipelines down)" \
  --namespace NovaScan \
  --metric-name ReceiptStatus \
  --dimensions Name=Status,Value=failed \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions "$TOPIC_ARN"
```

**Alarm: High Fallback Rate**

Triggers when 5 or more fallbacks occur in a 15-minute window, indicating the main pipeline is unstable.

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "novascan-${STAGE}-high-fallback-rate" \
  --alarm-description "Main pipeline unstable -- shadow fallback rate is high" \
  --namespace NovaScan \
  --metric-name UsedFallback \
  --dimensions Name=Status,Value=confirmed \
  --statistic Sum \
  --period 900 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions "$TOPIC_ARN"
```

**Alarm: API Lambda Errors**

Uses the built-in Lambda `Errors` metric (no custom metric needed).

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "novascan-${STAGE}-api-lambda-errors" \
  --alarm-description "API Lambda invocation errors" \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=novascan-${STAGE}-api \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions "$TOPIC_ARN"
```

**Alarm: DLQ Messages (Poison Messages)**

Monitors the SQS DLQ for messages that failed processing 3 times.

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "novascan-${STAGE}-dlq-messages" \
  --alarm-description "Messages landing in the receipt pipeline DLQ" \
  --namespace AWS/SQS \
  --metric-name ApproximateNumberOfMessagesVisible \
  --dimensions Name=QueueName,Value=novascan-${STAGE}-receipt-pipeline-dlq \
  --statistic Maximum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --treat-missing-data notBreaching \
  --alarm-actions "$TOPIC_ARN"
```

### Listing Alarms

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix "novascan-${STAGE}" \
  --query 'MetricAlarms[].{Name:AlarmName,State:StateValue}' \
  --output table
```

---

## 6. Cost Monitoring

### Target Budget

| Metric | Target |
|--------|--------|
| Monthly total | < $25 |
| Per-receipt processing | < $0.02 (both pipelines combined) |
| Zero-traffic baseline | < $5/month |

### Cost Breakdown by Service

**Lambda** -- pay per invocation and duration. 7 functions (API + 5 pipeline + 2 auth triggers). At low volume, Lambda is near-free (1M free requests/month).

```bash
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -v-30d +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics UnblendedCost \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["AWS Lambda"]}}' \
  --output table
```

**DynamoDB** -- on-demand mode, pay per read/write request. Single table `novascan-{stage}`.

```bash
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -v-30d +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics UnblendedCost \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon DynamoDB"]}}' \
  --output table
```

**S3** -- receipt images stored in the receipts bucket. Lifecycle rules transition to IA at 90 days, Glacier at 365 days, expire at ~7 years.

```bash
# Check receipts bucket size
aws s3 ls "s3://$(aws cloudformation describe-stacks \
  --stack-name novascan-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ReceiptsBucketName`].OutputValue' \
  --output text)" --recursive --summarize | tail -2
```

**Amazon Textract** -- AnalyzeExpense API, ~$0.01 per page.

**Amazon Bedrock** -- Nova Lite/Pro model invocations. Pricing depends on input/output tokens. Check usage:

```bash
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -v-30d +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics UnblendedCost \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon Bedrock"]}}' \
  --output table
```

**CloudFront** -- data transfer out. Free tier covers 1 TB/month. Negligible for a personal MVP.

**API Gateway** -- HTTP API pricing ($1.00 per million requests). Negligible at personal scale.

### AWS Budgets (Recommended)

Set up a monthly budget alert to catch unexpected cost spikes:

```bash
aws budgets create-budget \
  --account-id "$(aws sts get-caller-identity --query Account --output text)" \
  --budget '{
    "BudgetName": "novascan-monthly",
    "BudgetLimit": {"Amount": "25", "Unit": "USD"},
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }' \
  --notifications-with-subscribers '[{
    "Notification": {
      "NotificationType": "ACTUAL",
      "ComparisonOperator": "GREATER_THAN",
      "Threshold": 80,
      "ThresholdType": "PERCENTAGE"
    },
    "Subscribers": [{
      "SubscriptionType": "EMAIL",
      "Address": "your-email@example.com"
    }]
  }]'
```

This sends an email when actual spend reaches 80% of the $25 monthly budget.

---

## 7. Quick Reference

### Key Resource Names (replace `{stage}`)

| Resource | Name |
|----------|------|
| CDK Stack | `novascan-{stage}` |
| DynamoDB Table | `novascan-{stage}` |
| Step Functions State Machine | `novascan-{stage}-receipt-pipeline` |
| SQS Queue | `novascan-{stage}-receipt-pipeline` |
| SQS DLQ | `novascan-{stage}-receipt-pipeline-dlq` |
| API Gateway | `novascan-{stage}` |
| CloudWatch Metric Namespace | `NovaScan` |
| EventBridge Pipe Log | `/aws/vendedlogs/pipes/novascan-{stage}-receipt-pipe` |
| Step Functions Log | `/aws/vendedlogs/states/novascan-{stage}-receipt-pipeline` |
| SNS Alert Topic (manual) | `novascan-{stage}-alerts` |

### Lambda Function Names

| Function | Name |
|----------|------|
| API | `novascan-{stage}-api` |
| Textract Extract | `novascan-{stage}-textract-extract` |
| Nova Structure | `novascan-{stage}-nova-structure` |
| Nova Lite v1 Extract | `novascan-{stage}-nova-lite-v1-extract` |
| Nova Lite v2 Extract | `novascan-{stage}-nova-lite-v2-extract` |
| Load Custom Categories | `novascan-{stage}-load-custom-categories` |
| Finalize | `novascan-{stage}-finalize` |
| Pre-Sign-Up | `novascan-{stage}-pre-signup` |
| Post-Confirmation | `novascan-{stage}-post-confirmation` |

### Troubleshooting Flowchart

1. **Check receipt status** in DynamoDB (`status`, `failureReason` fields on the RECEIPT entity).
2. **Check pipeline results** in DynamoDB -- `PIPELINE#ocr-ai` and `PIPELINE#ai-multimodal` SK records show which succeeded/failed.
3. **Check Step Functions execution** -- visual workflow shows exactly which state failed and its error output.
4. **Check CloudWatch logs** for the specific Lambda that failed -- use `function_request_id` from Step Functions error output.
5. **Check the SQS DLQ** for messages that never reached Step Functions.
