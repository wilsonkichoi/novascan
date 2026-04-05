# Wave 3 Review — Milestone 3: Pipeline CDK Construct

**Reviewer:** code-reviewer (AI)
**Date:** 2026-04-04
**Branch:** `feature/m3-wave3-pipeline-cdk`
**Base:** `main`

## Task 3.5: Pipeline CDK Construct

### Spec Compliance

The implementation matches the SPEC diagram (Section 4, OCR Pipeline State Machine) accurately:

- **State machine flow:** LoadCustomCategories -> Parallel(Main, Shadow) -> Finalize -- matches SPEC.
- **Main branch:** TextractExtract -> NovaStructure (sequential within branch) -- matches SPEC.
- **Shadow branch:** BedrockExtract (single step) -- matches SPEC.
- **Catch blocks:** TextractExtract, NovaStructure, and BedrockExtract all have `Catch` on `States.ALL` producing error payloads -- matches SPEC ("Each branch has a Catch block -- returns either a success result or an error payload. The Parallel state never fails.").
- **S3 -> SQS -> EventBridge Pipes -> Step Functions:** Matches SPEC Section 3 Processing Flow.
- **SQS queue receives S3 ObjectCreated events with `receipts/` prefix filter** -- matches SPEC.
- **EventBridge Pipe batch_size=1 with FIRE_AND_FORGET invocation** -- reasonable.
- **Five pipeline Lambdas** with correct handlers and IAM grants.

The Finalize Lambda receives `pipelineResults` as an array where `[0]` is main (OCR-AI branch) and `[1]` is shadow (AI-multimodal branch), which matches the finalize handler's expectations.

**Two spec gaps are documented and acceptable for MVP:**
1. userId not in S3 event payload -- resolved with DynamoDB Scan.
2. MaximumConcurrency unsupported in CfnPipe -- documented, SQS batch_size=1 as workaround.

### Code Quality

**Strengths:**

- Clean separation of `_build_state_machine` and `_build_pipe` methods.
- SQS queue policy correctly scoped to the receipts bucket ARN via `ArnLike` condition.
- S3 bucket notification uses `s3n.SqsDestination` with prefix filter -- CDK handles the plumbing correctly.
- Lambda bundling reuses the proven uv-based pattern from `api.py` with appropriate exclusions (auth, api, __pycache__).
- All five Lambdas share a single code asset to reduce build time and S3 storage.
- CloudWatch PutMetricData is scoped to the `NovaScan` namespace via condition.
- `enforce_ssl=True` on SQS queue produces the correct Deny policy for non-TLS connections.
- The synthesized CloudFormation template validates correctly (`cdk synth` passes).
- Environment variables (`TABLE_NAME`, `LOG_LEVEL`, `STAGE`, `POWERTOOLS_LOG_LEVEL`, `POWERTOOLS_SERVICE_NAME`, `DEFAULT_PIPELINE`) are set correctly on the appropriate Lambdas.
- `common_lambda_props` dict with per-Lambda environment overrides avoids repetition without premature abstraction.
- The `_parse_s3_event` function handles both string and dict `s3EventBody` defensively.
- Error catch handlers produce clean error payloads with `error` and `errorType` keys matching what `finalize._parse_pipeline_result` expects.

### Issues Found

**SUGGESTION: S3 event notification URL-encodes object keys -- missing `urllib.parse.unquote_plus`**

File: `backend/src/novascan/pipeline/load_custom_categories.py`, line 164.

S3 event notifications URL-encode the object key (e.g., spaces become `+` or `%20`, special chars are percent-encoded). The `_parse_s3_event` function extracts `key` as-is without decoding. While receipt keys use ULIDs (no special characters), this is a latent bug if filenames ever contain spaces or special characters. The `_extract_receipt_id` function would also produce an incorrect receiptId from an encoded key.

Fix: Add `from urllib.parse import unquote_plus` and apply `key = unquote_plus(key)` after extracting from the S3 event record. This is standard practice for S3 event handlers.

Severity: Low for MVP (ULIDs have no special chars), but worth fixing for correctness.

---

**SUGGESTION: `bedrock:InvokeModel` IAM permissions use `Resource: *` -- should scope to specific model ARNs**

File: `infra/cdkconstructs/pipeline.py`, lines 224-228 and 244-248.

Both `nova_structure_fn` and `bedrock_extract_fn` have `bedrock:InvokeModel` with `resources=["*"]`. While Textract's `AnalyzeExpense` genuinely requires `Resource: *` (no resource-level permissions), Bedrock `InvokeModel` supports model ARN scoping: `arn:aws:bedrock:{region}::foundation-model/{model-id}`. Since the Lambdas default to `amazon.nova-lite-v1:0`, the IAM policy should be scoped to that model (or a pattern like `arn:aws:bedrock:*::foundation-model/amazon.nova-*`).

