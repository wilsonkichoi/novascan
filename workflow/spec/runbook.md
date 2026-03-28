# NovaScan Runbook

Operational guide organized by component. Each section covers local dev, deploy, rollback, and troubleshooting independently.

---

## 1. API Lambda

### Local Development

```bash
cd backend && uv venv --python 3.13 && uv sync
cd backend && uv run pytest                          # run tests
cd backend && uv run pytest --cov=novascan --cov-report=term-missing  # with coverage
cd backend && uv run ruff check .                    # lint
cd backend && uv run mypy src/                       # type check
```

### Deploy (CDK — updates API Lambda only if code changed)

```bash
cd infra && uv run cdk deploy --context stage=dev
```

CDK detects which resources changed and only updates those. If only the API Lambda code changed, only that function is updated.

### Hot Deploy (skip CDK — fastest iteration)

```bash
cd backend
uv pip install --target .build/layer/python .
cp -r src/novascan .build/layer/python/
cd .build/layer && zip -r ../lambda.zip . && cd ../..
aws lambda update-function-code \
  --function-name novascan-dev-api \
  --zip-file fileb://.build/lambda.zip
```

This bypasses CDK entirely — no synth, no diff, just code update. Takes ~10 seconds vs 2-5 minutes.

### Rollback

```bash
# List recent versions
aws lambda list-versions-by-function --function-name novascan-dev-api \
  --query 'Versions[-5:].[Version, Description, LastModified]'

# Rollback to a previous version (if using aliases)
aws lambda update-alias --function-name novascan-dev-api \
  --name live --function-version <version-number>

# Or redeploy the previous CDK state
cd infra && git stash && uv run cdk deploy --context stage=dev && git stash pop
```

### Troubleshoot

**500 errors on API calls:**
```bash
# Check CloudWatch logs for the API Lambda
aws logs filter-log-events \
  --log-group-name /aws/lambda/novascan-dev-api \
  --start-time $(date -v-1H +%s)000 \
  --filter-pattern "ERROR"
```

**Auth issues (401 on all calls):**
- Verify Cognito authorizer is configured on API Gateway
- Check the ID token is not expired (decode at jwt.io for debugging)
- Verify the Cognito User Pool ID and Client ID match between frontend env vars and CDK outputs

**Slow responses:**
- Check X-Ray traces for the API Lambda (AWS Console → X-Ray → Traces)
- Cold start flag appears in structured logs (`"cold_start": true`)
- If DynamoDB is slow, check consumed capacity in CloudWatch metrics

---

## 2. OCR Pipeline

### Local Development

Pipeline Lambdas share the same backend project:

```bash
cd backend && uv run pytest tests/unit/pipeline/     # pipeline tests only
cd backend && uv run pytest tests/integration/        # integration tests (needs DynamoDB Local)

# Start DynamoDB Local for integration tests
docker run -d -p 8000:8000 amazon/dynamodb-local
```

### Deploy (CDK — updates pipeline Lambdas, Step Functions, SQS, Pipes)

```bash
cd infra && uv run cdk deploy --context stage=dev
```

If only pipeline Lambda code changed, CDK updates those functions without touching the API Lambda or frontend.

### Hot Deploy (individual pipeline Lambda)

```bash
cd backend
uv pip install --target .build/layer/python .
cp -r src/novascan .build/layer/python/
cd .build/layer && zip -r ../lambda.zip . && cd ../..

# Update a specific pipeline Lambda (choose one):
aws lambda update-function-code --function-name novascan-dev-textract-extract --zip-file fileb://.build/lambda.zip
aws lambda update-function-code --function-name novascan-dev-nova-structure --zip-file fileb://.build/lambda.zip
aws lambda update-function-code --function-name novascan-dev-bedrock-extract --zip-file fileb://.build/lambda.zip
aws lambda update-function-code --function-name novascan-dev-finalize --zip-file fileb://.build/lambda.zip
```

### Rollback

Same as API Lambda — use version numbers or redeploy previous CDK state. Each pipeline Lambda is independently versioned.

### Change Pipeline Configuration

Pipeline settings in `cdk.json` under `context.config.{stage}`:

```bash
# Edit pipelineMaxConcurrency, defaultPipeline, etc. in cdk.json, then:
cd infra && uv run cdk deploy --context stage=dev
```

### Force Reprocess a Receipt

If a receipt needs reprocessing (e.g., pipeline was buggy and has since been fixed):

