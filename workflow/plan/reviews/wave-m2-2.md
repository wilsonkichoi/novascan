# Wave 2 Review (Milestone 2): API Endpoints

Reviewed: 2026-04-02
Reviewer: Claude Opus 4.6 (Claude Code)
Cross-referenced: SPEC.md §2 (M2 Acceptance Criteria), §5 (Database Schema, GSI1, Access Patterns), api-contracts.md (POST /api/receipts/upload-urls, GET /api/receipts), PLAN.md Tasks 2.3–2.4

## Task 2.3: Upload URLs API Endpoint

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Generates ULID for each receipt | PASS | `upload.py:56` — `str(ULID())` per file |
| Creates DynamoDB receipt records with status `processing`, `imageKey`, `createdAt` | PASS | `upload.py:62-77` — batch_writer with all required fields |
| Sets `GSI1PK = USER#{userId}` and `GSI1SK = {createdAt}#{ulid}` | PASS | `upload.py:74-75` — `now_date` (YYYY-MM-DD) + receipt_id |
| Generates presigned S3 PUT URLs with `presignedUrlExpirySec` from env (default 900) | PASS | `upload.py:46,82-89` — env var with fallback |
| Returns 201 with `receipts` array (receiptId, uploadUrl, imageKey, expiresIn) | PASS | `upload.py:91-104` — UploadResponse model |
| Validates request body via Pydantic: >10 files, invalid contentType, invalid fileSize | PASS | `upload.py:35-41` — catches `ValidationError` |
| All DynamoDB records scoped to `PK = USER#{userId}` from JWT sub | PASS | `upload.py:43,66` — sub claim extracted |
| `ruff check src/` passes | PASS | Verified |
| `mypy src/` passes | PASS | 14 source files, no issues |

### Issues Found

**Issue 1 — SUGGESTION: Malformed JSON request body returns 500 instead of 400**

`backend/src/novascan/api/upload.py:34-41` — The `except ValidationError` block only catches Pydantic validation errors. If the request body contains malformed JSON (not empty — Powertools returns `{}` for empty body), `router.current_event.json_body` raises `json.JSONDecodeError`, which is uncaught. The Lambda Powertools resolver catches it as an unhandled exception and returns a generic 500 response.

This means a client sending `Content-Type: application/json` with a body like `{invalid` gets a 500 instead of the spec-defined `400 VALIDATION_ERROR`. API Gateway HTTP API does not validate request body format by default.

**Suggested fix:** Widen the exception catch:
```python
try:
    body = router.current_event.json_body
    request = UploadRequest(**body)
except (ValidationError, TypeError, json.JSONDecodeError) as e:
    return Response(
        status_code=400,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps({"error": {"code": "VALIDATION_ERROR", "message": str(e)}}),
    )
```

---

## Task 2.4: List Receipts API Endpoint

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Queries GSI1 (`GSI1PK = USER#{userId}`) sorted by date descending | PASS | `receipts.py:62,82` — `ScanIndexForward: False` |
| Supports query params: status, category, startDate, endDate, limit, cursor | PASS | `receipts.py:46-55` — all six extracted |
| Status and category applied as FilterExpression | PASS | `receipts.py:71-76` — Attr conditions |
| Date range as KeyConditionExpression: `BETWEEN startDate AND endDate~` | PASS | `receipts.py:63-68` — trailing `~` included, plus gte/lte for partial ranges |
| Returns presigned GET URLs for receipt images (1-hour expiry) | PASS | `receipts.py:99-103` — ExpiresIn=3600 |
| Cursor-based pagination using ExclusiveStartKey/LastEvaluatedKey | PASS | `receipts.py:87,91,125` — encode/decode helpers |
| `ruff check src/` passes | PASS | Verified |
| `mypy src/` passes | PASS | 14 source files, no issues |

### Issues Found

**Issue 2 — SUGGESTION: Malformed pagination cursor returns 500 instead of 400**

`backend/src/novascan/api/receipts.py:87` — The `_decode_cursor` call at line 87 can raise `binascii.Error` (invalid base64) or `json.JSONDecodeError` (base64 decodes to non-JSON). Neither is caught, so a client sending a garbage `cursor` query parameter gets a 500 instead of a clean 400.

This is an input validation gap at a system boundary. While a well-behaved client will only send cursors received from previous responses, malformed cursors from bugs or tampering should return a clear error.

