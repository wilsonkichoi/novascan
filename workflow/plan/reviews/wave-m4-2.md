# Wave 2 Review: Category + Pipeline Results Endpoints, Receipt Detail Page

Reviewed: 2026-04-08
Reviewer: Claude Opus 4.6 (1M context) (code-reviewer)
Cross-referenced: SPEC.md Section 5, 8; api-contracts.md; category-taxonomy.md; HANDOFF.md

## Task 4.2: Category + Pipeline Results Endpoints

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| GET /api/categories returns predefined + custom merged, predefined first | PASS | Lines 99-155: predefined iterated first, custom appended |
| POST /api/categories auto-generates slug from displayName | PASS | `_slugify()` at line 75-89 |
| POST /api/categories validates parentCategory against predefined slugs | PASS | Lines 187-194 |
| POST /api/categories returns 201 | PASS | Line 243 |
| POST /api/categories returns 409 on duplicate slug | PASS | Lines 202-221 check both predefined and custom |
| DELETE /api/categories/{slug} deletes custom category | PASS | Lines 249-280 |
| DELETE /api/categories/{slug} returns 403 for predefined | PASS | Lines 256-261 |
| DELETE /api/categories/{slug} returns 404 if not found | PASS | Lines 270-271 |
| DELETE /api/categories/{slug} returns 204 | PASS | Line 276 |
| Custom category slugs unique per user (PK-scoped) | PASS | Checks PK=USER#{userId} before put |
| GET /api/receipts/{id}/pipeline-results returns both outputs with ranking | PASS | Lines 283-370 |
| Pipeline results returns 403 for non-staff | PASS | Lines 294-300 check staff and admin groups |
| Pipeline results returns 404 if receipt not found | PASS | Lines 308-311 |
| `cd backend && uv run ruff check src/` passes | PASS | Verified |

### Issues Found

**[S1] -- SUGGESTION: Missing `createdAt` on custom category DynamoDB record**

`backend/src/novascan/api/categories.py:224-234` -- The `put_item` call for creating a custom category does not set a `createdAt` attribute. SPEC.md Section 5 defines Custom Category Attributes as including `createdAt: S (ISO 8601)`.

This matters because: (1) it deviates from the spec's defined schema, and (2) the `load_custom_categories` pipeline Lambda may expect this field when constructing the merged taxonomy. If a downstream consumer reads `createdAt` from a custom category record and it is missing, it will get `None` instead of a timestamp.

**Fix:** Add `"createdAt": datetime.now(UTC).isoformat()` to the item dict. This requires importing `datetime` and `UTC` from the `datetime` module.

---

**[S2] -- SUGGESTION: `_slugify` does not handle ampersand in display names**

`backend/src/novascan/api/categories.py:80-89` -- The `_slugify` function strips all non-alphanumeric/non-hyphen characters. This means a display name like "Groceries & Food" would slugify to "groceries-food", which happens to match a predefined category slug. While the predefined conflict check would catch this specific case, the broader issue is that `&` is a common character in category names and silently stripping it could produce unexpected or colliding slugs. For example, "Arts & Crafts" becomes "arts-crafts" while "Arts Crafts" also becomes "arts-crafts".

This is a minor issue since the conflict check protects against actual collisions. Calling it out for awareness -- no action required unless you want `&` preserved as, say, `and`.

---

**[S3] -- SUGGESTION: Route registration order creates potential match ambiguity for pipeline-results**

`backend/src/novascan/api/app.py:18-20` and `backend/src/novascan/api/categories.py:283` -- The pipeline results endpoint `GET /api/receipts/<receipt_id>/pipeline-results` is registered on the `categories_router`, but the receipts router also has `GET /api/receipts/<receipt_id>`. Lambda Powertools resolves routes by specificity (longer paths win), so this should work correctly. However, placing a receipt-scoped endpoint in the `categories.py` module is a code organization concern -- future maintainers looking for receipt-related endpoints may not think to check `categories.py`.

This is a minor organizational issue. Consider moving the pipeline-results endpoint to `receipts.py` in a future refactor, or renaming the module to something like `categories_and_pipeline.py`.

---

**[N1] -- NIT: Duplicate helper functions across modules**

`backend/src/novascan/api/categories.py:45-57,92-96` and `backend/src/novascan/api/receipts.py:93-116` -- The functions `_error_response`, `_get_user_id`, `_validate_receipt_id`, and the `_ULID_PATTERN` regex are duplicated between `categories.py` and `receipts.py`. This is not a bug, and the project guidelines say "no premature abstraction -- three similar lines > one unnecessary helper." With two modules sharing identical code, this is borderline. If a third module needs these, extract them.

