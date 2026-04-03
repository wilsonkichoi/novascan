# Wave M2-3 Review: Upload Flow Integration + Receipts List Page

Reviewed: 2026-04-02
Reviewer: Claude Opus 4.6 (1M context)
Cross-referenced: SPEC.md §3 (Upload Flow), §5 (Database Schema), api-contracts.md (POST /api/receipts/upload-urls, GET /api/receipts), HANDOFF.md §M2

## Task 2.5: Upload Flow Integration

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Upload flow: request presigned URLs → parallel PUT to S3 → show summary | PASS | `startUpload` bulk-requests URLs, then `Promise.all` for parallel S3 uploads via XHR |
| Failed uploads retry up to 3 times with exponential backoff (1s, 2s, 4s) | PASS | `MAX_RETRIES=3`, delay `1000 * 2^attempt` = 1s, 2s, 4s |
| If presigned URL expires during retry, requests a new URL for the failed file | PASS | `urlMapRef.current.delete(key)` on failure → next attempt fetches fresh URL |
| Upload state transitions: idle → uploading → complete (with per-file status) | PASS | `UploadPhase` type + per-file `UploadFileStatus` (pending/uploading/success/failed) |
| After upload completes, navigates to receipts list or shows confirmation | PASS | `UploadSummary` shows confirmation with "View Receipts" link |
| `cd frontend && npm run build` succeeds | PASS | Build passes with 0 errors |

### Issues Found

**Issue 1 — SUGGESTION: Duplicate receipts API client pattern**

`frontend/src/hooks/useReceipts.ts:1-44` — Task 2.6 inlines its own `fetchReceipts` function with a separate `API_URL` constant and `getValidIdToken()` auth handling, duplicating the pattern established in `frontend/src/api/receipts.ts`. Two modules now independently know how to call the receipts API with authentication.

This was a conscious decision during parallel task execution ("to avoid conflicts with Task 2.5's api/receipts.ts" per task-2.6.md), but now that both tasks are merged into the feature branch, the duplication should be consolidated. M4 adds `getReceipt`, `updateReceipt`, `deleteReceipt`, and `updateItems` — all will go in `api/receipts.ts`. Having `fetchReceipts` live elsewhere creates a maintenance split where some receipt API calls are in `api/receipts.ts` and others are inline in hooks.

**Suggested fix:** Move `fetchReceipts` into `api/receipts.ts` and import it in `useReceipts.ts`. Also export the `ReceiptListItem` and `ReceiptListResponse` types from a shared location (either `api/receipts.ts` or `types/receipt.ts`).

---

**Issue 2 — NIT: URL map key uses filename-size composite**

`frontend/src/hooks/useUpload.ts:44` — The presigned URL cache key is `${file.name}-${file.size}`. If a user selects two different images with identical filenames and byte sizes (e.g., two `receipt.jpg` files of 2,048,576 bytes), they'd share a cache key and one receipt would be lost. Extremely unlikely in practice but technically incorrect.

**Suggested fix:** Include a per-upload index or a unique identifier (e.g., `${file.name}-${file.size}-${index}`) in the cache key.

## Task 2.6: Receipts List Page

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Displays receipt list with: merchant name, date, total, category, status badge | PASS | `ReceiptCard` renders all fields with proper null handling |
| Status badges: Processing (yellow), Confirmed (green), Failed (red) | PASS | `statusConfig` maps correct colors and icons |
| Receipts with status `processing` show placeholder values for merchant/total | PASS | "Processing..." for merchant, "--" for total |
| Pagination via "Load More" button using cursor | PASS | `useInfiniteQuery` + `getNextPageParam` + "Load More" button with `hasNextPage` |
| Receipt card links to receipt detail page (placeholder route for M4) | PASS | `<Link to={/receipts/${receipt.receiptId}}>` |
| TanStack Query manages server state with stale-while-revalidate | PASS | `useInfiniteQuery` provides SWR behavior by default |
| `cd frontend && npm run build` succeeds | PASS | Build passes with 0 errors |

### Issues Found

No additional issues specific to Task 2.6 beyond the cross-task Issue 1 above.

## Cross-Reference: Spec Alignment

