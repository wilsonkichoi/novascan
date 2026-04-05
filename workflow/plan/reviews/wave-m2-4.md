# Wave M2-4 Review: Tests

Reviewed: 2026-04-04
Reviewer: Claude Opus 4.6 (1M context)
Cross-referenced: PLAN.md (Task 2.7, 2.8), api-contracts.md (POST /api/receipts/upload-urls, GET /api/receipts), SPEC.md (Milestone 2)

## Review Summary

Both test tasks are well-executed with comprehensive coverage. Task 2.7 delivers 94 backend tests and Task 2.8 delivers 89 frontend tests, all passing. The tests correctly verify API contracts, spec requirements, and edge cases. Test quality is high: tests focus on behavior rather than implementation details, each test is independent with proper isolation via moto/mock fixtures, and assertions are specific and meaningful.

One suggestion and two nits identified. No blockers.

## Task 2.7: Receipt Upload + Storage API Tests

### Acceptance Criteria Check

| Criteria | Status | Notes |
|----------|--------|-------|
| Upload tests: valid request creates receipts and returns presigned URLs | PASS | `TestUploadUrlsHappyPath` — 9 tests cover 201 response, response shape, presigned URLs, expiresIn, batch of 10, mixed types |
| Upload tests: rejects >10 files | PASS | `test_eleven_files_rejected` verifies 400 + VALIDATION_ERROR |
| Upload tests: rejects invalid contentType | PASS | `test_invalid_content_type_rejected` with image/gif |
| Upload tests: rejects oversized files | PASS | `test_oversized_file_rejected` (10,485,761 bytes), `test_zero_file_size_rejected` (0 bytes) |
| Upload tests: each receipt gets unique ULID | PASS | `test_each_receipt_gets_unique_ulid` — 5 files, asserts 5 distinct IDs |
| Upload tests: DynamoDB records created with correct PK/SK/status | PASS | `TestUploadDynamoDBRecords` — 7 tests: PK/SK format, status=processing, entityType=RECEIPT, imageKey, timestamps, GSI1 keys, batch creation |
| List tests: returns user's receipts sorted by date desc | PASS | `test_sorted_by_date_descending` seeds 3 receipts in non-date order, verifies descending |
| List tests: pagination with cursor | PASS | 7 tests: default limit, custom limit, cursor navigation, no cursor when complete, limit clamping (min/max), invalid cursor 400 |
| List tests: filters by status/category/date range | PASS | 7 tests: status confirmed, status processing, category, date range (both/start-only/end-only), combined filters |
| List tests: does not return other users' receipts | PASS | `TestListReceiptsUserIsolation` — 3 tests: cross-user isolation, empty user, multi-user isolation |
| Model tests: Pydantic validation accepts valid data, rejects invalid | PASS | 38 tests covering all model classes with boundary values and rejection cases |
| `cd backend && uv run pytest tests/unit/test_upload.py tests/unit/test_receipts_list.py tests/unit/test_receipt_models.py -v` passes | PASS | 94 passed in 4.19s |

### Code Review

**Strengths:**

- **Full handler integration testing:** Tests invoke `api.app.handler()` with constructed API Gateway HTTP API v2 events through `_build_apigw_event`. This tests the real routing, Pydantic validation, and DynamoDB interaction — not just unit testing individual functions. This is the right level of abstraction for API contract tests.
- **FakeLambdaContext dataclass:** Clean solution to Lambda Powertools' context requirement. Avoids complex mocking while satisfying the framework's contract.
- **Comprehensive boundary testing:** `test_receipt_models.py` covers both sides of every boundary: fileSize=1 (accepted), fileSize=0 (rejected), fileSize=10,485,760 (accepted), fileSize=10,485,761 (rejected), fileName 255 chars (accepted), fileName 256 chars (rejected). This is thorough.
- **Deterministic receipt IDs in seed data:** `test_receipts_list.py` uses predictable `01RECEIPT000001AAAAAA0001`-style IDs for seeded data, making test assertions unambiguous.
- **Test isolation:** Each fixture creates its own moto `mock_aws` context. No shared mutable state between test classes.
- **Filter tests use specific assertions:** Category filter test verifies both the count (1 result) and the field value (`groceries-food`), not just one or the other.

**Observation on test style:**

The tests correctly avoid testing implementation details. They verify the API contract (response shape, status codes, error codes) and DynamoDB record structure (PK/SK format, required attributes) without asserting internal function call sequences.

### Issues Found

**SUGGESTION: `test_limit_minimum_clamped_to_1` has a weak assertion**

`backend/tests/unit/test_receipts_list.py:406-419` — The test for `limit=0` asserts `len(body["receipts"]) >= 0`, which is a tautology (a list always has length >= 0). The test is supposed to verify that limit=0 is clamped to at least 1, but the assertion would pass even if the endpoint returned an empty list or errored. Compare with the implementation at `receipts.py:54` which does `max(int(...), 1)`, meaning limit=0 should be clamped to 1 and with a seeded receipt, should return exactly 1 receipt.

