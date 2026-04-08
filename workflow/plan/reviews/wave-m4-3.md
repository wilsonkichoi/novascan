# Wave 3 Review: Line Item Editing UI + Category Picker + Pipeline Comparison Toggle

Reviewed: 2026-04-08
Reviewer: Claude Opus 4.6 (code-reviewer)
Cross-referenced: SPEC.md Section 2 (M4), Section 3 (RBAC), Section 8 (Custom Categories UX Flow), api-contracts.md, category-taxonomy.md, HANDOFF.md

## Task 4.4: Line Item Editing UI

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Each line item row has inline editable fields: name, quantity, price, subcategory | PASS | All four fields present in editing mode (LineItemEditor.tsx:337-425) |
| Add new line item button appends a row | PASS | "Add Item" button at bottom calls `addItem` (LineItemEditor.tsx:468-479) |
| Remove line item button on each row with confirmation | PASS | Inline confirm/cancel pattern replaces modal per key decision (LineItemEditor.tsx:428-459) |
| Save button calls PUT /api/receipts/{id}/items with full item list | PASS | `handleSave` builds payload and calls `onSave` -> `useUpdateItems` -> `updateItems` API call (LineItemEditor.tsx:197-212, useReceipt.ts:44-94) |
| Cancel button reverts to original data | PASS | `cancelEditing` re-initializes from `lineItems` prop (LineItemEditor.tsx:134-139) |
| Validation: name required, quantity > 0, prices >= 0 | PASS | `validateItems` checks all constraints (LineItemEditor.tsx:59-97) |
| Optimistic update with rollback on failure | PASS | `useUpdateItems` uses `onMutate`/`onError`/`onSettled` pattern (useReceipt.ts:49-93) |
| `cd frontend && npm run build` succeeds | PASS | Verified: build passes clean |

### Issues Found

**[S1] -- SUGGESTION: LineItemEditor does not exit editing mode on successful save**

`frontend/src/components/LineItemEditor.tsx:197-212` -- After `handleSave` fires `onSave(payload)`, the component stays in editing mode. There is no `onSuccess` callback to call `setIsEditing(false)`. The user saves, the optimistic update fires, but the editing table stays open with all inputs visible. This is a UX gap -- after a successful save, the user should see the read-only view reflecting their changes.

The parent ReceiptDetailPage.tsx does not pass a success callback either (line 91-96 only handles `onError`). The component has no mechanism to detect that the mutation succeeded and exit editing mode.

Fix: Either (a) accept an `onSaveSuccess` callback prop in LineItemEditor and call it from the parent's mutation `onSuccess`, then call `setIsEditing(false)`, or (b) have the parent pass `isSuccess` from the mutation and use a `useEffect` to exit editing mode when it transitions to success.

**[S2] -- SUGGESTION: Category picker does not close on outside click via keyboard (Escape key)**

`frontend/src/components/CategoryPicker.tsx:96-188` -- The dropdown closes on backdrop click (invisible full-screen div, line 119-123) but does not handle the Escape key. This is a common accessibility expectation for custom dropdowns (WCAG 2.1 pattern for listbox). Users navigating by keyboard have no way to dismiss the dropdown without clicking.

Fix: Add `onKeyDown` handler to the dropdown container or use a `useEffect` with a `keydown` event listener that calls `setIsOpen(false)` when Escape is pressed.

**[N1] -- NIT: Duplicate `formatCurrency` function**

`frontend/src/components/LineItemEditor.tsx:484-489` and `frontend/src/pages/ReceiptDetailPage.tsx:50-55` -- Identical `formatCurrency` helper is defined in both files. Not a bug, but if a third file needs it, consider extracting to `src/lib/utils.ts` or a `format.ts` utility.

## Task 4.5: Category Picker + Pipeline Comparison Toggle

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Category picker dropdown: lists predefined categories, then custom categories | PASS | Predefined group header + custom group header with correct ordering (CategoryPicker.tsx:131-169) |
| "Create Custom Category" option at bottom of dropdown opens modal: display name + optional parent category | PASS | "Create Custom Category" button at list bottom (line 173-184), opens dialog with displayName + parent select (line 191-264) |
| Custom categories show delete icon; delete calls API and removes from list | PASS | Delete button with Trash2 icon on custom options (CategoryOption component, line 304-311), calls `deleteCategory` API |
| Selecting a category/subcategory calls PUT /api/receipts/{id} to save | PASS | `onSelect` callback triggers `updateReceipt.mutate({ category: slug })` in ReceiptDetailPage.tsx:251-253 |
| Pipeline comparison toggle: only visible to staff-role users | PASS | `{isStaff && <PipelineComparison />}` guard (ReceiptDetailPage.tsx:318-320), isStaff checks both "staff" and "admin" roles (line 100) |
| Toggle shows both OCR-AI and AI-multimodal results side-by-side with confidence scores and ranking winner | PASS | Side-by-side grid with confidence, rankingScore, processingTime, modelId, and extracted data summary (PipelineComparison.tsx:87-107) |
| Non-staff users see no pipeline toggle | PASS | Conditional render on `isStaff` (ReceiptDetailPage.tsx:318) |
| `cd frontend && npm run build` succeeds | PASS | Verified: build passes clean |

