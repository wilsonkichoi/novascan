# Task 3.13 Review: Pipeline Lambda Input Validation + Error Sanitization [H4 + H5 + H6 + L5 + M8 + L6 + L7]

## Summary
Added comprehensive input validation and error sanitization across all pipeline Lambdas. Created a shared `validation.py` module with reusable validation functions.

## Changes
- **`backend/src/novascan/pipeline/validation.py`** (new): Shared validation utilities with `validate_event_fields()`, `validate_s3_key()`, `validate_model_id()`, `check_image_size()`.
- **`backend/src/novascan/pipeline/textract_extract.py`**: Added event validation (H6), S3 key validation (H5), sanitized error payloads to `"textract_extract_failed"` (H4), removed bucket/key from log extras (L6/L7).
- **`backend/src/novascan/pipeline/nova_structure.py`**: Added event validation (H6), S3 key validation (H5), image size guard on `_read_image_from_s3` (L5), model ID allowlist at module load (M8), sanitized error payloads to `"nova_structure_failed"` (H4).
- **`backend/src/novascan/pipeline/bedrock_extract.py`**: Same as nova_structure — event validation, S3 key validation, image size guard, model ID allowlist, sanitized errors.
- **`backend/src/novascan/pipeline/load_custom_categories.py`**: Sanitized error payloads to `"load_custom_categories_failed"` (H4), added receipt ID format validation in `_extract_receipt_id` (H5), sanitized S3 event logging to structure presence only (L6/L7).
- **Tests updated**: All existing tests updated for new error format and valid ULID-format S3 keys. Added new tests for event validation, S3 key validation, bucket mismatch, and error sanitization.

## Acceptance Criteria Checklist
- [x] H6 — Event validation: Each Lambda validates its event payload at entry with `"error": "invalid_event"`
- [x] H5 — S3 key validation: Shared regex `^receipts/[A-Za-z0-9]{26}\.(jpg|jpeg|png)$` + bucket match
- [x] H4 — Error sanitization: All `except` blocks return `{"error": "<lambda_name>_failed", "errorType": type(e).__name__}` (no `str(e)`)
- [x] L5 — Image size guard: `_read_image_from_s3` checks `ContentLength` before `.read()`, max 10MB
- [x] M8 — Model ID validation: Nova/Bedrock Lambdas validate `MODEL_ID` against allowlist at module load
- [x] L6 + L7 — Log hygiene: S3 event payloads logged as structure presence only, bucket/key stripped from error extras
- [x] Existing pipeline unit tests updated to match new error format
- [x] `ruff check src/` passes
- [x] `pytest tests/unit/ -v -k "textract or nova or bedrock or load_custom"` passes (60/60)

## Test Results
```
All checks passed!  (ruff)
60 passed, 188 deselected in 0.19s  (pytest)
```
