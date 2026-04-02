# Task 2.5: Upload Flow Integration

## Work Summary
- **Branch:** `task/2.5-upload-flow-integration` (based on `feature/m2-wave3-frontend-integration`)
- **What was implemented:** API client for receipt upload endpoints, upload orchestration hook with retry logic, and ScanPage integration wiring up all upload UI components.
- **Key decisions:**
  - `requestUploadUrls` uses `fetch` with `getValidIdToken()` for auth. Returns typed `UploadUrlReceipt[]`.
  - `uploadFileToS3` uses `XMLHttpRequest` (not fetch) to support upload progress tracking via `xhr.upload.progress` events.
  - `useUpload` hook manages three-phase state machine: idle -> uploading -> complete. Per-file status tracked in `UploadFile[]`.
  - Retry logic: up to 3 retries with exponential backoff (1s, 2s, 4s). On S3 upload failure, the presigned URL is cleared from the cache so the next attempt requests a fresh URL (handles expiration).
  - If the bulk `requestUploadUrls` call fails, individual files fall back to requesting their own URLs during `uploadSingleFile`.
  - Used a `filesRef` (useRef) alongside state to allow `retry` to read current file indices without abusing `setFiles` as a read mechanism.
  - URL map keyed by `${fileName}-${fileSize}` to match files to their presigned URLs.
- **Files created/modified:**
  - `frontend/src/api/receipts.ts` (created — API client functions)
  - `frontend/src/hooks/useUpload.ts` (created — upload orchestration hook)
  - `frontend/src/pages/ScanPage.tsx` (modified — integrated upload flow with UploadArea, UploadProgress, UploadSummary)
- **Test results:** `npm run build` PASS (tsc + vite build, 0 errors)
- **Spec gaps found:** none
- **Obstacles encountered:** none

## Review Discussion