### Issues Found

**[S3] -- SUGGESTION: No delete confirmation for custom categories**

`frontend/src/components/CategoryPicker.tsx:49-55` -- `handleDelete` immediately calls `deleteCategoryMutation.mutate(slug)` with no confirmation. SPEC Section 8 says "Deleting a custom category does not update receipts already assigned to it" -- this is a destructive action that could orphan category assignments on multiple receipts. A confirmation step (even an inline one like the line item remove pattern) would prevent accidental deletions.

Fix: Add an inline confirmation or a small dialog before executing the delete mutation.

**[S4] -- SUGGESTION: Category picker does not show subcategory selection**

`frontend/src/components/CategoryPicker.tsx` -- The spec (api-contracts.md PUT /api/receipts/{id}) says both `category` and `subcategory` can be updated. The acceptance criteria for Task 4.5 states "Selecting a category/subcategory calls PUT /api/receipts/{id} to save." The current picker only selects the top-level category -- there is no way to drill into or select a subcategory from the dropdown. The category API response includes `subcategories[]` on each category item, but this data is unused in the picker.

The ReceiptDetailPage.tsx (line 257-260) shows the current subcategory as read-only text but provides no way to change it. This is a partial implementation of the acceptance criteria.

This is marked SUGGESTION rather than BLOCKER because the spec says category/subcategory selection from "predefined taxonomy or custom categories" and the backend `PUT /api/receipts/{id}` does accept a standalone subcategory update. The category is the primary user-facing classification; subcategory is secondary. But it is technically incomplete against the acceptance criteria.

Fix: Either (a) add a secondary dropdown/nested selection for subcategory within the category picker, or (b) add a separate subcategory picker below the category picker on the detail page.

**[N2] -- NIT: `usePipelineResults` lives in `useCategories.ts`**

`frontend/src/hooks/useCategories.ts:41-47` -- The pipeline results query hook is defined in `useCategories.ts` even though pipeline results are conceptually separate from categories. This happened because `api/categories.ts` contains both category and pipeline result types/functions. Not a bug -- the file is small -- but it could confuse future contributors. The pipeline API function (`fetchPipelineResults`) also lives in `api/categories.ts` (line 135-157) which is semantically misleading.

## Cross-Reference: Spec Alignment

| Spec Requirement | Implementation | Verdict |
|-----------------|---------------|---------|
| M4: Line item editing: inline edit name, quantity, price, subcategory; add/remove items | LineItemEditor with read/edit toggle, all four fields, add/remove with confirmation | PASS |
| M4: Category picker: select from predefined taxonomy or custom categories | CategoryPicker with predefined + custom groups, create/delete custom | PASS (top-level only; no subcategory picker -- see [S4]) |
| M4: Custom category UX: create from receipt detail picker, modal, display name + parent | Dialog with displayName + parent select, auto-slug via API | PASS |
| M4: Custom category delete: from picker, calls API | Delete icon on custom categories, calls DELETE /api/categories/{slug} | PASS |
| M4: Pipeline comparison toggle: staff-only, side-by-side | `isStaff` guard, side-by-side grid with scores, winner badge | PASS |
| M4: Non-staff users do not see pipeline toggle | Conditional render on `isStaff` | PASS |
| M4: Pipeline toggle shows both OCR-AI and AI-multimodal results with confidence scores and ranking winner | PipelineCard shows confidence, rankingScore, processingTime, modelId, extractedData summary, winner badge | PASS |
| SPEC Section 8: Custom categories UX -- "Create Custom Category" in picker -> modal | Matches exactly | PASS |
| api-contracts.md: PUT /api/receipts/{id}/items payload shape | LineItemEditor builds correct payload: sortOrder, name, quantity, unitPrice, totalPrice, subcategory | PASS |
| api-contracts.md: PUT /api/receipts/{id} for category change | CategoryPicker calls updateReceipt with `{ category: slug }` | PASS |
| api-contracts.md: GET /api/receipts/{id}/pipeline-results shape | PipelineResultsResponse type matches contract (receiptId, usedFallback, rankingWinner, results with both pipeline types) | PASS |
| SPEC Section 3 (RBAC): staff = staff + admin | `isStaff` checks both `"staff"` and `"admin"` roles | PASS |
| api-contracts.md: POST /api/categories displayName max 100 chars | Client-side validation: maxLength=100 attribute + explicit check (CategoryPicker.tsx:73-75) | PASS |
| api-contracts.md: POST /api/categories 409 CONFLICT handling | Error message from API body displayed to user (CategoryPicker.tsx:87-89) | PASS |
| api-contracts.md: DELETE /api/categories/{slug} 403 for predefined | Backend enforces this; frontend only shows delete on `isCustom` categories | PASS |

