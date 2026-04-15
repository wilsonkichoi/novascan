# Production E2E Validation & Fixes

Date: 2026-04-15
Context: First production deployment of NovaScan (task 6.3 + 6.8)

## Issues Found & Fixed

### 1. Lambda import failure — `pydantic_core._pydantic_core` not found

**Symptom:** Every API call returned 500. Log group `/aws/lambda/novascan-prod-api` showed:
```
[ERROR] Runtime.ImportModuleError: Unable to import module 'api.app': No module named 'pydantic_core._pydantic_core'
```

**Root cause:** `_UvLocalBundling` in `infra/cdkconstructs/api.py` and `pipeline.py` ran `uv pip install` on macOS ARM64, packaging Darwin binaries. Lambda runs on Amazon Linux x86_64. The Docker fallback (which produces correct Linux binaries) was never reached because the local bundling succeeded first.

**Fix:** Added `--python-platform manylinux2014_x86_64 --python-version 3.13` to the `uv pip install` command in both `_UvLocalBundling.try_bundle()` methods. This tells `uv` to download Linux x86_64 wheels even when running on macOS.

Also removed unused `pandas` dependency from `backend/pyproject.toml` (was supposed to be removed in task 3.17/L3). `pandas` pulled in `numpy` which had no pre-built manylinux wheel for Python 3.14, blocking cross-compilation.

**Files changed:**
- `infra/cdkconstructs/api.py` — cross-platform bundling flags
- `infra/cdkconstructs/pipeline.py` — same
- `backend/pyproject.toml` — removed pandas
- `backend/uv.lock` — updated (removed pandas, numpy, tzdata)

**Verification:** Redeployed prod, `/api/health` returned 200, Lambda logs showed successful init.

**Commit:** `298f0ec fix: bundle Lambda deps for Linux x86_64 and remove unused pandas`

---

### 2. S3 presigned upload failed — CORS not configured on receipts bucket

**Symptom:** Receipt image upload failed with "Network error during upload" in the browser. The frontend does a cross-origin XHR PUT directly to S3 using a presigned URL. S3 blocked the request because the receipts bucket had no CORS configuration.

**Root cause:** `infra/cdkconstructs/storage.py` created the receipts bucket without any `cors` rules. The browser sends an `Origin` header on the PUT, S3 checks CORS, finds no matching rule, and rejects the request before the presigned URL is even evaluated.

**Fix:** Added CORS rule to the receipts bucket allowing PUT from any origin with `Content-Type` header:
```python
cors=[
    s3.CorsRule(
        allowed_methods=[s3.HttpMethods.PUT],
        allowed_origins=["*"],
        allowed_headers=["Content-Type"],
        max_age=3600,
    ),
],
```

`allowed_origins=["*"]` is safe here because the presigned URL itself is the authorization mechanism — CORS just tells the browser it's allowed to make the request. Without a valid presigned URL, the PUT still fails with 403.

**Files changed:**
- `infra/cdkconstructs/storage.py` — added CORS rule
- `infra/tests/snapshots/novascan-dev.template.json` — updated snapshot

**Verification:** Redeployed prod, receipt upload succeeded.

---

### 3. Invalid CSP directive — double wildcard in `connect-src`

**Symptom:** Browser console warning on every page load:
```
The source list for the Content Security Policy directive 'connect-src' contains an invalid source: 'https://*.execute-api.*.amazonaws.com'. It will be ignored.
```

**Root cause:** CSP only allows a single wildcard, and only in the leftmost label. The double wildcard `*.execute-api.*.amazonaws.com` is invalid syntax and was silently ignored by the browser. This was set in the CloudFront `ResponseHeadersPolicy` in task 3.12 (security headers).

The directive still worked because `https://*.amazonaws.com` (which was also present) already covers all amazonaws.com subdomains including `*.execute-api.us-east-1.amazonaws.com` and `*.s3.amazonaws.com`.

**Fix:** Removed the invalid double-wildcard entry from the CSP `connect-src` directive in `infra/cdkconstructs/frontend.py`. The remaining `https://*.amazonaws.com` covers all AWS service endpoints.

**Files changed:**
- `infra/cdkconstructs/frontend.py` — removed invalid CSP source
- `infra/tests/snapshots/novascan-dev.template.json` — updated snapshot

**Verification:** Redeployed prod + CloudFront cache invalidation, console warning gone.

---

### 4. Orphaned receipt records from failed uploads

**Symptom:** Receipts list showed ~9 "Processing..." entries despite only one successful upload. All orphaned entries were stuck permanently in `processing` status.