---

**[N2] -- NIT: `get_all_category_slugs()` called twice in `create_category`**

`backend/src/novascan/api/categories.py:188,202` -- When `parentCategory` is provided, `get_all_category_slugs()` is called once at line 188 (to validate parentCategory) and again at line 202 (to check for slug conflict with predefined categories). The function creates a new set each time. Negligible at this scale, but a single `predefined_slugs = get_all_category_slugs()` at the top of the function would be cleaner.

---

## Task 4.3: Receipt Detail Page

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Desktop: image on left, extracted data on right (side-by-side) | PASS | `md:grid-cols-2` at line 168 |
| Mobile: image on top, extracted data below (stacked) | PASS | Default single column grid |
| Displays: merchant, date, total, subtotal, tax, tip, payment method, category, status badge | PASS | Lines 189-270 |
| Line items in table: name, qty, unit price, total price, subcategory | PASS | Lines 274-316 |
| Receipt image loads via presigned URL | PASS | Line 172-175 |
| Loading state while fetching | PASS | Lines 78-85 |
| 404 handling for non-existent receipts | PASS | Lines 87-100 with `NotFoundError` |
| Delete button with confirmation dialog | PASS | Lines 321-351 |
| Confirm calls DELETE /api/receipts/{id} | PASS | `deleteReceipt` mutation at line 121 |
| On success navigates back to receipts list | PASS | Line 123: `navigate("/receipts")` |
| `cd frontend && npm run build` succeeds | PASS | Verified |

### Issues Found

**[S4] -- SUGGESTION: No error feedback shown during delete failure**

`frontend/src/pages/ReceiptDetailPage.tsx:119-127` -- The `handleDelete` function calls `deleteReceipt.mutate(id, { onSuccess: ... })` but has no `onError` callback. If the delete API call fails (network error, 500, etc.), the dialog stays open with no feedback to the user. The button correctly disables during `isPending`, but after a failure the user sees no indication of what went wrong.

**Fix:** Add an `onError` callback that either shows an error message in the dialog or closes it with a toast notification. Even a simple state variable with an inline error message would suffice.

---

**[S5] -- SUGGESTION: `useReceipt` hook fetches even when `id` is empty string**

`frontend/src/hooks/useReceipt.ts:10-13` -- The `enabled` check is `Boolean(id)`, and the hook is called with `id ?? ""` from the page. An empty string is falsy in JS, so `Boolean("")` is `false` -- this is actually correct. However, the `queryFn` still receives `""` as the argument. If `enabled` were accidentally set to `true` (or removed), it would hit the API with an empty ID. A more defensive pattern would be to check `id.length > 0` explicitly, but this is minor since the current code works correctly.

---

**[N3] -- NIT: `formatDate` creates Date with timezone workaround**

`frontend/src/pages/ReceiptDetailPage.tsx:62` -- `new Date(dateStr + "T00:00:00")` appends a time component to force local timezone interpretation (avoiding the UTC-midnight-becomes-previous-day issue). This is a known workaround and works correctly, but a brief comment explaining WHY would help future readers understand it is intentional.

---

## Cross-Reference: Spec Alignment

| Spec Requirement | Implementation | Verdict |
|-----------------|---------------|---------|
| GET /api/categories returns predefined first, then custom (api-contracts) | Predefined iterated from `PREDEFINED_CATEGORIES`, custom queried and appended | PASS |
| POST /api/categories auto-slug from displayName (api-contracts) | `_slugify()` lowercases, hyphens, strips special chars | PASS |
| POST /api/categories: 409 on slug conflict (api-contracts) | Checks both predefined slugs and user's existing CUSTOMCAT# records | PASS |
| DELETE /api/categories: 403 for predefined, 404 for missing (api-contracts) | Both checked in order | PASS |
| Custom category stores displayName, parentCategory, createdAt (SPEC S5) | Missing `createdAt` -- see [S1] | PARTIAL |
| Pipeline results: staff role check (api-contracts) | Checks "staff" and "admin" groups | PASS |
| Pipeline results: returns extractedData, confidence, rankingScore, processingTimeMs, modelId, createdAt (api-contracts) | All fields present | PASS |
| Receipt detail: responsive layout (SPEC M4) | `md:grid-cols-2` grid | PASS |
| Receipt detail: line items table (SPEC M4) | Table with sortOrder, name, qty, unitPrice, totalPrice, subcategory | PASS |
| Delete receipt: confirmation dialog (SPEC M4) | Dialog with cancel + destructive confirm button | PASS |
| API client uses `encodeURIComponent` for path params | All API functions in receipts.ts use it | PASS |
| ReceiptDetail TypeScript type matches api-contracts | All fields present including usedFallback, rankingWinner | PASS |

