# Task 2.2: Upload UI Components

## Work Summary
- **What was implemented:** Three presentational upload components (`UploadArea`, `UploadProgress`, `UploadSummary`) and upload-specific TypeScript types (`UploadFile`, `UploadFileStatus`). These components handle file selection, per-file progress display, and upload results summary — all without API integration (deferred to Task 2.5).
- **Key decisions:**
  - Used native HTML5 drag-and-drop events (`onDragOver`, `onDragLeave`, `onDrop`) instead of external libraries like react-dropzone, per project constraints
  - Camera capture input uses `capture="environment"` and is only visible on mobile (`md:hidden`) since it's primarily useful on phones
  - File picker uses `multiple` attribute for desktop multi-select
  - Client-side validation rejects non-JPEG/PNG, files > 10 MB, and files exceeding the max count (default 10) before calling `onFilesSelected`
  - Validation errors displayed in a styled alert list, cleared on next file selection
  - `UploadProgress` uses semantic `role="progressbar"` with proper `aria-valuenow`/`aria-valuemin`/`aria-valuemax` for accessibility
  - File size formatter uses 1,000-based KB/MB thresholds for human readability
  - Filename truncation preserves the file extension when truncating long names
  - `UploadSummary` uses green/yellow contextual styling for all-success vs partial-failure states
  - "View Receipts" button uses `react-router-dom` `Link` via shadcn `Button` `asChild` pattern
  - Types placed in `frontend/src/types/receipt.ts` (separate from the existing `index.ts` which has `Receipt`, `LineItem`, `ReceiptStatus`)
- **Files created:**
  - `frontend/src/types/receipt.ts` — `UploadFileStatus` and `UploadFile` types
  - `frontend/src/components/UploadArea.tsx` — File selection with camera, picker, and drag-and-drop
  - `frontend/src/components/UploadProgress.tsx` — Per-file progress bars with status icons
  - `frontend/src/components/UploadSummary.tsx` — Upload results summary with retry/upload-more/view-receipts actions
- **Test results:** `npm run build` passes with zero TypeScript errors
- **Spec gaps found:** none
- **Obstacles encountered:** none

## Review Discussion