## Things Done Well

1. **Optimistic updates with rollback** (useReceipt.ts:44-93) -- The `useUpdateItems` hook correctly snapshots, optimistically updates, rolls back on error, and always revalidates. This is textbook TanStack Query usage and will provide a responsive UX.

2. **String-based numeric editing** (LineItemEditor.tsx:16-24, task-4.4.md key decisions) -- Storing numeric fields as strings in editor state avoids the common React gotcha where `<input type="number">` fights with controlled components on decimal entry. Smart decision.

3. **Inline remove confirmation** instead of modal dialogs for row deletion (LineItemEditor.tsx:428-459) -- Lower friction than a dialog for a table row operation. Good UX judgment.

4. **Lazy-loading pipeline results** (useCategories.ts:41-46, PipelineComparison.tsx:31) -- The `enabled` flag on `useQuery` means pipeline results are only fetched when the staff user expands the toggle. No wasted API calls for non-staff users or when the toggle is collapsed.

5. **Proper ARIA attributes** -- Both components use `role="listbox"`, `role="option"`, `aria-expanded`, `aria-haspopup`, `aria-label`, `aria-invalid`, and `sr-only` labels consistently. Good accessibility hygiene.

6. **Encapsulation of the CategoryPicker create flow** -- The entire create custom category workflow (open modal -> validate -> POST -> select new category -> close modal) is self-contained within CategoryPicker.tsx. Clean component boundary.

7. **URL encoding in API calls** -- Both `api/categories.ts` and `api/receipts.ts` use `encodeURIComponent` on URL path parameters. Correct.

## Summary

| ID | Severity | Task | Issue | Action |
|----|----------|------|-------|--------|
| S1 | SUGGESTION | 4.4 | Editor stays in editing mode after successful save | Add save success callback to exit editing mode |
| S2 | SUGGESTION | 4.5 | Category picker dropdown has no Escape key handling | Add Escape keydown handler |
| S3 | SUGGESTION | 4.5 | No delete confirmation for custom categories | Add inline or dialog confirmation before delete |
| S4 | SUGGESTION | 4.5 | No subcategory picker (category-only selection) | Add subcategory selection or separate picker |
| N1 | NIT | 4.4 | Duplicate formatCurrency function | Extract to shared utility |
| N2 | NIT | 4.5 | Pipeline results hook in useCategories.ts | Move to own file or rename file |

**Overall verdict:** Solid implementation with no blockers. Four suggestions -- two are UX polish (S1 save-exit, S3 delete confirmation), one is accessibility (S2 Escape key), and one is a partial acceptance criteria gap (S4 subcategory selection). All existing tests pass, TypeScript compiles cleanly, build succeeds. The code is well-structured, follows project conventions, and the optimistic update/rollback pattern in useUpdateItems is exemplary.

## Security Review

Reviewed: 2026-04-08
Reviewer: Claude Opus 4.6 (1M context) (security-reviewer)
Methodology: STRIDE threat model, OWASP Top 10, CWE Top 25

### Threat Model Summary

| Component | Threats Assessed | Findings |
|-----------|-----------------|----------|
| LineItemEditor (Task 4.4) | Spoofing, Tampering, Information Disclosure, Elevation of Privilege | No issues -- input validation present, auth delegated to backend |
| CategoryPicker (Task 4.5) | Spoofing, Tampering, Repudiation, Elevation of Privilege | No issues -- all mutations go through authenticated API calls |
| PipelineComparison (Task 4.5) | Elevation of Privilege, Information Disclosure | 1 finding (S5) -- client-side role check only |
| API client layer (categories.ts, receipts.ts) | Spoofing, Tampering, Information Disclosure | No issues -- token attached to all requests, URL params encoded |
| TanStack Query hooks (useReceipt.ts, useCategories.ts) | Tampering, Information Disclosure | No issues -- optimistic updates with proper rollback |
| Data flows (line items, categories, pipeline results) | Information Disclosure, Tampering | No issues -- all sensitive data behind authenticated endpoints |

### STRIDE Analysis

**Spoofing:** All API calls in `categories.ts` and `receipts.ts` obtain a valid ID token via `getValidIdToken()` before each request. If the token is unavailable, the functions throw `"Not authenticated"` before any network call is made. The `Authorization: Bearer {token}` header is present on every fetch. No unauthenticated requests are possible from this wave's code. PASS.