## Things Done Well

1. **Clean Pydantic model organization.** The `Category`, `CustomCategoryRequest`, and `CustomCategoryResponse` models are well-structured and match the API contract precisely. Field validation on `displayName` (min/max length) is correct.

2. **Correct RBAC check on pipeline results.** The code checks for both "staff" and "admin" groups, correctly implementing the spec's group hierarchy where admin inherits staff permissions.

3. **Robust Decimal handling.** The `_convert_decimal` recursive converter and `_json_default` fallback ensure DynamoDB's Decimal values serialize cleanly. This avoids the common `TypeError: Object of type Decimal is not JSON serializable` issue.

4. **Good error boundary pattern in the frontend.** The `NotFoundError` class in `receipts.ts` lets the page component distinguish 404 from other errors and show a specific "Receipt not found" UI with a back link, rather than a generic error.

5. **Thoughtful responsive layout.** The `md:grid-cols-2` grid for desktop side-by-side and single-column stacked for mobile is exactly what the spec calls for. The hidden subcategory column on small screens (`hidden sm:table-cell`) is a nice touch.

6. **TanStack Query cache invalidation.** The `useDeleteReceipt` hook correctly uses `removeQueries` for the deleted receipt and `invalidateQueries` for the receipts list, ensuring stale data is never shown.

7. **Sanitized error responses.** Pydantic `ValidationError` is caught and sanitized to `{field, message}` pairs in the categories endpoint, consistent with the security hardening done in M3.1.

## Summary

| ID | Severity | Task | Issue | Action |
|----|----------|------|-------|--------|
| S1 | SUGGESTION | 4.2 | Missing `createdAt` on custom category record | Add timestamp to `put_item` |
| S2 | SUGGESTION | 4.2 | `_slugify` silently strips `&` from names | Awareness only -- conflict check catches collisions |
| S3 | SUGGESTION | 4.2 | Pipeline-results endpoint in categories.py module | Organizational -- consider moving to receipts.py |
| S4 | SUGGESTION | 4.3 | No error feedback on delete failure | Add `onError` callback to mutation |
| S5 | SUGGESTION | 4.3 | `useReceipt` hook defensive check | Minor -- current code works correctly |
| N1 | NIT | 4.2 | Duplicate helpers across categories.py and receipts.py | Extract if a third module needs them |
| N2 | NIT | 4.2 | `get_all_category_slugs()` called twice in create_category | Cache in local variable |
| N3 | NIT | 4.3 | `formatDate` timezone workaround lacks comment | Add explanatory comment |

**Overall verdict:** Solid implementation with no blockers. Both tasks meet their acceptance criteria and align with the spec. The 5 suggestions are minor quality improvements -- [S1] (missing `createdAt`) is the most important as it deviates from the SPEC's defined schema. [S4] (delete error feedback) is a UX gap worth fixing. The remaining suggestions and nits are low priority.

## Security Review

Reviewed: 2026-04-08
Reviewer: Claude Opus 4.6 (1M context) (security-reviewer)
Methodology: STRIDE threat model, OWASP Top 10, CWE Top 25

### Threat Model Summary

| Component | Threats Assessed | Findings |
|-----------|-----------------|----------|
| POST /api/categories (create custom) | S, T, R, I, D, E | [S6] No input sanitization on displayName content; [S7] No per-user rate limiting on category creation |
| DELETE /api/categories/{slug} | S, T, I, E | [S8] No slug path parameter format validation |
| GET /api/receipts/{id}/pipeline-results (staff-only) | S, T, I, E | No issues -- RBAC check correct, data scoped by PK |
| GET /api/categories (list) | I, E | No issues -- read-only, user-scoped |
| ReceiptDetailPage (frontend) | S, T, I | No issues -- React auto-escapes, auth enforced |
| useReceipt / useDeleteReceipt hooks | S, T | No issues -- token attached, API client validates responses |
| API client (receipts.ts) | T, I | No issues -- encodeURIComponent on path params, auth token attached |