1. Delete existing pipeline results from DynamoDB:
   ```bash
   # Query for pipeline results
   aws dynamodb query --table-name novascan-dev \
     --key-condition-expression "PK = :pk AND begins_with(SK, :sk)" \
     --expression-attribute-values '{":pk":{"S":"USER#<userId>"},":sk":{"S":"RECEIPT#<ulid>#PIPELINE#"}}'
   ```

2. Set receipt status back to `processing`:
   ```bash
   aws dynamodb update-item --table-name novascan-dev \
     --key '{"PK":{"S":"USER#<userId>"},"SK":{"S":"RECEIPT#<ulid>"}}' \
     --update-expression "SET #s = :s" \
     --expression-attribute-names '{"#s":"status"}' \
     --expression-attribute-values '{":s":{"S":"processing"}}'
   ```

3. Send a new message to the SQS queue:
   ```bash
   aws sqs send-message --queue-url <queue-url> \
     --message-body '{"Records":[{"s3":{"bucket":{"name":"novascan-dev-receipts"},"object":{"key":"receipts/<receiptId>.jpg"}}}]}'
   ```

### Troubleshoot

**Receipt stuck in "processing":**

1. Check DynamoDB — is `status` still `processing`? How long ago was `createdAt`?

2. Check SQS — is the message in the queue or dead-letter queue?
   ```bash
   aws sqs get-queue-attributes --queue-url <queue-url> \
     --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
   ```

3. Check Step Functions — is there an execution for this receipt?
   ```bash
   aws stepfunctions list-executions --state-machine-arn <arn> --status-filter RUNNING
   ```

4. Check EventBridge Pipes — is the pipe enabled and at max concurrency?
   ```bash
   aws pipes describe-pipe --name novascan-dev-pipeline-pipe
   ```

5. Check CloudWatch Logs for the receipt ID:
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/novascan-dev-textract-extract \
     --filter-pattern "{$.receipt_id = \"<receipt-id>\"}"
   ```

**Pipeline failure (receipt status = "failed"):**

1. Check `failureReason` on the receipt record in DynamoDB
2. Check both pipeline results: `PIPELINE#ocr-ai` and `PIPELINE#ai-multimodal`
3. Check Step Functions execution history (Console → Step Functions → find execution by receipt ID)
4. Check individual Lambda logs for the specific Lambda that failed

**SQS Dead-Letter Queue:**

Messages land here after 3 failed processing attempts:

```bash
# Check DLQ depth
aws sqs get-queue-attributes --queue-url <dlq-url> \
  --attribute-names ApproximateNumberOfMessages

# Inspect a message
aws sqs receive-message --queue-url <dlq-url> --max-number-of-messages 1

# After fixing the issue, redrive messages back to main queue
aws sqs start-message-move-task --source-arn <dlq-arn> --destination-arn <main-queue-arn>
```

**Textract ThrottlingException:**
- Should never happen with EventBridge Pipes rate limiting. If it does, lower `pipelineMaxConcurrency` in `cdk.json` and redeploy.
- This indicates a genuine issue — investigate whether Pipes concurrency is misconfigured.

### View Recent Pipeline Activity

```bash
# Last 10 Step Functions executions
aws stepfunctions list-executions --state-machine-arn <arn> --max-results 10

# CloudWatch Insights: pipeline completions in last hour
aws logs start-query \
  --log-group-name /aws/lambda/novascan-dev-finalize \
  --start-time $(date -v-1H +%s) --end-time $(date +%s) \
  --query-string 'fields @timestamp, receipt_id, status, ranking_winner | sort @timestamp desc | limit 20'

# Check pipeline concurrency
aws stepfunctions list-executions --state-machine-arn <arn> --status-filter RUNNING \
  --query 'executions | length(@)'
```

---

## 3. Frontend

### Local Development

```bash
cd frontend && npm install                           # first time
cd frontend && npm run dev                           # dev server (hot reload)
cd frontend && npm run test                          # vitest
cd frontend && npm run build                         # production build
```

### Deploy (no CDK needed)

```bash
# Build with environment variables from CDK stack outputs
cd frontend && VITE_API_URL=<api-url> \
  VITE_COGNITO_USER_POOL_ID=<pool-id> \
  VITE_COGNITO_CLIENT_ID=<client-id> \
  VITE_AWS_REGION=us-east-1 \
  npm run build

# Upload to S3
aws s3 sync dist/ s3://novascan-dev-frontend/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id <dist-id> --paths "/*"
```