**Root cause:** The upload flow creates DynamoDB receipt records (`POST /api/receipts/upload-urls`) *before* the S3 presigned URL upload. When the S3 PUT failed (due to missing CORS — issue #2), the receipt record was already written but no image was ever uploaded. Without an image in S3, no S3 event fires, no pipeline runs, and the record stays `processing` forever.

**Fix (immediate):** Manually delete the orphaned records via the UI (click each → delete) or DynamoDB.

**Fix (future — not implemented):** Two options to prevent this:
1. **Deferred record creation** — Don't create the DynamoDB record until the frontend confirms the S3 upload succeeded (requires a second API call after upload).
2. **TTL cleanup** — Add a DynamoDB TTL attribute on `processing` records (e.g., expire after 1 hour). Records that never get processed are automatically cleaned up.

Option 2 is simpler and handles other edge cases (user closes browser mid-upload, network drops after presign but before PUT). Not implementing for MVP — the current behavior is acceptable since failed uploads are rare once CORS is configured.

**Files changed:** none (documentation only)

---

### 5. Pipeline never runs — EventBridge Pipe input template produces invalid JSON

**Symptom:** Receipt uploaded successfully to S3, SQS received the event, but Step Functions had zero executions. DLQ had 1 message (the S3 test event from initial notification setup). The real upload's SQS message was stuck "in flight" — the pipe kept failing to start Step Functions.

**Root cause:** CloudTrail showed `InvalidExecutionInput` on `StartExecution`:
```
Invalid State Machine Execution Input: 'Unexpected character ('R' (code 82)):
was expecting comma to separate Object entries'
```

The pipe's input template was:
```json
{"s3EventBody": "<$.body>"}
```

`<$.body>` performs raw string interpolation. The SQS body is a JSON string containing quotes, so interpolation produced broken JSON like `{"s3EventBody": "{"Records":[...]}"}` — the inner quotes broke the outer object.

**Fix:** Changed the input template to extract bucket and key directly via JSONPath instead of passing the raw body:
```json
{"bucket": "<$.body.Records[0].s3.bucket.name>", "key": "<$.body.Records[0].s3.object.key>"}
```

EventBridge Pipes parses the SQS body as JSON automatically for SQS sources, so `$.body.Records[0]...` works as deep path traversal. The extracted values are simple strings (no nested JSON), so interpolation is safe.

The `LoadCustomCategories` Lambda already handles both input shapes (`s3EventBody` wrapper and direct `bucket`/`key`), so no Lambda code changes needed.

**Files changed:**
- `infra/cdkconstructs/pipeline.py` — new input template extracting bucket/key directly

**Verification:** Redeployed prod, re-uploaded receipt, Step Functions execution started and completed.

---

### 6. LoadCustomCategories Lambda receives array instead of dict

**Symptom:** Step Functions execution failed immediately at the `LoadCustomCategories` step:
```
[ERROR] AttributeError: 'list' object has no attribute 'get'
  File "pipeline/load_custom_categories.py", line 70, in handler
    key = event.get("key", "")
```

**Root cause:** EventBridge Pipes with an SQS source always sends a **batch** (JSON array) to the target, even when `batch_size=1`. The input template produces `{"bucket": "...", "key": "..."}` per message, but the pipe wraps it as `[{"bucket": "...", "key": "..."}]` before calling `StartExecution`. The Lambda expected a dict, got a list.

This was not caught in unit tests because tests invoke the Lambda handler directly with a dict — the array wrapping only happens in the real Pipes → Step Functions → Lambda flow.

**Fix:** Added array unwrapping at the top of `load_custom_categories.handler()`:
```python
if isinstance(event, list):
    if len(event) == 1:
        event = event[0]
```

Also added CloudWatch logging for both the EventBridge Pipe (`level="ERROR"`) and the Step Functions state machine (`level=ERROR`) so failures are directly visible in log groups instead of requiring CloudTrail forensics or execution history API calls.

**Files changed:**
- `backend/src/novascan/pipeline/load_custom_categories.py` — array unwrap
- `infra/cdkconstructs/pipeline.py` — pipe log group + state machine log group

**Verification:** Redeployed prod, re-uploaded receipt, pipeline executed successfully.

---

## Lessons Learned

1. **Always test Lambda packaging with cross-platform binaries.** Any Python dependency with native code (pydantic, cryptography, numpy) will silently break if packaged on a different architecture. The `--python-platform` flag on `uv pip install` is the clean fix for local bundling.

2. **S3 presigned URL uploads require CORS.** Presigned URLs authenticate the request, but the browser's CORS preflight check happens before the URL is evaluated. If the bucket has no CORS rule, the browser blocks the request at the network level.

3. **Validate CSP directives.** CSP wildcards only work in the leftmost label (`*.example.com` is valid, `*.sub.*.example.com` is not). Invalid entries are silently ignored — check the browser console during E2E testing.

4. **EventBridge Pipes `<$.field>` interpolation is raw string substitution.** If the value contains JSON (quotes, braces), the result is broken JSON. Extract leaf values via JSONPath (`<$.body.Records[0].s3.bucket.name>`) instead of passing nested JSON blobs. Always test pipe input templates with real event payloads, not just `cdk synth`.

5. **EventBridge Pipes SQS source always sends batches.** Even with `batch_size=1`, the target receives `[item]` not `item`. Lambda handlers consuming pipe output must handle the array wrapper. Unit tests that call handlers directly with dicts won't catch this — integration tests or real E2E are needed.

6. **Enable logging on Pipes and Step Functions from day one.** Without CloudWatch logs on the pipe and state machine, failures are invisible. You have to hunt through CloudTrail or call `get-execution-history`. Adding `level="ERROR"` log configuration costs nothing when there are no errors, and saves significant debugging time when there are.

7. **Remove unused dependencies early.** `pandas` was flagged in the security review (task 3.17/L3) but wasn't actually removed. It caused a cascading failure when cross-platform compilation couldn't build `numpy` for the target platform.