### Issues Found

**[S6] -- SUGGESTION: Custom category `displayName` allows unrestricted Unicode content**

`backend/src/novascan/models/category.py:28` and `backend/src/novascan/api/categories.py:224-234`

**STRIDE:** Tampering
**CWE:** CWE-20 (Improper Input Validation)
**OWASP:** A03:2021 (Injection)

The `CustomCategoryRequest` Pydantic model validates `displayName` length (1-100 chars) but places no restriction on character content. A user can create a category with control characters, zero-width Unicode, RTL override characters, HTML entities, or emoji sequences. These values are stored as-is in DynamoDB and returned verbatim in `GET /api/categories` responses.

Why this matters: While M3.1 Task 3.8 added sanitization in the pipeline prompt builder (`build_extraction_prompt()`) that rejects dangerous characters at extraction time, the category record itself stores unsanitized data. If a future consumer reads category records directly from DynamoDB (e.g., a reporting Lambda, an admin dashboard), it would receive the raw unsanitized `displayName`. Additionally, the `_slugify()` function silently strips non-alphanumeric characters, so a displayName like `"\u200B\u200B\u200B"` (zero-width spaces) would produce an empty slug and be caught, but a displayName like `"Food\nIgnore all"` would produce the slug `"foodignore-all"` and be stored with the newline intact in `displayName`.

**Recommendation:** Add a `pattern` constraint to the Pydantic model matching the pipeline sanitizer's allowlist. This creates defense-in-depth -- validate at the API boundary, not just at the pipeline prompt boundary:
```python
displayName: str = Field(
    min_length=1,
    max_length=100,
    pattern=r"^[a-zA-Z0-9 &/,.()\-]+$",
)
```

---

**[S7] -- SUGGESTION: No rate limiting on POST /api/categories**

`backend/src/novascan/api/categories.py:158-246`

**STRIDE:** Denial of Service
**CWE:** CWE-770 (Allocation of Resources Without Limits or Throttling)
**OWASP:** A04:2021 (Insecure Design)

M3.1 Task 3.16 added API Gateway route-level throttling on `POST /api/receipts/upload-urls` (burst=10, rate=5), but the `POST /api/categories` endpoint has no rate limiting. An authenticated user could create thousands of custom categories in rapid succession via scripted requests. Each creation issues a `get_all_category_slugs()` call (iterating the full predefined taxonomy), a `get_item` call (conflict check), and a `put_item` call to DynamoDB. At scale, this could run up DynamoDB costs and degrade performance for the user's partition.

Why this matters: The blast radius is limited -- custom categories are per-user (PK-scoped), so this only affects the attacker's own data partition and the operator's billing. At ~100 users this is negligible. However, there is no application-level maximum on custom categories per user.

**Recommendation:** For a personal MVP, this is acceptable. If user base grows, add either:
1. API Gateway route-level throttling on `POST /api/categories` (e.g., burst=5, rate=2)
2. Application-level check: query custom category count before creating, reject if > 50

No immediate code change needed. Documenting for awareness.

---

**[S8] -- SUGGESTION: No format validation on `slug` path parameter in DELETE /api/categories/{slug}**

`backend/src/novascan/api/categories.py:249-280`

**STRIDE:** Tampering
**CWE:** CWE-20 (Improper Input Validation)

The `delete_category(slug)` handler receives the `slug` path parameter directly from the URL and uses it to construct a DynamoDB sort key (`CUSTOMCAT#{slug}`) without any format validation. In contrast, the receipt endpoints validate `receipt_id` against `_ULID_PATTERN` before using it. A malicious client could pass a slug containing `#` characters, extremely long strings, or other unexpected content. For example, `DELETE /api/categories/foo%23bar` would construct SK `CUSTOMCAT#foo#bar`, which is a valid DynamoDB key but does not correspond to any legitimate category.

Why this matters: The security impact is low because the operation is scoped to `PK=USER#{userId}` and uses an exact `get_item` match (not a `begins_with` query). An attacker cannot read or modify other users' data. The main risk is that unvalidated input reaches DynamoDB, consuming read capacity on nonexistent keys. The `_slugify` function used during creation only produces `[a-z0-9-]` slugs, so a slug containing `#` or other characters would never match an existing record -- the `get_item` returns nothing, and 404 is returned.