Total deploy time: ~30 seconds (build) + ~10 seconds (sync) + ~60 seconds (invalidation propagation).

### Rollback

S3 versioning is enabled on the frontend bucket:

```bash
# List previous versions of index.html
aws s3api list-object-versions --bucket novascan-dev-frontend --prefix index.html

# To rollback: redeploy from a previous git commit
git checkout <previous-commit> -- frontend/
cd frontend && npm run build
aws s3 sync dist/ s3://novascan-dev-frontend/ --delete
aws cloudfront create-invalidation --distribution-id <dist-id> --paths "/*"
```

### Troubleshoot

**Blank page / app won't load:**
- Check browser console for JavaScript errors
- Verify CloudFront distribution is deployed and domain resolves
- Check that `index.html` exists in the S3 bucket
- Verify CloudFront custom error response (403/404 → `/index.html` with 200) for SPA routing

**CORS errors:**
- API Gateway CORS must allow the CloudFront origin
- Check `Access-Control-Allow-Origin` header in API responses
- Dev: CloudFront default URL. Prod: `https://subdomain.example.com`

**Wrong environment variables:**
- `VITE_*` vars are baked in at build time, not runtime
- Rebuild and redeploy if env vars are wrong
- Verify values match CDK stack outputs: `aws cloudformation describe-stacks --stack-name novascan-dev --query 'Stacks[0].Outputs'`

---

## 4. Infrastructure (CDK)

### Stack Architecture

NovaScan uses a **single CDK stack per stage** (`NovaScanDevStack`, `NovaScanProdStack`) with separate **constructs** for each component:

| Construct | File | Resources |
|-----------|------|-----------|
| `AuthConstruct` | `auth.py` | Cognito User Pool, Pre-Sign-Up Lambda |
| `StorageConstruct` | `storage.py` | DynamoDB table, S3 receipt bucket |
| `ApiConstruct` | `api.py` | API Gateway, API Lambda |
| `PipelineConstruct` | `pipeline.py` | SQS queue, EventBridge Pipes, Step Functions, pipeline Lambdas (Textract Extract, Nova Structure, Bedrock Extract, Finalize) |
| `FrontendConstruct` | `frontend.py` | S3 frontend bucket, CloudFront distribution |

**Important: `cdk deploy` always evaluates the entire stack.** CloudFormation diffs against the previous state and only updates resources whose definitions changed. If you only changed a pipeline Lambda's code, CloudFormation updates that Lambda and leaves API Gateway, DynamoDB, CloudFront etc. untouched. However, the synth+diff+deploy cycle still takes 30–60s even for a single Lambda change because CloudFormation must evaluate all resources.

### Deployment Granularity

| What Changed | Fastest Method | CDK Method |
|-------------|---------------|------------|
| Pipeline Lambda code only | `aws lambda update-function-code` (see Section 2: Hot Deploy) | `cdk deploy` — ~60s, only updates the changed Lambda |
| Pipeline infra (SQS, Pipes, Step Functions) | N/A — must use CDK | `cdk deploy` — updates only pipeline resources |
| API Lambda code only | `aws lambda update-function-code` (see Section 1: Hot Deploy) | `cdk deploy` — ~60s, only updates API Lambda |
| Frontend only | `npm run build && aws s3 sync` (see Section 3) | Not needed — no CDK resources involved |
| Multiple components | N/A — use CDK | `cdk deploy` — updates all changed resources |
| IAM / config / new resources | N/A — must use CDK | `cdk deploy` |

**The `aws lambda update-function-code` escape hatch** is the fastest way to update a single Lambda (~5s) without CDK evaluating the whole stack. Use it for tight iteration loops. Use `cdk deploy` when infrastructure (not just code) changes.

**Why a single stack (not multi-stack)?** At MVP scale with ~5 constructs, separate stacks add cross-stack reference complexity (exports, imports, deploy ordering) with no meaningful benefit. The single-stack model is simpler to reason about and deploy. If the system grows to need independent deploy cadences (e.g., separate team owns the pipeline), splitting into multiple stacks is a straightforward refactor — the constructs are already isolated.

### Deploy

```bash
cd infra && uv venv --python 3.13 && uv sync        # first time
cd infra && uv run cdk synth --context stage=dev     # synthesize (no deploy)
cd infra && uv run cdk diff --context stage=dev      # preview changes
cd infra && uv run cdk deploy --context stage=dev    # deploy
```

### Production Deploy

