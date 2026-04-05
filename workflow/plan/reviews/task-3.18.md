# Task 3.18 Review: Security Hardening Backend Tests [TEST]

## Summary
Created 5 backend security test files covering the security contract from SECURITY-REVIEW findings C1, H1, H4, H5, H6, M6, M7, M8, M11, L4, L5.

## Changes
- **`backend/tests/unit/test_security_prompt_injection.py`** (create): 34 tests for category name/slug validation and prompt builder injection prevention (C1).
- **`backend/tests/unit/test_security_cursor.py`** (create): 13 tests for cursor tampering rejection and error message sanitization (H1, M7).
- **`backend/tests/unit/test_security_pipeline.py`** (create): 25 tests for event validation, S3 key validation, image size guard, model ID validation, and error sanitization (H4, H5, H6, L5, M8).
- **`backend/tests/unit/test_security_finalize.py`** (create): 8 tests for generic failure reasons, idempotency, S3 encryption, and internal fields (H4, M11, M12, L8).
- **`backend/tests/unit/test_security_upload.py`** (create): 9 tests for presigned URL ContentLength, ValidationError sanitization, and GSI2PK creation (M6, L4).

## Acceptance Criteria Checklist
- [x] Prompt injection tests: names with newlines/markdown/instruction patterns rejected; safe names accepted; invalid slugs rejected
- [x] Cursor tests: tampered cursor (wrong GSI1PK, extra keys, missing keys) returns 400; valid cursor accepted
- [x] Pipeline tests: missing required event fields return "error": "invalid_event"; oversized image returns error; error payloads never contain raw exception messages
- [x] Finalize tests: duplicate pipeline execution doesn't create duplicate line items; idempotent receipt updates
- [x] Upload tests: presigned URL includes ContentLength; ValidationError response sanitized
- [x] `cd backend && uv run pytest tests/unit/test_security_*.py -v` passes

## Test Results
```
101 passed, 8 warnings in 1.90s
```

## Test Breakdown
| File | Tests | Coverage |
|------|-------|----------|
| test_security_prompt_injection.py | 34 | C1 |
| test_security_cursor.py | 13 | H1, M7 |
| test_security_pipeline.py | 25 | H4, H5, H6, L5, M8 |
| test_security_finalize.py | 8 | H4, M11, M12, L8 |
| test_security_upload.py | 9 | M6, L4 |
| **Total** | **101** | |
