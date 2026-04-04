# Task 2.7: Receipt Upload + Storage API Tests

## Work Summary
- **Branch:** `task/2.7-upload-storage-api-tests` (based on `feature/m2-wave4-tests`)
- **What was implemented:** Comprehensive test suites for the upload-urls and list-receipts API endpoints, plus Pydantic model validation tests. 94 total tests covering happy paths, error paths, boundary values, DynamoDB record verification, pagination, filtering, and user isolation.
- **Key decisions:**
  - Used `FakeLambdaContext` dataclass to satisfy Lambda Powertools' context requirement instead of mocking
  - Tests invoke the full handler via `api.app.handler()` with constructed API Gateway HTTP API v2 events, testing the real routing and validation
  - Each test class sets up its own moto `mock_aws` context via fixture to ensure isolation
  - Receipt IDs in seed data use deterministic strings for predictable test behavior
- **Files created/modified:**
  - `backend/tests/unit/test_receipt_models.py` (38 tests) -- Pydantic model validation
  - `backend/tests/unit/test_upload.py` (29 tests) -- POST /api/receipts/upload-urls endpoint
  - `backend/tests/unit/test_receipts_list.py` (27 tests) -- GET /api/receipts endpoint
- **Test results:** 94 passed, 0 failed, 0 errors
- **Spec gaps found:** none
- **Obstacles encountered:** Lambda Powertools requires a non-None Lambda context with function_name, memory_limit_in_mb, invoked_function_arn, and aws_request_id attributes. Solved with a `FakeLambdaContext` dataclass.

## Test Coverage Summary

### test_receipt_models.py (38 tests)
- UploadFileRequest: valid JPEG/PNG, boundary file sizes (1 byte, 10MB), rejection of zero/negative/oversized, invalid content types, filename constraints
- UploadRequest: single file, max 10, exceeds 10 rejected, empty rejected, mixed types, dict construction
- UploadResponse: field validation, serialization
- Receipt: processing/confirmed/failed states, status validation, rankingWinner enum, usedFallback, required fields
- ReceiptListItem: null OCR fields for processing, full fields for confirmed, field name contract
- ReceiptListResponse: empty, with cursor, null cursor, serialization

### test_upload.py (29 tests)
- Happy path: 201 response, response shape, ULID format, unique IDs, image key format, presigned URLs, expiresIn, 10-file batch, mixed types
- DynamoDB records: PK/SK format, status=processing, entityType=RECEIPT, imageKey, timestamps, GSI1 keys, batch record creation
- Validation: 11 files, empty files, invalid content type, oversized, zero size, empty filename, missing body, malformed JSON, missing keys, missing fields, long filename
- User isolation: records scoped to user, different users get separate partitions

### test_receipts_list.py (27 tests)
- Happy path: 200 response, empty list, user receipts returned, response field contract, presigned image URLs, processing null fields
- Sorting: date descending order
- Pagination: default limit, custom limit, cursor navigation, no cursor when complete, limit clamping, invalid cursor 400
- Filters: status (confirmed, processing), category, date range (both, start only, end only), combined filters
- User isolation: cross-user isolation, empty user gets empty list, multi-user isolation
- Edge cases: non-numeric limit fallback, response shape, total is numeric

## Review Discussion