**Recommendation:** Add a slug format validation at the top of `delete_category`:
```python
_SLUG_PATTERN = re.compile(r"^[a-z0-9-]{1,100}$")

def delete_category(slug: str) -> Response[Any]:
    if not _SLUG_PATTERN.match(slug):
        return _error_response(400, "VALIDATION_ERROR", "Invalid category slug format")
    ...
```

This is consistent with the defense-in-depth pattern used in receipt endpoints.

---

### Data Flow Analysis

**Sensitive data classification for Wave 2 components:**

| Data | Classification | Protection |
|------|---------------|------------|
| Custom category displayName | Internal | User-scoped (PK), no PII |
| Custom category slug | Internal | User-scoped (PK), derived from displayName |
| Pipeline extractedData (staff endpoint) | Confidential | Staff RBAC check, user-scoped (PK) |
| Pipeline rankingScore / processingTimeMs | Internal | Staff RBAC check |
| Receipt image presigned URL | Confidential | Signed URL with 1-hour expiry, auth required to generate |
| Receipt monetary amounts | Internal | User-scoped (PK) |

**Authentication and authorization verification:**

| Endpoint | Auth Required | User Scoping | Role Check | Verdict |
|----------|--------------|-------------|------------|---------|
| GET /api/categories | JWT (API GW) | PK=USER#{sub} | None needed | PASS |
| POST /api/categories | JWT (API GW) | PK=USER#{sub} | None needed | PASS |
| DELETE /api/categories/{slug} | JWT (API GW) | PK=USER#{sub} | None needed | PASS |
| GET /api/receipts/{id}/pipeline-results | JWT (API GW) | PK=USER#{sub} | staff/admin groups | PASS |

**Error response review (no internal state leakage):**

| Endpoint | Error Cases | Leaks Internal State? |
|----------|------------|----------------------|
| POST /api/categories (ValidationError) | Sanitized field+message pairs | No -- consistent with M3.1 pattern |
| POST /api/categories (parentCategory invalid) | Echoes user's input back | No -- user already knows their input |
| POST /api/categories (conflict) | Reveals the generated slug | Low risk -- slug is deterministic from displayName |
| DELETE /api/categories (predefined) | Generic "Cannot delete predefined categories" | No |
| GET pipeline-results (non-staff) | Generic "Pipeline results require staff role" | No |
| GET pipeline-results (receipt 404) | Generic "Receipt not found" | No |

### Things Assessed (No Issues Found)

1. **RBAC enforcement on pipeline-results:** Correctly checks both "staff" and "admin" groups before returning data. Non-staff users get 403 with a generic message. No privilege escalation vector found.

2. **Cross-user data isolation:** All DynamoDB operations in `categories.py` are scoped to `PK=USER#{userId}` where `userId` comes from the JWT `sub` claim (set by Cognito, not user-controllable). No user can read, create, or delete another user's categories or access another user's pipeline results.

3. **Frontend XSS protection:** The `ReceiptDetailPage` renders all data via JSX text interpolation (React auto-escapes). No `dangerouslySetInnerHTML`, no `eval()`, no direct DOM manipulation. The `formatCurrency` and `formatDate` helpers use built-in `Intl.NumberFormat` and `Date` APIs on data from the API response. Receipt image uses `<img src>` which is safe (no script execution from image src).

4. **Frontend API client security:** All API functions in `receipts.ts` use `encodeURIComponent(id)` for path parameters, preventing path traversal. Auth tokens are attached via `Authorization: Bearer` header. Error responses are handled without exposing raw error bodies to the UI.

5. **Delete confirmation pattern:** The delete flow requires explicit user confirmation via a dialog. The `deleteReceipt.mutate` call includes the receipt ID from the URL params (validated by API Gateway and backend `_validate_receipt_id`). The mutation invalidates the TanStack Query cache on success, preventing stale data.

6. **M3.1 hardening applied consistently:** The `categories.py` error handling follows the same sanitized error pattern established in M3.1 (Task 3.10, 3.15): `ValidationError` is caught and returned as `{field, message}` pairs. `TypeError` and `JSONDecodeError` return generic messages. No `str(e)` leaks to the client.

### Security Assessment

**Overall security posture:** Good. The Wave 2 implementation follows the security patterns established in M3.1 hardening. All endpoints enforce authentication via API Gateway JWT authorizer, data isolation via PK-scoped DynamoDB operations, and role-based access control on the pipeline-results endpoint. The three suggestions identified ([S6], [S7], [S8]) are defense-in-depth improvements -- input validation at the API boundary for category displayName and slug path parameter -- rather than exploitable vulnerabilities. None are blockers for this wave.