**Suggested fix:** Wrap the cursor decoding:
```python
if cursor:
    try:
        query_kwargs["ExclusiveStartKey"] = _decode_cursor(cursor)
    except (json.JSONDecodeError, Exception) as e:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": {"code": "VALIDATION_ERROR", "message": f"Invalid cursor: {e}"}}),
        )
```

---

**Issue 3 — NIT: S3 clients instantiated per request in both endpoints**

`backend/src/novascan/api/upload.py:47` and `backend/src/novascan/api/receipts.py:59` — Both files create `boto3.client("s3")` inside the route handler, which runs on every invocation. For Lambda, SDK clients should be at module scope so TCP connections are reused across warm invocations. This adds ~50-100ms of unnecessary latency on the first call per warm container.

Note: `get_table()` has the same pattern (pre-existing from Task 1.2). Fixing both at once would be cleaner but is out of scope for this wave.

**Suggested fix:** Move to module level in each file:
```python
s3_client = boto3.client("s3")
```

---

## Cross-Reference: Spec Alignment

| Spec Requirement | Implementation | Verdict |
|-----------------|---------------|---------|
| S3 key format: `receipts/{receiptId}.{ext}` (api-contracts.md line 99) | `upload.py:58` — `f"receipts/{receipt_id}.{ext}"` | PASS |
| DynamoDB key: `PK=USER#{userId}, SK=RECEIPT#{ulid}` (SPEC §5) | `upload.py:66-67` — exact format | PASS |
| GSI1 key: `GSI1PK=USER#{userId}, GSI1SK={date}#{ulid}` (SPEC §5) | `upload.py:74-75` — `now_date` + receipt_id | PASS |
| GSI1SK date range with trailing `~` (SPEC line 671) | `receipts.py:64` — `f"{end_date}~"` | PASS |
| GSI1 sparse: only RECEIPT entities indexed (SPEC line 598) | No entityType filter needed — correct by design | PASS |
| Error response format: `{"error": {"code": ..., "message": ...}}` (api-contracts.md) | `upload.py:40` — exact format | PASS |
| Upload response: 201 status code (api-contracts.md) | `upload.py:101` — 201 | PASS |
| List response: 200 with receipts + nextCursor (api-contracts.md) | `receipts.py:128,126` — 200 + ReceiptListResponse | PASS |
| Presigned URL expiry configurable via env var (SPEC §2) | `upload.py:46` — `PRESIGNED_URL_EXPIRY` env var, default 900 | PASS |
| User isolation: all operations scoped to authenticated userId (api-contracts.md) | Both files extract `sub` from JWT authorizer claim | PASS |
| `entityType` attribute set on DynamoDB records (SPEC §5) | `upload.py:68` — `entityType: RECEIPT` | PASS |
| Batch writer for DynamoDB writes (up to 10 items) | `upload.py:62` — `batch_writer()`, within 25-item DDB batch limit | PASS |
| DynamoDB writes before presigned URL generation | `upload.py` phases 2→3 — correct order | PASS |
| `ReceiptListItem` fields match api-contracts.md | All 11 fields present including subcategory, categoryDisplay, subcategoryDisplay (fixed in wave 1) | PASS |

## Cross-Task Interactions

**Upload → List consistency:** Task 2.3 creates receipt records with `receiptId`, `status`, `imageKey`, `createdAt`, `updatedAt`, `GSI1PK`, `GSI1SK`, `entityType`. Task 2.4 reads `receiptId`, `receiptDate`, `merchant`, `total`, `category`, `subcategory`, `categoryDisplay`, `subcategoryDisplay`, `status`, `imageKey`, `createdAt`. For newly uploaded receipts (status=processing), most fields are absent — the list handler correctly uses `.get()` with None fallbacks for all optional fields. No cross-task issues.

**Cursor security:** The cursor encodes DynamoDB `LastEvaluatedKey` which includes `PK`, `SK`, `GSI1PK`, `GSI1SK`. A tampered cursor with another user's `GSI1PK` is safe because the `KeyConditionExpression` always enforces `GSI1PK = USER#{authenticated_user_id}`. DynamoDB only returns items matching the key condition regardless of where the scan starts.

## Things Done Well

