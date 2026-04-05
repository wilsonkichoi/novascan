# Task 3.15 Review: Upload Endpoint Hardening [M6 + L4]

## Summary
Hardened the upload endpoint with ContentLength enforcement on presigned URLs and sanitized Pydantic ValidationError responses.

## Changes
- **`backend/src/novascan/api/upload.py`**:
  - M6: `generate_presigned_url` now includes `ContentLength: file_req.fileSize` in `Params` so S3 rejects uploads that don't match the declared size.
  - L4: Pydantic `ValidationError` handler returns sanitized field-level errors: `[{"field": name, "message": msg}]` instead of raw `str(e)`. TypeError/JSONDecodeError returns generic "Invalid request body" message. Full error logged server-side.

## Acceptance Criteria Checklist
- [x] M6 — Presigned URL includes ContentLength matching declared fileSize
- [x] L4 — ValidationError response sanitized to field-level errors
- [x] L4 — Full error logged server-side only
- [x] Existing upload tests pass (29/29)
- [x] `ruff check src/` passes

## Test Results
```
All checks passed!  (ruff)
29 passed in 1.65s  (pytest)
```
