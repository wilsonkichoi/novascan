# Task 4.5: Category Picker + Pipeline Comparison Toggle

## Work Summary
- **Branch:** `task/4.5-category-picker-pipeline-toggle` (based on `feature/m4-wave3-detail-features`)
- **What was implemented:** Category picker dropdown with predefined/custom categories (including create custom modal and delete), pipeline comparison toggle visible only to staff/admin users showing side-by-side OCR-AI vs AI-multimodal results. Both integrated into the ReceiptDetailPage.
- **Key decisions:**
  - Used a custom dropdown (button + positioned listbox) instead of a Radix Select primitive, because the category picker needs mixed content (group headers, action buttons, delete icons) that goes beyond a standard select
  - Used native `<select>` for the parent category dropdown in the create modal (simple list of predefined categories, no special UX needed)
  - PipelineComparison fetches data lazily only when the toggle is expanded (enabled flag on useQuery)
  - Staff check includes both "staff" and "admin" roles since admins should also have full access
  - Added `useUpdateReceipt` hook to `useReceipt.ts` since it was needed but didn't exist yet
- **Files created/modified:**
  - `frontend/src/api/categories.ts` (created) -- API client for categories CRUD + pipeline results
  - `frontend/src/hooks/useCategories.ts` (created) -- TanStack Query hooks for categories/pipeline results
  - `frontend/src/components/CategoryPicker.tsx` (created) -- dropdown with predefined + custom categories, create/delete
  - `frontend/src/components/PipelineComparison.tsx` (created) -- staff-only side-by-side pipeline results
  - `frontend/src/hooks/useReceipt.ts` (modified) -- added `useUpdateReceipt` mutation hook
  - `frontend/src/pages/ReceiptDetailPage.tsx` (modified) -- integrated CategoryPicker and PipelineComparison
- **Test results:**
  - `npm run build` -- PASS
  - `npm run lint` -- 7 errors, 2 warnings (all pre-existing, none in task files)
  - `npm run test` -- 175 tests PASS (9 test files)
- **Spec gaps found:** none
- **Obstacles encountered:** none

## Review Discussion

{Left empty unless the human adds *FEEDBACK:* comments.
Append-only -- never overwrite previous entries.}