| Spec Requirement | Implementation | Verdict |
|-----------------|---------------|---------|
| SPEC §3 Upload Flow: presigned URLs, parallel upload, retry with backoff | `requestUploadUrls` + `Promise.all` + exponential backoff in `uploadSingleFile` | PASS |
| SPEC §3 Upload Flow: presigned URL expiry handling | URL cache cleared on failure, fresh URL requested on retry | PASS |
| api-contracts: POST /api/receipts/upload-urls request/response shape | `UploadUrlRequest`/`UploadUrlReceipt` interfaces match contract exactly | PASS |
| api-contracts: GET /api/receipts response shape | `ReceiptListItem` interface matches contract (nullable fields for processing receipts) | PASS |
| SPEC M2 AC: up to 10 files, JPEG/PNG only, max 10 MB | Client-side validation in `UploadArea.tsx` (wave 2.2), API client passes through | PASS |
| SPEC M2 AC: receipts appear with "Processing" badge after upload | `ReceiptCard` shows yellow Processing badge with clock icon | PASS |
| SPEC M2 AC: upload summary shows per-file success/failure with retry | `UploadSummary` shows count, failed file details, and Retry button | PASS |
| SPEC §5: cursor-based pagination via DynamoDB LastEvaluatedKey | `useInfiniteQuery` with `nextCursor` → `getNextPageParam` | PASS |

## Things Done Well

- **XHR for upload progress** — Using `XMLHttpRequest` instead of `fetch` for S3 uploads to get granular progress tracking via `xhr.upload.progress` events. `fetch` doesn't support upload progress natively — this is the correct approach.
- **Ref + state sync pattern** — The `filesRef`/`updateFiles` pattern in `useUpload.ts` keeps a mutable ref in sync with React state, allowing the async `retry` function to read current file indices without stale closure issues. Clean and correct.
- **Graceful bulk fallback** — When the bulk `requestUploadUrls` call fails, individual `uploadSingleFile` calls fall back to requesting their own URLs. Good resilience without over-engineering.
- **Timezone-safe date formatting** — `ReceiptCard` uses `new Date(dateStr + "T00:00:00")` to parse date strings as local time, avoiding the UTC midnight offset issue that `new Date("2026-03-25")` would cause in US timezones.
- **Proper null handling** — Both `ReceiptCard` and `ReceiptsPage` correctly handle null fields for processing receipts (conditional rendering for date/category, `== null` check for total).
- **Accessibility** — `UploadProgress` uses `role="progressbar"` with proper `aria-valuenow/min/max` attributes. `UploadArea` uses `role="alert"` for validation errors.
- **Clean infinite query setup** — TanStack Query `useInfiniteQuery` with proper `getNextPageParam` mapping from `nextCursor` and `hasNextPage`-gated Load More button.
- **QueryClientProvider in main.tsx** — Correctly placed at the app root, wrapping both Router and App.

## Summary

| # | Severity | Task | Issue | Action |
|---|----------|------|-------|--------|
| 1 | SUGGESTION | 2.5/2.6 | Duplicate receipts API client pattern — `useReceipts.ts` inlines fetch instead of using `api/receipts.ts` | Consolidate `fetchReceipts` into `api/receipts.ts` |
| 2 | NIT | 2.5 | URL map key `${fileName}-${fileSize}` could collide for identically-named-and-sized files | Add index to cache key |

**Overall verdict:** Both tasks are well-implemented with correct spec alignment, good error handling, and proper accessibility. The only actionable item is consolidating the duplicate API client pattern (Issue 1) before M4 adds more receipt endpoints. Issue 2 is a theoretical edge case with negligible real-world impact.

## Review Discussion

### Fix Plan (Claude Opus 4.6 — 2026-04-02)

**Issue 1 (Duplicate receipts API client pattern)**
- Fix: Move `fetchReceipts`, `ReceiptListItem`, and `ReceiptListResponse` from `frontend/src/hooks/useReceipts.ts` into `frontend/src/api/receipts.ts`. Update `useReceipts.ts` to import from `api/receipts.ts`. This aligns with the project convention (SPEC §10: "API calls centralized in `src/api/`. One file per resource").
- Risk: If `ReceiptListItem` is imported from `api/receipts.ts` instead of `hooks/useReceipts.ts`, `ReceiptCard.tsx` needs its import path updated. Missing an import update would break the build — but `tsc` catches this.
- Files: `frontend/src/api/receipts.ts`, `frontend/src/hooks/useReceipts.ts`, `frontend/src/components/ReceiptCard.tsx`