- **Router pattern**: Clean separation using Powertools `Router` per endpoint file with `app.include_router()`. Scales well as more endpoints are added.
- **Phased execution in upload**: DynamoDB writes happen before presigned URL generation (Phase 2 → Phase 3), ensuring records exist before clients can upload. Good ordering.
- **Batch writer**: Using `table.batch_writer()` for up to 10 items is more efficient than individual `put_item` calls and handles automatic batching.
- **Robust date range handling**: List endpoint handles all four date range cases (both, start-only, end-only, neither) with correct GSI1SK conditions, going beyond the acceptance criteria which only specified BETWEEN.
- **Decimal handling**: Explicit `Decimal` → `float` conversion for DynamoDB numbers prevents JSON serialization errors.
- **Type safety**: mypy strict mode passes with targeted `type: ignore` comments where boto3-stubs types are overly broad — justified and minimal.
- **Import path solution**: Adding `src/novascan` to pythonpath, ruff src, and mypy_path with `explicit_package_bases` is a clean resolution for the Lambda-flat bundling vs dev tooling conflict.

## Summary

| # | Severity | Task | Issue | Action |
|---|----------|------|-------|--------|
| 1 | SUGGESTION | 2.3 | Malformed JSON body → 500 instead of 400 | Widen exception catch to include `JSONDecodeError` |
| 2 | SUGGESTION | 2.4 | Malformed cursor → 500 instead of 400 | Add try/except around `_decode_cursor` |
| 3 | NIT | 2.3, 2.4 | S3 client per request instead of module-level | Move `boto3.client("s3")` to module scope |

**Overall verdict:** Clean implementation. Both endpoints correctly implement the API contracts, DynamoDB access patterns, and user isolation. The two SUGGESTION issues are input validation gaps at system boundaries — the endpoints handle happy-path and Pydantic-validated input correctly but let malformed raw input bubble up as 500s. No BLOCKERs, no security issues, no spec deviations. The NIT is a Lambda best practice optimization.

## Review Discussion

### Fix Plan (Claude Opus 4.6 / Claude Code — 2026-04-02)

**Issue 1 (Malformed JSON body → 500 in upload endpoint)**
- Verified: Read `upload.py:34-36` — only `ValidationError` is caught. `router.current_event.json_body` calls `json.loads()` internally, which raises `json.JSONDecodeError` on malformed input like `{invalid`. A `TypeError` can also occur if body is an unexpected type. Both propagate as unhandled 500s.
- Alternatives considered: Adding a separate `json.loads()` call before Pydantic validation — rejected, redundant since `json_body` already parses. Catching bare `Exception` — rejected, too broad. Using Powertools `@validator` decorator — doesn't exist for this use case.
- Fix: Widen the except clause at `upload.py:36` from `except ValidationError` to `except (ValidationError, TypeError, json.JSONDecodeError)`. The error response format stays the same (`VALIDATION_ERROR` code, 400 status).
- Files: `backend/src/novascan/api/upload.py`

**Issue 2 (Malformed cursor → 500 in list endpoint)**
- Verified: Read `receipts.py:87` — `_decode_cursor(cursor)` is called without any exception handling. `_decode_cursor` (line 30-32) calls `base64.urlsafe_b64decode()` then `json.loads()`. Invalid base64 raises `binascii.Error`, non-JSON content raises `json.JSONDecodeError`. Both unhandled → 500.
- Alternatives considered: Validating cursor format before decoding (regex check for base64) — rejected, still doesn't catch invalid JSON after decode. Using a dedicated `CursorParam` Pydantic model — overengineered for a single field.
- Fix: Wrap the `_decode_cursor` call at line 87 in try/except catching `Exception` (multiple failure modes: `binascii.Error`, `json.JSONDecodeError`, `KeyError` if decoded dict has wrong shape). Return 400 with `VALIDATION_ERROR` code and `"Invalid cursor"` message.
- Files: `backend/src/novascan/api/receipts.py`