**Tampering:** Line item payloads are validated client-side (LineItemEditor.tsx:59-97) before submission. The backend enforces its own Pydantic validation on `PUT /api/receipts/{id}/items`. Category creation validates `displayName` length client-side (max 100, CategoryPicker.tsx:72-74) and the backend enforces slug uniqueness and parent category validity. The optimistic update pattern in `useUpdateItems` (useReceipt.ts:44-94) correctly rolls back on server rejection, preventing stale/tampered data from persisting in the UI. PASS.

**Repudiation:** Not applicable for this wave. All mutations are server-side operations tracked via API Gateway access logs and DynamoDB writes. No client-side-only state changes persist without server confirmation.

**Information Disclosure:** The pipeline comparison component (`PipelineComparison.tsx`) displays internal pipeline telemetry (confidence scores, ranking scores, processing times, model IDs, extracted data). This data is appropriately gated behind the `isStaff` check and the backend's `GET /api/receipts/{id}/pipeline-results` endpoint returns 403 for non-staff users. Error messages from API calls are generic user-facing messages (e.g., "Failed to load pipeline results") -- no internal state is leaked. Error responses from the backend are parsed but only `error.message` is surfaced; raw response bodies are not exposed to the user. PASS.

**Denial of Service:** No unbounded loops or recursive operations in the new code. The `LineItemEditor` allows adding items but is bounded by the backend's 0-100 item limit. Category picker fetches are cached by TanStack Query and not repeated excessively. PASS.

**Elevation of Privilege:** See finding S5 below regarding the client-side staff role check.

### Issues Found

**[S5] -- SUGGESTION: Staff role check for pipeline toggle is client-side only (defense-in-depth gap)**

`frontend/src/pages/ReceiptDetailPage.tsx:100` -- The `isStaff` check (`user?.roles.includes("staff") || user?.roles.includes("admin")`) controls whether the `<PipelineComparison>` component is rendered. This is a client-side visibility toggle based on the `cognito:groups` claim decoded from the ID token in `lib/auth.ts:84-97`.

**STRIDE category:** Elevation of Privilege
**OWASP:** A01:2021 -- Broken Access Control
**CWE:** CWE-602 (Client-Side Enforcement of Server-Side Security)

The backend already enforces this: `GET /api/receipts/{id}/pipeline-results` returns 403 for non-staff users (per SPEC and Task 4.2 implementation). So even if a user manipulated the client-side `roles` array (e.g., by modifying the in-memory `user` object via browser devtools), the API call would fail with 403. The pipeline data would not be disclosed.

This is NOT exploitable because the server-side check is authoritative. However, the defense-in-depth principle says that client-side gating should be documented as a UX convenience, not a security boundary. The current code has no such comment. If a future developer removes the backend 403 check believing the frontend handles it, the gate disappears.

Fix: Add a comment on line 100 clarifying the server-side enforcement:
```typescript
// UX convenience only — backend enforces staff-only access on GET /api/receipts/{id}/pipeline-results (403 for non-staff)
const isStaff = user?.roles.includes("staff") || user?.roles.includes("admin");
```
No code change required beyond the comment. The backend is the authoritative enforcement point.

**[S6] -- SUGGESTION: Category displayName in create modal is not sanitized for XSS before rendering**

`frontend/src/components/CategoryPicker.tsx:303` -- After a custom category is created, its `displayName` is rendered in the picker list via `<span>{category.displayName}</span>`. React's JSX escapes HTML by default, so this is NOT vulnerable to reflected or stored XSS through React's rendering pipeline. However, the `displayName` is sent to the backend via `POST /api/categories` and stored in DynamoDB. If any other rendering context (e.g., a future email notification, PDF export, or non-React admin view) renders this value without escaping, it could be exploited.

**STRIDE category:** Tampering
**OWASP:** A03:2021 -- Injection
**CWE:** CWE-79 (Cross-site Scripting)

The current implementation is safe because: (1) React escapes JSX interpolation, (2) the backend M3.1 hardening (Task 3.8) validates category names against an allowlist pattern (`alphanumeric, spaces, & / , . ( ) -`, max 64 chars) that excludes `<`, `>`, `"`, and `'`. So even stored XSS is mitigated by the backend validation.

Fix: No code change needed for the current wave. The backend sanitization from M3.1 is the appropriate defense layer. This is noted for awareness only -- if the backend validation is ever relaxed, the frontend should add its own sanitization. Low priority.

### Data Classification Assessment

| Data | Classification | Protection | Verdict |
|------|---------------|------------|---------|
| Line item fields (name, quantity, prices) | Internal -- user financial data | Auth-gated API, optimistic update with rollback | Adequate |
| Category names (predefined + custom) | Internal | Auth-gated API, backend validation | Adequate |
| Pipeline results (confidence, rankings, model IDs) | Confidential -- internal telemetry | Staff-only backend 403 + client-side gate | Adequate |
| Receipt images (presigned URLs) | Confidential -- PII content | Presigned URLs with expiry, no caching | Adequate |
| JWT tokens | Restricted | ID/access in memory, refresh in localStorage | Adequate (pre-existing M1 pattern, not modified in this wave) |

