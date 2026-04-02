# Wave 1 Review (Milestone 2): Backend Models + Upload UI

Reviewed: 2026-04-01
Reviewer: Claude Opus 4.6 (Claude Code)
Cross-referenced: SPEC.md §2 (M2 Acceptance Criteria), §5 (Receipt Attributes), api-contracts.md (POST /api/receipts/upload-urls, GET /api/receipts)

## Task 2.1: Receipts S3 Bucket + Pydantic Models

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| `cdk synth` includes second S3 bucket with SSE-S3, BlockPublicAccess, versioning | PASS | ReceiptsBucket has all three + enforce_ssl |
| Receipts bucket created without event notification | PASS | Deferred to M3 Task 3.5 per plan |
| Pydantic models match api-contracts.md field definitions exactly | FAIL | `nextCursor` named `cursor`; `subcategory` missing from list item (Issues 1, 2) |
| `UploadRequest` validates 1-10 files, contentType, fileSize | PASS | Literal type + Field constraints correct |
| `ruff check src/` passes | PASS | |
| `mypy src/` passes | PASS | 12 source files, no issues |

### Spec Alignment

| Spec Requirement | Implementation | Verdict |
|-----------------|---------------|---------|
| S3 bucket: private, SSE-S3, BlockPublicAccess, versioning (SPEC §2) | `storage.py:52-62` — all four configured | PASS |
| Presigned URL expiry configurable via `presignedUrlExpirySec` (SPEC §2) | `api.py:117` — reads from config, default 900 | PASS |
| Upload response: `receiptId`, `uploadUrl`, `imageKey`, `expiresIn` (api-contracts.md) | `receipt.py:24-30` — all four fields present | PASS |
| Upload request: 1-10 files, contentType jpeg/png, fileSize 1-10MB (api-contracts.md) | `receipt.py:10-21` — exact constraints | PASS |
| List response: `nextCursor` pagination field (api-contracts.md line 141) | `receipt.py:79` — named `cursor` | FAIL |
| List item: includes `subcategory` field (api-contracts.md line 134) | `receipt.py:62-72` — field missing | FAIL |
| Stack outputs: ReceiptsBucketName (SPEC §3) | `novascan_stack.py:73-78` — CfnOutput present | PASS |
| API Lambda env vars: RECEIPTS_BUCKET, PRESIGNED_URL_EXPIRY | `api.py:116-117` — both set | PASS |
| S3 grant to API Lambda | `api.py:127-128` — conditional grant_read_write | PASS |

### Issues Found

**Issue 1 — SUGGESTION: `ReceiptListResponse` uses `cursor` instead of `nextCursor`**

`backend/src/novascan/models/receipt.py:79` — The field is named `cursor` but api-contracts.md specifies `nextCursor` in the GET /api/receipts response (line 141: `"nextCursor": "eyJza..."`).

This violates the acceptance criterion "Pydantic models match api-contracts.md field definitions exactly." If left unfixed, the Task 2.4 implementer will either propagate the wrong name into the API response (breaking the frontend contract) or have to fix it ad hoc.

**Suggested fix:** Rename `cursor` to `nextCursor` on line 79:
```python
nextCursor: str | None = None
```

---

**Issue 2 — SUGGESTION: `ReceiptListItem` missing `subcategory` field**

`backend/src/novascan/models/receipt.py:62-72` — The API contract for GET /api/receipts (api-contracts.md lines 126-142) includes `subcategory` in each receipt list item. The full `Receipt` model at line 51 has `subcategory`, but `ReceiptListItem` omits it.

`subcategory` is a stored field on the DynamoDB receipt record, not a computed field. It should be part of the list projection since users filter and view by subcategory.

**Suggested fix:** Add to `ReceiptListItem` after `category`:
```python
subcategory: str | None = None
```

---

**Issue 3 — NIT: `ReceiptListItem` missing `categoryDisplay` and `subcategoryDisplay`**

`backend/src/novascan/models/receipt.py:62-72` — The API contract includes `categoryDisplay` and `subcategoryDisplay` in the list response (api-contracts.md lines 133, 135). These are not in `ReceiptListItem`.

These are computed fields derived from the category taxonomy at response time, not stored in DynamoDB. Deferring them to Task 2.4 (when the endpoint is built and the taxonomy module exists) is acceptable. However, the acceptance criterion technically requires exact match.

**Suggested fix:** Either add now as optional fields, or explicitly note in Task 2.4 that the response model needs these display fields. No blocker.

## Task 2.2: Upload UI Components

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Camera capture via `<input capture="environment">` | PASS | `UploadArea.tsx:167` — correct attribute |
| File picker for single and multi-file selection (up to 10) | PASS | `UploadArea.tsx:175-179` — `multiple` attribute, maxFiles=10 default |
| Client-side validation: reject non-JPEG/PNG, reject > 10 MB | PASS | `UploadArea.tsx:33-41` — type and size checks |
| Per-file progress bar with status | PASS | `UploadProgress.tsx:60-128` — status icons + progress bars |
| Upload summary shows "{N} of {M} receipts uploaded" with retry | PASS | `UploadSummary.tsx:47` — exact format |
| `npm run build` succeeds | PASS | Zero TypeScript errors |