This is a least-privilege concern, not a security vulnerability at MVP scale, but it prevents accidental (or malicious) invocation of expensive models like Claude or Nova Pro.

---

**SUGGESTION: No Dead Letter Queue (DLQ) on the SQS receipt queue**

File: `infra/cdkconstructs/pipeline.py`, lines 126-133.

If the EventBridge Pipe fails to process an SQS message after the visibility timeout expires, the message returns to the queue and retries indefinitely (up to the 4-day retention period). Without a DLQ, poison messages (e.g., malformed S3 events, corrupt image keys) will loop forever, consuming resources and generating noise. The SPEC doesn't explicitly require a DLQ, but it's standard SQS best practice.

Fix: Add a DLQ with `max_receive_count=3` (or similar) so messages that fail repeatedly are moved to a dead letter queue for investigation.

---

**SUGGESTION: `_lookup_user_id` returns empty string on failure -- pipeline continues with empty userId**

File: `backend/src/novascan/pipeline/load_custom_categories.py`, lines 230-231.

When `_lookup_user_id` fails to find the receipt in DynamoDB (race condition: S3 event fires before DynamoDB write completes, or genuinely missing), it returns `""`. The handler then sets `event["userId"] = ""` and continues. This means:
- `_query_custom_categories("")` queries `PK=USER#` (no user) -- returns empty, not an error.
- The pipeline runs all Lambdas with empty userId.
- Finalize attempts to write to DynamoDB with `PK=USER#` -- creates orphaned records.

This is a correctness concern. If userId can't be resolved, the pipeline should fail early with a clear error rather than producing garbage data.

Fix: Raise an exception (or return an error payload) when `_lookup_user_id` returns empty string and `userId` was not provided in the event. The Step Functions Catch on LoadCustomCategories will handle this gracefully.

However, note that LoadCustomCategories does NOT have a Catch block in the state machine (lines 298-304 of pipeline.py). If the Lambda raises an exception, the entire state machine execution fails. This is arguably the correct behavior -- a missing userId is unrecoverable. But consider adding a Catch block for consistency with the other steps.

---

**SUGGESTION: LoadCustomCategories has no Catch block in the state machine**

File: `infra/cdkconstructs/pipeline.py`, lines 298-304.