**Issue 2 (URL map key collision)**
- Fix: Change the key in `useUpload.ts` from `${file.name}-${file.size}` to `${file.name}-${file.size}-${index}` where `index` is the position in the selected files array. Pass the index through from `startUpload` and `retry`.
- Risk: Using index as part of the key means the same file would have different keys in different upload sessions. Since `urlMapRef` is cleared on each `startUpload` call, this is fine. However, the `retry` flow needs the same index mapping — which it already has via `filesRef`.
- Files: `frontend/src/hooks/useUpload.ts`

**Execution order:**
1. Issue 1: Move types and fetch function to `api/receipts.ts`, update imports
2. Issue 2: Update cache key in `useUpload.ts`
3. Verify: `cd frontend && npm run build`

**Verification:**
- `cd frontend && npm run build` — must pass with 0 errors
- `grep -r "API_URL" frontend/src/hooks/useReceipts.ts` — should return nothing (removed)
- `grep -r "fetchReceipts" frontend/src/api/receipts.ts` — should show the function

### Fix Results (Claude Opus 4.6 1M — 2026-04-02)

**Branch:** `fix/m2-w3-consolidate-api-and-cache-key` (based on `feature/m2-wave3-frontend-integration`)

**Issue 1 (Duplicate receipts API client pattern) — Fixed**
- What was changed: Moved `fetchReceipts`, `ReceiptListItem`, and `ReceiptListResponse` from `hooks/useReceipts.ts` into `api/receipts.ts`. Stripped duplicate `API_URL` constant and `getValidIdToken` import from the hook. Updated `useReceipts.ts` to import `fetchReceipts` from `@/api/receipts`. Updated `ReceiptCard.tsx` import path from `@/hooks/useReceipts` to `@/api/receipts`.
- Files modified: `frontend/src/api/receipts.ts`, `frontend/src/hooks/useReceipts.ts`, `frontend/src/components/ReceiptCard.tsx`

**Issue 2 (URL map key collision) — Fixed**
- What was changed: Changed cache key from `${file.name}-${file.size}` to `${file.name}-${file.size}-${index}` in both locations: `uploadSingleFile` (line 44) and `startUpload` bulk pre-cache (line 119).
- Files modified: `frontend/src/hooks/useUpload.ts`

**Verification:**
- `cd frontend && npm run build` — PASS (0 errors)
- `grep API_URL frontend/src/hooks/useReceipts.ts` — no matches (removed)
- `grep fetchReceipts frontend/src/api/receipts.ts` — present (line 83)

### Fix Plan Analysis (Claude Opus 4.6 1M — 2026-04-02)

**Issue 1 (Duplicate receipts API client pattern) — Approve**
My approach: Move `fetchReceipts`, `ReceiptListItem`, and `ReceiptListResponse` from `useReceipts.ts` into `api/receipts.ts`. Strip the duplicate `API_URL` constant and `getValidIdToken` import from the hook. Update `useReceipts.ts` to import `fetchReceipts` from `@/api/receipts` and re-export `ReceiptListItem` or have `ReceiptCard.tsx` import it directly from `@/api/receipts`. Update `ReceiptCard.tsx` import path from `@/hooks/useReceipts` to `@/api/receipts`.
Plan's approach: Move `fetchReceipts`, `ReceiptListItem`, and `ReceiptListResponse` into `api/receipts.ts`. Update `useReceipts.ts` to import from `api/receipts.ts`. Update `ReceiptCard.tsx` import path. Notes that `tsc` will catch any missed import updates.
Reasoning: The approaches are identical in substance. Both correctly identify all three files that need changes and the same set of symbols to relocate. The plan correctly flags the import-breakage risk and notes the compiler safety net. SPEC section 10 line 989 ("API calls centralized in `src/api/`. One file per resource") is the authoritative justification and both approaches cite it. No material difference.

