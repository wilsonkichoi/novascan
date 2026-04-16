# NovaScan Troubleshooting Guide

Practical guide for diagnosing and fixing failures across the NovaScan stack. Each scenario follows the **Symptoms / Diagnosis / Fix** pattern with real AWS CLI commands and CloudWatch Logs Insights queries.

> **Convention:** Replace `{stage}` with `dev` or `prod`. All commands assume the AWS CLI is configured with the correct profile and region (`us-east-1`).

---

## Table of Contents

1. [Reading Lambda Powertools Structured Logs](#1-reading-lambda-powertools-structured-logs)
2. [Pipeline Failures](#2-pipeline-failures)
   - [2.1 Textract Timeout](#21-textract-timeout)
   - [2.2 Bedrock Throttling](#22-bedrock-throttling)
   - [2.3 Both Pipelines Fail](#23-both-pipelines-fail)
   - [2.4 S3 Event Not Triggering SQS](#24-s3-event-not-triggering-sqs)
   - [2.5 EventBridge Pipe Failures](#25-eventbridge-pipe-failures-sqs--step-functions)
   - [2.6 Infinite Pipeline Loop](#26-infinite-pipeline-loop)
   - [2.7 Orphaned Processing Receipts](#27-orphaned-processing-receipts)
3. [API Failures](#3-api-failures)
   - [3.1 401 Unauthorized (Expired Token)](#31-401-unauthorized-expired-token)
   - [3.2 403 Forbidden (Wrong User / Insufficient Role)](#32-403-forbidden-wrong-user--insufficient-role)
   - [3.3 500 Internal Server Error](#33-500-internal-server-error)
   - [3.4 CORS Errors](#34-cors-errors)
4. [Auth Failures](#4-auth-failures)
   - [4.1 OTP Not Received](#41-otp-not-received)
   - [4.2 Session Expired](#42-session-expired)
   - [4.3 Refresh Token Invalid](#43-refresh-token-invalid)
5. [Frontend Failures](#5-frontend-failures)
   - [5.1 Blank Page After Deploy (S3 Issue)](#51-blank-page-after-deploy-s3-issue)
   - [5.2 Stale Content (CloudFront Cache)](#52-stale-content-cloudfront-cache)
   - [5.3 CSP Blocking Receipt Images](#53-csp-blocking-receipt-images)
6. [CDK / Infrastructure Failures](#6-cdk--infrastructure-failures)
   - [6.1 Deploy Fails (Resource Limit / IAM Permission)](#61-deploy-fails-resource-limit--iam-permission)
   - [6.2 Drift Detection](#62-drift-detection)
   - [6.3 Lambda Import Failure (Cross-Platform Bundling)](#63-lambda-import-failure-cross-platform-bundling)
7. [Replaying a Failed Pipeline Execution](#7-replaying-a-failed-pipeline-execution)
8. [DynamoDB Inspection Examples](#8-dynamodb-inspection-examples)

---

## 1. Reading Lambda Powertools Structured Logs

All NovaScan Lambdas emit structured JSON logs via AWS Lambda Powertools. Key fields:

| Field | Description | Example |
|-------|-------------|---------|
| `level` | Log level | `INFO`, `WARNING`, `ERROR` |
| `service` | Powertools service name | `novascan-textract-extract` |
| `correlation_id` | Request correlation ID (API: from API Gateway request ID) | `abc123-def456` |
| `xray_trace_id` | X-Ray trace ID for distributed tracing | `1-abc-def` |
| `cold_start` | Whether this invocation was a cold start | `true` / `false` |
| `function_name` | Lambda function name | `novascan-dev-textract-extract` |
| `function_request_id` | Lambda invocation request ID | `xxxx-yyyy-zzzz` |
| `timestamp` | ISO 8601 timestamp | `2026-04-09T10:30:00.000Z` |
| `exception` | Full traceback (only on `logger.exception()`) | Python traceback string |

### Finding logs by correlation ID

When an API request returns an error, the `x-amzn-requestid` response header is the correlation ID. Use it to find all related logs:

```
# CloudWatch Logs Insights — API Lambda
fields @timestamp, level, message, correlation_id, exception
| filter correlation_id = "YOUR-REQUEST-ID"
| sort @timestamp asc
| limit 50
```

Log group for the API Lambda: `/aws/lambda/novascan-{stage}-api`

### Finding pipeline logs by receipt ID

Pipeline Lambdas log `receipt_id` in the `extra` field. To trace a full pipeline execution:

```
# CloudWatch Logs Insights — search across all pipeline log groups
fields @timestamp, level, service, message, receipt_id
| filter @message like "RECEIPT_ID_HERE"
| sort @timestamp asc
| limit 100
```

Pipeline Lambda log groups:
- `/aws/lambda/novascan-{stage}-load-custom-categories`
- `/aws/lambda/novascan-{stage}-textract-extract`
- `/aws/lambda/novascan-{stage}-nova-structure`
- `/aws/lambda/novascan-{stage}-bedrock-extract`
- `/aws/lambda/novascan-{stage}-finalize`

### Finding errors across all Lambdas

```
# CloudWatch Logs Insights — all NovaScan Lambdas
fields @timestamp, service, level, message, exception
| filter level = "ERROR"
| sort @timestamp desc
| limit 50
```

### X-Ray tracing

All Lambdas have active tracing enabled (`Tracing.ACTIVE`). To find a trace:

```bash
# Find trace by trace ID (from logs)
aws xray get-trace-summaries \
  --start-time $(date -u -v-1H +%s) \
  --end-time $(date -u +%s) \
  --filter-expression 'annotation.Service = "novascan-finalize"'

# Get full trace details
aws xray batch-get-traces --trace-ids "1-abc-def"
```

Or use the AWS X-Ray console: filter by service name `novascan-{stage}-*` to see the full pipeline execution graph (LoadCustomCategories -> Parallel[Textract+Nova, Bedrock] -> Finalize).

---

## 2. Pipeline Failures

### 2.1 Textract Timeout

**Symptoms:**
- Receipt stays in `processing` status indefinitely
- Step Functions execution shows `TextractExtract` step failed or timed out
- Finalize Lambda logs show `"pipeline_type": "ocr-ai", "error": "textract_extract_failed"`

**Diagnosis:**

```
# CloudWatch Logs Insights — Textract Lambda
fields @timestamp, message, exception
| filter service = "novascan-textract-extract"
| filter level = "ERROR"
| sort @timestamp desc
| limit 20
```

```bash
# Check Step Functions execution history
aws stepfunctions list-executions \
  --state-machine-arn "arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:novascan-{stage}-receipt-pipeline" \
  --status-filter FAILED \
  --max-results 10

# Get execution details (replace EXECUTION_ARN)
aws stepfunctions get-execution-history \
  --execution-arn "EXECUTION_ARN" \
  --reverse-order
```

Common causes:
- Image is too large or corrupted (check S3 object size)
- Textract service throttling (check `ProvisionedThroughputExceededException` in logs)
- Lambda timeout at 120 seconds (check if the image is very high resolution)

**Fix:**

If Textract is consistently slow, the shadow pipeline (Bedrock direct multimodal) should have succeeded as a fallback. Check the receipt status:

```bash
aws dynamodb get-item \
  --table-name "novascan-{stage}" \
  --key '{"PK": {"S": "USER#USER_ID"}, "SK": {"S": "RECEIPT#RECEIPT_ID"}}' \
  --projection-expression "#s, usedFallback, failureReason" \
  --expression-attribute-names '{"#s": "status"}'
```

If `usedFallback` is `true`, the receipt was processed successfully by the shadow pipeline. If both failed, see [2.3 Both Pipelines Fail](#23-both-pipelines-fail).

To retry, see [Section 7: Replaying a Failed Pipeline Execution](#7-replaying-a-failed-pipeline-execution).

---

### 2.2 Bedrock Throttling

**Symptoms:**
- `bedrock_extract_failed` or `nova_structure_failed` error in Finalize Lambda logs
- `ThrottlingException` in Bedrock Lambda exception tracebacks
- CloudWatch metric `NovaScan/PipelineCompleted` with `Outcome=failure` for `PipelineType=ai-multimodal` or `PipelineType=ocr-ai`

**Diagnosis:**

```
# CloudWatch Logs Insights — Bedrock-related Lambdas
fields @timestamp, service, message, exception
| filter (service = "novascan-bedrock-extract" or service = "novascan-nova-structure")
| filter level = "ERROR"
| sort @timestamp desc
| limit 20
```

```bash
# Check Bedrock service quotas
aws service-quotas get-service-quota \
  --service-code bedrock \
  --quota-code L-XXXXXXXX
```

**Fix:**

- If this is intermittent, the Step Functions Catch block handles it and the other pipeline branch (if successful) is used as fallback.
- For sustained throttling, request a quota increase via the Service Quotas console.
- Verify the model ID environment variable is correct: `NOVA_MODEL_ID` should be `amazon.nova-lite-v1:0` (default) or `amazon.nova-pro-v1:0`.

```bash
# Check the Lambda environment variable
aws lambda get-function-configuration \
  --function-name "novascan-{stage}-bedrock-extract" \
  --query "Environment.Variables.NOVA_MODEL_ID"
```

---

### 2.3 Both Pipelines Fail

**Symptoms:**
- Receipt status is `failed` in DynamoDB
- `failureReason` attribute says `"Pipeline processing failed. Check CloudWatch logs for details."`
- Finalize Lambda logs contain `"Both pipelines failed"` at ERROR level with `main_error` and `shadow_error` fields

**Diagnosis:**

```
# CloudWatch Logs Insights — Finalize Lambda
fields @timestamp, message, main_error, main_error_type, shadow_error, shadow_error_type
| filter service = "novascan-finalize"
| filter message = "Both pipelines failed"
| sort @timestamp desc
| limit 10
```

Check each pipeline's error independently:

```bash
# Query pipeline result records from DynamoDB
aws dynamodb query \
  --table-name "novascan-{stage}" \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{
    ":pk": {"S": "USER#USER_ID"},
    ":sk": {"S": "RECEIPT#RECEIPT_ID#PIPELINE#"}
  }'
```

The `error` and `errorType` fields on each PIPELINE record indicate the classification (e.g., `ThrottlingException`, `ValidationError`). Full exception details are only in CloudWatch logs (H4 sanitization).

**Fix:**

1. Identify the root cause from both pipeline logs (typically: corrupt image, unsupported format, or simultaneous service outage).
2. If the image is valid, replay the pipeline (see [Section 7](#7-replaying-a-failed-pipeline-execution)).
3. If the image is corrupt, delete the receipt and ask the user to re-upload.

---

### 2.4 S3 Event Not Triggering SQS

**Symptoms:**
- Image uploaded successfully to S3 (presigned URL returned 200)
- Receipt stays in `processing` status forever
- No Step Functions execution appears for this receipt
- SQS queue is empty (no messages in flight or available)

**Diagnosis:**

```bash
# Verify S3 event notification is configured
aws s3api get-bucket-notification-configuration \
  --bucket "novascan-{stage}-receipts-ACCOUNT_HASH"

# Check SQS queue attributes (messages in flight, approximate count)
aws sqs get-queue-attributes \
  --queue-url "https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/novascan-{stage}-receipt-pipeline" \
  --attribute-names All

# Check the DLQ for poison messages
aws sqs get-queue-attributes \
  --queue-url "https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/novascan-{stage}-receipt-pipeline-dlq" \
  --attribute-names ApproximateNumberOfMessages

# Check EventBridge Pipe status
aws pipes describe-pipe --name "novascan-{stage}-receipt-pipe"
```

**Fix:**

- **Pipe errors in logs:** Check the EventBridge Pipe log group for errors:
  ```bash
  aws logs tail "/aws/vendedlogs/pipes/novascan-${STAGE}-receipt-pipe" --follow --format short
  ```
- **S3 notification missing:** This means CDK deploy did not complete or the notification was manually removed. Re-deploy: `python scripts/deploy.py backend {stage}`.
- **EventBridge Pipe is STOPPED:** Restart it:
  ```bash
  aws pipes start-pipe --name "novascan-{stage}-receipt-pipe"
  ```
- **SQS permissions:** Verify the SQS resource policy allows `s3.amazonaws.com` to send messages. The CDK construct adds this policy, but manual changes may have removed it.
- **S3 key prefix mismatch:** The notification filter is `prefix=receipts/`. Verify the uploaded object key starts with `receipts/` (the upload handler always creates keys in this format: `receipts/{ULID}.{ext}`).
- **DLQ has messages:** Messages that failed processing 3 times are moved to the DLQ. Read a message to inspect the failure:
  ```bash
  aws sqs receive-message \
    --queue-url "https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/novascan-{stage}-receipt-pipeline-dlq" \
    --max-number-of-messages 1
  ```

---

### 2.5 EventBridge Pipe Failures (SQS → Step Functions)

**Symptoms:**
- SQS message consumed (not visible in queue) but no Step Functions execution starts
- CloudTrail shows `InvalidExecutionInput` on `StartExecution`
- Pipe log group shows errors

**Diagnosis:**

```bash
# Check Pipe log group for errors
aws logs tail "/aws/vendedlogs/pipes/novascan-${STAGE}-receipt-pipe" --follow --format short

# Check CloudTrail for StartExecution failures
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=StartExecution \
  --max-results 10
```

Common causes:
- **Pipe input template produces invalid JSON.** The `<$.field>` syntax does raw string interpolation — if the value contains JSON (quotes, braces), the result is broken. Always extract leaf values via JSONPath (e.g., `<$.body.Records[0].s3.bucket.name>`) instead of passing nested blobs.
- **Batch wrapping.** EventBridge Pipes with SQS source always sends a batch (JSON array) to the target, even with `batch_size=1`. The Lambda receives `[item]` not `item`. The `LoadCustomCategories` handler unwraps this.

**Fix:**

If the input template is broken, fix it in `infra/cdkconstructs/pipeline.py` and redeploy. The current template extracts `bucket` and `key` directly from the S3 event.

---

### 2.6 Infinite Pipeline Loop

**Symptoms:**
- One receipt upload produces many Step Functions executions (~20 seconds apart)
- CloudWatch metrics show repeated `PipelineCompleted` events for the same receipt
- `LoadCustomCategories` logs show `"Receipt already processed, skipping pipeline"`

**Diagnosis:**

This is caused by the Finalize Lambda's `copy_object` call (which updates S3 object metadata) re-triggering the S3 `ObjectCreated` event notification. The pipeline re-runs for the same receipt indefinitely.

The idempotency guard in `LoadCustomCategories` prevents data corruption — it checks the receipt's DynamoDB status and short-circuits with `{"skip": true}` if the receipt is already `confirmed` or `failed`. The `CheckSkip` Choice state in Step Functions routes to `Succeed` immediately.

```
# Check how many times the guard fired
fields @timestamp, receipt_id, message
| filter message = "Receipt already processed, skipping pipeline"
| sort @timestamp desc
| limit 50
```

**Fix:**

The idempotency guard is the current fix. Each re-triggered execution completes instantly (LoadCustomCategories → CheckSkip → Succeed) with no data mutation. The loop is harmless but wastes Step Functions executions. If the volume is a concern, consider using a separate S3 prefix for processed objects or filtering S3 events by metadata.

---

### 2.7 Orphaned Processing Receipts

**Symptoms:**
- Receipts list shows entries permanently stuck in `processing` status
- No Step Functions execution exists for these receipts
- The receipt has no pipeline result records in DynamoDB

**Diagnosis:**

```bash
# Query the receipt record
aws dynamodb get-item \
  --table-name "novascan-{stage}" \
  --key '{"PK": {"S": "USER#USER_ID"}, "SK": {"S": "RECEIPT#RECEIPT_ID"}}' \
  --projection-expression "#s, imageKey, createdAt" \
  --expression-attribute-names '{"#s": "status"}'
```

If `status` is `processing` and no pipeline records exist, the S3 upload likely failed after the DynamoDB record was created. This happens when:
- The S3 presigned URL PUT failed (CORS misconfiguration, network error, browser closed mid-upload)
- The S3 event notification didn't fire (see [2.4](#24-s3-event-not-triggering-sqs))

**Fix:**

Delete the orphaned receipt via the UI (receipt detail → delete button) or directly:

```bash
aws dynamodb delete-item \
  --table-name "novascan-{stage}" \
  --key '{"PK": {"S": "USER#USER_ID"}, "SK": {"S": "RECEIPT#RECEIPT_ID"}}'
```

---

## 3. API Failures

### 3.1 401 Unauthorized (Expired Token)

**Symptoms:**
- API returns HTTP 401 with `{"message": "Unauthorized"}`
- Browser network tab shows the `Authorization` header is present but the JWT is expired
- This happens after the user has been idle for a while

**Diagnosis:**

The API Gateway JWT authorizer validates the `Authorization: Bearer {idToken}` header. A 401 means the token is expired or malformed. This is handled entirely by API Gateway -- the Lambda is never invoked.

Decode the JWT to check expiration:

```bash
# Decode JWT payload (base64, no verification)
echo "PASTE_TOKEN_HERE" | cut -d. -f2 | base64 -d 2>/dev/null | python3 -m json.tool
```

Check the `exp` claim (Unix timestamp). Cognito ID tokens expire after 1 hour by default.

**Fix:**

- The frontend should automatically refresh the token using the refresh token before the ID token expires.
- If refresh fails, the user must re-authenticate (start a new OTP flow).
- Check the frontend auth service code for token refresh logic. The Cognito `InitiateAuth` with `REFRESH_TOKEN_AUTH` flow should be called proactively before expiry.

---

### 3.2 403 Forbidden (Wrong User / Insufficient Role)

**Symptoms:**
- API returns HTTP 403
- The user is authenticated but trying to access a resource they do not own, or an endpoint restricted to a higher role (`staff` or `admin`)

**Diagnosis:**

All DynamoDB queries are scoped to `PK = USER#{authenticated userId}`. A 403 typically means:
1. The user is trying to access an admin-only endpoint without the required Cognito group.
2. The JWT `cognito:groups` claim does not include the required group.

```bash
# Check user's Cognito groups
aws cognito-idp admin-list-groups-for-user \
  --user-pool-id "USER_POOL_ID" \
  --username "USERNAME"
```

**Fix:**

- If the user needs a higher role, promote them via Cognito:
  ```bash
  aws cognito-idp admin-add-user-to-group \
    --user-pool-id "USER_POOL_ID" \
    --username "USERNAME" \
    --group-name "admin"
  ```
- If this is a data isolation issue (user trying to access another user's receipt), the error response is `NOT_FOUND` (404), not 403. The API never reveals that another user's data exists.

---

### 3.3 500 Internal Server Error

**Symptoms:**
- API returns HTTP 500 with a generic error body
- The `x-amzn-requestid` response header contains the request ID

**Diagnosis:**

```
# CloudWatch Logs Insights — API Lambda
fields @timestamp, level, message, exception, correlation_id
| filter service = "novascan-api" or function_name like "novascan-{stage}-api"
| filter level = "ERROR"
| sort @timestamp desc
| limit 20
```

Or search by the specific request ID:

```
fields @timestamp, level, message, exception
| filter correlation_id = "REQUEST_ID_FROM_HEADER"
| sort @timestamp asc
```

Common causes:
- `TABLE_NAME` environment variable missing or DynamoDB table does not exist
- `RECEIPTS_BUCKET` environment variable missing
- DynamoDB ConditionCheckFailedException (data consistency issue)
- Pydantic validation error on response serialization (bug in response model)
- boto3 client error (permissions, throttling)

**Fix:**

1. Read the exception traceback from CloudWatch logs.
2. If it is a missing environment variable, verify Lambda configuration:
   ```bash
   aws lambda get-function-configuration \
     --function-name "novascan-{stage}-api" \
     --query "Environment.Variables"
   ```
3. If it is a permissions error, check the Lambda execution role:
   ```bash
   aws lambda get-function-configuration \
     --function-name "novascan-{stage}-api" \
     --query "Role"
   ```
   Then check the role's attached policies in IAM.
4. Re-deploy if configuration drift is suspected: `cd infra && uv run cdk deploy --context stage={stage}`.

---

### 3.4 CORS Errors

**Symptoms:**
- Browser console shows `Access-Control-Allow-Origin` errors
- API requests fail in the browser but work from `curl`
- Preflight `OPTIONS` requests return unexpected headers

**Diagnosis:**

CORS is configured on the API Gateway HTTP API. The allowed origin must match the frontend domain exactly:
- **dev:** CloudFront default URL (e.g., `https://d1234abcdef.cloudfront.net`)
- **prod:** `https://subdomain.example.com`

```bash
# Check API Gateway CORS configuration
aws apigatewayv2 get-api \
  --api-id "API_ID" \
  --query "CorsConfiguration"
```

**Fix:**

- If the frontend domain changed (e.g., new CloudFront distribution), update the CDK config (`frontendUrl` in `cdk.json` or the stage context) and redeploy.
- If testing locally (`http://localhost:5173`), the CORS config does not include localhost. Use the Vite proxy configuration or temporarily add the origin to the CDK config for dev.
- Allowed methods must include the method being called: `GET, POST, PUT, DELETE, OPTIONS`.
- Allowed headers must include `Authorization` and `Content-Type`.

**Note: S3 presigned upload CORS is separate from API Gateway CORS.** If receipt image uploads fail with a CORS error, the issue is the S3 receipts bucket CORS configuration, not API Gateway. The bucket must allow PUT from the frontend origin. CDK configures this automatically (`storage.py`), but verify:

```bash
aws s3api get-bucket-cors \
  --bucket "$(aws cloudformation describe-stacks \
    --stack-name novascan-{stage} \
    --query 'Stacks[0].Outputs[?OutputKey==`ReceiptsBucketName`].OutputValue' \
    --output text)"
```

---

## 4. Auth Failures

### 4.1 OTP Not Received

**Symptoms:**
- User initiates sign-in / sign-up but the OTP email never arrives
- No error message shown in the frontend

**Diagnosis:**

Cognito sends OTP codes via SES (or Cognito's built-in email for dev). Check Cognito delivery status:

```bash
# Check SES sending statistics (if using SES)
aws ses get-send-statistics

# Check Cognito User Pool email configuration
aws cognito-idp describe-user-pool \
  --user-pool-id "USER_POOL_ID" \
  --query "UserPool.EmailConfiguration"
```

Common causes:
- SES is in sandbox mode and the recipient email is not verified
- Cognito's built-in email has a 50 emails/day limit
- The email is in spam/junk folder
- The user typed the wrong email address

**Fix:**

- Check the spam/junk folder first.
- If using SES sandbox, verify the recipient email:
  ```bash
  aws ses verify-email-identity --email-address "user@example.com"
  ```
- If the daily limit is hit, wait 24 hours or move SES out of sandbox mode.
- To resend the code, have the user click "Resend code" in the frontend, which calls Cognito's `ResendConfirmationCode` or re-initiates the auth flow.

---

### 4.2 Session Expired

**Symptoms:**
- User is suddenly logged out mid-session
- API calls start returning 401
- The frontend redirects to the login page

**Diagnosis:**

Cognito token lifetimes:
- **ID token:** 1 hour (not configurable for hosted UI, configurable via API)
- **Access token:** 1 hour
- **Refresh token:** 7 days (configured in `infra/cdkconstructs/auth.py`)

If the ID token expired and the refresh token is still valid, the frontend should silently refresh. If it does not, check the frontend auth service.

**Fix:**

- Verify the frontend implements token refresh:
  ```
  Cognito InitiateAuth with AuthFlow=REFRESH_TOKEN_AUTH
  ```
- If the refresh token is also expired (7 days), the user must re-authenticate.
- Check the User Pool refresh token expiration setting:
  ```bash
  aws cognito-idp describe-user-pool \
    --user-pool-id "USER_POOL_ID" \
    --query "UserPool.TokenValidityUnits"
  ```

---

### 4.3 Refresh Token Invalid

**Symptoms:**
- Token refresh call returns `NotAuthorizedException: Invalid Refresh Token`
- User is forced to re-authenticate

**Diagnosis:**

Common causes:
- Refresh token was revoked (admin action or user signed out on another device)
- Refresh token expired (default 7 days)
- The app client ID changed (token was issued by a different app client)
- User was disabled or deleted in Cognito

```bash
# Check if the user exists and is enabled
aws cognito-idp admin-get-user \
  --user-pool-id "USER_POOL_ID" \
  --username "USERNAME"
```

**Fix:**

- If the user exists and is enabled, have them re-authenticate to get a new refresh token.
- If the user was disabled, re-enable them:
  ```bash
  aws cognito-idp admin-enable-user \
    --user-pool-id "USER_POOL_ID" \
    --username "USERNAME"
  ```
- If the app client ID changed after a CDK deploy, all existing refresh tokens are invalidated. Users must re-authenticate.

---

## 5. Frontend Failures

### 5.1 Blank Page After Deploy (S3 Issue)

**Symptoms:**
- Visiting the site shows a blank white page
- Browser console shows 404 errors for JavaScript/CSS assets
- `index.html` loads but references assets that do not exist in S3

**Diagnosis:**

```bash
# Check if index.html exists in the S3 bucket
aws s3 ls "s3://novascan-{stage}-frontend/" --recursive | head -20

# Check CloudFront origin configuration
aws cloudfront get-distribution \
  --id "DISTRIBUTION_ID" \
  --query "Distribution.DistributionConfig.Origins"
```

Common causes:
- `aws s3 sync` was not run after `npm run build`
- The build output directory is wrong (should be `frontend/dist/`)
- S3 bucket policy blocks access from CloudFront
- The Vite `base` path does not match the deployment (should be `/`)

**Fix:**

Rebuild and redeploy the frontend. The deploy script handles build, S3 sync, and CloudFront invalidation, and auto-injects the correct env vars from CloudFormation:

```bash
python scripts/deploy.py frontend {stage}
```

---

### 5.2 Stale Content (CloudFront Cache)

**Symptoms:**
- The frontend shows an old version of the app after a deploy
- New features or bug fixes are not visible
- Hard refresh (Ctrl+Shift+R) shows the correct version

**Diagnosis:**

CloudFront caches objects at edge locations. After an S3 sync, the old cached version is still served until the TTL expires or the cache is invalidated.

```bash
# Check if there are pending invalidations
aws cloudfront list-invalidations \
  --distribution-id "DISTRIBUTION_ID" \
  --query "InvalidationList.Items[*].{Id:Id,Status:Status,CreateTime:CreateTime}" \
  --output table
```

**Fix:**

Create a CloudFront invalidation to purge the cache:

```bash
aws cloudfront create-invalidation \
  --distribution-id "DISTRIBUTION_ID" \
  --paths "/*"
```

The invalidation typically completes within 1-2 minutes. Check status:

```bash
aws cloudfront get-invalidation \
  --distribution-id "DISTRIBUTION_ID" \
  --id "INVALIDATION_ID"
```

To prevent this in the future, always run the invalidation after `aws s3 sync`. Vite's hashed asset filenames (e.g., `assets/index-abc123.js`) help with cache busting for JS/CSS, but `index.html` itself is not hashed and must be invalidated.

---

### 5.3 CSP Blocking Receipt Images

**Symptoms:**
- Receipt detail page shows broken image placeholder
- Browser console shows: `Refused to load the image '...' because it violates the following Content Security Policy directive: "img-src 'self' data: blob:"`

**Diagnosis:**

The CloudFront `ResponseHeadersPolicy` sets a Content Security Policy. Receipt images are loaded from S3 presigned URLs (a different origin from CloudFront), which requires the S3 domain in the `img-src` directive.

**Fix:**

The current CSP includes `https://*.s3.amazonaws.com` in `img-src`. If this is missing after a CDK change, verify the CSP in `infra/cdkconstructs/frontend.py` includes:

```python
"img-src 'self' data: blob: https://*.s3.amazonaws.com; "
```

Redeploy and invalidate CloudFront cache:

```bash
python scripts/deploy.py backend {stage}
python scripts/deploy.py frontend {stage}
```

**Tip:** Always check the browser console for CSP violations after modifying security headers. CSP wildcards only work in the leftmost label (`*.example.com` is valid, `*.sub.*.example.com` is not). Invalid entries are silently ignored.

---

## 6. CDK / Infrastructure Failures

### 6.1 Deploy Fails (Resource Limit / IAM Permission)

**Symptoms:**
- `cdk deploy` fails with a CloudFormation rollback
- Error message mentions `CREATE_FAILED`, `UPDATE_FAILED`, or `ROLLBACK_COMPLETE`
- Specific errors: `LimitExceededException`, `AccessDeniedException`, or resource-specific quota errors

**Diagnosis:**

```bash
# Check CloudFormation stack events for the failure reason
aws cloudformation describe-stack-events \
  --stack-name "novascan-{stage}" \
  --query "StackEvents[?ResourceStatus=='CREATE_FAILED' || ResourceStatus=='UPDATE_FAILED'].{Resource:LogicalResourceId,Reason:ResourceStatusReason,Time:Timestamp}" \
  --output table

# Check current stack status
aws cloudformation describe-stacks \
  --stack-name "novascan-{stage}" \
  --query "Stacks[0].StackStatus"
```

Common resource limit issues:
- **Lambda function limit:** Default 75 concurrent executions per account (adjustable)
- **API Gateway API limit:** 600 APIs per region
- **S3 bucket name collision:** Bucket names are globally unique
- **IAM role name collision:** Role names must be unique within the account
- **Cognito User Pool limit:** 1,000 per account per region

**Fix:**

1. **Resource limit:** Request a quota increase via the Service Quotas console or AWS Support.
2. **IAM permission:** Ensure the deploying role/user has sufficient permissions. CDK requires broad permissions for resource creation. Check the specific `AccessDeniedException` message for the missing permission.
3. **Stack in ROLLBACK_COMPLETE:** A stack in this state must be deleted before re-deploying:
   ```bash
   aws cloudformation delete-stack --stack-name "novascan-{stage}"
   aws cloudformation wait stack-delete-complete --stack-name "novascan-{stage}"
   cd infra && uv run cdk deploy --context stage={stage}
   ```
   **Warning:** Deleting a stack destroys all its resources. For production, use `cdk deploy` with `--no-rollback` during debugging to preserve resources on failure, then fix the issue and continue the update.
4. **Name collision:** CDK uses `novascan-{stage}-{resource}` naming. If a resource with that name already exists outside CDK, either import it or rename it.

---

### 6.2 Drift Detection

**Symptoms:**
- CDK deploy succeeds but resources do not behave as expected
- Manual changes were made in the AWS Console that conflict with CDK state
- `cdk diff` shows unexpected changes

**Diagnosis:**

```bash
# Run CDK diff to compare desired state with deployed state
cd infra && uv run cdk diff --context stage={stage}

# Detect drift via CloudFormation
aws cloudformation detect-stack-drift --stack-name "novascan-{stage}"

# Wait for detection to complete, then check results
aws cloudformation describe-stack-drift-detection-status \
  --stack-drift-detection-id "DETECTION_ID"

# List drifted resources
aws cloudformation describe-stack-resource-drifts \
  --stack-name "novascan-{stage}" \
  --stack-resource-drift-status-filters MODIFIED DELETED
```

**Fix:**

- **Reconcile drift:** If manual changes were intentional, update the CDK code to match and deploy. If accidental, re-deploy CDK to overwrite the manual changes:
  ```bash
  cd infra && uv run cdk deploy --context stage={stage}
  ```
- **Avoid drift:** Do not make manual changes to CDK-managed resources. All infrastructure changes should go through CDK.
- If a resource was manually deleted, CDK deploy may fail trying to update it. Check the CloudFormation events and either re-create the resource manually or delete the stack and redeploy.

---

### 6.3 Lambda Import Failure (Cross-Platform Bundling)

**Symptoms:**
- Every Lambda invocation returns 500 immediately after deploy
- CloudWatch logs show:
  ```
  [ERROR] Runtime.ImportModuleError: Unable to import module 'api.app':
  No module named 'pydantic_core._pydantic_core'
  ```
- Other common variants: missing `_cffi_backend`, `cryptography._rust`, or any `_<native_module>`

**Diagnosis:**

This happens when Lambda dependencies are packaged on macOS (ARM64 or x86) instead of Linux x86_64. Python packages with native C extensions (pydantic, cryptography, etc.) include platform-specific `.so` files that are incompatible across architectures.

The CDK bundling in `infra/cdkconstructs/api.py` and `pipeline.py` uses `uv pip install` with `--python-platform manylinux2014_x86_64` to cross-compile. If these flags are missing or the Docker fallback is used without the correct platform target, the wrong binaries get packaged.

**Fix:**

Verify the `_UvLocalBundling.try_bundle()` methods include the cross-platform flags:

```python
"uv", "pip", "install",
"--python-platform", "manylinux2014_x86_64",
"--python-version", "3.13",
```

Redeploy after fixing:

```bash
python scripts/deploy.py backend {stage}
```

---

## 7. Replaying a Failed Pipeline Execution

There are two approaches to retry a failed receipt pipeline execution.

### Option A: Re-upload the image (triggers full pipeline)

This is the safest approach. It creates a new receipt record and triggers the entire pipeline from scratch.

```bash
# 1. Get the image key from the failed receipt
aws dynamodb get-item \
  --table-name "novascan-{stage}" \
  --key '{"PK": {"S": "USER#USER_ID"}, "SK": {"S": "RECEIPT#RECEIPT_ID"}}' \
  --projection-expression "imageKey"

# 2. Download the image locally
aws s3 cp "s3://BUCKET/receipts/RECEIPT_ID.jpg" /tmp/receipt.jpg

# 3. Delete the failed receipt via API (or leave it for reference)
# The user can re-upload through the frontend, which generates a new
# presigned URL, creates a new receipt record, and triggers the pipeline.
```

### Option B: Manual Step Functions trigger (re-process existing image)

This re-runs the pipeline for an existing receipt without re-uploading. The Finalize Lambda uses idempotency guards (`ConditionExpression: updatedAt < :now`) to prevent stale overwrites.

```bash
# 1. Get receipt details
aws dynamodb get-item \
  --table-name "novascan-{stage}" \
  --key '{"PK": {"S": "USER#USER_ID"}, "SK": {"S": "RECEIPT#RECEIPT_ID"}}' \
  --projection-expression "imageKey, receiptId, PK"

# 2. Extract userId from PK (strip "USER#" prefix)
# userId = PK value without "USER#"

# 3. Get the receipts bucket name
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "novascan-{stage}" \
  --query "Stacks[0].Outputs[?OutputKey=='ReceiptsBucketName'].OutputValue" \
  --output text)

# 4. Start a new Step Functions execution
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:novascan-{stage}-receipt-pipeline" \
  --input '{
    "bucket": "'"$BUCKET"'",
    "key": "receipts/RECEIPT_ID.jpg",
    "userId": "USER_ID",
    "receiptId": "RECEIPT_ID"
  }'

# 5. Monitor execution
aws stepfunctions describe-execution \
  --execution-arn "RETURNED_EXECUTION_ARN"
```

Note: When providing `userId` and `receiptId` in the input, the `LoadCustomCategories` Lambda skips the S3 event parsing and GSI2 lookup, and directly loads custom categories for the given user.

---

## 8. DynamoDB Inspection Examples

Table name: `novascan-{stage}`

### Key schema reference

| Entity | PK | SK | Notes |
|--------|----|----|-------|
| Receipt | `USER#{userId}` | `RECEIPT#{ulid}` | Main receipt record |
| Line Item | `USER#{userId}` | `RECEIPT#{ulid}#ITEM#{nnn}` | nnn = 3-digit zero-padded index |
| Pipeline Result | `USER#{userId}` | `RECEIPT#{ulid}#PIPELINE#{type}` | type = `ocr-ai` or `ai-multimodal` |
| Custom Category | `USER#{userId}` | `CUSTOMCAT#{slug}` | User-defined categories |
| Profile | `USER#{userId}` | `PROFILE` | User profile record |

### Query a receipt and all its sub-items

```bash
aws dynamodb query \
  --table-name "novascan-{stage}" \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{
    ":pk": {"S": "USER#USER_ID"},
    ":sk": {"S": "RECEIPT#RECEIPT_ID"}
  }'
```

This returns the receipt record, all line items (`RECEIPT#...#ITEM#001`, etc.), and both pipeline result records (`RECEIPT#...#PIPELINE#ocr-ai`, `RECEIPT#...#PIPELINE#ai-multimodal`).

### Get just the receipt status

```bash
aws dynamodb get-item \
  --table-name "novascan-{stage}" \
  --key '{"PK": {"S": "USER#USER_ID"}, "SK": {"S": "RECEIPT#RECEIPT_ID"}}' \
  --projection-expression "#s, merchant, #t, failureReason, usedFallback, updatedAt" \
  --expression-attribute-names '{"#s": "status", "#t": "total"}'
```

### List all receipts for a user (via GSI1)

```bash
aws dynamodb query \
  --table-name "novascan-{stage}" \
  --index-name "GSI1" \
  --key-condition-expression "GSI1PK = :pk" \
  --expression-attribute-values '{
    ":pk": {"S": "USER#USER_ID"}
  }' \
  --scan-index-forward false \
  --projection-expression "receiptId, #s, merchant, #t, createdAt" \
  --expression-attribute-names '{"#s": "status", "#t": "total"}'
```

### Find a receipt by receiptId (via GSI2)

Useful when you only have the receipt ID and not the user ID:

```bash
aws dynamodb query \
  --table-name "novascan-{stage}" \
  --index-name "GSI2" \
  --key-condition-expression "GSI2PK = :pk" \
  --expression-attribute-values '{
    ":pk": {"S": "RECEIPT_ID"}
  }' \
  --projection-expression "PK, SK, #s, merchant" \
  --expression-attribute-names '{"#s": "status"}'
```

### List pipeline results for a receipt

```bash
aws dynamodb query \
  --table-name "novascan-{stage}" \
  --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
  --expression-attribute-values '{
    ":pk": {"S": "USER#USER_ID"},
    ":sk": {"S": "RECEIPT#RECEIPT_ID#PIPELINE#"}
  }' \
  --projection-expression "SK, modelId, processingTimeMs, confidence, rankingScore, #e, errorType" \
  --expression-attribute-names '{"#e": "error"}'
```

### Count receipts by status for a user

```bash
aws dynamodb query \
  --table-name "novascan-{stage}" \
  --index-name "GSI1" \
  --key-condition-expression "GSI1PK = :pk" \
  --filter-expression "#s = :status" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{
    ":pk": {"S": "USER#USER_ID"},
    ":status": {"S": "failed"}
  }' \
  --select COUNT
```

### Check the DLQ for unprocessed messages

```bash
# Get DLQ URL
DLQ_URL=$(aws sqs get-queue-url \
  --queue-name "novascan-{stage}-receipt-pipeline-dlq" \
  --query "QueueUrl" --output text)

# Check message count
aws sqs get-queue-attributes \
  --queue-url "$DLQ_URL" \
  --attribute-names ApproximateNumberOfMessages

# Read a message (does not delete it)
aws sqs receive-message \
  --queue-url "$DLQ_URL" \
  --max-number-of-messages 1 \
  --visibility-timeout 0
```