Suggested fix: Assert `len(body["receipts"]) == 1` (the test seeds one receipt and the clamped limit of 1 should return it).

**NIT: Duplicated `FakeLambdaContext` across test files**

`backend/tests/unit/test_upload.py:27-33` and `backend/tests/unit/test_receipts_list.py:27-33` — The identical `FakeLambdaContext` dataclass is duplicated in both test files. It could be extracted to `conftest.py` or a shared test helper. Not a correctness issue, but reduces maintenance if the context signature changes.

## Task 2.8: Upload + Receipts List UI Tests

### Acceptance Criteria Check

| Criteria | Status | Notes |
|----------|--------|-------|
| Upload area tests: accepts JPEG/PNG | PASS | `test_accepts_valid_jpeg`, `test_accepts_valid_png`, `test_accepts_multiple_valid_files` |
| Upload area tests: rejects other types | PASS | PDF, GIF, WebP rejection tests with error messages |
| Upload area tests: rejects >10 MB | PASS | Boundary tests: 10 MB accepted, 10 MB + 1 byte rejected, 11 MB rejected |
| Upload area tests: limits to 10 files | PASS | 11 files rejected, 10 accepted, custom maxFiles, currentFileCount accounting |
| Upload flow tests: calls upload-urls API | PASS | `test_calls_requestUploadUrls_with_the_selected_files` |
| Upload flow tests: uploads to presigned URLs | PASS | `test_uploads_each_file_to_presigned_URL_via_uploadFileToS3` verifies URL and file arguments |
| Upload flow tests: retries on failure with backoff | PASS | `test_retries_failed_uploads_up_to_3_times` — 4 total calls (1 initial + 3 retries) |
| Upload flow tests: requests new URL on expiry | PASS | `test_requests_a_new_presigned_URL_when_upload_fails` — `requestUploadUrls` called twice |
| Receipts page tests: renders receipt cards | PASS | Merchant, total, date, category display all verified |
| Receipts page tests: shows correct status badges | PASS | Processing, Confirmed, Failed badges tested |
| Receipts page tests: pagination works | PASS | 5 tests: Load More visible/hidden, fetches next page, passes cursor, hides after last page |
| `cd frontend && npm run test -- --run` passes | PASS | 175 tests passed (89 new + 86 existing) in 2.24s |

### Code Review

**Strengths:**

- **`simulateFileChange` helper:** Using `fireEvent.change` instead of `userEvent.upload` is the correct approach for testing the component's JavaScript validation layer. The detailed comment explaining why (userEvent respects the HTML `accept` attribute and silently drops non-matching files) is helpful for future maintainers.
- **Immediate setTimeout replacement:** The approach in `useUpload.test.ts` of replacing `setTimeout` with an immediate microtask-based implementation eliminates 7+ seconds of backoff delays per retry test while preserving the async ordering. Much better than using fake timers with `shouldAdvanceTime: true` which was noted as problematic.
- **Mock isolation in ScanPage tests:** Mocking the `useUpload` hook lets ScanPage tests focus on rendering behavior without being coupled to upload logic. The hook is tested separately in its own test file.
- **TanStack Query test setup:** Using `retry: false` and `gcTime: 0` in the test QueryClient prevents flaky tests from unexpected retries or cached data.
- **Pagination integration tests:** `ReceiptsPage.test.tsx` tests the full pagination flow: first page renders, click Load More, second page appears alongside first, cursor is passed correctly, button disappears after last page. This is the right way to test infinite query behavior.
- **Mixed batch validation:** `UploadArea.test.tsx` tests that from a batch of valid + invalid files, only valid files are passed to `onFilesSelected` while errors are shown for invalid ones. Good real-world scenario coverage.
- **Null handling edge cases:** Tests for confirmed receipts with null merchant ("Unknown") and null total ("--") cover a real scenario where OCR might extract some fields but not others.

**Observation on testing approach:**

The `useUpload` tests correctly verify the upload contract without testing internal state transitions mid-flight. They check initial state, final state after `startUpload`, and the API call patterns. This is behavior testing, not implementation testing.

### Issues Found

**NIT: ScanPage `startUpload` integration test is a placeholder**

`frontend/src/pages/__tests__/ScanPage.test.tsx:330-341` — The test titled "passes onFilesSelected to UploadArea that calls startUpload" only verifies that the Choose Files button exists, not that `startUpload` is actually connected to `UploadArea.onFilesSelected`. Since `useUpload` is mocked, the test cannot verify the wiring. This is noted in the test comments ("The actual file handling is tested in UploadArea tests"), but the test name overpromises relative to what it asserts.

This is acceptable because the wiring is trivially visible in ScanPage.tsx line 14 (`<UploadArea onFilesSelected={startUpload} />`), and the individual component tests cover the actual behavior. The test still provides value by verifying the component renders without error in idle phase.

## Test Execution Results

### Backend (Task 2.7)