**Issue 2 (URL map key collision) — Approve**
My approach: Change the cache key from `${file.name}-${file.size}` to `${file.name}-${file.size}-${index}` in both locations where the key is constructed (line 44 in `uploadSingleFile` and line 119 in `startUpload`). The `index` parameter is already available in both call sites: `uploadSingleFile` receives it as a parameter, and `startUpload` has it from the `for` loop iterator. The `retry` flow preserves original array indices via `filesRef.current` (line 151-153), so index-based keys remain consistent across retry attempts. `urlMapRef` is cleared at the start of each `startUpload` call, so cross-session key reuse is not a concern.
Plan's approach: Same change (`${file.name}-${file.size}-${index}`), same reasoning about `filesRef` preserving indices for retry, same observation that `urlMapRef.current.clear()` in `startUpload` prevents cross-session issues.
Reasoning: Identical approach. One detail I verified that the plan does not explicitly call out: the key is constructed in two separate locations (line 44 and line 119), so both must be updated. The plan says "change the key in `useUpload.ts`" without specifying both sites, but the intent is clear and the build step would catch a mismatch. No material difference.

### Fix Verification (Claude Opus 4.6 1M — 2026-04-02)

**Issue 1 (Duplicate receipts API client pattern) — Fixed** ✓
Verified by reading source and diffs:
- `frontend/src/api/receipts.ts` now contains `ReceiptListItem` (line 64), `ReceiptListResponse` (line 78), and `fetchReceipts` (line 83) — all exported. Uses the existing `API_URL` constant and `getValidIdToken` import already present in the file.
- `frontend/src/hooks/useReceipts.ts` reduced from 47 lines to 11 lines. Removed: duplicate `API_URL` constant, `getValidIdToken` import, `ReceiptListItem`/`ReceiptListResponse` interfaces, and inline `fetchReceipts` function. Now imports `fetchReceipts` from `@/api/receipts`.
- `frontend/src/components/ReceiptCard.tsx:4` — import updated from `@/hooks/useReceipts` to `@/api/receipts`.
- `grep API_URL frontend/src/hooks/useReceipts.ts` — no matches (confirmed removed).
- `grep getValidIdToken frontend/src/hooks/useReceipts.ts` — no matches (confirmed removed).
- No stale imports remain: `ReceiptListItem` is only imported from `@/api/receipts` (by `ReceiptCard.tsx`). `ReceiptsPage.tsx` imports only the `useReceipts` hook from `@/hooks/useReceipts` — correct.

**Issue 2 (URL map key collision) — Fixed** ✓
Verified by reading source and diff:
- `frontend/src/hooks/useUpload.ts:44` — cache key in `uploadSingleFile` changed from `` `${file.name}-${file.size}` `` to `` `${file.name}-${file.size}-${index}` ``. The `index` parameter is available from the function signature (line 42).
- `frontend/src/hooks/useUpload.ts:119` — cache key in `startUpload` bulk pre-cache changed from `` `${file.name}-${file.size}` `` to `` `${file.name}-${file.size}-${i}` ``. The `i` variable is the loop iterator (line 117).
- Both sites now produce consistent keys: `startUpload` pre-caches with index `i`, and `uploadSingleFile` looks up with the same `index` passed from `Promise.all(selectedFiles.map((file, index) => ...))` at line 128.
- The `retry` flow at line 151-153 uses `filesRef.current.map((f, index) => ...)` to recover original indices, so retry cache keys remain consistent.
- No remaining instances of the old `${file.name}-${file.size}` pattern without index suffix.

**Verification commands:**
- `cd frontend && npm run build` — PASS (0 errors, 2399 modules, built in 1.22s)
- `grep API_URL frontend/src/hooks/useReceipts.ts` — PASS (no matches)
- `grep fetchReceipts frontend/src/api/receipts.ts` — PASS (line 83)
- `grep 'from "@/hooks/useReceipts"' frontend/src/` — only `ReceiptsPage.tsx` (correct — imports the hook, not types)
- `grep 'from "@/api/receipts"' frontend/src/components/ReceiptCard.tsx` — PASS (line 4)
- No regressions detected. No other files affected.

**Verdict:** 2/2 issues resolved. All fixes correctly applied, no regressions.