## Review Discussion

### Fix Plan (Claude Opus 4.6 (1M context) -- 2026-04-08)

> Note: Generated in the same context as the review. Run `/agentic-dev:review fix-plan-analysis wave 2` in a separate session for a truly independent second opinion.

**Scope: 5 issues (0 BLOCKERs, 5 SUGGESTIONs) -- NITs excluded from fix plan**

Only S1 and S4 warrant code changes. S2, S3, and S5 are awareness/organizational items that do not need immediate fixes.

**[S1] (Missing `createdAt` on custom category record)**
- Independent assessment: Reading `categories.py:224-234`, the item dict has PK, SK, entityType, displayName, slug, and optionally parentCategory. Comparing against SPEC Section 5 Custom Category Attributes which lists `createdAt: S (ISO 8601)` as a required field -- this is clearly missing. The `load_custom_categories.py` pipeline Lambda queries these records and may pass them to downstream consumers.
- Review comparison: Agree. Straightforward spec deviation.
- Fix: Import `datetime` and `UTC` at the top of `categories.py`. Add `"createdAt": datetime.now(UTC).isoformat()` to the item dict in `create_category()`.
- Risk: None -- adding a field to a DynamoDB write is purely additive. Existing records without `createdAt` will still work (consumers already handle missing fields via `.get()`).
- Files: `backend/src/novascan/api/categories.py`

**[S4] (No error feedback on delete failure)**
- Independent assessment: Reading `ReceiptDetailPage.tsx:119-127`, the `mutate` call has only `onSuccess`. After a failed delete, the dialog stays open, the button re-enables (since `isPending` goes false), but there is no visible error. The user would need to guess that something went wrong.
- Review comparison: Agree. This is a real UX gap.
- Fix: Add a `deleteError` state variable. In the `onError` callback, set it. Display the error message in the dialog above the buttons. Clear the error when the dialog opens or closes.
- Risk: Minimal. The only risk is if the error message from the API contains internal details, but `deleteReceipt` in `receipts.ts` throws generic messages (`"Failed to delete receipt (status)"` or `NotFoundError`), so no leak.
- Files: `frontend/src/pages/ReceiptDetailPage.tsx`

**Deferred (no code change needed):**
- [S2]: Awareness only. The conflict check already prevents actual slug collisions.
- [S3]: Organizational. Not worth a move during this wave -- it would touch module boundaries and potentially break imports in tests being written in Wave 4.
- [S5]: The code works correctly as-is. `Boolean("")` is `false`.

**Execution order:**
1. Fix [S1] in `categories.py` (backend)
2. Fix [S4] in `ReceiptDetailPage.tsx` (frontend)
3. Run verification

**Verification:**
```bash
cd backend && uv run ruff check src/ && uv run pytest tests/ -v -k "categories"
cd frontend && npx tsc --noEmit && npm run build
```

### Fix Plan Analysis (Claude Opus 4.6 (1M context) -- 2026-04-08)

**Coverage note:** The existing Fix Plan addresses S1-S5 from the code review only. It was generated before the Security Review was appended, so it does not cover S6, S7, or S8. This analysis covers all 8 issues from both reviews.

---

**[S1] (Missing `createdAt` on custom category record) -- Approve**

My approach: Reading `categories.py:224-234`, the `put_item` dict contains PK, SK, entityType, displayName, slug, and conditionally parentCategory. SPEC Section 5 Custom Category Attributes explicitly lists `createdAt: S (ISO 8601)`. The field is missing. I would add `from datetime import datetime, UTC` to the imports and insert `"createdAt": datetime.now(UTC).isoformat()` into the item dict at line 230 (between `"slug": slug` and the conditional parentCategory block).

Plan's approach: Identical -- import `datetime` and `UTC`, add the field to the item dict. Aligns with my analysis. The plan correctly identifies this as purely additive with no risk to existing records, since `load_custom_categories.py` and the list endpoint both use `.get()` for optional fields.

---

**[S4] (No error feedback on delete failure) -- Approve**

