# Task 3.14 Review: Finalize Lambda Hardening [H4-finalize + M11 + M12 + L8]

## Summary
Hardened the Finalize Lambda with generic error messages in DynamoDB, idempotency guards, explicit S3 encryption, and internal-only field documentation.

## Changes
- **`backend/src/novascan/pipeline/finalize.py`**:
  - H4: `failure_reason` written to DynamoDB is now generic: "Pipeline processing failed. Check CloudWatch logs for details." Raw error details logged to CloudWatch only. Pipeline record `error` field stores error classification (`errorType`), not raw exception message.
  - M11: `_update_receipt` uses `ConditionExpression="attribute_not_exists(updatedAt) OR updatedAt < :now"` to prevent stale overwrites. `_create_line_items` deletes existing items for the receipt before writing new ones (delete-then-write pattern).
  - M12: `copy_object` call includes `ServerSideEncryption="AES256"` explicitly.
  - L8: `selectedPipeline`, `rankingWinner`, `usedFallback` documented as internal-only fields with inline comments.

## Acceptance Criteria Checklist
- [x] H4 — failure_reason is generic; raw details logged to CloudWatch only
- [x] M11 — ConditionExpression prevents stale overwrites
- [x] M11 — delete-then-write pattern for line items
- [x] M12 — S3 copy_object includes ServerSideEncryption="AES256"
- [x] L8 — Internal-only fields documented in code
- [x] `ruff check src/` passes
- [x] `pytest tests/unit/test_finalize.py -v` passes (37/37)

## Test Results
```
All checks passed!  (ruff)
37 passed in 2.66s  (pytest)
```