TextractExtract, NovaStructure, and BedrockExtract all have `add_catch` handlers. LoadCustomCategories does not. If this Lambda fails (DynamoDB throttle, timeout, userId lookup failure), the entire state machine execution fails with an unhandled error. While this may be intentional (you can't proceed without userId), it's inconsistent with the pattern and the SPEC's "each step has a Catch" principle.

The SPEC diagram shows Catch blocks on the steps *within* the parallel branches, not on LoadCustomCategories. So this is spec-compliant. But Finalize also lacks a Catch, which means a Finalize failure also crashes the execution. Consider whether a top-level Catch on the state machine (or on LoadCustomCategories/Finalize) would be useful for setting receipt status to `failed`.

Severity: Low -- LoadCustomCategories failure is unrecoverable, and the state machine timeout (15min) will eventually terminate stuck executions.

---

**SUGGESTION: Potential race condition between S3 upload and DynamoDB record creation**

File: `backend/src/novascan/pipeline/load_custom_categories.py`, `_lookup_user_id`.

The upload flow is: (1) API Lambda creates DynamoDB receipt record, (2) API returns presigned URL, (3) client uploads to S3, (4) S3 event triggers pipeline. Steps 1 and 3 have network latency, but the DynamoDB write (step 1) happens before the presigned URL is returned (step 2), so by the time the client uploads (step 3), the DynamoDB record should exist. The race window is essentially zero under normal conditions.

However, if the API Lambda fails after writing to DynamoDB but before returning the presigned URL, and the client somehow still has the URL from a retry, this could theoretically fail. Practically irrelevant at MVP scale.

No action needed, but the comment in `_lookup_user_id` should mention this timing assumption.

---

**NIT: Hardcoded `role_name` on the Pipe IAM role may cause deploy conflicts in multi-region**

File: `infra/cdkconstructs/pipeline.py`, line 441.

`role_name=f"novascan-{stage}-pipe-role"` hardcodes the role name. If this stack is ever deployed to multiple regions in the same account, the role names will conflict. CDK-generated names avoid this. However, since the project is explicitly single-region (per SPEC), this is a minor concern.

---

**NIT: Duplicate `result_path` on Catch handler Pass states and the `add_catch` call**

File: `infra/cdkconstructs/pipeline.py`, lines 318-330.

The TextractExtract Catch specifies `result_path="$.textractResult"` in two places:
1. On the `add_catch()` call (line 329): `result_path="$.textractResult"` -- this sets where the error object goes in the state.
2. On the Pass state handler (line 326): `result_path="$.textractResult"` -- this sets where the Pass state's `Result` goes.

The `add_catch` `result_path` controls what happens when the Catch transitions -- it places the error payload at `$.textractResult`. Then the Pass state *also* writes its `Result` to `$.textractResult`, overwriting the Catch's error payload with the static message. This works but is redundant -- the Catch's `result_path` doesn't matter because the Pass state immediately overwrites it. The code is correct but could be clearer.

---

**NIT: `_pipeline_lambda_code()` is called once and shared across all 5 Lambdas**

File: `infra/cdkconstructs/pipeline.py`, line 158.

This is actually a strength, not an issue. Noting it as a positive design choice -- all 5 pipeline Lambdas share one code asset, reducing S3 storage and build time.

## Verification Results

| Check | Result |
|-------|--------|
| `cdk synth --context stage=dev` | PASS |
| `ruff check cdkconstructs/ stacks/` (infra) | PASS |
| `ruff check src/` (backend) | PASS |
| `pytest -v` (backend, 144 tests) | PASS (144 passed, 0 failed) |
| State machine definition structure | Correct: LoadCustomCategories -> ParallelPipelines -> Finalize |
| SQS queue policy | Correct: S3 SendMessage + enforce_ssl Deny |
| S3 notification | Correct: ObjectCreated with `receipts/` prefix |
| EventBridge Pipe | Correct: SQS source -> SFN target, input_template extracts body |
| Pipe IAM role | Correct: SQS ConsumeMessages + states:StartExecution |
| Lambda IAM grants | Correct: DynamoDB read/write, S3 read/write, Textract, Bedrock, CloudWatch |

## Verdict

**PASS with SUGGESTIONS.** No blockers. The implementation is solid, spec-compliant, and synthesizes to a valid CloudFormation template. The suggestions are improvements for robustness and least-privilege, not correctness issues that would prevent merging.

The two documented spec gaps (userId resolution via Scan, MaximumConcurrency unsupported) are well-reasoned and appropriate for MVP scope.

### Fix Plan

Recommended fixes, ordered by priority:

1. **[SUGGESTION] Empty userId should fail the pipeline early** -- In `load_custom_categories.py`, after `_lookup_user_id` returns `""`, raise a `ValueError("Could not resolve userId for receiptId={receipt_id}")` instead of continuing with empty userId. The state machine execution will fail, which is the correct behavior for an unrecoverable error.

2. **[SUGGESTION] Add `urllib.parse.unquote_plus` to S3 key parsing** -- In `_parse_s3_event`, add `from urllib.parse import unquote_plus` and apply to the key: `key = unquote_plus(key)`. This is a one-line defensive fix.

3. **[SUGGESTION] Scope Bedrock IAM to specific model ARNs** -- Replace `resources=["*"]` with `resources=[f"arn:aws:bedrock:*::foundation-model/amazon.nova-*"]` on the two Bedrock InvokeModel policy statements.

4. **[SUGGESTION] Add DLQ to SQS queue** -- Add a DLQ with `max_receive_count=3`. This prevents poison messages from looping indefinitely.

5. **[SUGGESTION] Add Catch to LoadCustomCategories** -- Optional. Consider whether a Catch block that sets a failure status on the receipt would be useful for observability.

Items 1-4 are straightforward fixes (1-2 lines each) that improve robustness. Item 5 is optional and may be deferred.

## Review Discussion

### On the userId Scan approach

The DynamoDB Scan for userId lookup is the pragmatic MVP choice. The three proposed production alternatives (GSI on receiptId, userId in S3 key, S3 metadata) are all valid. My recommendation for post-MVP is option 3 (S3 object metadata via presigned URL condition) because it requires no schema changes and leverages S3's built-in capabilities. The presigned URL generation in the upload API would add `x-amz-meta-user-id` as a required condition, and LoadCustomCategories would read it from the S3 HeadObject response instead of scanning DynamoDB.

### On the MaximumConcurrency gap

The `batch_size=1` workaround does not actually limit concurrency. If 100 messages arrive in SQS simultaneously, EventBridge Pipes will start 100 Step Functions executions (each processing 1 message). The `batch_size` only controls how many messages are in each batch, not how many batches run concurrently. True concurrency limiting would require either:
- The actual `MaximumConcurrency` property (when CloudFormation supports it)
- A Lambda consumer between SQS and Step Functions that uses reserved concurrency
- SQS FIFO queue with a single message group

At MVP scale (single user, low volume), this is a non-issue. But the documentation should clarify that `batch_size=1` controls batch size, not concurrency.

### On the bundling pattern

The pipeline bundling correctly excludes `auth/` and `api/` directories. However, both the API construct and Pipeline construct independently define `_UvLocalBundling` classes. If this pattern grows to a third construct, consider extracting a shared bundling module in `infra/cdkconstructs/bundling.py`. For now, two copies is fine per the "no premature abstraction" project preference.

### Fix Plan Analysis (code-reviewer AI — 2026-04-04)

**Verdict:** approve

**Fix 1 — Empty userId should fail the pipeline early:** Approve. Apply now.

This is the highest-priority fix. The current code at `load_custom_categories.py:74-76` sets `event["userId"] = ""` when `_lookup_user_id` returns an empty string, then happily continues. The downstream damage is confirmed: `finalize.py:293` writes `PK=USER#` (no user suffix) and `finalize.py:329` creates line items under the same orphaned PK. This silently creates garbage records that are invisible to any user and would require manual DynamoDB cleanup.

The proposed fix (raise `ValueError`) is correct. The existing error-return pattern on lines 82-87 of `load_custom_categories.py` already handles exceptions by returning `{"error": ..., "errorType": ...}`, but that is for `_query_custom_categories` failures, not handler-level failures. A `ValueError` raised *before* the try block will propagate as an unhandled exception to Step Functions.

Since LoadCustomCategories has no Catch block (fix 5), the state machine execution will fail outright. This is the correct behavior -- an unrecoverable error should not silently succeed. A failed execution is visible in the Step Functions console and CloudWatch, which is better than invisible orphaned data.

Risk: None. A missing userId is already a broken state. Failing loudly is strictly better than failing silently.

**Fix 2 — Add `urllib.parse.unquote_plus` to S3 key parsing:** Approve. Apply now.

Standard defensive practice. The fix location is `_parse_s3_event` at line 164. The key should be decoded immediately after extraction (`key = unquote_plus(key)`) before it is returned in the event dict. This ensures `_extract_receipt_id` also receives the decoded key.

At MVP scale with ULID-based filenames this will never fire, but it costs nothing and prevents a latent bug if filename patterns ever change. The `unquote_plus` function is stdlib, no new dependency.

Risk: None.

**Fix 3 — Scope Bedrock IAM to specific model ARNs:** Approve. Apply now.

The fix replaces `resources=["*"]` with `resources=[f"arn:aws:bedrock:*::foundation-model/amazon.nova-*"]` on lines 224-228 and 244-248 of `pipeline.py`. The wildcard `amazon.nova-*` pattern covers `nova-lite-v1:0` and future Nova model versions without being overly specific.

One subtlety: the ARN format for Bedrock foundation models uses an empty account ID segment (`arn:aws:bedrock:{region}::foundation-model/...`). The proposed ARN with `*` for region is correct -- it allows cross-region invocation if the Lambda region changes.

Risk: Minimal. If the project switches to a non-Nova model (e.g., Claude), the IAM policy will deny the call and the error will be immediately obvious in Lambda logs. This is the desired fail-closed behavior.

**Fix 4 — Add DLQ to SQS queue:** Approve. Apply now, but keep it simple.

Add a DLQ with `max_receive_count=3`. This is a 5-line CDK change: create a `sqs.Queue` for the DLQ and set `dead_letter_queue=sqs.DeadLetterQueue(queue=dlq, max_receive_count=3)` on the main queue. No alarm or monitoring needed at MVP -- the DLQ's ApproximateNumberOfMessagesVisible metric is enough for manual inspection.

Risk: None. This only affects messages that have already failed 3 times. It prevents infinite retry loops without changing the happy path.

**Fix 5 — Add Catch to LoadCustomCategories:** Defer.

The review itself notes this is spec-compliant as-is (the SPEC diagram shows Catch blocks on the parallel branch steps, not on LoadCustomCategories). Adding a Catch block here would mean LoadCustomCategories failures produce an error payload that gets passed to the Parallel state, which then passes it to Finalize -- but Finalize expects `bucket`, `key`, `userId`, `receiptId` fields in the event (line 65-68 of `finalize.py`). An error payload from a Catch block would not have these fields, causing Finalize to crash with a KeyError anyway.

To make a Catch block useful, Finalize would need to handle the "LoadCustomCategories failed" case, which means it would need to extract the receipt info from somewhere else (not the event payload). This is more work than it's worth for MVP.

Combined with fix 1 (fail early on empty userId), the failure mode is already handled correctly: the state machine execution fails, it's visible in CloudWatch, and no garbage data is written. Deferring this is the right call.

**Summary:** Fixes 1-4 are straightforward, low-risk, 1-5 lines each. Apply all four. Fix 5 is deferred -- the fail-fast behavior from fix 1 makes a Catch block on LoadCustomCategories unnecessary at MVP scale.