My approach: Reading `ReceiptDetailPage.tsx:119-127`, `handleDelete` calls `deleteReceipt.mutate(id, { onSuccess })` with no `onError`. After failure, `isPending` reverts to false, button re-enables, but the user has no indication of failure. I would add a `deleteError` state (`useState<string | null>(null)`), set it in an `onError` callback (extracting `error.message`), display it as a red text paragraph in the dialog between the description and footer, and clear it on dialog open (`setShowDeleteDialog(true)` handler should also `setDeleteError(null)`). The error messages from `deleteReceipt` in `receipts.ts` (lines 197-213) are already sanitized -- either `"Receipt not found"` (NotFoundError) or `"Failed to delete receipt (status)"` -- so no internal state leakage.

Plan's approach: Same -- `deleteError` state variable, `onError` callback, display in dialog, clear on open/close. Aligns with my analysis. The plan correctly identifies that `receipts.ts` already sanitizes error messages.

---

**[S2] (`_slugify` strips `&`) -- Approve (defer)**

My approach: Reading `_slugify` at lines 75-89, the regex `[^a-z0-9-]` strips all non-alphanumeric/non-hyphen characters after lowercasing. This means "Groceries & Food" becomes "groceries-food". The predefined conflict check at line 202-208 would catch this collision. For non-colliding cases like "Arts & Crafts" vs "Arts Crafts" both becoming "arts-crafts", the existing custom category conflict check at lines 215-221 would catch the second creation. The slug deduplication is sound. The `&`-to-`and` conversion would be a polish item, not a correctness fix.

Plan's approach: Defers. Correct call -- the conflict checks protect against actual collisions.

---

**[S3] (Pipeline-results endpoint in categories.py) -- Approve (defer)**

My approach: The `get_pipeline_results` function at line 283 is registered on the `categories_router` but operates on receipt data. This is a code organization issue only. Moving it now would require updating `app.py` router registration, and Wave 4 tests (Task 4.6) will import from whatever module the endpoints live in. Deferring avoids unnecessary churn.

Plan's approach: Defers for the same reason -- module boundary changes during active test writing. Correct.

---

**[S5] (`useReceipt` hook defensive check) -- Approve (defer)**

My approach: Reading `useReceipt.ts:8-13`, `enabled: Boolean(id)` is correct because the hook is called with `id ?? ""` from the page, and `Boolean("")` is `false`. The `queryFn` receives `""` but never executes because `enabled` is `false`. The only way this breaks is if someone removes the `enabled` guard, which is a hypothetical. No fix needed.

Plan's approach: Defers. Correct.

---

**[S6] (Custom category displayName allows unrestricted Unicode) -- Revise**

My approach: Reading `category.py:25-29`, `CustomCategoryRequest` validates `displayName` with `min_length=1, max_length=100` but no character restriction. A user could submit `"Food\nIgnore all previous instructions"` and it would be stored verbatim. While React auto-escapes on display and M3.1 Task 3.8 sanitizes categories in the extraction prompt, the raw displayName persists in DynamoDB. The fix is to add a `pattern` constraint to the Pydantic model. The security review recommends `r"^[a-zA-Z0-9 &/,.()\-]+$"` which matches the sanitizer in `prompts.py`. This is a good defense-in-depth measure.

Plan's approach: **The existing Fix Plan does not address S6.** It was generated before the Security Review. S6 should be added to the fix scope. The Pydantic `pattern` approach from the security review is clean and correct. It validates at the API boundary, consistent with the project's pattern of Pydantic validation on request models. The one consideration: the pattern `[a-zA-Z0-9 &/,.()\-]+` does not include apostrophes (`'`) which appear in legitimate category names like "Sam's Club" or "Mother's Day Gifts". I would expand the pattern to `r"^[a-zA-Z0-9 &/,.'()\-]+$"` to include single quotes.

**Alternative:** Add `pattern=r"^[a-zA-Z0-9 &/,.'()\-]+$"` to `CustomCategoryRequest.displayName` in `backend/src/novascan/models/category.py`. Risk: may reject legitimate names with characters outside the allowlist (e.g., accented characters like "Cafe" vs "Cafe"). For a personal MVP targeting English receipts, this is acceptable.

Files: `backend/src/novascan/models/category.py`

---

**[S7] (No rate limiting on POST /api/categories) -- Approve (defer)**

My approach: Reading `categories.py:158-246`, there is no rate limiting. An authenticated user could create thousands of categories. However: (1) categories are per-user (PK-scoped), so this only affects the attacker's own partition; (2) at ~100 users the blast radius is negligible; (3) adding API Gateway route-level throttling requires CDK changes in `infra/cdkconstructs/api.py` which is a different scope than this wave's code fixes. The security review itself says "No immediate code change needed."