```bash
cd infra && uv run cdk diff --context stage=prod     # always diff before prod deploy
cd infra && uv run cdk deploy --context stage=prod
```

### Teardown

```bash
cd infra && uv run cdk destroy --context stage=dev
```

**Warning:** `cdk destroy` on prod deletes all data (DynamoDB, S3). Ensure you have backups.

### Rollback

CDK tracks stack state in CloudFormation. If a deploy fails mid-way, CloudFormation automatically rolls back to the previous state.

For a manual rollback after a successful deploy:

```bash
# Option 1: Redeploy from a previous commit
git checkout <previous-commit> -- infra/
cd infra && uv run cdk deploy --context stage=dev

# Option 2: CloudFormation console → select stack → Roll back
# (Only available if the stack is in UPDATE_COMPLETE state)
```

### Common CDK Issues

| Issue | Fix |
|-------|-----|
| `cdk synth` fails with Python import error | `cd infra && uv sync` — dependencies may be out of date |
| Deploy hangs on CloudFront | CloudFront distribution updates take 5-15 minutes — this is normal |
| `DELETE_FAILED` on `cdk destroy` | Check for S3 buckets with remaining objects — empty them first: `aws s3 rm s3://bucket --recursive` |
| Resource already exists | Another stack created the resource. Check for name collisions with stage prefix. |

---

## 5. Configuration

All tunable settings are in `cdk.json` under `context.config.{stage}`.

### View Current Configuration

```bash
cat infra/cdk.json | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['context']['config'], indent=2))"
```

### Change a Setting

1. Edit `cdk.json` — update the value for the target stage
2. Preview: `cd infra && uv run cdk diff --context stage=dev`
3. Deploy: `cd infra && uv run cdk deploy --context stage=dev`

### Settings Reference

| Setting | Default | Used By | Description |
|---------|---------|---------|-------------|
| `pipelineMaxConcurrency` | 2 | EventBridge Pipes | Max concurrent Step Functions executions |
| `presignedUrlExpirySec` | 900 | API Lambda (upload) | Presigned URL expiration |
| `maxUploadFiles` | 10 | API Lambda + frontend | Max files per batch upload |
| `maxUploadSizeMb` | 10 | API Lambda + frontend | Max file size |
| `logLevel` | DEBUG/INFO | All Lambdas | Lambda Powertools log level |
| `defaultPipeline` | ocr-ai | Finalize Lambda | Which pipeline is main vs shadow |

---

## 6. Role Management

### Add User to a Cognito Group

```bash
# Promote to staff
aws cognito-idp admin-add-user-to-group \
  --user-pool-id <pool-id> \
  --username <email> \
  --group-name staff

# Promote to admin
aws cognito-idp admin-add-user-to-group \
  --user-pool-id <pool-id> \
  --username <email> \
  --group-name admin
```

The user must sign out and sign in again for the new group to appear in their JWT. For immediate effect, force sign-out:

```bash
aws cognito-idp admin-user-global-sign-out \
  --user-pool-id <pool-id> \
  --username <email>
```

### Remove User from a Group

```bash
aws cognito-idp admin-remove-user-from-group \
  --user-pool-id <pool-id> \
  --username <email> \
  --group-name staff
```

### List Group Members

```bash
aws cognito-idp list-users-in-group \
  --user-pool-id <pool-id> \
  --group-name staff
```

---

## 7. Common Error Reference

| Error | Component | Cause | Fix |
|-------|-----------|-------|-----|
| `ThrottlingException` from Textract | Pipeline | Concurrency too high | Lower `pipelineMaxConcurrency` in `cdk.json` |
| S3 `403 AccessDenied` on presigned URL | Upload | URL expired or wrong bucket policy | Check expiry, verify `BlockPublicAccess` settings |
| `UserNotFoundException` on `InitiateAuth` | Auth | New user — expected behavior | Frontend catches this and calls `SignUp` first |
| Lambda timeout (>30s) | Pipeline | Large receipt or cold start | Check image size, consider SnapStart |
| `CORS error` in browser | Frontend → API | Origin not allowed | Verify CORS config in API Gateway matches CloudFront domain |
| `cognito:groups` claim missing | Auth | User not in any group | Verify user is in a Cognito group; check Pre-Sign-Up Lambda |
| `409 CONFLICT` on category create | API | Slug already exists | Choose a different display name |
| `403 FORBIDDEN` on pipeline-results | API | User lacks `staff` role | Promote user to staff group |