### OWASP Top 10 Checklist

| OWASP ID | Category | Status | Notes |
|----------|----------|--------|-------|
| A01 | Broken Access Control | PASS | Backend enforces user-scoped DynamoDB queries (PK=USER#{userId}). Staff-only endpoint returns 403. Client-side `isStaff` is UX convenience (see S5). |
| A02 | Cryptographic Failures | N/A | No new cryptographic operations in this wave. Tokens handled by pre-existing auth module. |
| A03 | Injection | PASS | React JSX escapes output. Backend validates category names (M3.1). URL params use `encodeURIComponent`. |
| A04 | Insecure Design | PASS | Optimistic updates have proper rollback. Delete confirmation on receipts (not yet on categories -- see S3 from code review). |
| A05 | Security Misconfiguration | N/A | No infrastructure changes in this wave. |
| A06 | Vulnerable Components | N/A | No new dependencies added. |
| A07 | Auth Failures | PASS | All API calls use `getValidIdToken()` with proactive refresh. Token expiry handled. |
| A08 | Data Integrity Failures | PASS | API responses typed via TypeScript interfaces. Optimistic updates always reconciled with `onSettled` invalidation. |
| A09 | Logging/Monitoring | N/A | Frontend-only wave. Backend logging unchanged. |
| A10 | SSRF | N/A | No server-side requests initiated from frontend code. |

### Security Assessment

**Overall security posture:** Strong for a frontend-only wave. All data flows are properly authenticated via JWT tokens obtained before each API call. The authorization model correctly delegates to the backend -- no security-critical decisions are made exclusively on the client side. The pipeline comparison staff gate is defense-in-depth (backend is authoritative). Input validation exists at both client and server layers. The M3.1 security hardening on the backend provides a solid foundation that this wave's frontend code correctly relies on. Two suggestions identified (S5 documentation comment, S6 awareness note), neither representing exploitable vulnerabilities.

## Review Discussion

### Fix Plan (Claude Opus 4.6 -- 2026-04-08)

Note: Generated in the same context as the review (subagent spawning not available). Run `/agentic-dev:review fix-plan-analysis wave 3` in a separate session for a truly independent second opinion.

**Scope: 4 issues (0 BLOCKERs, 4 SUGGESTIONs)**

NITs (N1, N2) are excluded from this fix plan -- they are low priority and can be addressed opportunistically.

**[S1] (Editor stays in editing mode after successful save)**
- Independent assessment: Reading LineItemEditor.tsx:197-212, `handleSave` calls `onSave(payload)` which is a fire-and-forget call. The component has `isEditing` state but no path back to `false` after a successful mutation. The parent (ReceiptDetailPage.tsx:79-98) wraps the mutation in `handleSaveItems` which only handles `onError`. The mutation's `onSuccess` is never wired to `setIsEditing(false)` -- this is clearly a missing piece.
- Review comparison: Agree with the review's characterization. The issue is straightforward -- there is no success signal flowing back to the editor component.
- Fix: Add an `onSaveSuccess` callback prop to LineItemEditor. In ReceiptDetailPage, pass a function that the mutation's `onSuccess` path invokes. Inside LineItemEditor, when `onSaveSuccess` is called, `setIsEditing(false)`. Concretely: (a) add `onSaveSuccess?: () => void` to LineItemEditorProps, (b) in handleSaveItems in ReceiptDetailPage, add `onSuccess` to the mutation options, (c) have LineItemEditor accept and invoke the callback.
- Risk: If the optimistic update fires but the server round-trip fails, `onSettled` will re-fetch. But the editor will already be closed (from `onMutate` timing). The user might see a flash of the read-only view then get the error. The `onError` already rolls back the optimistic data, but `setIsEditing(false)` will have already fired. Mitigation: only exit editing on the mutation's `onSuccess`, not on `onMutate`.
- Files: `frontend/src/components/LineItemEditor.tsx`, `frontend/src/pages/ReceiptDetailPage.tsx`

**[S2] (Category picker dropdown has no Escape key handling)**
- Independent assessment: Reading CategoryPicker.tsx:94-188, the dropdown opens/closes via `setIsOpen`. Closing paths: (1) backdrop click (line 119-123), (2) selecting an option (line 44-47). No keyboard dismissal path exists. The `<ul role="listbox">` at line 124 does not have an `onKeyDown` handler. The trigger button at line 97-114 also has no Escape handler.
- Review comparison: Agree fully.
- Fix: Add a `useEffect` that listens for `keydown` on `document` when `isOpen` is true. On Escape, call `setIsOpen(false)` and return focus to the trigger button. This is the standard pattern for custom dropdowns. Alternatively, add `onKeyDown` to the `<ul>` element, but the document listener is more reliable since focus may not be on the list.
- Risk: If the CategoryPicker is inside a Dialog (e.g., the create modal is open), the Escape key could close both the dialog and the dropdown. Mitigation: the create modal closes the dropdown first (`setIsOpen(false)` on line 58) so this should not overlap. But check that `e.stopPropagation()` is used if needed.
- Files: `frontend/src/components/CategoryPicker.tsx`

**[S3] (No delete confirmation for custom categories)**
- Independent assessment: Reading CategoryPicker.tsx:49-55, `handleDelete` calls `deleteCategoryMutation.mutate(slug)` immediately. The delete icon is a small 3.5px trash icon (line 309) right next to the category text. Accidental clicks are plausible, especially on mobile. Unlike the line item removal (which has an inline confirm/cancel pattern), the category delete has no guard.
- Review comparison: Agree. The line item editor already established an inline confirm pattern in this same wave -- reusing it here would be consistent.
- Fix: Add a `pendingDeleteSlug` state to CategoryPicker. When the delete button is clicked, set `pendingDeleteSlug = slug` instead of calling the mutation. Render confirm/cancel buttons in place of the delete icon (same pattern as LineItemEditor). On confirm, call `deleteCategoryMutation.mutate(pendingDeleteSlug)`. On cancel, clear `pendingDeleteSlug`.
- Risk: The dropdown's max-height is 72 (max-h-72). The confirm/cancel buttons add width to each row. If the category name is long, the row might overflow horizontally. Mitigation: use small icon-only confirm/cancel buttons (same size as the delete icon).
- Files: `frontend/src/components/CategoryPicker.tsx`

**[S4] (No subcategory picker)**
- Independent assessment: Reading CategoryPicker.tsx and ReceiptDetailPage.tsx:257-260, the subcategory is displayed as read-only text (`receipt.subcategoryDisplay`). The `CategoryItem` type includes `subcategories: SubcategoryItem[]` from the API response, but this data is never rendered in the picker. The acceptance criteria say "Selecting a category/subcategory calls PUT /api/receipts/{id} to save." The backend supports `PUT /api/receipts/{id}` with a `subcategory` field. This is genuinely incomplete.
- Review comparison: Agree. The review correctly categorized this as SUGGESTION rather than BLOCKER because the primary user-facing classification is category, and subcategory is secondary. The subcategory is still populated by the OCR pipeline -- it just cannot be manually changed.
- Fix: Add a separate SubcategoryPicker component (or extend CategoryPicker with a second-level selection). The simplest approach: add a `<select>` element below the CategoryPicker in ReceiptDetailPage that shows subcategories for the currently selected category. When a subcategory is selected, call `updateReceipt.mutate({ subcategory: slug })`. This avoids complicating the CategoryPicker's already-complex dropdown with nested navigation.
- Risk: When the user changes the category, the subcategory list changes. The current subcategory may no longer be valid for the new category. The PUT endpoint should handle this gracefully (the backend validates subcategory against the category). Mitigation: when category changes, clear the subcategory selection or auto-select the first subcategory of the new category.
- Files: `frontend/src/pages/ReceiptDetailPage.tsx` (add subcategory select inline), or create `frontend/src/components/SubcategoryPicker.tsx`

**Execution order:**
1. S1 (save-exit) -- self-contained change to LineItemEditor + ReceiptDetailPage
2. S2 (Escape key) -- self-contained change to CategoryPicker
3. S3 (delete confirmation) -- self-contained change to CategoryPicker (can be done in parallel with S2)
4. S4 (subcategory picker) -- depends on understanding CategoryPicker's data flow, should be done last

**Verification:**
- `cd frontend && npx tsc --noEmit` -- TypeScript check
- `cd frontend && npm run build` -- production build
- `cd frontend && npm run test -- --run` -- all 175 tests should still pass
- Manual verification: open receipt detail, edit line items -> save -> verify editor exits to read-only view
- Manual verification: open category picker -> press Escape -> verify dropdown closes
- Manual verification: click delete on custom category -> verify confirmation appears before deletion

### Fix Plan Analysis (Claude Opus 4.6 (1M context) -- 2026-04-08)

Note: Fix plan covers S1-S4. Security review (S5, S6) was appended after the fix plan was generated. This analysis covers all six SUGGESTIONs.

**[S1] (Editor stays in editing mode after successful save) -- Approve**

My approach: Reading `LineItemEditor.tsx`, I confirmed that `handleSave` (line 197-212) calls `onSave(payload)` with no success/failure feedback channel. The component owns `isEditing` state (line 121) but the only paths to `setIsEditing(false)` are `cancelEditing` (line 134-139) and the initial mount (starts `false`). The parent's `handleSaveItems` (ReceiptDetailPage.tsx:79-98) calls `updateItems.mutate(items, { onError })` -- no `onSuccess` callback. My fix: add an `onSaveSuccess` callback prop, have the parent wire it to the mutation's `onSuccess`, and call `setIsEditing(false)` inside it. The key detail is that `onSuccess` fires only after the server confirms, so the editor stays open during the optimistic period and only closes on actual success.

Plan's approach: Identical to mine -- `onSaveSuccess` callback prop, wired through `onSuccess` on the mutation. The risk assessment about `onMutate` timing is correct: exit must happen on `onSuccess`, not `onMutate`. If it were wired to `onMutate`, a failed server call would leave the user staring at read-only view with stale data after rollback. The plan explicitly calls this out. Aligns with my analysis.

**[S2] (Category picker dropdown has no Escape key handling) -- Approve with minor clarification**

My approach: Confirmed two closing paths exist: backdrop click (line 119-123) and option selection (line 44-47). No keyboard path. I would add a `useEffect` with a `document` `keydown` listener gated on `isOpen`, calling `setIsOpen(false)` on Escape. I would also add a `ref` to the trigger button and call `triggerRef.current?.focus()` after closing so focus returns to the trigger (WCAG 2.1 listbox pattern).

Plan's approach: Same -- `useEffect` with `document` `keydown` listener when `isOpen` is true. The plan mentions returning focus to the trigger button. The risk about Dialog/Escape overlap is valid but academic since `handleOpenCreate` (line 57-63) explicitly calls `setIsOpen(false)` before opening the modal. The Escape event on the document listener fires before the Dialog's own Escape handler, but since `isOpen` is already `false` when the create modal opens, the listener's cleanup will have already removed it. No conflict.

One clarification the plan omits: the `useEffect` cleanup function must remove the listener when `isOpen` goes `false` or on unmount. Standard pattern but worth stating explicitly in the fix for the implementer.

**[S3] (No delete confirmation for custom categories) -- Approve**

My approach: Reading `handleDelete` (line 49-55), the mutation fires immediately on click. The `CategoryOption` delete button (line 304-311) is small (`size-3.5`) with no guard. My fix: add `pendingDeleteSlug` state. On click, set the slug instead of mutating. Show confirm/cancel icons in place of the trash icon. On confirm, mutate. On cancel, clear state. This mirrors the `pendingRemoveKey` pattern in `LineItemEditor.tsx` (line 126, 174-195).

Plan's approach: Identical -- `pendingDeleteSlug` state, inline confirm/cancel replacing the delete icon, same pattern as LineItemEditor. The risk about horizontal overflow in a max-h-72 dropdown is a good observation. Icon-only buttons (no text labels) will fit. Aligns with my analysis.

**[S4] (No subcategory picker) -- Revise**

My approach: Reading `ReceiptDetailPage.tsx:246-261`, the category picker sits in a `<dd>` block. Below it, the subcategory is displayed read-only (line 257-261) when `receipt.subcategoryDisplay` exists. The `CategoryItem` type (categories.ts:16-22) includes `subcategories: SubcategoryItem[]` but this data is never surfaced in the picker. The backend `PUT /api/receipts/{id}` accepts `subcategory` as a separate field. My fix: add a simple `<select>` element below the CategoryPicker that shows subcategories for the currently selected category. Source the subcategory list from the `useCategories()` data by finding the selected category's `subcategories[]` array. On change, call `updateReceipt.mutate({ subcategory: selectedSlug })`. When the category changes, clear the subcategory if it does not exist in the new category's subcategory list. This is the simplest approach -- no new component file needed, just 15-20 lines in ReceiptDetailPage.

Plan's approach is substantially similar but proposes either a separate `SubcategoryPicker` component or an inline `<select>`. The plan mentions a separate component file as an option, which adds unnecessary file creation for what is essentially a native `<select>` element with 5-10 options.

**Alternative:** Keep it inline in ReceiptDetailPage. A separate component is premature abstraction for a single `<select>` that exists in one place. The plan's risk assessment about category changes invalidating the current subcategory is correct. However, the plan's mitigation ("auto-select the first subcategory of the new category") is wrong -- the correct behavior is to clear the subcategory to `null` when the category changes, not silently pick one. The user should explicitly choose. The backend should accept `null` subcategory, and the category change mutation should send `{ category: newSlug, subcategory: null }`.

**[S5] (Staff role check is client-side only -- defense-in-depth gap) -- Approve (no code change needed)**

My approach: Reading `ReceiptDetailPage.tsx:100`, `isStaff` is a client-side check on `user?.roles`. The `PipelineComparison` component (line 318-320) renders conditionally. The `fetchPipelineResults` API call (categories.ts:135-157) includes the auth token, and the backend returns 403 for non-staff. So the server is the authoritative enforcement point. The client check is UX convenience only. My fix: add a one-line comment above line 100 documenting this.

Plan's approach: N/A -- the fix plan was generated before the security review. The security review itself proposes exactly this: a comment on line 100. No code change beyond the comment. I agree -- no functional change needed, just documentation.

**[S6] (Category displayName not sanitized for XSS before rendering) -- Approve (no code change needed)**

My approach: Reading `CategoryPicker.tsx:303`, `<span>{category.displayName}</span>` uses JSX interpolation which React escapes by default. The backend (M3.1 Task 3.8) validates category names against `alphanumeric, spaces, & / , . ( ) -`, max 64 chars, which excludes all HTML special characters. Double protection: React escaping + backend validation. No XSS vector exists.

Plan's approach: N/A -- generated before security review. The security review says no code change needed for the current wave. I agree entirely. This is an awareness note, not an actionable fix.

**Overall assessment:**

The fix plan is well-structured and its proposed fixes for S1-S3 are correct. For S4, I recommend the inline `<select>` approach (no separate component) and correcting the subcategory-clearing behavior on category change. S5 and S6 require no functional changes, just a single documentation comment for S5.

**Revised execution order (incorporating S5):**
1. S1 (save-exit) -- LineItemEditor + ReceiptDetailPage
2. S2 (Escape key) -- CategoryPicker
3. S3 (delete confirmation) -- CategoryPicker (parallel with S2)
4. S5 (staff check comment) -- ReceiptDetailPage line 100 (trivial, do alongside S1)
5. S4 (subcategory picker) -- ReceiptDetailPage (last, depends on category data flow)
6. S6 -- no action

**Verification:** Same as fix plan, plus:
- Verify the subcategory `<select>` shows correct options for the selected category
- Verify changing category clears the subcategory
- Verify the staff comment is present on the `isStaff` line

### Fix Results (Claude Opus 4.6 (1M context) -- 2026-04-08)

**Branch:** `fix/wave3-review-fixes` (based on `feature/m4-wave3-detail-features`)
**Status: 5/5 fixed, 1 deferred (S6 -- no action needed)**

**[S1] (Editor stays in editing mode after successful save) -- Fixed**
- What was changed: Added `useEffect` in LineItemEditor that detects when `isSaving` transitions from `true` to `false` with no `saveError`, indicating successful save. On this transition, `setIsEditing(false)` exits editing mode. Also added optional `onSaveSuccess` callback prop for parent notification. Uses `useRef` for previous `isSaving` tracking to avoid stale closure issues.
- Files modified: `frontend/src/components/LineItemEditor.tsx`

**[S2] (Category picker dropdown has no Escape key handling) -- Fixed**
- What was changed: Added `useEffect` with document `keydown` listener gated on `isOpen`. When Escape is pressed, closes dropdown via `setIsOpen(false)` and returns focus to trigger button via `triggerRef`. Cleanup removes listener when `isOpen` goes false or on unmount. Added `e.stopPropagation()` to prevent Escape from bubbling to parent Dialogs.
- Files modified: `frontend/src/components/CategoryPicker.tsx`

**[S3] (No delete confirmation for custom categories) -- Fixed**
- What was changed: Added `pendingDeleteSlug` state. Delete button click now sets `pendingDeleteSlug` instead of immediately calling mutation. When pending, inline confirm (Check icon) and cancel (X icon) buttons replace the trash icon, matching the LineItemEditor's inline confirm pattern. Confirm executes the delete mutation; cancel clears pending state. All click handlers use `e.stopPropagation()` to prevent row selection.
- Files modified: `frontend/src/components/CategoryPicker.tsx`

**[S4] (No subcategory picker) -- Fixed**
- What was changed: Added `useCategories()` hook call in ReceiptDetailPage to access subcategory data. When the selected category has subcategories, renders a native `<select>` element below the CategoryPicker. Selecting a subcategory calls `updateReceipt.mutate({ subcategory })`. When the category changes, subcategory is cleared by sending `{ category: newSlug, subcategory: "" }`. Falls back to read-only display when subcategories are not available but `subcategoryDisplay` exists.
- Files modified: `frontend/src/pages/ReceiptDetailPage.tsx`

**[S5] (Staff role check is client-side only -- defense-in-depth gap) -- Fixed**
- What was changed: Added documentation comment above the `isStaff` const: "UX convenience only -- backend enforces staff-only access on GET /api/receipts/{id}/pipeline-results (403 for non-staff)". No functional code change.
- Files modified: `frontend/src/pages/ReceiptDetailPage.tsx`

**[S6] (Category displayName not sanitized for XSS before rendering) -- Deferred**
- Reason: No code change needed. React JSX escapes interpolation by default, and backend (M3.1 Task 3.8) validates category names against allowlist pattern excluding HTML special characters. Double protection already in place.

**Verification:**
- `npx tsc --noEmit` -- PASS (no errors)
- `npm run build` -- PASS (clean build)
- `npm run test -- --run` -- PASS (175/175 tests passed)