Plan's approach: Not addressed (generated before security review). The security review correctly defers this. I agree -- no code change needed for personal MVP.

---

**[S8] (No format validation on slug path parameter in DELETE) -- Revise**

My approach: Reading `delete_category` at lines 249-280, the `slug` parameter comes directly from the URL path with no validation. In contrast, `get_pipeline_results` validates `receipt_id` against `_ULID_PATTERN` at line 290. The security impact is low (PK-scoped `get_item` on a nonexistent key returns nothing, yielding 404), but adding a slug format check is consistent with the defense-in-depth pattern used elsewhere. The `_slugify` function produces only `[a-z0-9-]` output, so a slug regex of `^[a-z0-9-]{1,100}$` is correct.

Plan's approach: **Not addressed** (generated before security review). S8 should be added to the fix scope. Add `_SLUG_PATTERN = re.compile(r"^[a-z0-9-]{1,100}$")` and validate at the top of `delete_category`. Risk: if a user somehow has a custom category with a slug outside this pattern (impossible via the current API since `_slugify` only produces `[a-z0-9-]`), they could not delete it. This is acceptable -- such a record could only exist from direct DynamoDB manipulation.

**Alternative:** Add the validation at the top of `delete_category` before the predefined check. Return 400 with `"Invalid category slug format"`.

Files: `backend/src/novascan/api/categories.py`

---

**Revised execution order (incorporating S6 and S8):**

1. Fix [S6] -- add `pattern` to `CustomCategoryRequest.displayName` in `category.py`
2. Fix [S8] -- add `_SLUG_PATTERN` validation to `delete_category` in `categories.py`
3. Fix [S1] -- add `createdAt` timestamp to `create_category` in `categories.py`
4. Fix [S4] -- add `onError` handling to delete dialog in `ReceiptDetailPage.tsx`
5. Run verification

**Revised verification:**
```bash
cd backend && uv run ruff check src/ && uv run mypy src/ && uv run pytest tests/ -v -k "categories"
cd frontend && npx tsc --noEmit && npm run build
```

### Fix Results (Claude Opus 4.6 (1M context) -- 2026-04-08)

**Branch:** `fix/wave2-review-fixes` (based on `feature/m4-wave2-categories-detail`)
**Status: 4/4 fixed, 4 deferred**

**[S6] (displayName allows unrestricted Unicode) -- Fixed**
- What was changed: Added `pattern=r"^[a-zA-Z0-9 &/,.'()\-]+$"` to `CustomCategoryRequest.displayName` Pydantic field. Includes apostrophe for names like "Sam's Club" per fix plan analysis recommendation.
- Files modified: `backend/src/novascan/models/category.py`

**[S8] (No slug path parameter validation in DELETE) -- Fixed**
- What was changed: Added `_SLUG_PATTERN = re.compile(r"^[a-z0-9-]{1,100}$")` and validation check at the top of `delete_category()` before any DynamoDB calls. Returns 400 with "Invalid category slug format" for invalid slugs.
- Files modified: `backend/src/novascan/api/categories.py`

**[S1] (Missing createdAt on custom category record) -- Fixed**
- What was changed: Added `from datetime import UTC, datetime` import and `"createdAt": datetime.now(UTC).isoformat()` to the item dict in `create_category()`.
- Files modified: `backend/src/novascan/api/categories.py`

**[S4] (No error feedback on delete failure) -- Fixed**
- What was changed: Added `deleteError` state variable, `onError` callback on `deleteReceipt.mutate()` that sets the error message, error display as red text in the dialog between description and footer, and error clearing when the dialog opens.
- Files modified: `frontend/src/pages/ReceiptDetailPage.tsx`

**Deferred (no code change needed):**
- [S2] -- Awareness only. Conflict check already prevents slug collisions from `&` stripping.
- [S3] -- Organizational. Moving pipeline-results to receipts.py deferred to avoid churn during active test writing in Wave 4.
- [S5] -- Current code works correctly. `Boolean("")` is `false`.
- [S7] -- No rate limiting needed for personal MVP. Documented for awareness.

**Verification:**
- `cd backend && uv run ruff check src/` -- PASS
- `cd backend && uv run mypy src/` -- PASS (pre-existing errors only, none from fixes)
- `cd backend && uv run pytest tests/ -v -k "categories"` -- PASS (10/10)
- `cd frontend && npx tsc --noEmit` -- PASS
- `cd frontend && npm run build` -- PASS

