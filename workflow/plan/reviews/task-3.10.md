# Task 3.10 Review: Validate Pagination Cursor + Sanitize API Errors [H1 + M7]

## Summary
Added strict validation for pagination cursors to prevent cursor injection attacks and cross-user data exposure. Error messages are now generic to prevent information leakage.

## Changes
- **`backend/src/novascan/api/receipts.py`**:
  - `_decode_cursor()` now accepts `user_id` parameter and validates:
    - Decoded JSON has exactly `{GSI1PK, GSI1SK, PK, SK}` keys
    - `GSI1PK` equals `USER#{authenticated_userId}` (ownership check)
  - Error response uses generic `"Invalid pagination cursor"` message
  - Detailed error logged server-side via `logger.warning()`
- **`backend/tests/unit/test_receipts_list.py`**:
  - Updated existing invalid cursor test to check for generic message
  - Added `test_cursor_with_wrong_keys_returns_400`
  - Added `test_cursor_targeting_other_user_returns_400`

## Acceptance Criteria Checklist
- [x] `_decode_cursor()` validates decoded JSON has exactly `{GSI1PK, GSI1SK, PK, SK}` keys
- [x] Decoded cursor's `GSI1PK` must equal `USER#{authenticated_userId}`
- [x] Error response uses generic message `"Invalid pagination cursor"` (no `str(e)`)
- [x] Detailed error logged server-side via `logger.warning()`
- [x] Existing list receipts tests updated and passing
- [x] `ruff check src/` passes
- [x] `pytest tests/unit/test_receipts_list.py -v` passes (29 tests)

## Test Results
```
All checks passed!  (ruff)
29 passed in 2.04s  (pytest)
```
