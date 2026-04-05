# Wave 2 Review: Pipeline + API + IAM Hardening

Reviewed: 2026-04-04
Reviewer: Claude Opus 4.6 (1M context)
Cross-referenced: SPEC.md Section 3 (Processing Flow), Section 5 (Database Schema), Section 12 (Security), HANDOFF.md, SECURITY-REVIEW.md

## Task 3.13: Pipeline Lambda Input Validation + Error Sanitization [H4 + H5 + H6 + L5 + M8 + L6 + L7]

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| H6 — Event validation with `"error": "invalid_event"` | PASS | All four pipeline Lambdas validate required fields at entry via shared `validate_event_fields()` |
| H5 — S3 key regex `^receipts/[A-Za-z0-9]{26}\.(jpg\|jpeg\|png)$` + bucket match | PASS | Shared `validate_s3_key()` in `validation.py`, RECEIPTS_BUCKET env var used |
| H4 — Error sanitization: `{"error": "<lambda_name>_failed", "errorType": ...}` | PASS | All except blocks return generic error names, no `str(e)` |
| L5 — Image size guard: ContentLength check before `.read()`, max 10MB | PASS | `check_image_size()` called in `_read_image_from_s3()` in both nova_structure.py and bedrock_extract.py |
| M8 — Model ID allowlist validation at module load | PASS | Both nova_structure.py and bedrock_extract.py validate MODEL_ID against `ALLOWED_MODEL_IDS` at import time |
| L6 + L7 — Log hygiene: structure presence only, no bucket/key in extras | PASS | `key_present: bool(key)` pattern used consistently; `_parse_s3_event` logs `has_bucket`/`has_key` |
| Existing pipeline unit tests updated | PASS | 60/60 tests pass with new error format and valid ULID S3 keys |
| `ruff check src/` passes | PASS | Confirmed |

### Issues Found

No issues found for task 3.13. Implementation is thorough and consistent.

---

## Task 3.14: Finalize Lambda Hardening [H4-finalize + M11 + M12 + L8]

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| H4 — Generic failure_reason in DynamoDB | PASS | `"Pipeline processing failed. Check CloudWatch logs for details."` — raw details logged only |
| H4 — Pipeline record error field stores errorType, not raw message | PASS | `item["error"] = raw.get("errorType", "Unknown")` at line 323 |
| M11 — ConditionExpression prevents stale overwrites | PASS | `attribute_not_exists(updatedAt) OR updatedAt < :now` with ConditionalCheckFailedException handler |
| M11 — Delete-then-write for line items | PASS | Queries existing ITEM# records and batch-deletes before writing new ones (lines 444-454) |
| M12 — `copy_object` includes `ServerSideEncryption="AES256"` | PASS | Line 503 |
| L8 — Internal-only fields documented | PASS | Comment at lines 151-153 documents fields as internal-only |
| Existing finalize tests pass | PASS | 37/37 |

### Issues Found

No issues found for task 3.14.

---

## Task 3.15: Upload Endpoint Hardening [M6 + L4]

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| M6 — Presigned URL includes ContentLength | PASS | `"ContentLength": file_req.fileSize` in Params (line 103) |
| L4 — ValidationError sanitized to field-level errors | PASS | Returns `[{"field": ..., "message": ...}]`, no raw `str(e)` |
| L4 — TypeError/JSONDecodeError returns generic message | PASS | `"Invalid request body"` (line 54) |
| L4 — Full error logged server-side | PASS | `logger.warning` with error_count / error_type |
| Existing upload tests pass | PASS | 29/29 |

### Issues Found

No issues found for task 3.15.

---

## Task 3.16: CDK IAM + API Gateway Hardening [M1 + M5 + M9 + M10]

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| M1 — S3 grants scoped to `receipts/*` | PASS | `grant_put(fn, "receipts/*")` + `grant_read(fn, "receipts/*")` in api.py line 130-131; confirmed in CDK snapshot lines 241, 270 |
| M5 — Route-level throttling (burst=10, rate=5) | PASS | L1 escape hatch via `add_property_override` on CfnStage; confirmed in snapshot lines 425-426 |
| M5 — Access logging to CloudWatch log group | PASS | `ApiAccessLog` log group created, DestinationArn set in snapshot line 412 |
| M9 — Textract `resources=["*"]` documented | PASS | Comment at pipeline.py lines 229-231 citing AWS docs URL |
| M10 — Bedrock ARN scoped to deployment region | PASS | `f"arn:aws:bedrock:{cdk.Aws.REGION}::foundation-model/..."` for both Nova and Bedrock Lambdas; snapshot confirms `Ref: AWS::Region` |
| `cdk synth` succeeds | PASS | Snapshot regenerated |
| All infra tests pass | PASS | 82/82 |