**Issue 3 (S3 client per request → module scope)**
- Verified: Read `upload.py:47` — `s3_client = boto3.client("s3")` inside `upload_urls()`. Read `receipts.py:59` — same inside `list_receipts()`. Both create a new client on every invocation instead of reusing across warm Lambda containers.
- Note: `get_table()` in `shared/dynamo.py:28` has the same pattern (`boto3.resource("dynamodb")` per call). The review flagged this as pre-existing and out of scope. Fixing `get_table()` is a separate concern — skip for this wave.
- Alternatives considered: Creating a shared `shared/s3.py` helper mirroring `shared/dynamo.py` — rejected, premature abstraction for two callsites. Lazy-init with a module-level `None` sentinel — rejected, unnecessary complexity when module-level init works fine for Lambda.
- Fix: Move `s3_client = boto3.client("s3")` to module scope in both `upload.py` and `receipts.py`. Remove the per-request assignment inside the handler.
- Files: `backend/src/novascan/api/upload.py`, `backend/src/novascan/api/receipts.py`

**Execution order:**
1. Edit `upload.py`: move `s3_client` to module scope, widen except clause to include `TypeError` and `json.JSONDecodeError`
2. Edit `receipts.py`: move `s3_client` to module scope, wrap `_decode_cursor` call in try/except

No ordering dependencies between the two files.

**Verification:**
```bash
cd backend && uv run ruff check src/ && uv run mypy src/
```

### Fix Results (Claude Opus 4.6 / Claude Code — 2026-04-02)

**Branch:** `fix/wave2-review-issues` (based on `feature/m2-wave2-api-endpoints`)

**Issue 1 (Malformed JSON body → 500 in upload endpoint) — Fixed**
- What was changed: Widened except clause from `ValidationError` to `(ValidationError, TypeError, json.JSONDecodeError)` at `upload.py:36`
- Files modified: `backend/src/novascan/api/upload.py`

**Issue 2 (Malformed cursor → 500 in list endpoint) — Fixed**
- What was changed: Wrapped `_decode_cursor(cursor)` call in try/except at `receipts.py:85-92`, returns 400 with `VALIDATION_ERROR` code on any decoding failure
- Files modified: `backend/src/novascan/api/receipts.py`

**Issue 3 (S3 client per request → module scope) — Fixed**
- What was changed: Moved `s3_client = boto3.client("s3")` to module scope in both files, removed per-request instantiation inside handlers
- Files modified: `backend/src/novascan/api/upload.py`, `backend/src/novascan/api/receipts.py`

**Verification:**
- `uv run ruff check src/` — PASS (all checks passed)
- `uv run mypy src/` — PASS (no issues found in 14 source files)

### Fix Verification (Claude Opus 4.6 / Claude Code — 2026-04-02)

**Issue 1 (Malformed JSON body → 500 in upload endpoint) — Fixed** ✓
Verified: Read `upload.py:35-42`. The except clause at line 37 now catches `(ValidationError, TypeError, json.JSONDecodeError)`. The `json` module is imported at line 5. Confirmed via `git diff feature/m2-wave2-api-endpoints..fix/wave2-review-issues` — the old `except ValidationError` was replaced with the widened tuple. The error response format (`VALIDATION_ERROR` code, 400 status, `str(e)` message) is preserved. Malformed JSON bodies will now return a proper 400 instead of 500.

**Issue 2 (Malformed cursor → 500 in list endpoint) — Fixed** ✓
Verified: Read `receipts.py:85-93`. The `_decode_cursor(cursor)` call is now wrapped in `try/except Exception`. Any failure (including `binascii.Error` from invalid base64, `json.JSONDecodeError` from non-JSON content, or `KeyError` from malformed dict) returns 400 with `VALIDATION_ERROR` code and `f"Invalid cursor: {e}"` message. Confirmed via diff — the bare assignment was replaced with the guarded block.

**Issue 3 (S3 client per request → module scope) — Fixed** ✓
Verified: Read `upload.py:24` — `s3_client = boto3.client("s3")` at module scope. Read `receipts.py:23` — same. Confirmed via diff — both files had per-handler `s3_client = boto3.client("s3")` lines removed and a module-scope assignment added. The module-scope client is referenced at `upload.py:81` and `receipts.py:105`. TCP connections will now be reused across warm Lambda invocations.

**Regression check:** No regressions detected. Both files maintain the same external behavior for valid inputs. The diff is additive (broader exception handling, client initialization moved) with no functional changes to happy-path logic.

**Verification commands:**
- `uv run ruff check src/` — PASS
- `uv run mypy src/` — PASS
- `uv run pytest -v` — PASS (0 tests collected — no backend tests exist yet for wave 2, expected)

**Verdict:** 3/3 issues resolved. All fixes correctly applied, no regressions.