```
94 passed in 4.19s

tests/unit/test_upload.py — 29 tests (all passed)
  TestUploadUrlsHappyPath: 9 passed
  TestUploadDynamoDBRecords: 7 passed
  TestUploadValidation: 11 passed
  TestUploadUserIsolation: 2 passed

tests/unit/test_receipts_list.py — 27 tests (all passed)
  TestListReceiptsHappyPath: 6 passed
  TestListReceiptsSorting: 1 passed
  TestListReceiptsPagination: 7 passed
  TestListReceiptsFilters: 7 passed
  TestListReceiptsUserIsolation: 3 passed
  TestListReceiptsEdgeCases: 3 passed

tests/unit/test_receipt_models.py — 38 tests (all passed)
  TestUploadFileRequest: 13 passed
  TestUploadRequest: 7 passed
  TestUploadResponse: 3 passed
  TestReceipt: 8 passed
  TestReceiptListItem: 3 passed
  TestReceiptListResponse: 4 passed
```

### Frontend (Task 2.8)

```
175 passed (89 new + 86 existing) in 2.24s

src/components/__tests__/UploadArea.test.tsx — 27 tests (all passed)
src/hooks/__tests__/useUpload.test.ts — 16 tests (all passed)
src/pages/__tests__/ScanPage.test.tsx — 22 tests (all passed)
src/pages/__tests__/ReceiptsPage.test.tsx — 24 tests (all passed)

Pre-existing test files also passing:
src/lib/__tests__/auth.test.ts — 30 tests
src/hooks/__tests__/useAuth.test.tsx — 11 tests
src/components/__tests__/ProtectedRoute.test.tsx — 8 tests
src/components/__tests__/AppShell.test.tsx — 15 tests
src/pages/__tests__/LoginPage.test.tsx — 22 tests
```

## Review Discussion

### Issue Summary

| # | Severity | Task | Issue | Action |
|---|----------|------|-------|--------|
| 1 | SUGGESTION | 2.7 | `test_limit_minimum_clamped_to_1` asserts `len >= 0` (tautology), should assert `== 1` | Strengthen assertion |
| 2 | NIT | 2.7 | `FakeLambdaContext` duplicated across test_upload.py and test_receipts_list.py | Extract to conftest.py |
| 3 | NIT | 2.8 | ScanPage integration test name overpromises (verifies button exists, not wiring) | Rename or add assertion |

### Fix Plan

**Issue 1 (Weak limit=0 assertion)**
- File: `backend/tests/unit/test_receipts_list.py`
- Change: In `test_limit_minimum_clamped_to_1`, replace `assert len(body["receipts"]) >= 0  # At minimum doesn't error` with `assert len(body["receipts"]) == 1` since the test seeds one receipt and the implementation clamps limit=0 to 1.
- Risk: None. The test already seeds one receipt and the implementation at `receipts.py:54` does `max(int(...), 1)`, so the assertion should pass.
- Verification: `cd backend && uv run pytest tests/unit/test_receipts_list.py::TestListReceiptsPagination::test_limit_minimum_clamped_to_1 -v`

**Issues 2 and 3 are NITs and do not require action.**

**Overall verdict:** Both test tasks deliver comprehensive, well-structured test suites that correctly validate the API contracts and UI behavior specified in PLAN.md and api-contracts.md. The single SUGGESTION is a minor assertion improvement. No blockers. The wave is ready for merge after optionally addressing Issue 1.

### Fix Plan Analysis (Claude Opus 4.6 — 2026-04-04)

**Issue 1 (Weak limit=0 assertion) — Approved**
- Analysis: The fix plan is correct. The implementation at `receipts.py:54` does `min(max(int(...), 1), 100)`, which clamps `limit=0` to `1`. The DynamoDB query uses this as `Limit: 1` (line 82). The test seeds exactly one receipt for `user-abc-123` with no filters applied (no status/category/date query params), so the GSI1 query on `USER#user-abc-123` will return that single receipt. Changing `assert len(body["receipts"]) >= 0` to `assert len(body["receipts"]) == 1` converts a tautology into a meaningful assertion that actually verifies the clamping behavior. The existing `assert response["statusCode"] == 200` remains and correctly guards against error responses.
- Risk: None. The assertion is deterministic given the test setup (one seeded receipt, clamped limit of 1, no filters). No flakiness risk.

### Fix Results (Claude Opus 4.6 — 2026-04-04)

**Branch:** `feature/m2-wave4-tests` (applied directly — single-line fix)

**Issue 1 (Weak limit=0 assertion) — Fixed**
- What was changed: `backend/tests/unit/test_receipts_list.py:418` — replaced `assert len(body["receipts"]) >= 0` with `assert len(body["receipts"]) == 1`
- Files modified: `backend/tests/unit/test_receipts_list.py`

**Issues 2, 3 (NITs) — Skipped**
- Reason: NITs do not require action per pipeline rules.

**Verification:**
- `uv run pytest tests/unit/test_receipts_list.py::TestListReceiptsPagination::test_limit_minimum_clamped_to_1 -v` — PASS
- `uv run pytest tests/unit/test_upload.py tests/unit/test_receipts_list.py tests/unit/test_receipt_models.py -v` — PASS (94/94)