### Issues Found

No issues found for task 3.16.

---

## Task 3.17: Storage Lifecycle + Encryption + Dependency Cleanup [M3 + L2 + L3]

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| M3 — IA transition at 90 days | PASS | `Transition(storage_class=s3.StorageClass.INFREQUENT_ACCESS, transition_after=cdk.Duration.days(90))` in storage.py |
| M3 — Glacier at 365 days | PASS | `Transition(storage_class=s3.StorageClass.GLACIER, transition_after=cdk.Duration.days(365))` |
| M3 — Expiration at 2555 days (~7 years) | PASS | `expiration=cdk.Duration.days(2555)` |
| L2 — TODO comment for KMS upgrade path | PASS | Comment at storage.py lines 62-65 documenting upgrade path and deferral rationale |
| L3 — pandas removed from dependencies | PASS | Not in `backend/pyproject.toml` `[project.dependencies]`; uv.lock updated |
| L3 — No pandas import exists | PASS | No import statement found in backend source |
| `cdk synth` succeeds | PASS | Confirmed in snapshot (ExpirationInDays: 2555 at line 2643) |
| `uv sync` succeeds | PASS | pandas + numpy uninstalled |

### Issues Found

No issues found for task 3.17.

---

## Cross-Reference: Spec Alignment

| Spec Requirement | Implementation | Verdict |
|-----------------|---------------|---------|
| SPEC 3: Error payloads from pipeline Lambdas (not exceptions) | All 4 Lambdas return `{"error": ..., "errorType": ...}`; no exceptions raised | PASS |
| SPEC 3: Both pipelines execute in parallel with Catch blocks | Existing behavior preserved; new validation returns error payloads before try/except | PASS |
| SPEC 5: S3 key format `receipts/{receiptId}.{ext}` | Validated by regex `^receipts/[A-Za-z0-9]{26}\.(jpg\|jpeg\|png)$` | PASS |
| SPEC 12: IAM least-privilege for all Lambda execution roles | S3 scoped to `receipts/*`, DynamoDB scoped to Query+GetItem (no Scan), Bedrock region-scoped, Textract documented as requiring `*` | PASS |
| SPEC 12: S3 encryption at rest | Explicit `ServerSideEncryption="AES256"` on copy_object in finalize | PASS |
| SPEC 12: Presigned URLs expire after 15 minutes | ContentLength enforcement added; expiry behavior unchanged | PASS |
| SPEC 3: Receipt status transitions | Finalize idempotency guards prevent stale overwrites; status transition logic unchanged | PASS |
| SPEC 2: Upload endpoint creates receipt records | GSI2PK set on creation (from wave 1 task 3.9); ContentLength added to presigned URL params | PASS |

## Things Done Well

1. **Shared validation module** (`validation.py`) — Clean, well-documented utilities with a single source of truth for S3 key patterns, model allowlists, and image size limits. Avoids duplication across four Lambda files.

2. **Consistent error sanitization pattern** — Every pipeline Lambda follows the same `{"error": "<name>_failed", "errorType": type(e).__name__}` contract. The finalize Lambda correctly stores the error classification (not raw message) in DynamoDB and writes a generic failure_reason.

3. **L1 escape hatch for API Gateway throttling** — CDK L2 HttpApi doesn't expose DefaultRouteSettings. Using `add_property_override` on the CfnStage is the right approach, clean and well-commented.

4. **Idempotency in finalize** — Both the ConditionExpression on receipt updates and the delete-then-write pattern for line items are sound. The ConditionalCheckFailedException is caught and logged as a warning (not an error), which is correct since it's an expected race condition, not a failure.

5. **Module-level model ID validation** — Failing at import time (before the first invocation) is the right call for configuration validation. Bad MODEL_ID prevents the Lambda from serving any requests at all, surfacing misconfiguration immediately during deployment verification.

6. **Clean pandas removal** — Dependency removed, lock file updated, no orphaned imports. Wave 3 (task 3.18/3.19) will add dedicated security tests, so the current test coverage is appropriate.

## Summary

| ID | Severity | Task | Issue | Action |
|----|----------|------|-------|--------|

No issues found.

**Overall verdict:** All five wave 2 tasks pass acceptance criteria and align with the spec. The security hardening is thorough, consistent, and well-tested. 248 backend tests and 82 infra tests pass. The implementation follows the project's coding standards (no premature abstraction, AWS-native patterns, Pydantic models throughout). Ready to merge.

## Review Discussion

No issues found — no fix cycle required. Tasks 3.13-3.17 marked `done`.

{Append-only — never overwrite previous entries.}