### Spec Alignment

| Spec Requirement | Implementation | Verdict |
|-----------------|---------------|---------|
| Camera capture `<input capture="environment">` (SPEC §2) | `UploadArea.tsx:167` | PASS |
| Bulk selection up to 10 files (SPEC §2) | `UploadArea.tsx:12` — `maxFiles` prop, default 10 | PASS |
| Reject non-JPEG/PNG client-side (SPEC §2) | `UploadArea.tsx:7,33-34` — `ACCEPTED_TYPES` Set | PASS |
| Reject > 10 MB client-side (SPEC §2) | `UploadArea.tsx:6,37-38` — `MAX_FILE_SIZE` constant | PASS |
| Per-file progress indicators (SPEC §2) | `UploadProgress.tsx` — full component with ARIA | PASS |
| Upload summary with per-file status + retry (SPEC §2) | `UploadSummary.tsx` — retry button + failed file list | PASS |
| Drag-and-drop zone (task spec) | `UploadArea.tsx:108-111` — native HTML5 DnD events | PASS |

### Issues Found

No issues found.

## Things Done Well

**Task 2.1:**
- S3 bucket security configuration is thorough: BlockPublicAccess, SSE-S3, enforce_ssl, versioning, stage-aware removal policy
- Backward-compatible `receipts_bucket: s3.IBucket | None = None` parameter on ApiConstruct — clean extension point
- Pydantic validation constraints are precise: `Literal` for contentType, `Field(ge=1, le=10_485_760)` for fileSize
- CDK snapshot test updated to reflect new resources
- All 47 infrastructure tests pass with new bucket

**Task 2.2:**
- Native HTML5 drag-and-drop implementation avoids external library dependency (react-dropzone), consistent with project's "minimize third-party deps" philosophy
- Accessible progress bars with full ARIA support (`role="progressbar"`, `aria-valuenow/min/max`, `aria-label`)
- `truncateFilename()` preserves file extensions when truncating long names — good UX detail
- Validation errors use `role="alert"` for screen reader announcement
- Camera button correctly scoped to mobile-only (`md:hidden`)
- File input refs are reset after selection (`e.target.value = ""`) to allow re-selecting the same file
- Components are presentational-only, cleanly separating concerns for Task 2.5 integration

## Cross-Task Observations

**`frontend/src/types/index.ts` — Receipt type field misalignment (out of scope)**

The `Receipt` type created in Task 1.3 scaffolding has field names that don't match the API contract:
- `id` should be `receiptId`
- `merchantName` should be `merchant`
- `transactionDate` should be `receiptDate`
- `LineItem.description` should be `name`
- `LineItem.category` should be `subcategory`

This will need reconciliation when Tasks 2.5/2.6 integrate the upload components with the actual API. Not actionable now, but the Task 2.5/2.6 implementer should be aware.

## Summary

| # | Severity | Task | Issue | Action |
|---|----------|------|-------|--------|
| 1 | SUGGESTION | 2.1 | `cursor` should be `nextCursor` in ReceiptListResponse | Rename field in receipt.py:79 |
| 2 | SUGGESTION | 2.1 | `ReceiptListItem` missing `subcategory` field | Add `subcategory: str \| None = None` |
| 3 | NIT | 2.1 | `ReceiptListItem` missing `categoryDisplay`/`subcategoryDisplay` | Add or defer to Task 2.4 |

**Overall verdict:** Solid wave. Infrastructure is correctly configured with proper security controls. Upload UI components are well-crafted and accessible. Two field-level spec deviations in the Pydantic models need fixing before Task 2.4 builds the list endpoint — both are trivial one-line changes. Task 2.2 passes cleanly with no issues.

## Review Discussion

### Fix Plan (Claude Opus 4.6 / Claude Code — 2026-04-01)

**Issue 1 (`cursor` → `nextCursor`)**
- Verified: Read `receipt.py:79` — field is `cursor: str | None = None`. Read api-contracts.md line 141 — contract specifies `"nextCursor"`. Mismatch confirmed.
- Alternatives considered: Using a Pydantic `Field(alias="nextCursor")` to keep the Python name as `cursor` — rejected because the project convention is to use camelCase field names matching the API contract directly (see `UploadReceiptResponse`, `UploadFileRequest`), not aliases.
- Fix: Rename `cursor` to `nextCursor` on `ReceiptListResponse` line 79. No consumers exist yet (Task 2.4 not implemented).
- Files: `backend/src/novascan/models/receipt.py`

**Issue 2 (Missing `subcategory` on `ReceiptListItem`)**
- Verified: Read `receipt.py:62-72` — `ReceiptListItem` has `category` but no `subcategory`. Read api-contracts.md line 134 — contract includes `subcategory` in list response. Full `Receipt` model at line 51 has `subcategory`. Omission confirmed.
- Alternatives considered: None — this is a straightforward missing field. Deferring would mean Task 2.4 inherits the gap.
- Fix: Add `subcategory: str | None = None` after `category` (line 69) in `ReceiptListItem`.
- Files: `backend/src/novascan/models/receipt.py`

**Issue 3 (Missing `categoryDisplay`/`subcategoryDisplay` on `ReceiptListItem`)**
- Verified: Read `receipt.py:62-72` — neither display field present. Read api-contracts.md lines 133, 135 — both fields in list response.
- Alternatives considered: Defer to Task 2.4 when the taxonomy module exists (Task 4.1). Rejected — adding the fields now as `str | None = None` costs nothing, satisfies the "exact match" acceptance criterion, and means Task 2.4 only needs to populate them rather than also adding them.
- Fix: Add `categoryDisplay: str | None = None` and `subcategoryDisplay: str | None = None` after `subcategory` in `ReceiptListItem`. These are computed fields populated at response time by the endpoint handler, not stored in DynamoDB.
- Files: `backend/src/novascan/models/receipt.py`

**Execution order:**
1. Edit `backend/src/novascan/models/receipt.py`: add `subcategory`, `categoryDisplay`, `subcategoryDisplay` to `ReceiptListItem` (after `category` field)
2. Edit `backend/src/novascan/models/receipt.py`: rename `cursor` → `nextCursor` on `ReceiptListResponse`

All changes are in one file with no ordering dependencies.

**Verification:**
```bash
cd backend && uv run ruff check src/ && uv run mypy src/ && uv run python -c "from novascan.models.receipt import ReceiptListItem, ReceiptListResponse; r = ReceiptListResponse(receipts=[]); assert hasattr(r, 'nextCursor'); i = ReceiptListItem(receiptId='x', status='processing', imageUrl=None, createdAt='2026-01-01'); assert hasattr(i, 'subcategory'); assert hasattr(i, 'categoryDisplay'); print('PASS')"
```

### Fix Results (Claude Opus 4.6 / Claude Code — 2026-04-01)

**Issue 1 (`cursor` → `nextCursor`) — Fixed**
- What was changed: Renamed `cursor` to `nextCursor` on `ReceiptListResponse`
- Files modified: `backend/src/novascan/models/receipt.py`

**Issue 2 (Missing `subcategory` on `ReceiptListItem`) — Fixed**
- What was changed: Added `subcategory: str | None = None` after `category` field
- Files modified: `backend/src/novascan/models/receipt.py`

**Issue 3 (Missing `categoryDisplay`/`subcategoryDisplay` on `ReceiptListItem`) — Fixed**
- What was changed: Added `categoryDisplay: str | None = None` and `subcategoryDisplay: str | None = None` after `subcategory`
- Files modified: `backend/src/novascan/models/receipt.py`

**Verification:**
- `ruff check src/` — PASS
- `mypy src/` — PASS (12 source files, no issues)
- Model attribute assertions — PASS

### Fix Verification (Claude Opus 4.6 QA — 2026-04-01)

Verified on branch `fix/2.1-receipt-model-fields` (commit `582e838`).

**Issue 1 (`cursor` → `nextCursor`) — Fixed** ✓
Verified: `receipt.py:82` — field is `nextCursor: str | None = None`. Cross-checked against api-contracts.md line 141 (`"nextCursor": "eyJza..."`) and line 148 (`nextCursor — Opaque pagination token`). Match confirmed. Old `cursor` field does not exist (assertion verified programmatically).

**Issue 2 (Missing `subcategory` on `ReceiptListItem`) — Fixed** ✓
Verified: `receipt.py:70` — `subcategory: str | None = None` present after `category`. Cross-checked against api-contracts.md line 134 (`"subcategory": "supermarket-grocery"`). Match confirmed. Consistent with full `Receipt` model which also has `subcategory` at line 51.

**Issue 3 (Missing `categoryDisplay`/`subcategoryDisplay` on `ReceiptListItem`) — Fixed** ✓
Verified: `receipt.py:71-72` — `categoryDisplay: str | None = None` and `subcategoryDisplay: str | None = None` present after `subcategory`. Cross-checked against api-contracts.md lines 133, 135. Match confirmed. Both are `str | None = None` — correct for computed fields populated at response time.

**Field ordering:** `ReceiptListItem` fields now follow the same order as the api-contracts.md JSON response: `receiptId`, `receiptDate`, `merchant`, `total`, `category`, `subcategory`, `categoryDisplay`, `subcategoryDisplay`, `status`, `imageUrl`, `createdAt`. Exact match.

**Verification commands:**
- `cd backend && uv run ruff check src/` — PASS (all checks passed)
- `cd backend && uv run mypy src/` — PASS (12 source files, no issues)
- Model attribute assertions (`hasattr` checks for `nextCursor`, `subcategory`, `categoryDisplay`, `subcategoryDisplay`; absence check for old `cursor`) — ALL PASS
- `cd backend && uv run pytest` — no tests collected (Task 2.7 not yet implemented; no regressions possible)

**Verdict:** 3/3 issues resolved. No regressions. All verification commands pass.

